"""
TelePhisDebate - Evaluation Script
Evaluasi deteksi phishing menggunakan dataset CSV

Menghitung metrik:
- Accuracy, Precision, Recall, F1-Score
- Confusion Matrix
- Stage distribution (Triage / Single-Shot / MAD)
- Token usage per message
- Processing time statistics
- Per-message detail (untuk analisis error)

Usage:
    python evaluate.py --dataset data/dataset_phishing.csv
    python evaluate.py --dataset data/dataset_phishing.csv --output results/
    python evaluate.py --dataset data/dataset_phishing.csv --limit 10   # test dulu 10 pesan
    python evaluate.py --dataset data/dataset_phishing.csv --eval-mode mad_only --mad-mode mad5
"""

import sys
import csv
import json
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config as app_config
from src.detection import (
    PhishingDetectionPipeline,
    close_url_checker_sync,
    get_url_checker,
)
from src.detection.triage import RuleBasedTriage
from src.detection.mad import MultiAgentDebate as MAD3Debate
from src.detection.mad5 import MultiAgentDebate as MAD5Debate

# ============================================================
# Configuration
# ============================================================

# Map label di CSV ke label pipeline
LABEL_MAP = {
    # Phishing variants
    "phishing": "PHISHING",
    "PHISHING": "PHISHING",
    "Phishing": "PHISHING",
    "phising": "PHISHING",     # common typo
    "Phising": "PHISHING",
    "spam": "PHISHING",
    "scam": "PHISHING",
    "malicious": "PHISHING",
    
    # Safe/legitimate variants
    "safe": "SAFE",
    "SAFE": "SAFE",
    "Safe": "SAFE",
    "legitimate": "SAFE",
    "LEGITIMATE": "SAFE",
    "Legitimate": "SAFE",
    "normal": "SAFE",
    "ham": "SAFE",
    
    # Suspicious variants
    "suspicious": "SUSPICIOUS",
    "SUSPICIOUS": "SUSPICIOUS",
    "Suspicious": "SUSPICIOUS",
}

# Resource profiling constants
COST_INPUT = 0.28 / 1_000_000   # $0.28 per 1M tokens
COST_OUTPUT = 0.42 / 1_000_000  # $0.42 per 1M tokens

logger = logging.getLogger(__name__)


def _llm_identity() -> tuple[str, str]:
    provider = (getattr(app_config, "LLM_PROVIDER", "") or "deepseek").strip().lower()
    if provider == "openrouter":
        model = (getattr(app_config, "OPENROUTER_MODEL", "") or "openai/gpt-oss-120b:free").strip()
        return "openrouter", model
    return "deepseek", "deepseek-chat"


def load_dataset(csv_path: str, text_col: str = "chat", label_col: str = "tipe",
                 delimiter: str = ";", limit: int | None = None) -> list[dict]:
    """
    Load dataset dari CSV file.
    
    Args:
        csv_path: Path ke file CSV
        text_col: Nama kolom teks pesan
        label_col: Nama kolom label
        delimiter: Separator CSV
        limit: Batasi jumlah data (untuk testing)
    """
    dataset = []
    path = Path(csv_path)
    
    if not path.exists():
        print(f"❌ File tidak ditemukan: {csv_path}")
        sys.exit(1)
    
    # Try different encodings
    for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            with open(path, "r", encoding=encoding) as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                
                # Validate columns
                if text_col not in reader.fieldnames:
                    print(f"❌ Kolom '{text_col}' tidak ditemukan. Kolom tersedia: {reader.fieldnames}")
                    sys.exit(1)
                if label_col not in reader.fieldnames:
                    print(f"❌ Kolom '{label_col}' tidak ditemukan. Kolom tersedia: {reader.fieldnames}")
                    sys.exit(1)
                
                for row in reader:
                    text = row[text_col].strip()
                    label = row[label_col].strip()
                    
                    if not text:
                        continue
                    
                    # Normalize label
                    normalized = LABEL_MAP.get(label, label.upper())
                    
                    dataset.append({
                        "text": text,
                        "expected_label": normalized,
                        "original_label": label,
                    })
                    
                    if limit and len(dataset) >= limit:
                        break
                
                break  # encoding worked
        except UnicodeDecodeError:
            continue
    
    if not dataset:
        print(f"❌ Dataset kosong atau tidak bisa dibaca: {csv_path}")
        sys.exit(1)
    
    return dataset


def evaluate_dataset(pipeline, dataset: list[dict], verbose: bool = True) -> dict:
    """
    Run pipeline pada semua data dan kumpulkan hasil.
    
    Returns:
        Dict berisi semua results dan metrics
    """
    results = []
    total_start = time.time()
    
    for i, data in enumerate(dataset, 1):
        if verbose:
            print(f"\r  Processing {i}/{len(dataset)}... ", end="", flush=True)
        
        msg_start = time.time()
        
        try:
            result = pipeline.process_message(
                message_text=data["text"],
                message_id=f"eval_{i}",
                message_timestamp=datetime.now()
            )
            
            results.append({
                "index": i,
                "text": data["text"],
                "expected": data["expected_label"],
                "predicted": result.classification,
                "confidence": result.confidence,
                "decided_by": result.decided_by,
                "action": result.action,
                "processing_time_ms": result.total_processing_time_ms,
                "tokens_total": result.total_tokens_used,
                "tokens_input": result.tokens_input,
                "tokens_output": result.tokens_output,
                "triage_risk_score": result.triage_result.get("risk_score", 0) if result.triage_result else 0,
                "triage_flags": result.triage_result.get("triggered_flags", []) if result.triage_result else [],
                "single_shot_result": result.single_shot_result,
                "mad_result": result.mad_result,
                "correct": _is_correct(data["expected_label"], result.classification),
                "error": None,
            })
            
        except Exception as e:
            results.append({
                "index": i,
                "text": data["text"],
                "expected": data["expected_label"],
                "predicted": "ERROR",
                "confidence": 0,
                "decided_by": "error",
                "action": "none",
                "processing_time_ms": int((time.time() - msg_start) * 1000),
                "tokens_total": 0,
                "tokens_input": 0,
                "tokens_output": 0,
                "triage_risk_score": 0,
                "triage_flags": [],
                "single_shot_result": None,
                "mad_result": None,
                "correct": False,
                "error": str(e),
            })
    
    if verbose:
        print(f"\r  Processing {len(dataset)}/{len(dataset)} ✅")
    
    total_time = time.time() - total_start
    
    # Calculate metrics
    metrics = calculate_metrics(results, total_time)
    
    return {
        "results": results,
        "metrics": metrics,
        "dataset_size": len(dataset),
        "eval_mode": "pipeline",
        "mad_mode": getattr(pipeline, "mad_mode", "mad3"),
        "llm_provider": _llm_identity()[0],
        "llm_model": _llm_identity()[1],
        "total_time_seconds": round(total_time, 2),
    }


def _create_mad_debate(mad_mode: str):
    """Create MAD debate instance based on selected mode."""
    if mad_mode == "mad3":
        return MAD3Debate(skip_round_2_on_consensus=True)
    if mad_mode == "mad5":
        return MAD5Debate(skip_round_2_on_consensus=True)
    raise ValueError(f"Unsupported mad_mode='{mad_mode}'. Use 'mad3' or 'mad5'.")


def _normalize_mad_classification(decision: str) -> str:
    normalized = (decision or "").upper()
    if normalized == "LEGITIMATE":
        return "SAFE"
    return normalized or "SUSPICIOUS"


def _determine_action(classification: str, confidence: float) -> str:
    """Mirror pipeline action mapping for report consistency."""
    if classification == "SAFE":
        return "none"
    if classification == "PHISHING":
        return "flag_review"
    if classification == "SUSPICIOUS":
        return "warn" if confidence >= 0.60 else "flag_review"
    return "flag_review"


def _collect_url_checks(urls_found: list[str]) -> dict | None:
    """Collect URL checks similarly to the full pipeline's MAD preparation."""
    if not urls_found:
        return None

    try:
        checker = get_url_checker()
        try:
            return checker.check_urls_sync(urls_found)
        except Exception as e:
            logger.warning(f"Sync URL check failed, fallback to heuristic: {e}")
            try:
                url_checks = {}
                for url in urls_found:
                    result = checker._heuristic_check(url)
                    url_checks[url] = result.to_dict()
                return url_checks
            except Exception as fallback_error:
                logger.warning(f"Heuristic URL check failed: {fallback_error}")
                return None
    except Exception as checker_error:
        logger.warning(f"URL checker initialization failed: {checker_error}")
        return None


def evaluate_dataset_mad_only(
    mad,
    triage: RuleBasedTriage,
    dataset: list[dict],
    mad_mode: str,
    verbose: bool = True
) -> dict:
    """
    Evaluate dataset using MAD only for final decision.

    Triage is kept for context only (risk flags, URLs), but never finalizes output.
    """
    results = []
    total_start = time.time()

    for i, data in enumerate(dataset, 1):
        if verbose:
            print(f"\r  Processing {i}/{len(dataset)}... ", end="", flush=True)

        msg_start = time.time()
        message_timestamp = datetime.now()

        try:
            triage_result = triage.analyze(
                message_text=data["text"],
                message_timestamp=message_timestamp,
                user_baseline=None,
                url_checks=None
            )
            url_checks = _collect_url_checks(triage_result.urls_found or [])

            mad_result = mad.run_debate(
                message_text=data["text"],
                message_timestamp=message_timestamp,
                sender_info=None,
                baseline_metrics=None,
                triage_result=triage_result.to_dict(),
                single_shot_result=None,
                url_checks=url_checks,
                parallel=True
            )

            classification = _normalize_mad_classification(mad_result.decision)
            confidence = mad_result.confidence

            tokens_in = sum(
                r.get("tokens_input", 0) for r in (mad_result.round_1_summary or [])
            ) + sum(
                r.get("tokens_input", 0) for r in (mad_result.round_2_summary or [])
            )
            tokens_out = sum(
                r.get("tokens_output", 0) for r in (mad_result.round_1_summary or [])
            ) + sum(
                r.get("tokens_output", 0) for r in (mad_result.round_2_summary or [])
            )

            # Fallback for legacy summaries that may not carry token in/out fields.
            if tokens_in == 0 and tokens_out == 0 and mad_result.total_tokens > 0:
                tokens_in = int(mad_result.total_tokens * 0.6)
                tokens_out = mad_result.total_tokens - tokens_in

            mad_payload = mad_result.to_dict()
            mad_payload.setdefault("variant", mad_mode)

            results.append({
                "index": i,
                "text": data["text"],
                "expected": data["expected_label"],
                "predicted": classification,
                "confidence": confidence,
                "decided_by": "mad",
                "action": _determine_action(classification, confidence),
                "processing_time_ms": int((time.time() - msg_start) * 1000),
                "tokens_total": mad_result.total_tokens,
                "tokens_input": tokens_in,
                "tokens_output": tokens_out,
                "triage_risk_score": triage_result.risk_score,
                "triage_flags": triage_result.triggered_flags,
                "single_shot_result": None,
                "mad_result": mad_payload,
                "correct": _is_correct(data["expected_label"], classification),
                "error": None,
            })

        except Exception as e:
            results.append({
                "index": i,
                "text": data["text"],
                "expected": data["expected_label"],
                "predicted": "ERROR",
                "confidence": 0,
                "decided_by": "error",
                "action": "none",
                "processing_time_ms": int((time.time() - msg_start) * 1000),
                "tokens_total": 0,
                "tokens_input": 0,
                "tokens_output": 0,
                "triage_risk_score": 0,
                "triage_flags": [],
                "single_shot_result": None,
                "mad_result": None,
                "correct": False,
                "error": str(e),
            })

    if verbose:
        print(f"\r  Processing {len(dataset)}/{len(dataset)} ✅")

    total_time = time.time() - total_start
    metrics = calculate_metrics(results, total_time)

    return {
        "results": results,
        "metrics": metrics,
        "dataset_size": len(dataset),
        "eval_mode": "mad_only",
        "mad_mode": mad_mode,
        "llm_provider": _llm_identity()[0],
        "llm_model": _llm_identity()[1],
        "total_time_seconds": round(total_time, 2),
    }


def _is_correct(expected: str, predicted: str) -> bool:
    """
    Check apakah prediksi benar.
    
    Untuk evaluasi deteksi:
    - PHISHING expected → PHISHING or SUSPICIOUS predicted = detected (true positive)
    - SAFE expected → SAFE predicted = correct
    - SUSPICIOUS is acceptable for both directions
    """
    if expected == predicted:
        return True
    
    # PHISHING expected, SUSPICIOUS predicted → still detected (partial)
    # Tapi untuk strict evaluation, hanya exact match
    return False


def calculate_metrics(results: list[dict], total_time: float) -> dict:
    """Calculate evaluation metrics."""
    
    total = len(results)
    errors = sum(1 for r in results if r["predicted"] == "ERROR")
    valid_results = [r for r in results if r["predicted"] != "ERROR"]
    
    if not valid_results:
        return {"error": "No valid results"}
    
    # ============================================================
    # Classification metrics
    # ============================================================
    correct = sum(1 for r in valid_results if r["correct"])
    accuracy = correct / len(valid_results) if valid_results else 0
    
    # Count per class
    expected_counts = Counter(r["expected"] for r in valid_results)
    predicted_counts = Counter(r["predicted"] for r in valid_results)
    
    # Confusion matrix components (binary: PHISHING vs NOT-PHISHING)
    tp = sum(1 for r in valid_results if r["expected"] == "PHISHING" and r["predicted"] == "PHISHING")
    fn = sum(1 for r in valid_results if r["expected"] == "PHISHING" and r["predicted"] != "PHISHING")
    fp = sum(1 for r in valid_results if r["expected"] != "PHISHING" and r["predicted"] == "PHISHING")
    tn = sum(1 for r in valid_results if r["expected"] != "PHISHING" and r["predicted"] != "PHISHING")
    
    # Also count "detection" (PHISHING or SUSPICIOUS counts as detected)
    tp_detected = sum(1 for r in valid_results 
                      if r["expected"] == "PHISHING" and r["predicted"] in ("PHISHING", "SUSPICIOUS"))
    fn_missed = sum(1 for r in valid_results 
                    if r["expected"] == "PHISHING" and r["predicted"] not in ("PHISHING", "SUSPICIOUS"))
    
    # Precision, Recall, F1 (strict: only PHISHING = PHISHING)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    # Detection rate (PHISHING or SUSPICIOUS = detected)
    detection_rate = tp_detected / (tp_detected + fn_missed) if (tp_detected + fn_missed) > 0 else 0
    
    # ============================================================
    # Stage distribution
    # ============================================================
    stage_counts = Counter(r["decided_by"] for r in valid_results)
    stage_pct = {stage: count / len(valid_results) * 100 for stage, count in stage_counts.items()}
    
    # Accuracy per stage
    stage_accuracy = {}
    for stage in stage_counts:
        stage_results = [r for r in valid_results if r["decided_by"] == stage]
        if stage_results:
            stage_correct = sum(1 for r in stage_results if r["correct"])
            stage_accuracy[stage] = stage_correct / len(stage_results)
    
    # ============================================================
    # Performance metrics
    # ============================================================
    times = [r["processing_time_ms"] for r in valid_results]
    tokens_total = [r["tokens_total"] for r in valid_results]
    tokens_in = [r["tokens_input"] for r in valid_results]
    tokens_out = [r["tokens_output"] for r in valid_results]
    
    # Cost
    total_cost_in = sum(tokens_in) * COST_INPUT
    total_cost_out = sum(tokens_out) * COST_OUTPUT
    total_cost = total_cost_in + total_cost_out
    
    # ============================================================
    # Confidence analysis
    # ============================================================
    correct_confs = [r["confidence"] for r in valid_results if r["correct"]]
    wrong_confs = [r["confidence"] for r in valid_results if not r["correct"]]
    
    return {
        # Classification
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "detection_rate": round(detection_rate, 4),
        
        # Confusion matrix (binary)
        "confusion_matrix": {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "tp_detected": tp_detected,
            "fn_missed": fn_missed,
        },
        
        # Counts
        "total": total,
        "correct": correct,
        "wrong": len(valid_results) - correct,
        "errors": errors,
        "expected_distribution": dict(expected_counts),
        "predicted_distribution": dict(predicted_counts),
        
        # Stage
        "stage_distribution": dict(stage_counts),
        "stage_percentage": {k: round(v, 1) for k, v in stage_pct.items()},
        "stage_accuracy": {k: round(v, 4) for k, v in stage_accuracy.items()},
        
        # Performance
        "avg_time_ms": round(sum(times) / len(times), 1) if times else 0,
        "min_time_ms": min(times) if times else 0,
        "max_time_ms": max(times) if times else 0,
        "total_time_seconds": round(total_time, 2),
        
        # Tokens
        "total_tokens": sum(tokens_total),
        "total_tokens_input": sum(tokens_in),
        "total_tokens_output": sum(tokens_out),
        "avg_tokens_per_msg": round(sum(tokens_total) / len(valid_results), 1) if valid_results else 0,
        
        # Cost
        "total_cost_usd": round(total_cost, 6),
        "avg_cost_per_msg": round(total_cost / len(valid_results), 6) if valid_results else 0,
        
        # Confidence
        "avg_confidence_correct": round(sum(correct_confs) / len(correct_confs), 4) if correct_confs else 0,
        "avg_confidence_wrong": round(sum(wrong_confs) / len(wrong_confs), 4) if wrong_confs else 0,
    }


def print_report(eval_result: dict):
    """Print evaluation report to terminal."""
    
    metrics = eval_result["metrics"]
    results = eval_result["results"]
    
    print(f"\n{'═'*70}")
    print(f"  TELEPHISDEBATE — EVALUATION REPORT")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Eval Mode: {eval_result.get('eval_mode', 'pipeline')}")
    print(f"  MAD Mode: {eval_result.get('mad_mode', 'mad3')}")
    print(f"{'═'*70}")
    
    # ── Dataset Overview ──
    print(f"\n📊 DATASET")
    print(f"   Total messages: {metrics['total']}")
    print(f"   Expected: {metrics['expected_distribution']}")
    print(f"   Predicted: {metrics['predicted_distribution']}")
    if metrics['errors'] > 0:
        print(f"   ⚠️  Errors: {metrics['errors']}")
    
    # ── Classification Metrics ──
    print(f"\n📈 CLASSIFICATION METRICS")
    print(f"   ┌──────────────────┬──────────┐")
    print(f"   │ Accuracy         │ {metrics['accuracy']:>7.1%}  │")
    print(f"   │ Precision        │ {metrics['precision']:>7.1%}  │")
    print(f"   │ Recall           │ {metrics['recall']:>7.1%}  │")
    print(f"   │ F1-Score         │ {metrics['f1_score']:>7.1%}  │")
    print(f"   │ Detection Rate*  │ {metrics['detection_rate']:>7.1%}  │")
    print(f"   └──────────────────┴──────────┘")
    print(f"   * Detection Rate = PHISHING|SUSPICIOUS / total PHISHING expected")
    
    # ── Confusion Matrix ──
    cm = metrics["confusion_matrix"]
    print(f"\n📋 CONFUSION MATRIX (Binary: PHISHING vs non-PHISHING)")
    print(f"                        Predicted")
    print(f"                   PHISHING  non-PHISH")
    print(f"   Actual PHISHING   {cm['tp']:>4}      {cm['fn']:>4}    (TP / FN)")
    print(f"   Actual non-PHISH  {cm['fp']:>4}      {cm['tn']:>4}    (FP / TN)")
    print(f"")
    print(f"   Detected (PHISHING|SUSPICIOUS): {cm['tp_detected']}")
    print(f"   Missed  (classified SAFE):      {cm['fn_missed']}")
    
    # ── Stage Distribution ──
    stage_names = {
        "triage": "Rule-Based Triage",
        "single_shot": "Single-Shot LLM",
        "mad": "Multi-Agent Debate",
    }
    
    print(f"\n🔀 STAGE DISTRIBUTION")
    for stage, count in sorted(metrics["stage_distribution"].items()):
        pct = metrics["stage_percentage"].get(stage, 0)
        acc = metrics["stage_accuracy"].get(stage, 0)
        name = stage_names.get(stage, stage)
        
        bar = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
        print(f"   {name:<22} {count:>3} ({pct:>5.1f}%) │{bar}│ acc: {acc:.0%}")
    
    # ── Performance ──
    print(f"\n⏱️  PERFORMANCE")
    print(f"   Total time:    {metrics['total_time_seconds']:.1f}s")
    print(f"   Avg per msg:   {metrics['avg_time_ms']:.0f}ms")
    print(f"   Min / Max:     {metrics['min_time_ms']}ms / {metrics['max_time_ms']}ms")
    
    # ── Token profile ──
    print(f"\n🧠 TOKEN PROFILE")
    print(f"   Total tokens:  {metrics['total_tokens']:,} (in: {metrics['total_tokens_input']:,}, out: {metrics['total_tokens_output']:,})")
    print(f"   Avg per msg:   {metrics['avg_tokens_per_msg']:,.0f} tokens")
    
    # ── Confidence Analysis ──
    print(f"\n🎯 CONFIDENCE")
    print(f"   Avg (correct):   {metrics['avg_confidence_correct']:.0%}")
    print(f"   Avg (incorrect): {metrics['avg_confidence_wrong']:.0%}")
    
    # ── Misclassifications Detail ──
    wrong = [r for r in results if not r["correct"] and r["predicted"] != "ERROR"]
    if wrong:
        print(f"\n❌ MISCLASSIFICATIONS ({len(wrong)} messages)")
        print(f"   {'─'*66}")
        for r in wrong:
            text_preview = r["text"][:60] + "..." if len(r["text"]) > 60 else r["text"]
            print(f"   #{r['index']:>2} Expected: {r['expected']:<12} Got: {r['predicted']:<12} "
                  f"conf: {r['confidence']:.0%} stage: {r['decided_by']}")
            print(f"       \"{text_preview}\"")
            if r.get("triage_flags"):
                print(f"       Triage flags: {', '.join(r['triage_flags'])}")
            print()
    else:
        print(f"\n✅ Semua prediksi benar!")
    
    # ── Summary ──
    print(f"{'═'*70}")
    emoji = "🎉" if metrics['f1_score'] >= 0.9 else "✅" if metrics['f1_score'] >= 0.7 else "⚠️"
    print(f"  {emoji} F1-Score: {metrics['f1_score']:.1%} | "
          f"Detection Rate: {metrics['detection_rate']:.1%} | "
          f"Avg Time: {metrics['avg_time_ms']:.0f}ms")
    print(f"{'═'*70}\n")


def save_results(eval_result: dict, output_dir: str):
    """Save detailed results to files."""
    
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. Save metrics summary (JSON)
    metrics_path = output / f"eval_metrics_{timestamp}.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(eval_result["metrics"], f, indent=2, ensure_ascii=False)
    print(f"  📄 Metrics: {metrics_path}")
    
    # 2. Save detailed results (CSV)
    csv_path = output / f"eval_details_{timestamp}.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "index", "text", "expected", "predicted", "correct",
            "confidence", "decided_by", "action",
            "processing_time_ms", "tokens_total", "tokens_input", "tokens_output",
            "triage_risk_score", "triage_flags", "error"
        ])
        for r in eval_result["results"]:
            writer.writerow([
                r["index"],
                r["text"][:500],
                r["expected"],
                r["predicted"],
                r["correct"],
                r["confidence"],
                r["decided_by"],
                r["action"],
                r["processing_time_ms"],
                r["tokens_total"],
                r["tokens_input"],
                r["tokens_output"],
                r["triage_risk_score"],
                "|".join(r["triage_flags"]),
                r.get("error", ""),
            ])
    print(f"  📄 Details: {csv_path}")
    
    # 3. Save full results with stage details (JSON)
    full_path = output / f"eval_full_{timestamp}.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(eval_result, f, indent=2, ensure_ascii=False, default=str)
    print(f"  📄 Full:    {full_path}")


def main():
    parser = argparse.ArgumentParser(
        description="TelePhisDebate - Dataset Evaluation"
    )
    parser.add_argument(
        "--dataset", "-d",
        required=True,
        help="Path ke file CSV dataset (kolom: chat;tipe)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Directory untuk simpan hasil evaluasi (default: tidak disimpan)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Batasi jumlah pesan yang diproses (untuk testing)"
    )
    parser.add_argument(
        "--text-col",
        default="chat",
        help="Nama kolom teks pesan di CSV (default: chat)"
    )
    parser.add_argument(
        "--label-col",
        default="tipe",
        help="Nama kolom label di CSV (default: tipe)"
    )
    parser.add_argument(
        "--delimiter",
        default=";",
        help="Separator CSV (default: ;)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output (hanya metrik akhir)"
    )
    parser.add_argument(
        "--mad-mode",
        choices=["mad3", "mad5"],
        default="mad3",
        help="Pilih varian MAD untuk Stage 3 (default: mad3)",
    )
    parser.add_argument(
        "--eval-mode",
        choices=["pipeline", "mad_only"],
        default="pipeline",
        help="Mode evaluasi: pipeline lengkap atau MAD-only (default: pipeline)",
    )
    
    args = parser.parse_args()
    
    # Suppress noisy logs
    logging.basicConfig(level=logging.WARNING)
    
    # Banner
    if not args.quiet:
        print(f"\n{'━'*70}")
        print(f"  TelePhisDebate — Dataset Evaluation")
        print(f"  Phishing Detection via Multi-Agent Debate")
        print(f"{'━'*70}")
    
    # Load dataset
    print(f"\n📂 Loading dataset: {args.dataset}")
    dataset = load_dataset(
        args.dataset,
        text_col=args.text_col,
        label_col=args.label_col,
        delimiter=args.delimiter,
        limit=args.limit
    )
    
    label_dist = Counter(d["expected_label"] for d in dataset)
    print(f"   Loaded {len(dataset)} messages")
    print(f"   Distribution: {dict(label_dist)}")
    
    if args.limit:
        print(f"   ⚠️  Limited to first {args.limit} messages")
    
    pipeline = None
    triage = None
    mad = None

    if args.eval_mode == "pipeline":
        print(f"\n🔧 Initializing detection pipeline...")
        pipeline = PhishingDetectionPipeline(mad_mode=args.mad_mode)
        print(f"   Pipeline ready (Triage → Single-Shot → {args.mad_mode.upper()})")
    else:
        print(f"\n🔧 Initializing MAD-only evaluator...")
        triage = RuleBasedTriage()
        mad = _create_mad_debate(args.mad_mode)
        print(f"   MAD-only ready (Triage context → {args.mad_mode.upper()} decision)")
    
    try:
        # Run evaluation
        print(f"\n🔄 Running evaluation on {len(dataset)} messages...")
        if args.eval_mode == "pipeline":
            eval_result = evaluate_dataset(pipeline, dataset, verbose=not args.quiet)
        else:
            eval_result = evaluate_dataset_mad_only(
                mad=mad,
                triage=triage,
                dataset=dataset,
                mad_mode=args.mad_mode,
                verbose=not args.quiet
            )
        
        # Print report
        print_report(eval_result)
        
        # Save results
        if args.output:
            print(f"💾 Saving results...")
            save_results(eval_result, args.output)
            print()
    finally:
        # Prevent aiohttp unclosed session warnings from URL checker singleton
        close_url_checker_sync()


if __name__ == "__main__":
    main()
