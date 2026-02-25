"""
Generate visualization plots for all evaluation results.

Scans `results/**/eval_metrics_*.json`, then writes:
- global summary plots in `plots/summary/`
- per-run plots in `plots/runs/<run_key>/`
- run index CSV in `plots/summary/evaluation_runs_index.csv`
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
PLOTS_DIR = ROOT / "plots"
SUMMARY_DIR = PLOTS_DIR / "summary"
RUNS_DIR = PLOTS_DIR / "runs"


@dataclass
class EvalRun:
    run_key: str
    timestamp_key: str
    timestamp: datetime | None
    run_dir: str
    provider: str
    model: str
    eval_mode: str
    mad_mode: str
    metrics_path: Path
    full_path: Path | None
    metrics: dict[str, Any]


def parse_timestamp(ts_key: str) -> datetime | None:
    try:
        return datetime.strptime(ts_key, "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def pct(v: float) -> float:
    # Input metric usually in 0..1 scale, convert to percent.
    return v * 100.0


def infer_provider_from_run_dir(run_dir: str) -> str:
    lower_dir = run_dir.lower()
    if "/deepseek/" in f"/{lower_dir}/":
        return "deepseek"
    if "/openrouter/" in f"/{lower_dir}/":
        return "openrouter"
    # Legacy folders under results/ (before provider metadata)
    if lower_dir == "results" or lower_dir.startswith("results/"):
        return "legacy"
    return "unknown"


def infer_eval_mode_from_run_dir(run_dir: str) -> str:
    lower_dir = run_dir.lower()
    if "_mad_only" in lower_dir:
        return "mad_only"
    if "mad" in lower_dir:
        return "pipeline"
    return "unknown"


def infer_mad_mode_from_run_dir(run_dir: str) -> str:
    lower_dir = run_dir.lower()
    if "mad3" in lower_dir:
        return "mad3"
    if "mad5" in lower_dir:
        return "mad5"
    return "unknown"


def build_short_label(run: EvalRun) -> str:
    ts_short = run.timestamp_key[-6:] if len(run.timestamp_key) >= 6 else run.timestamp_key
    return f"{run.provider}:{run.eval_mode}:{run.mad_mode}\n{ts_short}"


def discover_runs() -> list[EvalRun]:
    runs: list[EvalRun] = []
    for metrics_path in RESULTS_DIR.rglob("eval_metrics_*.json"):
        timestamp_key = metrics_path.stem.replace("eval_metrics_", "")
        run_dir = str(metrics_path.parent.relative_to(ROOT)).replace("\\", "/")
        full_path = metrics_path.parent / f"eval_full_{timestamp_key}.json"
        full_data = {}
        if full_path.exists():
            try:
                full_data = json.loads(full_path.read_text(encoding="utf-8"))
            except Exception:
                full_data = {}

        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        provider = str(full_data.get("llm_provider") or "unknown").strip() or "unknown"
        model = str(full_data.get("llm_model") or "unknown").strip() or "unknown"
        eval_mode = str(full_data.get("eval_mode") or "unknown").strip() or "unknown"
        mad_mode = str(full_data.get("mad_mode") or "unknown").strip() or "unknown"

        if provider == "unknown":
            provider = infer_provider_from_run_dir(run_dir)
        if eval_mode == "unknown":
            eval_mode = infer_eval_mode_from_run_dir(run_dir)
        if mad_mode == "unknown":
            mad_mode = infer_mad_mode_from_run_dir(run_dir)
        if model == "unknown":
            model = "n/a"

        run_key = f"{run_dir.replace('/', '__')}__{timestamp_key}"
        runs.append(
            EvalRun(
                run_key=run_key,
                timestamp_key=timestamp_key,
                timestamp=parse_timestamp(timestamp_key),
                run_dir=run_dir,
                provider=provider,
                model=model,
                eval_mode=eval_mode,
                mad_mode=mad_mode,
                metrics_path=metrics_path,
                full_path=full_path if full_path.exists() else None,
                metrics=metrics,
            )
        )

    runs.sort(key=lambda r: r.timestamp or datetime.min)
    return runs


def ensure_dirs() -> None:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def write_index_csv(runs: list[EvalRun]) -> None:
    out = SUMMARY_DIR / "evaluation_runs_index.csv"
    fieldnames = [
        "run_key",
        "timestamp_key",
        "timestamp",
        "run_dir",
        "provider",
        "model",
        "eval_mode",
        "mad_mode",
        "accuracy_pct",
        "precision_pct",
        "recall_pct",
        "f1_pct",
        "detection_rate_pct",
        "avg_time_ms",
        "avg_tokens_per_msg",
        "total_cost_usd",
        "total",
        "correct",
        "wrong",
    ]

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in runs:
            m = r.metrics
            writer.writerow(
                {
                    "run_key": r.run_key,
                    "timestamp_key": r.timestamp_key,
                    "timestamp": r.timestamp.isoformat(sep=" ") if r.timestamp else "",
                    "run_dir": r.run_dir,
                    "provider": r.provider,
                    "model": r.model,
                    "eval_mode": r.eval_mode,
                    "mad_mode": r.mad_mode,
                    "accuracy_pct": round(pct(safe_float(m.get("accuracy"))), 2),
                    "precision_pct": round(pct(safe_float(m.get("precision"))), 2),
                    "recall_pct": round(pct(safe_float(m.get("recall"))), 2),
                    "f1_pct": round(pct(safe_float(m.get("f1_score"))), 2),
                    "detection_rate_pct": round(pct(safe_float(m.get("detection_rate"))), 2),
                    "avg_time_ms": round(safe_float(m.get("avg_time_ms")), 2),
                    "avg_tokens_per_msg": round(safe_float(m.get("avg_tokens_per_msg")), 2),
                    "total_cost_usd": round(safe_float(m.get("total_cost_usd")), 6),
                    "total": int(safe_float(m.get("total"), 0)),
                    "correct": int(safe_float(m.get("correct"), 0)),
                    "wrong": int(safe_float(m.get("wrong"), 0)),
                }
            )


def save_plot(fig, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def make_summary_plots(runs: list[EvalRun]) -> None:
    if not runs:
        return

    labels = [build_short_label(r) for r in runs]
    f1 = [pct(safe_float(r.metrics.get("f1_score"))) for r in runs]
    acc = [pct(safe_float(r.metrics.get("accuracy"))) for r in runs]
    avg_ms = [safe_float(r.metrics.get("avg_time_ms")) for r in runs]
    tok = [safe_float(r.metrics.get("avg_tokens_per_msg")) for r in runs]

    # 1) F1 by run
    fig, ax = plt.subplots(figsize=(max(10, len(runs) * 0.55), 5))
    ax.bar(range(len(runs)), f1, color="#0a7cff")
    ax.set_title("F1-Score by Evaluation Run")
    ax.set_ylabel("F1 (%)")
    ax.set_ylim(0, 105)
    ax.set_xticks(range(len(runs)))
    ax.set_xticklabels(labels, rotation=55, ha="right", fontsize=8)
    save_plot(fig, SUMMARY_DIR / "f1_by_run.png")

    # 2) Accuracy vs F1
    fig, ax = plt.subplots(figsize=(max(10, len(runs) * 0.55), 5))
    width = 0.42
    x = list(range(len(runs)))
    ax.bar([i - width / 2 for i in x], acc, width=width, label="Accuracy", color="#24b47e")
    ax.bar([i + width / 2 for i in x], f1, width=width, label="F1", color="#0a7cff")
    ax.set_title("Accuracy vs F1 by Run")
    ax.set_ylabel("Score (%)")
    ax.set_ylim(0, 105)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=55, ha="right", fontsize=8)
    ax.legend()
    save_plot(fig, SUMMARY_DIR / "accuracy_vs_f1_by_run.png")

    # 3) Speed vs F1 scatter
    fig, ax = plt.subplots(figsize=(8, 5))
    provider_colors = {
        "deepseek": "#0a7cff",
        "openrouter": "#f59e0b",
        "legacy": "#64748b",
        "unknown": "#6b7280",
    }
    for r, x_ms, y_f1 in zip(runs, avg_ms, f1):
        ax.scatter(
            x_ms,
            y_f1,
            color=provider_colors.get(r.provider, "#6b7280"),
            s=70,
            alpha=0.9,
        )
        ax.text(x_ms, y_f1, r.mad_mode, fontsize=7, alpha=0.85)
    ax.set_title("Tradeoff: Avg Time vs F1")
    ax.set_xlabel("Avg Time per Message (ms)")
    ax.set_ylabel("F1 (%)")
    ax.grid(alpha=0.25)
    save_plot(fig, SUMMARY_DIR / "tradeoff_time_vs_f1.png")

    # 4) Tokens vs F1 scatter
    fig, ax = plt.subplots(figsize=(8, 5))
    for r, x_tok, y_f1 in zip(runs, tok, f1):
        ax.scatter(
            x_tok,
            y_f1,
            color=provider_colors.get(r.provider, "#6b7280"),
            s=70,
            alpha=0.9,
        )
        ax.text(x_tok, y_f1, r.mad_mode, fontsize=7, alpha=0.85)
    ax.set_title("Tradeoff: Avg Tokens/Msg vs F1")
    ax.set_xlabel("Avg Tokens per Message")
    ax.set_ylabel("F1 (%)")
    ax.grid(alpha=0.25)
    save_plot(fig, SUMMARY_DIR / "tradeoff_tokens_vs_f1.png")


def make_deepseek_vs_openrouter_gemini_plot(runs: list[EvalRun]) -> None:
    if not runs:
        return

    def scenario_key(run: EvalRun) -> tuple[str, str]:
        return (run.eval_mode, run.mad_mode)

    def scenario_rank(key: tuple[str, str]) -> int:
        order = {
            ("pipeline", "mad3"): 0,
            ("pipeline", "mad5"): 1,
            ("mad_only", "mad3"): 2,
            ("mad_only", "mad5"): 3,
        }
        return order.get(key, 99)

    # Keep only latest run per scenario.
    deepseek_latest: dict[tuple[str, str], EvalRun] = {}
    gemini_latest: dict[tuple[str, str], EvalRun] = {}
    for run in runs:
        key = scenario_key(run)
        ts = run.timestamp or datetime.min
        if run.provider == "deepseek":
            prev = deepseek_latest.get(key)
            if prev is None or ts > (prev.timestamp or datetime.min):
                deepseek_latest[key] = run
        elif run.provider == "openrouter" and "gemini" in run.model.lower():
            prev = gemini_latest.get(key)
            if prev is None or ts > (prev.timestamp or datetime.min):
                gemini_latest[key] = run

    common_keys = sorted(set(deepseek_latest.keys()) & set(gemini_latest.keys()), key=scenario_rank)
    if not common_keys:
        return

    labels = [f"{eval_mode}\n{mad_mode}" for eval_mode, mad_mode in common_keys]
    short_labels = [f"{eval_mode}-{mad_mode}" for eval_mode, mad_mode in common_keys]
    acc_deepseek = [pct(safe_float(deepseek_latest[k].metrics.get("accuracy"))) for k in common_keys]
    acc_gemini = [pct(safe_float(gemini_latest[k].metrics.get("accuracy"))) for k in common_keys]
    f1_deepseek = [pct(safe_float(deepseek_latest[k].metrics.get("f1_score"))) for k in common_keys]
    f1_gemini = [pct(safe_float(gemini_latest[k].metrics.get("f1_score"))) for k in common_keys]
    time_deepseek = [safe_float(deepseek_latest[k].metrics.get("avg_time_ms")) for k in common_keys]
    time_gemini = [safe_float(gemini_latest[k].metrics.get("avg_time_ms")) for k in common_keys]
    tok_deepseek = [safe_float(deepseek_latest[k].metrics.get("avg_tokens_per_msg")) for k in common_keys]
    tok_gemini = [safe_float(gemini_latest[k].metrics.get("avg_tokens_per_msg")) for k in common_keys]

    width = 0.36
    x = list(range(len(common_keys)))

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    ax = axes[0]
    deepseek_bars = ax.bar([i - width / 2 for i in x], f1_deepseek, width=width, label="deepseek", color="#0a7cff")
    gemini_bars = ax.bar(
        [i + width / 2 for i in x], f1_gemini, width=width, label="openrouter:gemini", color="#f59e0b"
    )
    ax.set_title("DeepSeek vs OpenRouter Gemini (Latest Run per Scenario)")
    ax.set_ylabel("F1 (%)")
    ax.set_ylim(0, 105)
    ax.legend()
    for bars in [deepseek_bars, gemini_bars]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 1, f"{h:.1f}", ha="center", fontsize=8)

    ax = axes[1]
    deepseek_bars = ax.bar([i - width / 2 for i in x], time_deepseek, width=width, label="deepseek", color="#0a7cff")
    gemini_bars = ax.bar(
        [i + width / 2 for i in x], time_gemini, width=width, label="openrouter:gemini", color="#f59e0b"
    )
    ax.set_ylabel("Avg Time (ms/msg)")
    ax.set_xlabel("Scenario")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    for bars in [deepseek_bars, gemini_bars]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 120, f"{h:.0f}", ha="center", fontsize=8)

    save_plot(fig, SUMMARY_DIR / "deepseek_vs_openrouter_gemini.png")

    # F1-only comparison chart.
    fig, ax = plt.subplots(figsize=(10, 5))
    deepseek_bars = ax.bar([i - width / 2 for i in x], f1_deepseek, width=width, label="deepseek", color="#0a7cff")
    gemini_bars = ax.bar(
        [i + width / 2 for i in x], f1_gemini, width=width, label="openrouter:gemini", color="#f59e0b"
    )
    ax.set_title("F1 by Run: DeepSeek vs OpenRouter Gemini")
    ax.set_ylabel("F1 (%)")
    ax.set_ylim(0, 105)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    for bars in [deepseek_bars, gemini_bars]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 1, f"{h:.1f}", ha="center", fontsize=8)
    save_plot(fig, SUMMARY_DIR / "deepseek_vs_openrouter_gemini_f1_by_run.png")

    # Accuracy vs F1 per scenario for each provider.
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

    ax = axes[0]
    ds_acc = ax.bar([i - width / 2 for i in x], acc_deepseek, width=width, label="Accuracy", color="#24b47e")
    ds_f1 = ax.bar([i + width / 2 for i in x], f1_deepseek, width=width, label="F1", color="#0a7cff")
    ax.set_title("deepseek")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Score (%)")
    for bars in [ds_acc, ds_f1]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 1, f"{h:.1f}", ha="center", fontsize=8)

    ax = axes[1]
    or_acc = ax.bar([i - width / 2 for i in x], acc_gemini, width=width, label="Accuracy", color="#24b47e")
    or_f1 = ax.bar([i + width / 2 for i in x], f1_gemini, width=width, label="F1", color="#f59e0b")
    ax.set_title("openrouter:gemini")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 105)
    for bars in [or_acc, or_f1]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 1, f"{h:.1f}", ha="center", fontsize=8)
    ax.legend(loc="upper right")

    fig.suptitle("Accuracy vs F1 by Run: DeepSeek vs OpenRouter Gemini", fontsize=12)
    save_plot(fig, SUMMARY_DIR / "deepseek_vs_openrouter_gemini_accuracy_vs_f1_by_run.png")

    # Tradeoff (Time vs F1) dedicated compare.
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(time_deepseek, f1_deepseek, color="#0a7cff", s=80, label="deepseek")
    ax.scatter(time_gemini, f1_gemini, color="#f59e0b", s=80, label="openrouter:gemini")
    for x_ms, y_f1, label in zip(time_deepseek, f1_deepseek, short_labels):
        ax.text(x_ms, y_f1, f" {label}", fontsize=8, color="#0a7cff")
    for x_ms, y_f1, label in zip(time_gemini, f1_gemini, short_labels):
        ax.text(x_ms, y_f1, f" {label}", fontsize=8, color="#b45309")
    ax.set_title("Tradeoff Time vs F1: DeepSeek vs OpenRouter Gemini")
    ax.set_xlabel("Avg Time per Message (ms)")
    ax.set_ylabel("F1 (%)")
    ax.grid(alpha=0.25)
    ax.legend()
    save_plot(fig, SUMMARY_DIR / "deepseek_vs_openrouter_gemini_tradeoff_time_vs_f1.png")

    # Tradeoff (Tokens vs F1) dedicated compare.
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(tok_deepseek, f1_deepseek, color="#0a7cff", s=80, label="deepseek")
    ax.scatter(tok_gemini, f1_gemini, color="#f59e0b", s=80, label="openrouter:gemini")
    for x_tok, y_f1, label in zip(tok_deepseek, f1_deepseek, short_labels):
        ax.text(x_tok, y_f1, f" {label}", fontsize=8, color="#0a7cff")
    for x_tok, y_f1, label in zip(tok_gemini, f1_gemini, short_labels):
        ax.text(x_tok, y_f1, f" {label}", fontsize=8, color="#b45309")
    ax.set_title("Tradeoff Tokens vs F1: DeepSeek vs OpenRouter Gemini")
    ax.set_xlabel("Avg Tokens per Message")
    ax.set_ylabel("F1 (%)")
    ax.grid(alpha=0.25)
    ax.legend()
    save_plot(fig, SUMMARY_DIR / "deepseek_vs_openrouter_gemini_tradeoff_tokens_vs_f1.png")


def make_mad3_vs_mad5_plot(runs: list[EvalRun]) -> None:
    if not runs:
        return

    def mode_rank(mode: str) -> int:
        return {"pipeline": 0, "mad_only": 1}.get(mode, 99)

    def provider_rank(provider: str) -> int:
        return {"deepseek": 0, "openrouter": 1, "legacy": 2, "unknown": 3}.get(provider, 99)

    # Keep latest run for each (provider, eval_mode, mad_mode).
    latest: dict[tuple[str, str, str], EvalRun] = {}
    for run in runs:
        if run.mad_mode not in {"mad3", "mad5"}:
            continue
        if run.eval_mode not in {"pipeline", "mad_only"}:
            continue
        key = (run.provider, run.eval_mode, run.mad_mode)
        ts = run.timestamp or datetime.min
        prev = latest.get(key)
        if prev is None or ts > (prev.timestamp or datetime.min):
            latest[key] = run

    base_keys = sorted(
        {(provider, eval_mode) for provider, eval_mode, _ in latest.keys()},
        key=lambda k: (provider_rank(k[0]), mode_rank(k[1])),
    )

    # Keep only scenarios that have both mad3 and mad5.
    paired = [k for k in base_keys if (k[0], k[1], "mad3") in latest and (k[0], k[1], "mad5") in latest]
    if not paired:
        return

    labels = [f"{provider}\n{eval_mode}" for provider, eval_mode in paired]
    f1_mad3 = [pct(safe_float(latest[(p, e, "mad3")].metrics.get("f1_score"))) for p, e in paired]
    f1_mad5 = [pct(safe_float(latest[(p, e, "mad5")].metrics.get("f1_score"))) for p, e in paired]
    acc_mad3 = [pct(safe_float(latest[(p, e, "mad3")].metrics.get("accuracy"))) for p, e in paired]
    acc_mad5 = [pct(safe_float(latest[(p, e, "mad5")].metrics.get("accuracy"))) for p, e in paired]

    x = list(range(len(paired)))
    width = 0.36

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    ax = axes[0]
    mad3_bars = ax.bar([i - width / 2 for i in x], f1_mad3, width=width, label="MAD3", color="#0a7cff")
    mad5_bars = ax.bar([i + width / 2 for i in x], f1_mad5, width=width, label="MAD5", color="#f59e0b")
    ax.set_title("MAD3 vs MAD5 (Latest Run per Provider & Eval Mode)")
    ax.set_ylabel("F1 (%)")
    ax.set_ylim(0, 105)
    ax.legend()
    for bars in [mad3_bars, mad5_bars]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 1, f"{h:.1f}", ha="center", fontsize=8)

    ax = axes[1]
    mad3_bars = ax.bar([i - width / 2 for i in x], acc_mad3, width=width, label="MAD3", color="#0a7cff")
    mad5_bars = ax.bar([i + width / 2 for i in x], acc_mad5, width=width, label="MAD5", color="#f59e0b")
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 105)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel("Provider / Eval Mode")
    for bars in [mad3_bars, mad5_bars]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 1, f"{h:.1f}", ha="center", fontsize=8)

    save_plot(fig, SUMMARY_DIR / "mad3_vs_mad5_by_provider_mode.png")


def make_deepseek_mad3_vs_mad5_plot(runs: list[EvalRun]) -> None:
    if not runs:
        return

    def eval_mode_rank(mode: str) -> int:
        return {"pipeline": 0, "mad_only": 1}.get(mode, 99)

    # Latest deepseek run per (eval_mode, mad_mode)
    latest: dict[tuple[str, str], EvalRun] = {}
    for run in runs:
        if run.provider != "deepseek":
            continue
        if run.mad_mode not in {"mad3", "mad5"}:
            continue
        if run.eval_mode not in {"pipeline", "mad_only"}:
            continue
        key = (run.eval_mode, run.mad_mode)
        ts = run.timestamp or datetime.min
        prev = latest.get(key)
        if prev is None or ts > (prev.timestamp or datetime.min):
            latest[key] = run

    eval_modes = [m for m in ["pipeline", "mad_only"] if (m, "mad3") in latest and (m, "mad5") in latest]
    eval_modes.sort(key=eval_mode_rank)
    if not eval_modes:
        return

    labels = eval_modes
    f1_mad3 = [pct(safe_float(latest[(mode, "mad3")].metrics.get("f1_score"))) for mode in eval_modes]
    f1_mad5 = [pct(safe_float(latest[(mode, "mad5")].metrics.get("f1_score"))) for mode in eval_modes]
    acc_mad3 = [pct(safe_float(latest[(mode, "mad3")].metrics.get("accuracy"))) for mode in eval_modes]
    acc_mad5 = [pct(safe_float(latest[(mode, "mad5")].metrics.get("accuracy"))) for mode in eval_modes]
    time_mad3 = [safe_float(latest[(mode, "mad3")].metrics.get("avg_time_ms")) for mode in eval_modes]
    time_mad5 = [safe_float(latest[(mode, "mad5")].metrics.get("avg_time_ms")) for mode in eval_modes]

    x = list(range(len(eval_modes)))
    width = 0.36

    fig, axes = plt.subplots(3, 1, figsize=(9, 10), sharex=True)

    ax = axes[0]
    mad3_bars = ax.bar([i - width / 2 for i in x], f1_mad3, width=width, label="MAD3", color="#0a7cff")
    mad5_bars = ax.bar([i + width / 2 for i in x], f1_mad5, width=width, label="MAD5", color="#f59e0b")
    ax.set_title("DeepSeek Only: MAD3 vs MAD5")
    ax.set_ylabel("F1 (%)")
    ax.set_ylim(0, 105)
    ax.legend()
    for bars in [mad3_bars, mad5_bars]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 1, f"{h:.1f}", ha="center", fontsize=8)

    ax = axes[1]
    mad3_bars = ax.bar([i - width / 2 for i in x], acc_mad3, width=width, label="MAD3", color="#0a7cff")
    mad5_bars = ax.bar([i + width / 2 for i in x], acc_mad5, width=width, label="MAD5", color="#f59e0b")
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 105)
    for bars in [mad3_bars, mad5_bars]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 1, f"{h:.1f}", ha="center", fontsize=8)

    ax = axes[2]
    mad3_bars = ax.bar([i - width / 2 for i in x], time_mad3, width=width, label="MAD3", color="#0a7cff")
    mad5_bars = ax.bar([i + width / 2 for i in x], time_mad5, width=width, label="MAD5", color="#f59e0b")
    ax.set_ylabel("Avg Time (ms/msg)")
    ax.set_xlabel("Eval Mode")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    for bars in [mad3_bars, mad5_bars]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 120, f"{h:.0f}", ha="center", fontsize=8)

    save_plot(fig, SUMMARY_DIR / "deepseek_mad3_vs_mad5_by_eval_mode.png")


def make_gemini_mad3_vs_mad5_plot(runs: list[EvalRun]) -> None:
    if not runs:
        return

    def eval_mode_rank(mode: str) -> int:
        return {"pipeline": 0, "mad_only": 1}.get(mode, 99)

    # Latest openrouter gemini run per (eval_mode, mad_mode)
    latest: dict[tuple[str, str], EvalRun] = {}
    for run in runs:
        if run.provider != "openrouter":
            continue
        if "gemini" not in run.model.lower():
            continue
        if run.mad_mode not in {"mad3", "mad5"}:
            continue
        if run.eval_mode not in {"pipeline", "mad_only"}:
            continue
        key = (run.eval_mode, run.mad_mode)
        ts = run.timestamp or datetime.min
        prev = latest.get(key)
        if prev is None or ts > (prev.timestamp or datetime.min):
            latest[key] = run

    eval_modes = [m for m in ["pipeline", "mad_only"] if (m, "mad3") in latest and (m, "mad5") in latest]
    eval_modes.sort(key=eval_mode_rank)
    if not eval_modes:
        return

    labels = eval_modes
    f1_mad3 = [pct(safe_float(latest[(mode, "mad3")].metrics.get("f1_score"))) for mode in eval_modes]
    f1_mad5 = [pct(safe_float(latest[(mode, "mad5")].metrics.get("f1_score"))) for mode in eval_modes]
    acc_mad3 = [pct(safe_float(latest[(mode, "mad3")].metrics.get("accuracy"))) for mode in eval_modes]
    acc_mad5 = [pct(safe_float(latest[(mode, "mad5")].metrics.get("accuracy"))) for mode in eval_modes]
    time_mad3 = [safe_float(latest[(mode, "mad3")].metrics.get("avg_time_ms")) for mode in eval_modes]
    time_mad5 = [safe_float(latest[(mode, "mad5")].metrics.get("avg_time_ms")) for mode in eval_modes]

    x = list(range(len(eval_modes)))
    width = 0.36

    fig, axes = plt.subplots(3, 1, figsize=(9, 10), sharex=True)

    ax = axes[0]
    mad3_bars = ax.bar([i - width / 2 for i in x], f1_mad3, width=width, label="MAD3", color="#0a7cff")
    mad5_bars = ax.bar([i + width / 2 for i in x], f1_mad5, width=width, label="MAD5", color="#f59e0b")
    ax.set_title("OpenRouter Gemini Only: MAD3 vs MAD5")
    ax.set_ylabel("F1 (%)")
    ax.set_ylim(0, 105)
    ax.legend()
    for bars in [mad3_bars, mad5_bars]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 1, f"{h:.1f}", ha="center", fontsize=8)

    ax = axes[1]
    mad3_bars = ax.bar([i - width / 2 for i in x], acc_mad3, width=width, label="MAD3", color="#0a7cff")
    mad5_bars = ax.bar([i + width / 2 for i in x], acc_mad5, width=width, label="MAD5", color="#f59e0b")
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 105)
    for bars in [mad3_bars, mad5_bars]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 1, f"{h:.1f}", ha="center", fontsize=8)

    ax = axes[2]
    mad3_bars = ax.bar([i - width / 2 for i in x], time_mad3, width=width, label="MAD3", color="#0a7cff")
    mad5_bars = ax.bar([i + width / 2 for i in x], time_mad5, width=width, label="MAD5", color="#f59e0b")
    ax.set_ylabel("Avg Time (ms/msg)")
    ax.set_xlabel("Eval Mode")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    for bars in [mad3_bars, mad5_bars]:
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 120, f"{h:.0f}", ha="center", fontsize=8)

    save_plot(fig, SUMMARY_DIR / "gemini_mad3_vs_mad5_by_eval_mode.png")


def make_per_run_plots(run: EvalRun) -> None:
    run_dir = RUNS_DIR / run.run_key
    run_dir.mkdir(parents=True, exist_ok=True)
    m = run.metrics

    # A) core metrics bar
    metric_names = ["Accuracy", "Precision", "Recall", "F1", "Detection Rate"]
    metric_vals = [
        pct(safe_float(m.get("accuracy"))),
        pct(safe_float(m.get("precision"))),
        pct(safe_float(m.get("recall"))),
        pct(safe_float(m.get("f1_score"))),
        pct(safe_float(m.get("detection_rate"))),
    ]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar(metric_names, metric_vals, color=["#24b47e", "#0ea5e9", "#f59e0b", "#0a7cff", "#8b5cf6"])
    ax.set_ylim(0, 105)
    ax.set_ylabel("Score (%)")
    ax.set_title(
        f"Run Metrics: {run.provider}/{run.eval_mode}/{run.mad_mode}\n"
        f"{run.model} | {run.timestamp_key}"
    )
    for b, val in zip(bars, metric_vals):
        ax.text(b.get_x() + b.get_width() / 2, val + 1, f"{val:.1f}%", ha="center", fontsize=8)
    save_plot(fig, run_dir / "metrics_overview.png")

    # B) confusion matrix
    cm = m.get("confusion_matrix", {}) or {}
    tp = int(safe_float(cm.get("tp"), 0))
    fn = int(safe_float(cm.get("fn"), 0))
    fp = int(safe_float(cm.get("fp"), 0))
    tn = int(safe_float(cm.get("tn"), 0))
    mat = [[tp, fn], [fp, tn]]

    fig, ax = plt.subplots(figsize=(5, 4.6))
    im = ax.imshow(mat, cmap="Blues")
    ax.set_xticks([0, 1], ["PHISHING", "non-PHISH"])
    ax.set_yticks([0, 1], ["PHISHING", "non-PHISH"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Confusion Matrix (Binary)")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(mat[i][j]), ha="center", va="center", color="black", fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    save_plot(fig, run_dir / "confusion_matrix.png")

    # C) stage distribution
    stage_pct = m.get("stage_percentage", {}) or {}
    if stage_pct:
        names = list(stage_pct.keys())
        vals = [safe_float(stage_pct[k]) for k in names]
        fig, ax = plt.subplots(figsize=(7, 4.5))
        bars = ax.bar(names, vals, color="#64748b")
        ax.set_ylim(0, 105)
        ax.set_ylabel("Percentage (%)")
        ax.set_title("Stage Distribution")
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.1f}%", ha="center", fontsize=8)
        save_plot(fig, run_dir / "stage_distribution.png")


def write_manifest(runs: list[EvalRun]) -> None:
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results_root": str(RESULTS_DIR),
        "plots_root": str(PLOTS_DIR),
        "run_count": len(runs),
        "runs": [
            {
                "run_key": r.run_key,
                "run_dir": r.run_dir,
                "timestamp_key": r.timestamp_key,
                "provider": r.provider,
                "model": r.model,
                "eval_mode": r.eval_mode,
                "mad_mode": r.mad_mode,
            }
            for r in runs
        ],
    }
    (PLOTS_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    ensure_dirs()
    runs = discover_runs()
    write_index_csv(runs)
    make_summary_plots(runs)
    make_deepseek_vs_openrouter_gemini_plot(runs)
    make_mad3_vs_mad5_plot(runs)
    make_deepseek_mad3_vs_mad5_plot(runs)
    make_gemini_mad3_vs_mad5_plot(runs)
    for run in runs:
        make_per_run_plots(run)
    write_manifest(runs)
    print(f"Generated plots for {len(runs)} evaluation runs.")
    print(f"Output directory: {PLOTS_DIR}")


if __name__ == "__main__":
    main()
