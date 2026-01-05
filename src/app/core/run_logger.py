"""
ORBIT MVP - Run Logger
実行ログの JSONL ファイル管理
"""
import json
import logging
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
        runs = []

        # 全ログファイルを日付降順で読む
        log_files = sorted(self.runs_dir.glob("*.jsonl"), reverse=True)

        for log_file in log_files:
            file_runs = self._read_log_file(log_file, workflow_name)
            runs.extend(file_runs)

        # ソートしてからオフセットと制限を適用
        sorted_runs = sorted(runs, key=lambda x: x.started_at, reverse=True)
        return sorted_runs[offset:offset + limit]

    def get_all_runs(self, limit: int = 50, offset: int = 0, workflow_filter: str | None = None) -> list[RunLog]:
        """全実行履歴を取得（新しい順）

        Args:
            limit: 取得件数（デフォルト: 50）
            offset: オフセット（デフォルト: 0）
            workflow_filter: フィルタするワークフロー名（オプション）
        """
        runs = []

        log_files = sorted(self.runs_dir.glob("*.jsonl"), reverse=True)

        for log_file in log_files:
            file_runs = self._read_log_file(log_file, workflow_filter)
            runs.extend(file_runs)

        # ソートしてからオフセットと制限を適用
        sorted_runs = sorted(runs, key=lambda x: x.started_at, reverse=True)
        return sorted_runs[offset:offset + limit]

    def get_latest_run(self, workflow_name: str) -> RunLog | None:
        """ワークフローの最新実行結果を取得"""
        runs = self.get_runs_for_workflow(workflow_name, limit=1)
        return runs[0] if runs else None

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
        count = 0
        log_files = sorted(self.runs_dir.glob("*.jsonl"), reverse=True)

        for log_file in log_files:
            file_runs = self._read_log_file(log_file, workflow_name)
            count += len(file_runs)

        return count

    def count_all_runs(self, workflow_filter: str | None = None) -> int:
        """全実行履歴の総件数を取得"""
        count = 0
        log_files = sorted(self.runs_dir.glob("*.jsonl"), reverse=True)

        for log_file in log_files:
            file_runs = self._read_log_file(log_file, workflow_filter)
            count += len(file_runs)

        return count

    def cleanup(self, retention_days: int = 30) -> dict:
        """
        古いログファイルを削除

        Args:
            retention_days: 保持日数（デフォルト: 30日）

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
