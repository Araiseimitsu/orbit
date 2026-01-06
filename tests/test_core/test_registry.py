"""
ORBIT Test Suite - Action Registry
"""
import pytest

from src.app.core.registry import (
    ActionRegistry,
    get_registry,
    register_action,
    ActionMetadata,
)


class TestActionRegistry:
    """アクションレジストリのテスト"""

    def test_register_action(self):
        """アクションを登録"""
        registry = ActionRegistry()

        async def dummy_action(params: dict, context: dict) -> dict:
            return {"result": "ok"}

        registry.register("test_action", dummy_action)
        assert registry.has("test_action")
        assert registry.get("test_action") == dummy_action

    def test_register_action_with_metadata(self):
        """メタデータ付きでアクションを登録"""
        registry = ActionRegistry()

        async def dummy_action(params: dict, context: dict) -> dict:
            return {"result": "ok"}

        metadata = {
            "type": "test_action",
            "title": "テストアクション",
            "description": "テスト用アクション",
            "category": "test",
            "params": [
                {"key": "message", "description": "メッセージ", "required": True}
            ],
            "outputs": [
                {"key": "result", "description": "結果"}
            ],
        }

        registry.register("test_action", dummy_action, metadata)

        # メタデータが取得できる
        action_metadata = registry.get_metadata("test_action")
        assert action_metadata is not None
        assert action_metadata.type == "test_action"
        assert action_metadata.title == "テストアクション"
        assert action_metadata.category == "test"
        assert len(action_metadata.params) == 1
        assert action_metadata.params[0]["key"] == "message"

    def test_register_action_auto_type_in_metadata(self):
        """メタデータにtypeがない場合はaction_typeを自動設定"""
        registry = ActionRegistry()

        async def dummy_action(params: dict, context: dict) -> dict:
            return {"result": "ok"}

        metadata = {
            "title": "テスト",
            "description": "説明",
            "category": "test",
        }

        registry.register("my_action", dummy_action, metadata)

        action_metadata = registry.get_metadata("my_action")
        assert action_metadata.type == "my_action"

    def test_get_action(self):
        """登録したアクションを取得"""
        registry = ActionRegistry()

        async def dummy_action(params: dict, context: dict) -> dict:
            return {"result": "ok"}

        registry.register("test_action", dummy_action)
        retrieved = registry.get("test_action")

        assert retrieved is not None
        assert retrieved == dummy_action

    def test_get_nonexistent_action(self):
        """存在しないアクションの取得"""
        registry = ActionRegistry()
        assert registry.get("nonexistent") is None

    def test_has_action(self):
        """アクションが登録されているか確認"""
        registry = ActionRegistry()

        async def dummy_action(params: dict, context: dict) -> dict:
            return {"result": "ok"}

        assert not registry.has("test_action")
        registry.register("test_action", dummy_action)
        assert registry.has("test_action")

    def test_list_actions(self):
        """登録済みアクション一覧を取得"""
        registry = ActionRegistry()

        async def action1(params: dict, context: dict) -> dict:
            return {"result": "1"}

        async def action2(params: dict, context: dict) -> dict:
            return {"result": "2"}

        registry.register("action1", action1)
        registry.register("action2", action2)

        actions = registry.list_actions()
        assert set(actions) == {"action1", "action2"}

    def test_list_all_metadata(self):
        """全アクションのメタデータを取得"""
        registry = ActionRegistry()

        async def action1(params: dict, context: dict) -> dict:
            return {"result": "1"}

        async def action2(params: dict, context: dict) -> dict:
            return {"result": "2"}

        registry.register("action1", action1, {
            "type": "action1",
            "title": "アクション1",
            "description": "説明1",
            "category": "cat1",
        })
        registry.register("action2", action2, {
            "type": "action2",
            "title": "アクション2",
            "description": "説明2",
            "category": "cat2",
        })

        all_metadata = registry.list_all_metadata()
        assert "action1" in all_metadata
        assert "action2" in all_metadata
        assert all_metadata["action1"]["title"] == "アクション1"
        assert all_metadata["action2"]["title"] == "アクション2"

    def test_register_action_without_metadata(self):
        """メタデータなしでアクションを登録"""
        registry = ActionRegistry()

        async def dummy_action(params: dict, context: dict) -> dict:
            return {"result": "ok"}

        registry.register("test_action", dummy_action)

        # メタデータは登録されない
        assert registry.get_metadata("test_action") is None
        # アクション自体は登録されている
        assert registry.has("test_action")

    def test_override_existing_action(self):
        """既存のアクションを上書き"""
        registry = ActionRegistry()

        async def action1(params: dict, context: dict) -> dict:
            return {"result": "1"}

        async def action2(params: dict, context: dict) -> dict:
            return {"result": "2"}

        registry.register("test_action", action1)
        assert registry.get("test_action") == action1

        registry.register("test_action", action2)
        assert registry.get("test_action") == action2


class TestGlobalRegistry:
    """グローバルレジストリのテスト"""

    def test_get_registry_singleton(self):
        """get_registryは同じインスタンスを返す"""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    def test_register_action_decorator(self):
        """デコレータでアクションを登録"""
        # テスト前にリセット
        registry = get_registry()
        initial_count = len(registry.list_actions())

        @register_action("decorated_test", {
            "type": "decorated_test",
            "title": "デコレータテスト",
            "description": "デコレータで登録",
            "category": "test",
        })
        async def test_action(params: dict, context: dict) -> dict:
            return {"result": "decorated"}

        # アクションが登録された
        assert registry.has("decorated_test")

        # メタデータも登録された
        metadata = registry.get_metadata("decorated_test")
        assert metadata is not None
        assert metadata.title == "デコレータテスト"

        # クリーンアップ
        registry._actions.pop("decorated_test", None)
        registry._metadata.pop("decorated_test", None)


class TestActionMetadata:
    """アクションメタデータのテスト"""

    def test_create_action_metadata_minimal(self):
        """最小限のパラメータでメタデータを作成"""
        metadata = ActionMetadata(
            type="test",
            title="テスト",
            description="説明",
            category="test",
        )
        assert metadata.type == "test"
        assert metadata.title == "テスト"
        assert metadata.description == "説明"
        assert metadata.category == "test"
        assert metadata.params == []
        assert metadata.outputs == []
        assert metadata.example is None

    def test_create_action_metadata_full(self):
        """全パラメータでメタデータを作成"""
        metadata = ActionMetadata(
            type="test",
            title="テスト",
            description="説明",
            category="test",
            params=[
                {"key": "message", "description": "メッセージ", "required": True, "example": "Hello"}
            ],
            outputs=[
                {"key": "result", "description": "結果"}
            ],
            example="example:\n  type: test\n  params:\n    message: Hello",
        )
        assert len(metadata.params) == 1
        assert metadata.params[0]["key"] == "message"
        assert len(metadata.outputs) == 1
        assert metadata.example is not None

    def test_action_metadata_serialization(self):
        """メタデータのシリアライズ"""
        metadata = ActionMetadata(
            type="test",
            title="テスト",
            description="説明",
            category="test",
        )
        data = metadata.model_dump()
        assert data["type"] == "test"
        assert data["title"] == "テスト"
        assert data["category"] == "test"


class TestActionParamMetadata:
    """アクションパラメータメタデータのテスト"""

    def test_create_param_metadata_required(self):
        """必須パラメータのメタデータ"""
        from src.app.core.registry import ActionParamMetadata

        param = ActionParamMetadata(
            key="message",
            description="メッセージ",
            required=True,
        )
        assert param.key == "message"
        assert param.description == "メッセージ"
        assert param.required is True
        assert param.default is None
        assert param.example is None

    def test_create_param_metadata_optional(self):
        """オプションパラメータのメタデータ"""
        from src.app.core.registry import ActionParamMetadata

        param = ActionParamMetadata(
            key="count",
            description="回数",
            required=False,
            default=1,
            example="5",
        )
        assert param.key == "count"
        assert param.required is False
        assert param.default == 1
        assert param.example == "5"
