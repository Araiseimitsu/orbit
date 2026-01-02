"""
ORBIT MVP - Action Registry
アクション（type -> 実行関数）の登録と取得
"""
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# アクション関数の型: async def action(params, context) -> dict
ActionFunc = Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]


class ActionRegistry:
    """アクション登録・実行管理"""

    def __init__(self):
        self._actions: dict[str, ActionFunc] = {}

    def register(self, action_type: str, func: ActionFunc) -> None:
        """アクションを登録"""
        self._actions[action_type] = func
        logger.debug(f"Registered action: {action_type}")

    def get(self, action_type: str) -> ActionFunc | None:
        """アクションを取得"""
        return self._actions.get(action_type)

    def has(self, action_type: str) -> bool:
        """アクションが登録されているか確認"""
        return action_type in self._actions

    def list_actions(self) -> list[str]:
        """登録済みアクション一覧"""
        return list(self._actions.keys())


# グローバルレジストリ（シングルトン）
_registry = ActionRegistry()


def get_registry() -> ActionRegistry:
    """グローバルレジストリを取得"""
    return _registry


def register_action(action_type: str):
    """デコレータ: アクション関数を登録"""
    def decorator(func: ActionFunc) -> ActionFunc:
        _registry.register(action_type, func)
        return func
    return decorator
