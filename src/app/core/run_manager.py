"""
ORBIT MVP - Run Manager
実行中ワークフローのタスク管理
"""
from __future__ import annotations

import asyncio

from .models import RunLog


class RunManager:
    """実行中タスクをワークフロー名で管理"""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[RunLog]] = {}
        self._lock = asyncio.Lock()

    async def register(self, workflow_name: str, task: asyncio.Task[RunLog]) -> bool:
        async with self._lock:
            existing = self._tasks.get(workflow_name)
            if existing and not existing.done():
                return False
            self._tasks[workflow_name] = task
            return True

    async def unregister(self, workflow_name: str) -> None:
        async with self._lock:
            self._tasks.pop(workflow_name, None)

    async def is_running(self, workflow_name: str) -> bool:
        async with self._lock:
            task = self._tasks.get(workflow_name)
            return bool(task and not task.done())

    async def cancel(self, workflow_name: str) -> bool:
        async with self._lock:
            task = self._tasks.get(workflow_name)
            if not task or task.done():
                return False
            task.cancel()
            return True
