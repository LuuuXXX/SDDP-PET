"""Application-layer heartbeat (Dev-Phase 1 D1-7).

Per Decision 3 (`design.md`) + `specs/websocket-ipc/spec.md` Requirement: heartbeat
MUST use application-layer JSON `{"type":"ping"}` / `{"type":"pong"}`, NOT RFC 6455
protocol control frames (Starlette's WebSocket wrapper doesn't expose the latter).

Timing:
  - Server sends ping every 30 seconds
  - Client MUST reply pong within 10 seconds
  - Server triggers "connection lost" callback after 3 consecutive misses (≥ 90s)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

from .schemas import Ping, Pong

logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    """Server-side heartbeat monitor: emits pings, tracks pongs, fires on_missed callback.

    Lifecycle:
      monitor = HeartbeatMonitor(send_fn, on_connection_lost)
      await monitor.start()           # begins the 30s ping loop
      await monitor.notify_pong(pong) # call when client replies
      await monitor.stop()            # clean shutdown
    """

    PING_INTERVAL_SECONDS = 30.0
    PONG_TIMEOUT_SECONDS = 10.0
    MISS_THRESHOLD = 3

    def __init__(
        self,
        send_fn: Callable[[dict], Awaitable[None]],
        on_connection_lost: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._send = send_fn
        self._on_lost = on_connection_lost
        self._task: asyncio.Task | None = None
        self._consecutive_misses = 0
        self._awaiting_pong_since: datetime | None = None
        self._stopped = False

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopped = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def notify_pong(self, pong: Pong) -> None:
        """Reset miss counter on pong arrival."""
        self._consecutive_misses = 0
        self._awaiting_pong_since = None
        logger.debug("pong received (ping_ts=%s)", pong.ping_timestamp)

    async def _loop(self) -> None:
        """Loop: every PING_INTERVAL, send ping; check if previous pong timed out."""
        try:
            while not self._stopped:
                # If we were awaiting a pong and didn't get it within the window, count a miss.
                if self._awaiting_pong_since is not None:
                    elapsed = (datetime.now(timezone.utc) - self._awaiting_pong_since).total_seconds()
                    if elapsed > self.PONG_TIMEOUT_SECONDS:
                        self._consecutive_misses += 1
                        logger.warning(
                            "heartbeat miss %d/%d (no pong within %.0fs)",
                            self._consecutive_misses, self.MISS_THRESHOLD, self.PONG_TIMEOUT_SECONDS,
                        )
                        self._awaiting_pong_since = None
                        if self._consecutive_misses >= self.MISS_THRESHOLD:
                            logger.error("heartbeat threshold reached — triggering connection-lost")
                            if self._on_lost is not None:
                                await self._on_lost()
                            return  # end loop; supervisor should clean up the WS connection

                # Send next ping (unless we just incremented a miss and are still awaiting)
                if self._awaiting_pong_since is None:
                    ping = Ping(timestamp=datetime.now(timezone.utc).isoformat())
                    try:
                        await self._send(ping.model_dump())
                        self._awaiting_pong_since = datetime.now(timezone.utc)
                    except Exception as e:
                        logger.error("failed to send ping: %s", e)
                        # Treat send failure as immediate connection loss
                        if self._on_lost is not None:
                            await self._on_lost()
                        return

                await asyncio.sleep(self.PING_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.debug("heartbeat task cancelled")
            raise


__all__ = ["HeartbeatMonitor"]
