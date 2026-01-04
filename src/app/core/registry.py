"""
ORBIT MVP - Action Registry
アクション（type -> 実行関数）の登録と取得
"""
import logging
from typing import Any, Callable, Awaitable

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# アクション関数の型: async def action(params, context) -> dict
ActionFunc = Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]


class ActionParamMetadata(BaseModel):
    """アクションパラメータのメタデータ"""
    key: str
    description: str
    required: bool = False
    default: Any = None
    example: str | None = None


class ActionMetadata(BaseModel):
    """アクションのメタデータ"""
    type: str
    title: str  # 表示名（日本語）
    description: str  # アクションの説明
    category: str  # カテゴリ
    params: list[dict] = []  # パラメータ定義
    outputs: list[dict] = []  # 出力定義
    example: str | None = None  # YAML使用例


class ActionRegistry:
    """アクション登録・実行管理"""

    def __init__(self):
        self._actions: dict[str, ActionFunc] = {}
        self._metadata: dict[str, ActionMetadata] = {}

    def register(self, action_type: str, func: ActionFunc, metadata: dict | None = None) -> None:
        """アクションとメタデータを登録"""
        self._actions[action_type] = func

        # メタデータがあればパースして保存
        if metadata:
            # type が含まれていない場合は action_type を設定
            if "type" not in metadata:
                metadata = metadata.copy()
                metadata["type"] = action_type
            self._metadata[action_type] = ActionMetadata(**metadata)

        logger.debug(f"Registered action: {action_type}")

    def get(self, action_type: str) -> ActionFunc | None:
        """アクションを取得"""
        return self._actions.get(action_type)

    def get_metadata(self, action_type: str) -> ActionMetadata | None:
        """アクションのメタデータを取得"""
        return self._metadata.get(action_type)

    def has(self, action_type: str) -> bool:
        """アクションが登録されているか確認"""
        return action_type in self._actions

    def list_actions(self) -> list[str]:
        """登録済みアクション一覧"""
        return list(self._actions.keys())

    def list_all_metadata(self) -> dict[str, dict]:
        """全アクションのメタデータを取得"""
        return {
            action_type: metadata.dict()
            for action_type, metadata in self._metadata.items()
        }


# グローバルレジストリ（シングルトン）
_registry = ActionRegistry()


def get_registry() -> ActionRegistry:
    """グローバルレジストリを取得"""
    return _registry


def register_action(action_type: str, metadata: dict | None = None):
    """デコレータ: アクション関数とメタデータを登録"""
    def decorator(func: ActionFunc) -> ActionFunc:
        _registry.register(action_type, func, metadata)
        return func
    return decorator
