"""
ORBIT MVP - Retry Mechanism
非同期関数のリトライ処理を提供する
"""
import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Type, Tuple, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_async(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    非同期関数のリトライデコレータ

    Args:
        max_attempts: 最大試行回数（初期試行を含む）
        delay: 最初のリトライまでの待機時間（秒）
        backoff: バックオフ乗数（各リトライで待機時間がこの倍数になる）
        exceptions: リトライ対象の例外タプル

    Returns:
        デコレータ関数

    Example:
        @retry_async(max_attempts=3, delay=1.0, backoff=2.0)
        async def api_call():
            # API呼び出し
            pass
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_error = e

                    # 最後の試行で失敗した場合は再送出
                    if attempt == max_attempts - 1:
                        logger.error(
                            f"{func.__name__} が {max_attempts} 回の試行で失敗: {e}"
                        )
                        raise

                    # 次のリトライまで待機
                    wait_time = delay * (backoff ** attempt)
                    logger.warning(
                        f"{func.__name__} 失敗 (試行 {attempt + 1}/{max_attempts}): {e}. "
                        f"{wait_time:.1f}秒後にリトライします"
                    )
                    await asyncio.sleep(wait_time)

            # ここには到達しないはず（max_attempts >= 1のため）
            if last_error:
                raise last_error
            raise RuntimeError("リトライ処理で予期しないエラーが発生しました")

        return wrapper

    return decorator


def retry_sync(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    同期関数のリトライデコレータ

    Args:
        max_attempts: 最大試行回数（初期試行を含む）
        delay: 最初のリトライまでの待機時間（秒）
        backoff: バックオフ乗数（各リトライで待機時間がこの倍数になる）
        exceptions: リトライ対象の例外タプル

    Returns:
        デコレータ関数
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            import time

            last_error: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e

                    if attempt == max_attempts - 1:
                        logger.error(
                            f"{func.__name__} が {max_attempts} 回の試行で失敗: {e}"
                        )
                        raise

                    wait_time = delay * (backoff ** attempt)
                    logger.warning(
                        f"{func.__name__} 失敗 (試行 {attempt + 1}/{max_attempts}): {e}. "
                        f"{wait_time:.1f}秒後にリトライします"
                    )
                    time.sleep(wait_time)

            if last_error:
                raise last_error
            raise RuntimeError("リトライ処理で予期しないエラーが発生しました")

        return wrapper

    return decorator
