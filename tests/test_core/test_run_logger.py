"""
RunLogger utility tests.
"""
import json

from src.app.core.models import RunLog
from src.app.core.run_logger import RunLogger


def _write_jsonl(path, runs: list[RunLog]) -> None:
    lines = [json.dumps(run.model_dump(), ensure_ascii=False) for run in runs]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_get_latest_runs_map_picks_latest(temp_dir):
    runs_dir = temp_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_logger = RunLogger(runs_dir)

    older = runs_dir / "20260110.jsonl"
    newer = runs_dir / "20260111.jsonl"

    run_a_old = RunLog(
        run_id="a_old",
        workflow="A",
        status="success",
        started_at="2026-01-10T08:00:00",
        ended_at="2026-01-10T08:01:00",
    )
    run_b_old = RunLog(
        run_id="b_old",
        workflow="B",
        status="failed",
        started_at="2026-01-10T09:00:00",
        ended_at="2026-01-10T09:01:00",
    )
    run_b_new = RunLog(
        run_id="b_new",
        workflow="B",
        status="success",
        started_at="2026-01-10T10:00:00",
        ended_at="2026-01-10T10:01:00",
    )
    _write_jsonl(older, [run_a_old, run_b_old, run_b_new])

    run_a_new = RunLog(
        run_id="a_new",
        workflow="A",
        status="success",
        started_at="2026-01-11T08:00:00",
        ended_at="2026-01-11T08:01:00",
    )
    _write_jsonl(newer, [run_a_new])

    result = run_logger.get_latest_runs_map({"A", "B", "C"})

    assert result["A"].run_id == "a_new"
    assert result["B"].run_id == "b_new"
    assert "C" not in result


def test_get_latest_runs_map_empty_returns_empty(temp_dir):
    runs_dir = temp_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_logger = RunLogger(runs_dir)

    assert run_logger.get_latest_runs_map(set()) == {}
