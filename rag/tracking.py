"""Optional MLflow tracking for the RAG evaluation.

MLflow is an optional dependency: nothing here is imported unless you run
`python -m rag.eval --mlflow`, so the web app and the test suite never need it.

    uv sync --extra tracking
    uv run python -m rag.eval --mlflow
    uv run mlflow ui --backend-store-uri sqlite:///mlflow.db     # http://127.0.0.1:5000

Each evaluation becomes one run holding:
* params   - embedding model, dataset size and hash, index size, git commit
* metrics  - headline and per-slice Hit/Recall/Precision/nDCG/MRR, filter
             integrity, duplicates and the out-of-scope distance calibration
* artifact - the full JSON report (every case, with expected vs retrieved ids)
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from rag.config import BASE_DIR

DEFAULT_EXPERIMENT = "rehlaguide-rag-eval"
DEFAULT_TRACKING_URI = f"sqlite:///{(BASE_DIR / 'mlflow.db').as_posix()}"


def mlflow_available() -> bool:
    try:
        import mlflow  # noqa: F401
    except ImportError:
        return False
    return True


def resolve_tracking_uri(explicit: Optional[str] = None) -> str:
    """--tracking-uri wins, then MLFLOW_TRACKING_URI, then a local SQLite file."""
    return explicit or os.getenv("MLFLOW_TRACKING_URI", "").strip() or DEFAULT_TRACKING_URI


def metric_name(*parts: str) -> str:
    """MLflow metric keys allow letters, digits, _ - . space : /, so `hit@3` becomes `hit_at_3`."""
    joined = ".".join(parts).replace("@", "_at_")
    return re.sub(r"[^A-Za-z0-9_\-. :/]", "_", joined)


def dataset_fingerprint(dataset: Any) -> str:
    """Short stable hash of the labelled dataset, to tell whether two runs are comparable."""
    blob = json.dumps(dataset, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def git_commit() -> Optional[str]:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR,
                             capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def flatten_metrics(summary: Dict[str, Any], health: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """Turn the eval summary into the flat {name: number} dict MLflow expects."""
    metrics: Dict[str, float] = {}
    for key, value in summary.get("headline", {}).items():
        metrics[metric_name("headline", key)] = float(value)
    for slice_name, values in summary.get("by_type", {}).items():
        for key, value in values.items():
            if key == "n":
                metrics[metric_name("slice", slice_name, "n")] = float(value)
            else:
                metrics[metric_name("slice", slice_name, key)] = float(value)
    metrics["filter_violations"] = float(summary.get("filter_violations", 0))
    metrics["cases_with_duplicates"] = float(summary.get("cases_with_duplicates", 0))
    for key, value in summary.get("distance", {}).items():
        if value is not None:  # None when a slice is empty
            metrics[metric_name("distance", key)] = float(value)
    if health is not None:
        metrics["index_healthy"] = 1.0 if health.get("healthy") else 0.0
        metrics["index_rows"] = float(health.get("indexed_rows", 0))
    return metrics


def build_params(report: Dict[str, Any]) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "embedding_model": report.get("embedding_model"),
        "dataset_size": report.get("dataset_size"),
        "dataset_hash": report.get("dataset_hash"),
        "headline_n": report.get("summary", {}).get("headline_n"),
    }
    health = report.get("index_health")
    if health:
        params["raw_attractions"] = health.get("raw_attractions")
    return {k: v for k, v in params.items() if v is not None}


def log_eval_run(report: Dict[str, Any], experiment: str = DEFAULT_EXPERIMENT,
                 run_name: Optional[str] = None,
                 tracking_uri: Optional[str] = None) -> str:
    """Log one evaluation report as an MLflow run and return the run id."""
    import mlflow

    mlflow.set_tracking_uri(resolve_tracking_uri(tracking_uri))
    mlflow.set_experiment(experiment)
    name = run_name or f"{report.get('embedding_model', 'model')}"
    with mlflow.start_run(run_name=name) as run:
        mlflow.log_params(build_params(report))
        commit = git_commit()
        if commit:
            mlflow.set_tag("git_commit", commit)
        mlflow.log_metrics(flatten_metrics(report.get("summary", {}), report.get("index_health")))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "eval_report.json"
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            mlflow.log_artifact(str(path))
        return run.info.run_id
