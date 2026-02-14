"""
Dashboard Flask Application
Provides web interface for monitoring bot activity
"""

import os
import glob
import json
import csv
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

from src.config import config
from src.database.client import get_supabase_client


def create_app():
    """Create and configure Flask application"""
    
    # Get template and static folders
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    
    # Results directory (project root)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    results_dir = os.path.join(project_root, 'results')
    
    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir
    )
    
    # Enable CORS
    CORS(app)
    
    # Initialize database
    db = get_supabase_client()

    def _format_eval_timestamp(timestamp_str: str) -> str:
        """Convert evaluation filename timestamp into display format."""
        try:
            return datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S").strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            return timestamp_str

    def _load_eval_details(details_path: str | None) -> list[dict]:
        """Load evaluation details CSV with encoding fallback."""
        details: list[dict] = []
        if not details_path or not os.path.exists(details_path):
            return details

        encodings = ["utf-8-sig", "utf-8", "latin-1"]
        for enc in encodings:
            try:
                with open(details_path, "r", encoding=enc) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        details.append(
                            {
                                "index": int(row.get("index", 0)),
                                "text": row.get("text", "")[:150],
                                "expected": row.get("expected", ""),
                                "predicted": row.get("predicted", ""),
                                "correct": row.get("correct", "") == "True",
                                "confidence": float(row.get("confidence", 0) or 0),
                                "decided_by": row.get("decided_by", ""),
                                "action": row.get("action", ""),
                                "processing_time_ms": int(
                                    row.get("processing_time_ms", 0) or 0
                                ),
                                "tokens_total": int(row.get("tokens_total", 0) or 0),
                                "tokens_input": int(row.get("tokens_input", 0) or 0),
                                "tokens_output": int(row.get("tokens_output", 0) or 0),
                                "triage_risk_score": int(
                                    row.get("triage_risk_score", 0) or 0
                                ),
                                "triage_flags": row.get("triage_flags", ""),
                                "error": row.get("error", ""),
                            }
                        )
                break
            except (UnicodeDecodeError, KeyError):
                continue
        return details

    def _metric_snapshot(eval_data: dict | None) -> dict | None:
        """Extract compact metric view for comparison pages."""
        if not eval_data:
            return None
        metrics = eval_data.get("metrics", {})
        return {
            "accuracy": metrics.get("accuracy", 0),
            "precision": metrics.get("precision", 0),
            "recall": metrics.get("recall", 0),
            "f1_score": metrics.get("f1_score", 0),
            "detection_rate": metrics.get("detection_rate", 0),
            "avg_time_ms": metrics.get("avg_time_ms", 0),
            "avg_tokens_per_msg": metrics.get("avg_tokens_per_msg", 0),
            "total_cost_usd": metrics.get("total_cost_usd", 0),
            "total": metrics.get("total", 0),
            "correct": metrics.get("correct", 0),
            "wrong": metrics.get("wrong", 0),
            "stage_distribution": metrics.get("stage_distribution", {}),
        }

    def _load_evaluation_by_timestamp(
        base_dir: str,
        timestamp_str: str,
        full_path: str | None = None
    ) -> dict | None:
        """Load one evaluation run from a directory and timestamp key."""
        metrics_path = os.path.join(base_dir, f"eval_metrics_{timestamp_str}.json")
        if not os.path.exists(metrics_path):
            return None

        details_path = os.path.join(base_dir, f"eval_details_{timestamp_str}.csv")
        if not os.path.exists(details_path):
            details_path = None

        if not full_path:
            candidate_full = os.path.join(base_dir, f"eval_full_{timestamp_str}.json")
            full_path = candidate_full if os.path.exists(candidate_full) else None

        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        details = _load_eval_details(details_path)
        wrong_predictions = [d for d in details if not d["correct"]]

        full_data = {}
        if full_path and os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    full_data = json.load(f)
            except Exception:
                full_data = {}

        return {
            "metrics": metrics,
            "details": details,
            "wrong_predictions": wrong_predictions,
            "eval_timestamp": _format_eval_timestamp(timestamp_str),
            "eval_mode": full_data.get("eval_mode", "pipeline"),
            "mad_mode": full_data.get("mad_mode"),
            "run_dir": os.path.relpath(base_dir, project_root),
            "timestamp_key": timestamp_str,
            "files": {
                "metrics": os.path.basename(metrics_path),
                "details": os.path.basename(details_path) if details_path else None,
                "full": os.path.basename(full_path) if full_path else None,
            },
        }

    def _load_latest_evaluation(base_dir: str) -> dict | None:
        """Load latest evaluation run from a specific directory."""
        metrics_files = sorted(glob.glob(os.path.join(base_dir, "eval_metrics_*.json")))
        if not metrics_files:
            return None

        latest_metrics = metrics_files[-1]
        timestamp_str = os.path.basename(latest_metrics).replace(
            "eval_metrics_", ""
        ).replace(".json", "")

        full_path = os.path.join(base_dir, f"eval_full_{timestamp_str}.json")
        if not os.path.exists(full_path):
            full_path = None

        return _load_evaluation_by_timestamp(base_dir, timestamp_str, full_path=full_path)

    def _find_latest_evaluation_recursive(
        mad_mode: str | None = None,
        eval_mode: str | None = None
    ) -> dict | None:
        """Find latest evaluation recursively in results/ filtered by modes."""
        full_files = sorted(
            glob.glob(os.path.join(results_dir, "**", "eval_full_*.json"), recursive=True),
            key=os.path.getmtime,
            reverse=True
        )

        for full_path in full_files:
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    full_data = json.load(f)
            except Exception:
                continue

            run_mad_mode = full_data.get("mad_mode")
            run_eval_mode = full_data.get("eval_mode", "pipeline")

            if mad_mode and run_mad_mode != mad_mode:
                continue
            if eval_mode and run_eval_mode != eval_mode:
                continue

            base_dir = os.path.dirname(full_path)
            timestamp_str = os.path.basename(full_path).replace(
                "eval_full_", ""
            ).replace(".json", "")
            run = _load_evaluation_by_timestamp(
                base_dir, timestamp_str, full_path=full_path
            )
            if run:
                return run

        return None
    
    # ============================================================
    # Routes
    # ============================================================
    
    @app.route('/')
    def index():
        """Main dashboard page"""
        return render_template('index.html')
    
    @app.route('/evaluation')
    def evaluation():
        """Evaluation results page"""
        return render_template('evaluation.html')

    @app.route('/evaluation/compare')
    def evaluation_compare():
        """MAD comparison page (mad3 vs mad5)."""
        return render_template('mad_compare.html')

    @app.route('/evaluation/modes')
    def evaluation_modes():
        """Pipeline vs MAD-only comparison page."""
        return render_template('evaluation_modes.html')
    
    @app.route('/api/evaluation')
    def get_evaluation_data():
        """Get latest evaluation results from results/ directory"""
        try:
            eval_data = _load_latest_evaluation(results_dir)
            if not eval_data:
                eval_data = _find_latest_evaluation_recursive()
            if not eval_data:
                return jsonify({"error": "No evaluation results found"}), 404
            return jsonify(eval_data)
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/evaluation/compare')
    def get_evaluation_comparison():
        """Compare latest MAD3 and MAD5 evaluation runs."""
        try:
            requested_eval_mode = request.args.get("eval_mode", "pipeline")
            if requested_eval_mode not in {"pipeline", "mad_only"}:
                return jsonify({"error": "eval_mode must be 'pipeline' or 'mad_only'"}), 400

            if requested_eval_mode == "pipeline":
                mad3_dir = os.path.join(results_dir, "mad3")
                mad5_dir = os.path.join(results_dir, "mad5")
            else:
                mad3_dir = os.path.join(results_dir, "mad3_mad_only")
                mad5_dir = os.path.join(results_dir, "mad5_mad_only")

            mad3 = _load_latest_evaluation(mad3_dir) or _find_latest_evaluation_recursive(
                mad_mode="mad3", eval_mode=requested_eval_mode
            )
            mad5 = _load_latest_evaluation(mad5_dir) or _find_latest_evaluation_recursive(
                mad_mode="mad5", eval_mode=requested_eval_mode
            )

            if not mad3 and not mad5:
                return jsonify({
                    "error": (
                        f"No MAD comparison runs found for eval_mode='{requested_eval_mode}'. "
                        "Run evaluate.py first and save results."
                    )
                }), 404

            mad3_metrics = _metric_snapshot(mad3)
            mad5_metrics = _metric_snapshot(mad5)

            deltas = {}
            if mad3_metrics and mad5_metrics:
                for key in [
                    "accuracy",
                    "precision",
                    "recall",
                    "f1_score",
                    "detection_rate",
                    "avg_time_ms",
                    "avg_tokens_per_msg",
                    "total_cost_usd",
                ]:
                    deltas[key] = mad5_metrics.get(key, 0) - mad3_metrics.get(key, 0)

            return jsonify({
                "requested_eval_mode": requested_eval_mode,
                "mad3": {
                    "available": mad3 is not None,
                    "eval_mode": mad3.get("eval_mode") if mad3 else None,
                    "mad_mode": mad3.get("mad_mode") if mad3 else "mad3",
                    "run_dir": mad3.get("run_dir") if mad3 else os.path.relpath(mad3_dir, project_root),
                    "timestamp": mad3.get("eval_timestamp") if mad3 else None,
                    "files": mad3.get("files") if mad3 else None,
                    "metrics": mad3_metrics,
                },
                "mad5": {
                    "available": mad5 is not None,
                    "eval_mode": mad5.get("eval_mode") if mad5 else None,
                    "mad_mode": mad5.get("mad_mode") if mad5 else "mad5",
                    "run_dir": mad5.get("run_dir") if mad5 else os.path.relpath(mad5_dir, project_root),
                    "timestamp": mad5.get("eval_timestamp") if mad5 else None,
                    "files": mad5.get("files") if mad5 else None,
                    "metrics": mad5_metrics,
                },
                "deltas": deltas,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/evaluation/modes')
    def get_evaluation_mode_comparison():
        """Compare pipeline vs mad_only for a selected MAD variant."""
        try:
            mad_mode = request.args.get("mad_mode", "mad5")
            if mad_mode not in {"mad3", "mad5"}:
                return jsonify({"error": "mad_mode must be 'mad3' or 'mad5'"}), 400

            default_pipeline_dir = os.path.join(results_dir, mad_mode)
            default_mad_only_dir = os.path.join(results_dir, f"{mad_mode}_mad_only")

            pipeline_run = _load_latest_evaluation(default_pipeline_dir) or _find_latest_evaluation_recursive(
                mad_mode=mad_mode, eval_mode="pipeline"
            )
            mad_only_run = _load_latest_evaluation(default_mad_only_dir) or _find_latest_evaluation_recursive(
                mad_mode=mad_mode, eval_mode="mad_only"
            )

            if not pipeline_run and not mad_only_run:
                return jsonify({
                    "error": (
                        f"No runs found for {mad_mode}. "
                        "Run evaluate.py for both eval modes first."
                    )
                }), 404

            pipeline_metrics = _metric_snapshot(pipeline_run)
            mad_only_metrics = _metric_snapshot(mad_only_run)

            deltas = {}
            if pipeline_metrics and mad_only_metrics:
                for key in [
                    "accuracy",
                    "precision",
                    "recall",
                    "f1_score",
                    "detection_rate",
                    "avg_time_ms",
                    "avg_tokens_per_msg",
                    "total_cost_usd",
                ]:
                    deltas[key] = mad_only_metrics.get(key, 0) - pipeline_metrics.get(key, 0)

            return jsonify({
                "mad_mode": mad_mode,
                "pipeline": {
                    "available": pipeline_run is not None,
                    "eval_mode": pipeline_run.get("eval_mode") if pipeline_run else "pipeline",
                    "run_dir": pipeline_run.get("run_dir") if pipeline_run else os.path.relpath(default_pipeline_dir, project_root),
                    "timestamp": pipeline_run.get("eval_timestamp") if pipeline_run else None,
                    "files": pipeline_run.get("files") if pipeline_run else None,
                    "metrics": pipeline_metrics,
                },
                "mad_only": {
                    "available": mad_only_run is not None,
                    "eval_mode": mad_only_run.get("eval_mode") if mad_only_run else "mad_only",
                    "run_dir": mad_only_run.get("run_dir") if mad_only_run else os.path.relpath(default_mad_only_dir, project_root),
                    "timestamp": mad_only_run.get("eval_timestamp") if mad_only_run else None,
                    "files": mad_only_run.get("files") if mad_only_run else None,
                    "metrics": mad_only_metrics,
                },
                "deltas": deltas,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/evaluation/list')
    def list_evaluations():
        """List all available evaluation runs"""
        try:
            full_files = sorted(
                glob.glob(os.path.join(results_dir, "**", "eval_full_*.json"), recursive=True),
                key=os.path.getmtime,
                reverse=True
            )

            evaluations = []
            for full_path in full_files:
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        full_data = json.load(f)
                except Exception:
                    continue

                filename = os.path.basename(full_path)
                timestamp_str = filename.replace("eval_full_", "").replace(".json", "")
                evaluations.append(
                    {
                        "file": filename,
                        "timestamp": _format_eval_timestamp(timestamp_str),
                        "run_dir": os.path.relpath(os.path.dirname(full_path), project_root),
                        "mad_mode": full_data.get("mad_mode"),
                        "eval_mode": full_data.get("eval_mode", "pipeline"),
                    }
                )
            
            return jsonify(evaluations)
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/stats')
    def get_stats():
        """Get overall statistics"""
        try:
            # Get message counts by classification
            messages = db.table("messages").select("classification").execute()
            
            stats = {
                "total": len(messages.data) if messages.data else 0,
                "safe": 0,
                "suspicious": 0,
                "phishing": 0
            }
            
            if messages.data:
                for msg in messages.data:
                    classification = msg.get("classification", "").upper()
                    if classification == "SAFE":
                        stats["safe"] += 1
                    elif classification == "SUSPICIOUS":
                        stats["suspicious"] += 1
                    elif classification == "PHISHING":
                        stats["phishing"] += 1
            
            # Calculate detection rate
            if stats["total"] > 0:
                stats["detection_rate"] = round(
                    (stats["suspicious"] + stats["phishing"]) / stats["total"] * 100, 1
                )
            else:
                stats["detection_rate"] = 0
            
            return jsonify(stats)
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/stats/today')
    def get_today_stats():
        """Get today's statistics"""
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            messages = db.table("messages").select(
                "classification, timestamp"
            ).gte("timestamp", today.isoformat()).execute()
            
            stats = {
                "total": len(messages.data) if messages.data else 0,
                "safe": 0,
                "suspicious": 0,
                "phishing": 0,
                "date": today.strftime("%Y-%m-%d")
            }
            
            if messages.data:
                for msg in messages.data:
                    classification = msg.get("classification", "").upper()
                    if classification == "SAFE":
                        stats["safe"] += 1
                    elif classification == "SUSPICIOUS":
                        stats["suspicious"] += 1
                    elif classification == "PHISHING":
                        stats["phishing"] += 1
            
            return jsonify(stats)
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/detections/recent')
    def get_recent_detections():
        """Get recent detection logs"""
        try:
            logs = db.table("detection_logs").select(
                "*"
            ).order("created_at", desc=True).limit(50).execute()
            
            detections = []
            if logs.data:
                for log in logs.data:
                    stage_result = log.get("stage_result", {}) or {}
                    detections.append({
                        "id": log.get("id"),
                        "message_id": log.get("message_id"),
                        "stage": log.get("stage"),
                        "classification": stage_result.get("classification"),
                        "confidence": stage_result.get("confidence"),
                        "processing_time": log.get("processing_time_ms"),
                        "tokens": (log.get("tokens_input", 0) or 0) + (log.get("tokens_output", 0) or 0),
                        "timestamp": log.get("created_at")
                    })
            
            return jsonify(detections)
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/detections/phishing')
    def get_phishing_detections():
        """Get phishing detections only - filter from messages table"""
        try:
            messages = db.table("messages").select(
                "id, classification, confidence, decided_by, created_at"
            ).eq("classification", "PHISHING").order(
                "created_at", desc=True
            ).limit(20).execute()
            
            detections = []
            if messages.data:
                for msg in messages.data:
                    detections.append({
                        "id": msg.get("id"),
                        "message_id": msg.get("id"),
                        "stage": msg.get("decided_by", "unknown"),
                        "confidence": msg.get("confidence"),
                        "triage_flags": [],
                        "timestamp": msg.get("created_at")
                    })
            
            return jsonify(detections)
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/stats/activity')
    def get_activity_stats():
        """Get message activity distribution for a given time range.
        
        Query params:
            range: '24h' | '7d' | '30d' (default '24h')
        """
        from flask import request as req
        try:
            time_range = req.args.get('range', '24h')
            now = datetime.utcnow()
            
            if time_range == '30d':
                since = now - timedelta(days=30)
            elif time_range == '7d':
                since = now - timedelta(days=7)
            else:
                since = now - timedelta(hours=24)
                time_range = '24h'
            
            messages = db.table("messages").select(
                "timestamp, classification"
            ).gte("timestamp", since.isoformat()).execute()
            
            # Build buckets based on range
            if time_range == '24h':
                # 24 hourly buckets with real timestamps
                buckets = {}
                for i in range(24):
                    t = now - timedelta(hours=23 - i)
                    key = t.strftime("%H:00")
                    buckets[key] = {"safe": 0, "suspicious": 0, "phishing": 0}
                
                if messages.data:
                    for msg in messages.data:
                        try:
                            ts = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00")).replace(tzinfo=None)
                            key = ts.strftime("%H:00")
                            if key in buckets:
                                cls = msg.get("classification", "").upper()
                                if cls in ("SAFE", "SUSPICIOUS", "PHISHING"):
                                    buckets[key][cls.lower()] += 1
                        except:
                            pass
                
                result = [{"label": k, **v} for k, v in buckets.items()]
            
            elif time_range == '7d':
                # 7 daily buckets
                buckets = {}
                day_names = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min']
                for i in range(7):
                    t = now - timedelta(days=6 - i)
                    key = t.strftime("%Y-%m-%d")
                    label = f"{day_names[t.weekday()]} {t.strftime('%d/%m')}"
                    buckets[key] = {"label": label, "safe": 0, "suspicious": 0, "phishing": 0}
                
                if messages.data:
                    for msg in messages.data:
                        try:
                            ts = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00")).replace(tzinfo=None)
                            key = ts.strftime("%Y-%m-%d")
                            if key in buckets:
                                cls = msg.get("classification", "").upper()
                                if cls in ("SAFE", "SUSPICIOUS", "PHISHING"):
                                    buckets[key][cls.lower()] += 1
                        except:
                            pass
                
                result = [{"label": v["label"], "safe": v["safe"], "suspicious": v["suspicious"], "phishing": v["phishing"]} for v in buckets.values()]
            
            else:  # 30d
                # 30 daily buckets
                buckets = {}
                for i in range(30):
                    t = now - timedelta(days=29 - i)
                    key = t.strftime("%Y-%m-%d")
                    label = t.strftime("%d/%m")
                    buckets[key] = {"label": label, "safe": 0, "suspicious": 0, "phishing": 0}
                
                if messages.data:
                    for msg in messages.data:
                        try:
                            ts = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00")).replace(tzinfo=None)
                            key = ts.strftime("%Y-%m-%d")
                            if key in buckets:
                                cls = msg.get("classification", "").upper()
                                if cls in ("SAFE", "SUSPICIOUS", "PHISHING"):
                                    buckets[key][cls.lower()] += 1
                        except:
                            pass
                
                result = [{"label": v["label"], "safe": v["safe"], "suspicious": v["suspicious"], "phishing": v["phishing"]} for v in buckets.values()]
            
            return jsonify({"range": time_range, "data": result})
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/stats/stages')
    def get_stage_stats():
        """Get statistics by detection stage from messages table"""
        try:
            messages = db.table("messages").select(
                "decided_by, processing_time_ms"
            ).execute()
            
            stages = {
                "triage": {"count": 0, "tokens": 0, "time": 0},
                "single_shot": {"count": 0, "tokens": 0, "time": 0},
                "mad": {"count": 0, "tokens": 0, "time": 0}
            }
            
            if messages.data:
                for msg in messages.data:
                    stage = msg.get("decided_by", "")
                    if stage in stages:
                        stages[stage]["count"] += 1
                        stages[stage]["time"] += msg.get("processing_time_ms", 0) or 0
            
            # Get token usage from detection_logs
            logs = db.table("detection_logs").select(
                "stage, tokens_input, tokens_output"
            ).execute()
            
            if logs.data:
                for log in logs.data:
                    stage = log.get("stage", "")
                    if stage in stages:
                        tokens = (log.get("tokens_input", 0) or 0) + (log.get("tokens_output", 0) or 0)
                        stages[stage]["tokens"] += tokens
            
            # Calculate averages
            for stage in stages:
                if stages[stage]["count"] > 0:
                    stages[stage]["avg_tokens"] = round(
                        stages[stage]["tokens"] / stages[stage]["count"]
                    )
                    stages[stage]["avg_time"] = round(
                        stages[stage]["time"] / stages[stage]["count"]
                    )
                else:
                    stages[stage]["avg_tokens"] = 0
                    stages[stage]["avg_time"] = 0
            
            return jsonify(stages)
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/usage')
    def get_api_usage():
        """Get inference activity statistics (tokens/requests/stage breakdown)."""
        
        try:
            # Try api_usage table first
            usage = db.table("api_usage").select("*").order(
                "date", desc=True
            ).limit(100).execute()
            
            total_tokens_in = 0
            total_tokens_out = 0
            total_cost_legacy = 0
            total_requests = 0
            stage_breakdown = {
                "triage": {"requests": 0, "tokens": 0},
                "single_shot": {"requests": 0, "tokens": 0},
                "mad": {"requests": 0, "tokens": 0}
            }
            daily_records = []
            
            if usage.data and len(usage.data) > 0:
                for record in usage.data:
                    tokens_in = record.get("total_tokens_input", 0) or 0
                    tokens_out = record.get("total_tokens_output", 0) or 0
                    cost_legacy = float(record.get("estimated_cost_usd", 0) or 0)
                    requests = record.get("total_requests", 0) or 0
                    
                    total_tokens_in += tokens_in
                    total_tokens_out += tokens_out
                    total_cost_legacy += cost_legacy
                    total_requests += requests
                    
                    # Accumulate stage breakdown
                    stage_breakdown["triage"]["requests"] += record.get("triage_requests", 0) or 0
                    stage_breakdown["single_shot"]["requests"] += record.get("single_shot_requests", 0) or 0
                    stage_breakdown["single_shot"]["tokens"] += record.get("single_shot_tokens", 0) or 0
                    stage_breakdown["mad"]["requests"] += record.get("mad_requests", 0) or 0
                    stage_breakdown["mad"]["tokens"] += record.get("mad_tokens", 0) or 0
                    
                    daily_records.append({
                        "date": record.get("date", ""),
                        "tokens_input": tokens_in,
                        "tokens_output": tokens_out,
                        "cost_legacy": round(cost_legacy, 6),
                        "requests": requests
                    })
            else:
                # Fallback: aggregate from detection_logs if api_usage is empty
                logs = db.table("detection_logs").select(
                    "stage, tokens_input, tokens_output"
                ).limit(1000).execute()
                
                if logs.data:
                    for log in logs.data:
                        t_in = log.get("tokens_input", 0) or 0
                        t_out = log.get("tokens_output", 0) or 0
                        stage = log.get("stage", "")
                        total_tokens_in += t_in
                        total_tokens_out += t_out
                        
                        if stage in stage_breakdown:
                            stage_breakdown[stage]["requests"] += 1
                            stage_breakdown[stage]["tokens"] += t_in + t_out
                    
                    total_requests = len(logs.data)
            
            return jsonify({
                "total_tokens": total_tokens_in + total_tokens_out,
                "tokens_input": total_tokens_in,
                "tokens_output": total_tokens_out,
                "total_cost_legacy": round(total_cost_legacy, 6),
                "total_requests": total_requests,
                "stage_breakdown": stage_breakdown,
                "daily_records": daily_records[:30],
                "pricing_legacy": None
            })
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/debates/recent')
    def get_recent_debates():
        """Get recent MAD debates with agent conversations"""
        try:
            # Get detection logs where stage is 'mad'
            logs = db.table("detection_logs").select(
                "id, message_id, stage, stage_result, processing_time_ms, created_at"
            ).eq("stage", "mad").order("created_at", desc=True).limit(10).execute()
            
            debates = []
            if logs.data:
                for log in logs.data:
                    stage_result = log.get("stage_result", {}) or {}
                    mad_result = stage_result.get("mad", {}) or {}
                    
                    # Extract agent conversations from MAD result
                    debate_data = {
                        "id": log.get("id"),
                        "message_id": log.get("message_id"),
                        "timestamp": log.get("created_at"),
                        "decision": mad_result.get("decision", "UNKNOWN"),
                        "confidence": mad_result.get("confidence", 0),
                        "rounds_executed": mad_result.get("rounds_executed", 0),
                        "consensus_reached": mad_result.get("consensus_reached", False),
                        "consensus_type": mad_result.get("consensus_type", ""),
                        "agent_votes": mad_result.get("agent_votes", {}),
                        "round_1": [],
                        "round_2": []
                    }
                    
                    # Extract round 1 summaries
                    round_1 = mad_result.get("round_1_summary", [])
                    if round_1:
                        for agent in round_1:
                            debate_data["round_1"].append({
                                "agent": agent.get("agent_type", "unknown"),
                                "stance": agent.get("stance", "UNKNOWN"),
                                "confidence": agent.get("confidence", 0),
                                "arguments": agent.get("key_arguments", [])
                            })
                    
                    # Extract round 2 summaries if exists
                    round_2 = mad_result.get("round_2_summary", [])
                    if round_2:
                        for agent in round_2:
                            debate_data["round_2"].append({
                                "agent": agent.get("agent_type", "unknown"),
                                "stance": agent.get("stance", "UNKNOWN"),
                                "confidence": agent.get("confidence", 0),
                                "arguments": agent.get("key_arguments", [])
                            })
                    
                    debates.append(debate_data)
            
            return jsonify(debates)
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/debate/<int:debate_id>')
    def get_debate_detail(debate_id):
        """Get detailed debate information"""
        try:
            log = db.table("detection_logs").select(
                "*"
            ).eq("id", debate_id).execute()
            
            if not log.data:
                return jsonify({"error": "Debate not found"}), 404
            
            log_data = log.data[0]
            stage_result = log_data.get("stage_result", {}) or {}
            
            # Get associated message content
            message_id = log_data.get("message_id")
            message_content = ""
            if message_id:
                msg = db.table("messages").select("content").eq("id", message_id).execute()
                if msg.data:
                    message_content = msg.data[0].get("content", "")
            
            return jsonify({
                "id": log_data.get("id"),
                "message_id": message_id,
                "message_content": message_content[:500] if message_content else "",
                "stage": log_data.get("stage"),
                "triage": stage_result.get("triage"),
                "single_shot": stage_result.get("single_shot"),
                "mad": stage_result.get("mad"),
                "processing_time_ms": log_data.get("processing_time_ms"),
                "timestamp": log_data.get("created_at")
            })
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/messages/recent')
    def get_recent_messages():
        """Get recent processed messages"""
        try:
            messages = db.table("messages").select(
                "telegram_message_id, content, classification, confidence, timestamp"
            ).order("timestamp", desc=True).limit(20).execute()
            
            result = []
            if messages.data:
                for msg in messages.data:
                    content = msg.get("content", "") or ""
                    result.append({
                        "message_id": msg.get("telegram_message_id"),
                        "content": content[:100] + "..." if len(content) > 100 else content,
                        "classification": msg.get("classification"),
                        "confidence": msg.get("confidence"),
                        "timestamp": msg.get("timestamp")
                    })
            
            return jsonify(result)
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return app


def run_dashboard(host="0.0.0.0", port=5000, debug=False):
    """Run dashboard server with automatic fallback ports on bind failure."""
    app = create_app()
    fallback_ports = [5001, 5050, 8000, 8080]
    candidate_ports: list[int] = []

    for candidate in [port, *fallback_ports]:
        if candidate not in candidate_ports:
            candidate_ports.append(candidate)

    last_error: Exception | None = None

    for selected_port in candidate_ports:
        try:
            print(f"\n🌐 Dashboard running at http://{host}:{selected_port}")
            print("   Press Ctrl+C to stop\n")
            app.run(host=host, port=selected_port, debug=debug)
            return
        except OSError as exc:
            last_error = exc
            err_text = str(exc).lower()
            winerror = getattr(exc, "winerror", None)

            is_blocked = winerror == 10013 or "forbidden by its access permissions" in err_text
            is_in_use = winerror == 10048 or "address already in use" in err_text

            if is_blocked or is_in_use:
                reason = "forbidden" if is_blocked else "already in use"
                print(f"⚠️  Port {selected_port} {reason}, trying next port...")
                continue
            raise

    if last_error:
        raise last_error


if __name__ == "__main__":
    run_dashboard(debug=True)
