import asyncio
import logging
from typing import Optional

from memory.manager import MemoryManager


logger = logging.getLogger(__name__)


class ConsolidationJob:
    def __init__(
        self,
        manager: MemoryManager,
        interval_seconds: int = 300,
    ):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")

        self.manager = manager
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def run_once(self) -> int:
        try:
            result = self.manager.run_consolidation()

            if result is None:
                return 0

            return int(result)

        except Exception:
            logger.exception("Memory consolidation failed")
            return 0

    async def run_forever(self):
        if self._running:
            return

        self._running = True

        try:
            while self._running:
                await self.run_once()
                await asyncio.sleep(self.interval_seconds)

        finally:
            self._running = False

    def start(self):
        if self._task and not self._task.done():
            return self._task

        self._task = asyncio.create_task(self.run_forever())
        return self._task

    async def stop(self):
        self._running = False

        if self._task and not self._task.done():
            self._task.cancel()

            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._task = None

    @property
    def running(self) -> bool:
        return self._running
