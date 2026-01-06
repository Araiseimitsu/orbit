"""
ORBIT Test Suite - Retry Mechanism
"""
import asyncio
import pytest

from src.app.core.retry import retry_async, retry_sync
from src.app.core.models import Workflow, Step, TriggerManual


class TestRetryAsync:
    """非同期リトライデコレータのテスト"""

    @pytest.mark.asyncio
    async def test_retry_async_success_on_first_try(self):
        """最初の試行で成功"""
        call_count = 0

        @retry_async(max_attempts=3)
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await test_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_async_success_after_retry(self):
        """リトライ後に成功"""
        call_count = 0

        @retry_async(max_attempts=3, delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary failure")
            return "success"

        result = await test_func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_async_max_attempts_reached(self):
        """最大試行回数到達で例外送出"""
        call_count = 0

        @retry_async(max_attempts=3, delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent failure")

        with pytest.raises(ValueError, match="Persistent failure"):
            await test_func()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_specific_exception_only(self):
        """特定の例外のみリトライ"""
        call_count = 0

        @retry_async(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Retry this")
            if call_count == 2:
                raise TypeError("Don't retry this")
            return "success"

        # TypeErrorはリトライされない
        with pytest.raises(TypeError, match="Don't retry this"):
            await test_func()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_async_backoff(self):
        """バックオフ時間が増加することを確認"""
        import time
        call_times = []

        @retry_async(max_attempts=4, delay=0.05, backoff=2.0)
        async def test_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("Fail")
            return "success"

        await test_func()

        assert len(call_times) == 3
        # 遅延時間が増加していることを確認
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        assert delay1 >= 0.05  # 最初の遅延
        assert delay2 >= 0.10  # 2回目の遅延（backoff=2.0）


class TestRetrySync:
    """同期リトライデコレータのテスト"""

    def test_retry_sync_success_on_first_try(self):
        """最初の試行で成功"""
        call_count = 0

        @retry_sync(max_attempts=3)
        def test_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = test_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_sync_success_after_retry(self):
        """リトライ後に成功"""
        call_count = 0

        @retry_sync(max_attempts=3, delay=0.01)
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary failure")
            return "success"

        result = test_func()
        assert result == "success"
        assert call_count == 2

    def test_retry_sync_max_attempts_reached(self):
        """最大試行回数到達で例外送出"""
        call_count = 0

        @retry_sync(max_attempts=3, delay=0.01)
        def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent failure")

        with pytest.raises(ValueError, match="Persistent failure"):
            test_func()

        assert call_count == 3


class TestExecutorTimeout:
    """エグゼキューターのタイムアウト処理のテスト"""

    @pytest.mark.asyncio
    async def test_step_timeout(self, executor, reset_registry):
        """ステップがタイムアウトする"""
        from src.app.core.registry import register_action

        async def slow_action(params, context):
            # デフォルトタイムアウトは300秒だが、実際にはテストの時間を考慮
            # タイムアウト処理をテストするため、直接_execute_stepをテスト
            await asyncio.sleep(1)  # 1秒スリープ
            return {"result": "should not reach here"}

        register_action("slow_action")(slow_action)

        # 直接 _execute_step をテスト（短いタイムアウト指定）
        result = await executor._execute_step(
            step_id="step1",
            step_type="slow_action",
            params={},
            context={},
            timeout=0.1  # 0.1秒でタイムアウト
        )

        assert result["status"] == "failed"
        assert "timed out" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_step_completes_before_timeout(self, executor, reset_registry):
        """ステップがタイムアウト前に完了する"""
        from src.app.core.registry import register_action

        async def quick_action(params, context):
            await asyncio.sleep(0.01)
            return {"result": "success"}

        register_action("quick_action")(quick_action)

        # 直接 _execute_step をテスト
        result = await executor._execute_step(
            step_id="step1",
            step_type="quick_action",
            params={},
            context={},
            timeout=1.0  # 1秒タイムアウト（十分に長い）
        )

        assert result["status"] == "success"
