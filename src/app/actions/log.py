"""
ORBIT MVP - Log Action
デバッグ用のログ出力アクション
"""
import logging
from typing import Any

from ..core.registry import register_action

logger = logging.getLogger(__name__)


@register_action("log")
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
