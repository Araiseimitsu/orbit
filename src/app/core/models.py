"""
ORBIT MVP - Pydantic Models for Workflow Definition
"""
from typing import Any, Literal

from pydantic import BaseModel, Field


class TriggerSchedule(BaseModel):
    """スケジュールトリガー"""
    type: Literal["schedule"] = "schedule"
    cron: str = Field(..., description="Cron式 (例: '0 9 * * *')")


class TriggerManual(BaseModel):
    """手動トリガー"""
    type: Literal["manual"] = "manual"


class TriggerWebhook(BaseModel):
    """Webhookトリガー（将来用）"""
    type: Literal["webhook"] = "webhook"
    path: str | None = None


# Triggerの統合型
Trigger = TriggerSchedule | TriggerManual | TriggerWebhook


class Step(BaseModel):
    """ワークフローステップ"""
    id: str = Field(..., description="ステップID（一意）")
    type: str = Field(..., description="アクションタイプ (log, file_write, ai, etc.)")
    params: dict[str, Any] = Field(default_factory=dict, description="パラメータ")
    meta: dict[str, Any] | None = Field(default=None, description="UI用メタ情報（位置など）")


class Workflow(BaseModel):
    """ワークフロー定義"""
    name: str = Field(..., description="ワークフロー名")
    trigger: Trigger = Field(..., description="トリガー設定")
    steps: list[Step] = Field(..., min_length=1, description="ステップ一覧")
    description: str | None = Field(default=None, description="説明（任意）")
    enabled: bool = Field(default=True, description="有効/無効フラグ（スケジュール登録に影響）")


class WorkflowInfo(BaseModel):
    """ワークフロー一覧表示用"""
    name: str
    filename: str
    status: str = "未実行"
    last_run: str | None = None
    trigger_type: str = "manual"
    step_count: int = 0
    is_valid: bool = True
    error: str | None = None
    enabled: bool = True


class RunLog(BaseModel):
    """実行ログ（JSONL用）"""
    run_id: str
    workflow: str
    status: Literal["running", "success", "failed"]
    started_at: str
    ended_at: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
