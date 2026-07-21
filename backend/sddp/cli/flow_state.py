"""SQLite-backed persistence for Flow state (@persist).

Per design.md decision 9: SQLite (not JSON files) for atomic concurrent writes.
Default DB path: ~/.sddp-pet/flow_state.db
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(os.environ.get("SDDP_FLOW_STATE_DB", str(Path.home() / ".sddp-pet" / "flow_state.db")))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS flow_state (
    flow_id    TEXT NOT NULL,
    step       TEXT NOT NULL,
    data       TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (flow_id, step)
);

CREATE TABLE IF NOT EXISTS flow_meta (
    flow_id     TEXT PRIMARY KEY,
    inputs      TEXT NOT NULL,
    status      TEXT NOT NULL,  -- 'running' / 'paused' / 'completed' / 'aborted'
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_flow_state_flow_id ON flow_state(flow_id);
CREATE INDEX IF NOT EXISTS idx_flow_meta_status   ON flow_meta(status);
"""


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def save_state(flow_id: str, step: str, data: dict[str, Any], db_path: str | Path | None = None) -> None:
    """Persist one step's data for flow_id. Idempotent: overwrites same (flow_id, step)."""
    from datetime import datetime, timezone
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO flow_state(flow_id, step, data, updated_at) VALUES (?, ?, ?, ?)",
            (flow_id, step, json.dumps(data, default=str), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def load_state(flow_id: str, step: str | None = None, db_path: str | Path | None = None) -> dict[str, Any] | None:
    """Load state for flow_id. If step=None, returns the latest step's data."""
    conn = _connect(db_path)
    try:
        if step is None:
            row = conn.execute(
                "SELECT data FROM flow_state WHERE flow_id=? ORDER BY updated_at DESC LIMIT 1",
                (flow_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT data FROM flow_state WHERE flow_id=? AND step=? ORDER BY updated_at DESC LIMIT 1",
                (flow_id, step),
            ).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()


def list_steps(flow_id: str, db_path: str | Path | None = None) -> list[str]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT step FROM flow_state WHERE flow_id=? ORDER BY updated_at", (flow_id,)
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def create_flow_meta(flow_id: str, inputs: dict[str, Any], db_path: str | Path | None = None) -> None:
    from datetime import datetime, timezone
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO flow_meta(flow_id, inputs, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (flow_id, json.dumps(inputs, default=str), "running",
             datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def update_flow_status(flow_id: str, status: str, db_path: str | Path | None = None) -> None:
    from datetime import datetime, timezone
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE flow_meta SET status=?, updated_at=? WHERE flow_id=?",
            (status, datetime.now(timezone.utc).isoformat(), flow_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_pending_flows(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return flows with status='running' or 'paused' — candidates for resume."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT flow_id, inputs, status, updated_at FROM flow_meta WHERE status IN ('running', 'paused') ORDER BY updated_at DESC"
        ).fetchall()
        return [{"flow_id": r[0], "inputs": json.loads(r[1]), "status": r[2], "updated_at": r[3]} for r in rows]
    finally:
        conn.close()
