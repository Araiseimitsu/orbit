"""
ORBIT MVP - Workflow Backup Manager
ワークフロー定義の自動バックアップ管理
"""
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupManager:
    """ワークフローバックアップ管理"""

    def __init__(self, backup_dir: Path, max_backups: int = 10):
        self.backup_dir = backup_dir
        self.max_backups = max_backups

    def backup_workflow(self, workflow_name: str, yaml_content: str) -> Path | None:
        """
        ワークフローをバックアップ

        Args:
            workflow_name: ワークフロー名
            yaml_content: 現在のYAML内容

        Returns:
            バックアップファイルパス（バックアップ不要な場合はNone）
        """
        if not yaml_content:
            return None

        workflow_backup_dir = self.backup_dir / workflow_name
        workflow_backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = workflow_backup_dir / f"{timestamp}.yaml"

        backup_path.write_text(yaml_content, encoding="utf-8")
        logger.info(f"Backup created: {backup_path}")

        self._cleanup_old_backups(workflow_backup_dir)

        return backup_path

    def _cleanup_old_backups(self, workflow_backup_dir: Path) -> None:
        """古いバックアップを削除（max_backups件まで保持）"""
        backups = sorted(
            workflow_backup_dir.glob("*.yaml"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

        for old_backup in backups[self.max_backups :]:
            old_backup.unlink()
            logger.debug(f"Old backup removed: {old_backup}")

    def list_backups(self, workflow_name: str) -> list[dict]:
        """ワークフローのバックアップ一覧を取得"""
        workflow_backup_dir = self.backup_dir / workflow_name
        if not workflow_backup_dir.exists():
            return []

        backups = []
        for backup_file in sorted(
            workflow_backup_dir.glob("*.yaml"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        ):
            backups.append(
                {
                    "filename": backup_file.name,
                    "timestamp": backup_file.stem,
                    "size": backup_file.stat().st_size,
                }
            )
        return backups
