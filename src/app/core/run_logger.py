"""
ORBIT MVP - Run Logger
実行ログの JSONL ファイル管理
"""
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .models import RunLog

logger = logging.getLogger(__name__)

# 日本時間
JST = timezone(timedelta(hours=9))


class RunLogger:
    """実行ログ管理"""

    def __init__(self, runs_dir: Path):
        self.runs_dir = runs_dir
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_file(self, date: datetime | None = None) -> Path:
        """日付ごとのログファイルパスを取得"""
        if date is None:
            date = datetime.now(JST)
        filename = f"{date.strftime('%Y%m%d')}.jsonl"
        return self.runs_dir / filename

    def save(self, run_log: RunLog) -> None:
        """実行ログを JSONL に追記"""
        log_file = self._get_log_file()

        log_data = run_log.model_dump()
        log_line = json.dumps(log_data, ensure_ascii=False)

        with log_file.open("a", encoding="utf-8") as f:
            f.write(log_line + "\n")

        logger.debug(f"Run log saved: {run_log.run_id} -> {log_file}")

    def get_runs_for_workflow(self, workflow_name: str, limit: int = 50, offset: int = 0) -> list[RunLog]:
        """特定ワークフローの実行履歴を取得（新しい順）

        Args:
            workflow_name: ワークフロー名
            limit: 取得件数（デフォルト: 50）
            offset: オフセット（デフォルト: 0）
        """
        return self.get_all_runs(limit=limit, offset=offset, workflow_filter=workflow_name)

    def get_all_runs(self, limit: int = 50, offset: int = 0, workflow_filter: str | None = None) -> list[RunLog]:
        """実行履歴を取得（新しい順）

        ログファイルは `YYYYMMDD.jsonl`（日付降順＝新しい順）で、各ファイル内も
        追記＝時系列順。新しいファイルから順に必要件数（offset+limit）が揃うまで
        だけ読み、それ以降の古いファイルは開かない（遅延読み込み）。

        Args:
            limit: 取得件数（デフォルト: 50）
            offset: オフセット（デフォルト: 0）
            workflow_filter: フィルタするワークフロー名（オプション）
        """
        needed = offset + limit
        runs: list[RunLog] = []

        log_files = sorted(self.runs_dir.glob("*.jsonl"), reverse=True)

        for log_file in log_files:
            file_runs = self._read_log_file(log_file, workflow_filter)
            # ファイル内は追記＝古い→新しい順なので、新しい順に並べ替える
            file_runs.sort(key=lambda x: x.started_at, reverse=True)
            runs.extend(file_runs)

            # 必要件数が揃ったら、これより古いファイルは開かない
            if len(runs) >= needed:
                break

        # 念のため全体を新しい順に整列（ファイル名と started_at のズレに備える）
        runs.sort(key=lambda x: x.started_at, reverse=True)
        return runs[offset:offset + limit]

    def get_latest_run(self, workflow_name: str) -> RunLog | None:
        """ワークフローの最新実行結果を取得"""
        runs = self.get_runs_for_workflow(workflow_name, limit=1)
        return runs[0] if runs else None

    def get_latest_runs_map(self, workflow_names: set[str]) -> dict[str, RunLog]:
        """複数ワークフローの最新実行結果をまとめて取得"""
        if not workflow_names:
            return {}

        start_time = time.perf_counter()
        latest: dict[str, RunLog] = {}
        remaining = set(workflow_names)
        log_files = sorted(self.runs_dir.glob("*.jsonl"), reverse=True)

        for log_file in log_files:
            if not remaining:
                break
            try:
                lines = log_file.read_text(encoding="utf-8").splitlines()
            except Exception as e:
                logger.error(f"Failed to read log file {log_file}: {e}")
                continue

            for line in reversed(lines):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    run = RunLog.model_validate(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in {log_file}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Failed to parse run log: {e}")
                    continue

                if run.workflow in remaining:
                    latest[run.workflow] = run
                    remaining.remove(run.workflow)
                    if not remaining:
                        break

        elapsed = time.perf_counter() - start_time
        logger.info(
            "Latest runs map: workflows=%d found=%d files=%d elapsed=%.3fs",
            len(workflow_names),
            len(latest),
            len(log_files),
            elapsed,
        )
        return latest

    def _read_log_file(self, log_file: Path, workflow_filter: str | None = None) -> list[RunLog]:
        """ログファイルを読み込み"""
        runs = []

        try:
            with log_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        run = RunLog.model_validate(data)

                        if workflow_filter is None or run.workflow == workflow_filter:
                            runs.append(run)

                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON in {log_file}: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to parse run log: {e}")

        except Exception as e:
            logger.error(f"Failed to read log file {log_file}: {e}")

        return runs

    def count_runs_for_workflow(self, workflow_name: str) -> int:
        """特定ワークフローの実行履歴の総件数を取得"""
        return self.count_all_runs(workflow_filter=workflow_name)

    def count_all_runs(self, workflow_filter: str | None = None) -> int:
        """実行履歴の総件数を取得（Pydantic 検証はしない）

        フィルタなしなら空行を除いた行数を数えるだけ。フィルタありの場合のみ
        各行を JSON パースして workflow を判定するが、RunLog 検証は行わない。
        """
        count = 0
        log_files = self.runs_dir.glob("*.jsonl")

        for log_file in log_files:
            try:
                with log_file.open("r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        if workflow_filter is None:
                            count += 1
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if data.get("workflow") == workflow_filter:
                            count += 1
            except Exception as e:
                logger.error(f"Failed to read log file {log_file}: {e}")
                continue

        return count

    def cleanup(self, retention_days: int = 3) -> dict:
        """
        古いログファイルを削除

        Args:
            retention_days: 保持日数（デフォルト: 3日）

        Returns:
            削除結果の統計情報
        """
        cutoff_date = datetime.now(JST) - timedelta(days=retention_days)
        deleted_files = []
        deleted_size = 0
        kept_files = []

        for log_file in self.runs_dir.glob("*.jsonl"):
            try:
                # ファイル名から日付を抽出（YYYYMMDD.jsonl）
                date_str = log_file.stem
                file_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=JST)

                if file_date < cutoff_date:
                    file_size = log_file.stat().st_size
                    log_file.unlink()
                    deleted_files.append(log_file.name)
                    deleted_size += file_size
                    logger.info(f"Deleted old log file: {log_file}")
                else:
                    kept_files.append(log_file.name)

            except ValueError:
                # 日付形式でないファイルはスキップ
                logger.warning(f"Skipped non-date log file: {log_file}")
                continue
            except Exception as e:
                logger.error(f"Error deleting {log_file}: {e}")
                continue

        result = {
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "deleted_count": len(deleted_files),
            "deleted_files": deleted_files,
            "deleted_size_bytes": deleted_size,
            "kept_count": len(kept_files),
        }

        logger.info(f"Log cleanup completed: {len(deleted_files)} files deleted")
        return result
