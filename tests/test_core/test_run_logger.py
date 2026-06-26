"""
RunLogger utility tests.
"""
import json
from pathlib import Path

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


def _make_run(run_id: str, workflow: str, started_at: str) -> RunLog:
    return RunLog(
        run_id=run_id,
        workflow=workflow,
        status="success",
        started_at=started_at,
        ended_at=started_at,
    )


def test_get_all_runs_returns_newest_first(temp_dir):
    runs_dir = temp_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_logger = RunLogger(runs_dir)

    _write_jsonl(
        runs_dir / "20260110.jsonl",
        [
            _make_run("r1", "A", "2026-01-10T08:00:00"),
            _make_run("r2", "A", "2026-01-10T09:00:00"),
        ],
    )
    _write_jsonl(
        runs_dir / "20260111.jsonl",
        [_make_run("r3", "B", "2026-01-11T08:00:00")],
    )

    result = run_logger.get_all_runs(limit=10, offset=0)

    assert [r.run_id for r in result] == ["r3", "r2", "r1"]


def test_get_all_runs_pagination_offset_and_limit(temp_dir):
    runs_dir = temp_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_logger = RunLogger(runs_dir)

    _write_jsonl(
        runs_dir / "20260110.jsonl",
        [_make_run(f"r{i}", "A", f"2026-01-10T08:{i:02d}:00") for i in range(5)],
    )

    # 新しい順: r4, r3, r2, r1, r0
    page2 = run_logger.get_all_runs(limit=2, offset=2)
    assert [r.run_id for r in page2] == ["r2", "r1"]


def test_get_all_runs_filters_by_workflow(temp_dir):
    runs_dir = temp_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_logger = RunLogger(runs_dir)

    _write_jsonl(
        runs_dir / "20260110.jsonl",
        [
            _make_run("a1", "A", "2026-01-10T08:00:00"),
            _make_run("b1", "B", "2026-01-10T09:00:00"),
            _make_run("a2", "A", "2026-01-10T10:00:00"),
        ],
    )

    result = run_logger.get_all_runs(limit=10, offset=0, workflow_filter="A")

    assert [r.run_id for r in result] == ["a2", "a1"]


def test_get_all_runs_does_not_read_older_files_when_satisfied(temp_dir):
    """必要件数が新しいファイルだけで揃うなら、古いファイルは開かない（遅延読み込み）。"""
    runs_dir = temp_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_logger = RunLogger(runs_dir)

    older = runs_dir / "20260110.jsonl"
    newer = runs_dir / "20260111.jsonl"
    _write_jsonl(older, [_make_run("old1", "A", "2026-01-10T08:00:00")])
    _write_jsonl(
        newer,
        [_make_run(f"new{i}", "A", f"2026-01-11T08:{i:02d}:00") for i in range(3)],
    )

    opened: list[str] = []
    original_open = Path.open

    def tracking_open(self, *args, **kwargs):
        if self.suffix == ".jsonl":
            opened.append(self.name)
        return original_open(self, *args, **kwargs)

    import unittest.mock as mock

    with mock.patch.object(Path, "open", tracking_open):
        result = run_logger.get_all_runs(limit=2, offset=0)

    assert [r.run_id for r in result] == ["new2", "new1"]
    assert "20260110.jsonl" not in opened, f"古いファイルを開いた: {opened}"


def test_count_all_runs_counts_lines(temp_dir):
    runs_dir = temp_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_logger = RunLogger(runs_dir)

    _write_jsonl(
        runs_dir / "20260110.jsonl",
        [_make_run("a1", "A", "2026-01-10T08:00:00"),
         _make_run("b1", "B", "2026-01-10T09:00:00")],
    )
    _write_jsonl(
        runs_dir / "20260111.jsonl",
        [_make_run("a2", "A", "2026-01-11T08:00:00")],
    )

    assert run_logger.count_all_runs() == 3
    assert run_logger.count_all_runs(workflow_filter="A") == 2


def test_count_all_runs_does_not_validate(temp_dir):
    """件数カウントは Pydantic 検証をしない（不正行があっても件数は数えられる方向）。

    フィルタなしのカウントは行数だけ数えるため、検証エラーで落ちない。
    """
    runs_dir = temp_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_logger = RunLogger(runs_dir)

    (runs_dir / "20260110.jsonl").write_text(
        '{"run_id": "ok", "workflow": "A", "status": "success", '
        '"started_at": "2026-01-10T08:00:00"}\n'
        '{"this_is": "garbage but still a line"}\n'
        "\n",  # 空行はカウントしない
        encoding="utf-8",
    )

    assert run_logger.count_all_runs() == 2
