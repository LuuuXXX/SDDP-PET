"""Heartbeat miss-detection tests (D1-7)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from sddp.ipc.heartbeat import HeartbeatMonitor
from sddp.ipc.schemas import Pong


@pytest.mark.asyncio
async def test_heartbeat_sends_ping_periodically(monkeypatch):
    """Server emits ping at PING_INTERVAL_SECONDS cadence."""
    # Speed up the test by shortening intervals
    monkeypatch.setattr(HeartbeatMonitor, "PING_INTERVAL_SECONDS", 0.1)
    monkeypatch.setattr(HeartbeatMonitor, "PONG_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(HeartbeatMonitor, "MISS_THRESHOLD", 99)  # don't fire lost

    sent: list[dict] = []

    async def send_fn(msg):
        sent.append(msg)

    monitor = HeartbeatMonitor(send_fn)
    await monitor.start()
    await asyncio.sleep(0.35)  # should produce ≥3 pings
    await monitor.stop()

    pings = [m for m in sent if m["type"] == "ping"]
    assert len(pings) >= 3, f"expected ≥3 pings, got {len(pings)}"


@pytest.mark.asyncio
async def test_heartbeat_triggers_connection_lost_after_3_misses(monkeypatch):
    """3 consecutive pong misses MUST trigger on_connection_lost callback."""
    monkeypatch.setattr(HeartbeatMonitor, "PING_INTERVAL_SECONDS", 0.05)
    monkeypatch.setattr(HeartbeatMonitor, "PONG_TIMEOUT_SECONDS", 0.025)
    monkeypatch.setattr(HeartbeatMonitor, "MISS_THRESHOLD", 3)

    sent: list[dict] = []
    lost_calls = 0

    async def send_fn(msg):
        sent.append(msg)

    async def on_lost():
        nonlocal lost_calls
        lost_calls += 1

    monitor = HeartbeatMonitor(send_fn, on_connection_lost=on_lost)
    await monitor.start()

    # Don't reply to pongs → misses accumulate
    for _ in range(20):
        await asyncio.sleep(0.05)
        if lost_calls > 0:
            break

    await monitor.stop()
    assert lost_calls == 1, f"expected on_connection_lost called once, got {lost_calls}"


@pytest.mark.asyncio
async def test_heartbeat_pong_resets_miss_counter(monkeypatch):
    """If pong arrives within window, miss counter MUST stay 0."""
    monkeypatch.setattr(HeartbeatMonitor, "PING_INTERVAL_SECONDS", 0.1)
    monkeypatch.setattr(HeartbeatMonitor, "PONG_TIMEOUT_SECONDS", 0.5)
    monkeypatch.setattr(HeartbeatMonitor, "MISS_THRESHOLD", 3)

    sent: list[dict] = []

    async def send_fn(msg):
        sent.append(msg)
        # Immediately reply pong when a ping is sent
        if msg.get("type") == "ping":
            async def reply():
                await asyncio.sleep(0.01)
                await monitor.notify_pong(Pong(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    ping_timestamp=msg["timestamp"],
                ))
            asyncio.create_task(reply())

    lost = 0

    async def on_lost():
        nonlocal lost
        lost += 1

    monitor = HeartbeatMonitor(send_fn, on_connection_lost=on_lost)
    await monitor.start()
    await asyncio.sleep(0.5)
    await monitor.stop()

    assert lost == 0, "should not have fired connection-lost when pongs arrive"
    pings = [m for m in sent if m["type"] == "ping"]
    assert len(pings) >= 3


@pytest.mark.asyncio
async def test_heartbeat_can_be_stopped_cleanly(monkeypatch):
    """stop() MUST cancel the loop and not leave dangling tasks."""
    monkeypatch.setattr(HeartbeatMonitor, "PING_INTERVAL_SECONDS", 0.1)

    async def send_fn(msg):
        pass

    monitor = HeartbeatMonitor(send_fn)
    await monitor.start()
    await asyncio.sleep(0.05)
    await monitor.stop()  # should not raise
    assert monitor._task is None or monitor._task.cancelled() or monitor._task.done()
