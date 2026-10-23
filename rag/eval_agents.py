"""Agent/orchestration evaluation for RehlaGuide/Fosha.

Run from the repository root:
    uv run python -m rag.eval_agents --validate
    uv run python -m rag.eval_agents --json agent_eval_report.json
    uv run python -m rag.eval_agents --mlflow --json agent_eval_report.json

This suite evaluates planner routing, retrieval-tool invocation, task completion,
and graceful handling of a retrieval-tool failure. It is intentionally separate
from `rag.eval` (retrieval ranking) and `rag.eval_answers` (final answer quality).
The live cases call the configured LLM and the local retrieval index.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.planner import plan_trip
from rag.config import EMBEDDING_MODEL_NAME

# These are orchestration tests, not a second retrieval relevance dataset.
# The expected values describe planner behavior, not the exact wording of its reply.
DATASET: List[Dict[str, Any]] = [
    {
        "id": "en-luxor-two-days",
        "language": "en",
        "question": "Plan a two-day trip in Luxor focused on ancient Egyptian temples.",
        "expected_status": "planned", "expected_task": "plan_trip",
        "expected_region": "Luxor", "expected_days": 2, "requires_retrieval": True,
    },
    {
        "id": "ar-luxor-two-days",
        "language": "ar",
        "question": "عايز برنامج يومين في الأقصر يركز على المعابد المصرية القديمة.",
        "expected_status": "planned", "expected_task": "plan_trip",
        "expected_region": "Luxor", "expected_days": 2, "requires_retrieval": True,
    },
    {
        "id": "en-cairo-one-day",
        "language": "en",
        "question": "Plan one day in Cairo focused on museums and cultural history.",
        "expected_status": "planned", "expected_task": "plan_trip",
        "expected_region": "Cairo", "expected_days": 1, "requires_retrieval": True,
    },
    {
        "id": "ar-aswan-three-days",
        "language": "ar",
        "question": "اعمل لي برنامج ٣ أيام في أسوان يهتم بالثقافة النوبية والأماكن التاريخية.",
        "expected_status": "planned", "expected_task": "plan_trip",
        "expected_region": "Aswan", "expected_days": 3, "requires_retrieval": True,
    },
    {
        "id": "en-missing-duration",
        "language": "en",
        "question": "I want to visit Luxor and see ancient temples.",
        "expected_status": "needs_clarification", "expected_task": "plan_trip",
        "expected_region": "Luxor", "expected_days": None, "requires_retrieval": False,
    },
    {
        "id": "ar-missing-destination",
        "language": "ar",
        "question": "عايز أعمل رحلة لمدة يومين، ممكن تساعدني؟",
        "expected_status": "needs_clarification", "expected_task": "plan_trip",
        "expected_region": None, "expected_days": 2, "requires_retrieval": False,
    },
    {
        "id": "en-out-of-scope",
        "language": "en",
        "question": "Explain how photosynthesis works in plants.",
        "expected_status": "out_of_scope", "expected_task": "other",
        "expected_region": None, "expected_days": None, "requires_retrieval": False,
    },
    {
        "id": "ar-out-of-scope",
        "language": "ar",
        "question": "اشرح لي الفرق بين الانحدار الخطي والانحدار اللوجستي في تعلم الآلة.",
        "expected_status": "out_of_scope", "expected_task": "other",
        "expected_region": None, "expected_days": None, "requires_retrieval": False,
    },
]


def validate_dataset(dataset: List[Dict[str, Any]] = DATASET) -> List[str]:
    errors: List[str] = []
    ids = [case.get("id") for case in dataset]
    if len(ids) != len(set(ids)):
        errors.append("case ids must be unique")
    required = ("id", "language", "question", "expected_status", "expected_task", "requires_retrieval")
    for index, case in enumerate(dataset, start=1):
        for key in required:
            if key not in case:
                errors.append(f"case #{index} missing {key}")
        if not str(case.get("question", "")).strip():
            errors.append(f"case {case.get('id', index)} has an empty question")
        if case.get("expected_status") == "planned":
            if not case.get("expected_region") or not case.get("expected_days"):
                errors.append(f"{case.get('id')}: planned cases need expected_region and expected_days")
            if not case.get("requires_retrieval"):
                errors.append(f"{case.get('id')}: planned cases must require retrieval")
    return errors


def _region_matches(expected: Optional[str], actual: Any) -> bool:
    if expected is None:
        return actual in (None, "")
    if not actual:
        return False
    # Cairo is represented as Cairo by intent extraction; retrieval expands it to Cairo + Giza.
    return str(actual).strip().casefold() == expected.casefold()


def _intent_matches(case: Dict[str, Any], intent: Dict[str, Any]) -> bool:
    if intent.get("task") != case["expected_task"]:
        return False
    if "expected_region" in case and not _region_matches(case.get("expected_region"), intent.get("region")):
        return False
    if "expected_days" in case and intent.get("days") != case.get("expected_days"):
        return False
    if intent.get("language") != case.get("language"):
        return False
    return True


def _itinerary_complete(result: Dict[str, Any], expected_days: Optional[int]) -> bool:
    itinerary = result.get("itinerary")
    if not isinstance(itinerary, dict):
        return False
    days = itinerary.get("days")
    if not isinstance(days, list) or not days:
        return False
    if expected_days is not None and len(days) != expected_days:
        return False
    return all(isinstance(day, dict) and bool(day.get("stops")) for day in days)


def _tracked_search(calls: List[Dict[str, Any]], fail: bool = False):
    """Return a low-level retriever wrapper that records actual tool calls."""
    from rag.retriever import search_attractions as real_search

    def search(**kwargs):
        record: Dict[str, Any] = {
            "query_chars": len(str(kwargs.get("query", ""))),
            "region": kwargs.get("region"),
            "category": kwargs.get("category"),
            "top_k": kwargs.get("top_k"),
            "ok": False,
            "result_count": 0,
            "error": None,
        }
        calls.append(record)
        if fail:
            record["error"] = "Injected retrieval failure for agent error-handling check"
            raise RuntimeError(record["error"])
        try:
            hits = real_search(**kwargs)
            record["ok"] = isinstance(hits, list)
            record["result_count"] = len(hits) if isinstance(hits, list) else 0
            if not isinstance(hits, list):
                record["error"] = "Retriever returned a non-list result"
            return hits
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            raise
    return search


def run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    calls: List[Dict[str, Any]] = []
    try:
        result = plan_trip(case["question"], search_fn=_tracked_search(calls))
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    intent = result.get("intent") if isinstance(result.get("intent"), dict) else {}
    status_correct = result.get("status") == case["expected_status"]
    intent_correct = _intent_matches(case, intent)
    called_retrieval = len(calls) > 0
    tool_usage_correct = called_retrieval == bool(case["requires_retrieval"])
    successful_calls = sum(bool(call["ok"]) for call in calls)
    failed_calls = len(calls) - successful_calls

    if case["expected_status"] == "planned":
        task_completed = status_correct and _itinerary_complete(result, case.get("expected_days"))
    elif case["expected_status"] == "needs_clarification":
        task_completed = status_correct and bool(result.get("reply")) and not called_retrieval
    elif case["expected_status"] == "out_of_scope":
        task_completed = status_correct and bool(result.get("reply")) and not called_retrieval
    else:
        task_completed = status_correct

    return {
        "id": case["id"], "language": case["language"], "question": case["question"],
        "expected_status": case["expected_status"], "actual_status": result.get("status"),
        "expected_task": case["expected_task"], "actual_task": intent.get("task"),
        "expected_region": case.get("expected_region"), "actual_region": intent.get("region"),
        "expected_days": case.get("expected_days"), "actual_days": intent.get("days"),
        "pipeline_ok": bool(result.get("ok")), "pipeline_error": result.get("error"),
        "status_correct": status_correct, "intent_correct": intent_correct,
        "routing_correct": status_correct and intent_correct,
        "requires_retrieval": bool(case["requires_retrieval"]),
        "retrieval_called": called_retrieval, "tool_usage_correct": tool_usage_correct,
        "tool_calls": calls, "tool_calls_total": len(calls),
        "tool_calls_successful": successful_calls, "tool_calls_failed": failed_calls,
        "itinerary_complete": _itinerary_complete(result, case.get("expected_days")),
        "task_completed": task_completed,
        "reply": result.get("reply", ""),
    }


def run_error_handling_check() -> Dict[str, Any]:
    """Verify a retrieval-tool failure is returned as a controlled pipeline error.

    Intent extraction still uses the configured LLM; the retrieval failure itself is injected.
    """
    calls: List[Dict[str, Any]] = []
    question = "Plan one day in Luxor focused on ancient temples."
    try:
        result = plan_trip(question, search_fn=_tracked_search(calls, fail=True))
    except Exception as exc:
        result = {"ok": False, "error": f"Unhandled exception: {type(exc).__name__}: {exc}"}
    passed = (not result.get("ok") and bool(result.get("error")) and bool(calls)
              and calls[0].get("error") is not None)
    return {
        "question": question, "injected_failure": "retrieval tool raises RuntimeError",
        "passed": passed, "pipeline_ok": bool(result.get("ok")),
        "error": result.get("error"), "tool_calls": calls,
    }


def _rate(rows: List[Dict[str, Any]], key: str) -> float:
    return sum(bool(row.get(key)) for row in rows) / len(rows) if rows else 0.0


def summarize(rows: List[Dict[str, Any]], error_check: Dict[str, Any]) -> Dict[str, Any]:
    total_calls = sum(row["tool_calls_total"] for row in rows)
    successful_calls = sum(row["tool_calls_successful"] for row in rows)
    failed_calls = sum(row["tool_calls_failed"] for row in rows)
    planned = [row for row in rows if row["expected_status"] == "planned"]
    summary: Dict[str, Any] = {
        "dataset_size": len(rows),
        "routing_accuracy": _rate(rows, "routing_correct"),
        "intent_accuracy": _rate(rows, "intent_correct"),
        "status_accuracy": _rate(rows, "status_correct"),
        "tool_selection_accuracy": _rate(rows, "tool_usage_correct"),
        "tool_success_rate": successful_calls / total_calls if total_calls else 1.0,
        "tool_calls_total": total_calls,
        "tool_calls_successful": successful_calls,
        "tool_calls_failed": failed_calls,
        "task_completion_rate": _rate(rows, "task_completed"),
        "planned_itinerary_completion_rate": _rate(planned, "itinerary_complete"),
        "pipeline_success_rate": _rate(rows, "pipeline_ok"),
        "error_handling_pass": 1.0 if error_check.get("passed") else 0.0,
        "error_handling_test_count": 1,
    }
    summary["by_language"] = {}
    for language in sorted({row["language"] for row in rows}):
        subset = [row for row in rows if row["language"] == language]
        summary["by_language"][language] = {
            "n": len(subset),
            "routing_accuracy": _rate(subset, "routing_correct"),
            "intent_accuracy": _rate(subset, "intent_correct"),
            "task_completion_rate": _rate(subset, "task_completed"),
        }
    return summary


def log_mlflow(report: Dict[str, Any], experiment: str, run_name: Optional[str] = None,
               tracking_uri: Optional[str] = None) -> str:
    import mlflow
    from rag.tracking import dataset_fingerprint, git_commit, resolve_tracking_uri

    mlflow.set_tracking_uri(resolve_tracking_uri(tracking_uri))
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=run_name or "agent-eval") as run:
        mlflow.log_params({
            "evaluation_type": "agent_orchestration",
            "dataset_size": len(DATASET),
            "dataset_hash": dataset_fingerprint(DATASET),
            "embedding_model": EMBEDDING_MODEL_NAME,
        })
        commit = git_commit()
        if commit:
            mlflow.set_tag("git_commit", commit)
        for key, value in report["summary"].items():
            if isinstance(value, (int, float)) and value is not None:
                mlflow.log_metric(key, float(value))
        for language, metrics in report["summary"].get("by_language", {}).items():
            for key, value in metrics.items():
                if isinstance(value, (int, float)) and value is not None:
                    mlflow.log_metric(f"by_language.{language}.{key}", float(value))
        for case in report["cases"]:
            case_id = "".join(c if c.isalnum() or c in "_-" else "_" for c in case["id"])
            for key in ("routing_correct", "intent_correct", "status_correct", "tool_usage_correct",
                        "task_completed", "pipeline_ok", "itinerary_complete"):
                mlflow.log_metric(f"case.{case_id}.{key}", float(bool(case.get(key))))
            mlflow.log_metric(f"case.{case_id}.tool_calls_total", float(case["tool_calls_total"]))
            mlflow.log_metric(f"case.{case_id}.tool_calls_failed", float(case["tool_calls_failed"]))
            mlflow.set_tag(f"case.{case_id}.language", case["language"])
            mlflow.set_tag(f"case.{case_id}.expected_status", case["expected_status"])
            mlflow.set_tag(f"case.{case_id}.actual_status", str(case.get("actual_status") or "none"))
        mlflow.log_metric("error_handling.injected_retrieval_failure_pass", float(report["error_handling"]["passed"]))
        mlflow.set_tag("evaluation", "agent_orchestration")
        with __import__("tempfile").TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "agent_eval_report.json"
            artifact.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            mlflow.log_artifact(str(artifact))
        return run.info.run_id


def evaluate(json_path: Optional[str] = None,
             mlflow_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    errors = validate_dataset()
    if errors:
        raise SystemExit("Agent evaluation dataset is invalid:\n  " + "\n  ".join(errors))
    if mlflow_options is not None:
        try:
            import mlflow  # noqa: F401
        except ImportError as exc:
            raise SystemExit("MLflow is not installed. Run: uv sync --extra tracking") from exc

    print("RehlaGuide/Fosha — agent/orchestration evaluation")
    print(f"Cases: {len(DATASET)} | This suite measures routing, tool use, and task completion.")
    rows: List[Dict[str, Any]] = []
    for index, case in enumerate(DATASET, start=1):
        print(f"[{index}/{len(DATASET)}] {case['id']}: {case['question']}", flush=True)
        row = run_case(case)
        rows.append(row)
        print(f"  status={row['actual_status']} | route={row['routing_correct']} | "
              f"tool_calls={row['tool_calls_total']} | completed={row['task_completed']}")
    error_check = run_error_handling_check()
    summary = summarize(rows, error_check)
    report = {
        "evaluation": "agent_orchestration",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_size": len(DATASET), "embedding_model": EMBEDDING_MODEL_NAME,
        "summary": summary, "cases": rows, "error_handling": error_check,
        "limitations": [
            "Routing labels are hand-authored expected behaviors; review failures before changing prompts.",
            "Tool success measures the low-level retrieval call completing, not whether its ranking is relevant; see rag.eval for retrieval quality.",
            "Task completion is a structural check (status, day count, and non-empty stops), not a human quality judgment; see rag.eval_answers for answer quality.",
            "The live cases and injected-error check make real intent-extraction LLM calls and may consume API quota.",
        ],
    }
    print("\nSummary")
    for key in ("routing_accuracy", "intent_accuracy", "status_accuracy", "tool_selection_accuracy",
                "tool_success_rate", "task_completion_rate", "planned_itinerary_completion_rate",
                "pipeline_success_rate", "error_handling_pass"):
        print(f"  {key}: {summary[key]:.1%}")
    if json_path:
        Path(json_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved JSON report to {json_path}")
    if mlflow_options is not None:
        run_id = log_mlflow(report, **mlflow_options)
        from rag.tracking import resolve_tracking_uri
        print(f"Logged MLflow run {run_id}; tracking URI: {resolve_tracking_uri(mlflow_options.get('tracking_uri'))}")
    return report


def ensure_utf8_output(stream: Any = None) -> None:
    stream = stream if stream is not None else sys.stdout
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    ensure_utf8_output()
    parser = argparse.ArgumentParser(description="Evaluate RehlaGuide/Fosha agent orchestration.")
    parser.add_argument("--validate", action="store_true", help="validate test cases without model or DB calls")
    parser.add_argument("--json", metavar="PATH", help="save a machine-readable report")
    parser.add_argument("--mlflow", action="store_true", help="log agent metrics and report to MLflow")
    parser.add_argument("--experiment", default="rehlaguide-agent-eval", help="MLflow experiment name")
    parser.add_argument("--run-name", default=None, help="MLflow run name")
    parser.add_argument("--tracking-uri", default=None, help="MLflow tracking URI")
    args = parser.parse_args()
    if args.validate:
        issues = validate_dataset()
        if issues:
            raise SystemExit("Dataset problems:\n  " + "\n  ".join(issues))
        print(f"Dataset OK: {len(DATASET)} agent cases; no model or database calls made.")
    else:
        options = ({"experiment": args.experiment, "run_name": args.run_name, "tracking_uri": args.tracking_uri}
                   if args.mlflow else None)
        evaluate(json_path=args.json, mlflow_options=options)
