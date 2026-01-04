"""
ORBIT MVP - Log Action
デバッグ用のログ出力アクション
"""
import logging
from typing import Any

from ..core.registry import register_action

logger = logging.getLogger(__name__)


@register_action(
    "log",
    metadata={
        "title": "ログ出力",
        "description": "指定メッセージをログに出力します。テンプレートで前のステップ結果を参照できます。",
        "category": "ログ",
        "params": [
            {
                "key": "message",
                "description": "出力メッセージ",
                "required": True,
                "example": "Hello {{ step_1.text }}"
            },
            {
                "key": "level",
                "description": "ログレベル (debug/info/warning/error)",
                "required": False,
                "default": "info",
                "example": "info"
            }
        ],
        "outputs": [
            {"key": "logged", "description": "出力成功フラグ"},
            {"key": "message", "description": "出力したメッセージ"}
        ]
    }
)
async def action_log(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """
    ログ出力アクション

    params:
        message: 出力メッセージ（テンプレート展開済み）
        level: ログレベル (debug, info, warning, error) - デフォルト: info

    returns:
        logged: True
        message: 出力したメッセージ
    """
    message = params.get("message", "")
    level = params.get("level", "info").lower()

    log_func = {
        "debug": logger.debug,
        "info": logger.info,
        "warning": logger.warning,
        "error": logger.error,
    }.get(level, logger.info)

    log_func(f"[WORKFLOW] {message}")

    return {
        "logged": True,
        "message": message
    }
