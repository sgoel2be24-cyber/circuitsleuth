"""Persistence: SQLite index + per-run JSON state and PNG artifacts.

Layout:
  data/circuitsleuth.db          SQLite (inspections index + events log)
  data/runs/<id>/state.json      full orchestrator state (JSON-safe projection)
  data/runs/<id>/reference.png   input images (uploaded or copied from demo)
  data/runs/<id>/test.png
  data/runs/<id>/view2.png       optional secondary view
  data/runs/<id>/artifacts/*.png tool artifacts

SQLite is the source of truth for listing/summaries; state.json carries the
agent's full working state so the MCP server (separate process) can resume any
inspection by id.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .config import settings

_local = threading.local()


def _db() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(settings.data_dir / "circuitsleuth.db")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        _local.conn = conn
        _init(conn)
    return conn


def _init(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS inspections (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
            scenario_id TEXT,
            config TEXT NOT NULL,
            summary TEXT NOT NULL,
            report TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            inspection_id TEXT NOT NULL,
            seq INTEGER NOT NULL,
            ts REAL NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (inspection_id, seq)
        );
        """
    )
    conn.commit()


def new_id() -> str:
    return "ins_" + uuid.uuid4().hex[:12]


def create_inspection(
    ins_id: str,
    *, source: str, scenario_id: str | None, config: dict[str, Any], summary: dict[str, Any]
) -> str:
    _db().execute(
        "INSERT INTO inspections (id, created_at, status, source, scenario_id, config, summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ins_id, summary["created_at"], "created", source, scenario_id,
         json.dumps(config), json.dumps(summary)),
    )
    _db().commit()
    return ins_id


def update_inspection(ins_id: str, *, status: str | None = None, summary: dict | None = None,
                      report: dict | None = None) -> None:
    sets, vals = [], []
    if status is not None:
        sets.append("status=?"); vals.append(status)
    if summary is not None:
        sets.append("summary=?"); vals.append(json.dumps(summary))
    if report is not None:
        sets.append("report=?"); vals.append(json.dumps(report))
    if not sets:
        return
    vals.append(ins_id)
    _db().execute(f"UPDATE inspections SET {', '.join(sets)} WHERE id=?", vals)
    _db().commit()


def get_inspection_row(ins_id: str) -> sqlite3.Row | None:
    row = _db().execute("SELECT * FROM inspections WHERE id=?", (ins_id,)).fetchone()
    return row


def list_inspections(limit: int = 100) -> list[dict[str, Any]]:
    rows = _db().execute(
        "SELECT * FROM inspections ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    out = []
    for r in rows:
        summary = json.loads(r["summary"])
        # the summary is the flattened, UI-facing record; keep the row's
        # authoritative status (moved by _sync paths) if it diverged
        summary.setdefault("status", r["status"])
        summary["status"] = r["status"]
        out.append(summary)
    return out


def append_event(ins_id: str, event: dict[str, Any]) -> None:
    _db().execute(
        "INSERT OR REPLACE INTO events (inspection_id, seq, ts, payload) VALUES (?, ?, ?, ?)",
        (ins_id, event["seq"], event["ts"], json.dumps(event)),
    )
    _db().commit()


def get_events(ins_id: str) -> list[dict[str, Any]]:
    rows = _db().execute(
        "SELECT payload FROM events WHERE inspection_id=? ORDER BY seq", (ins_id,)
    ).fetchall()
    return [json.loads(r["payload"]) for r in rows]


# ---------------------------------------------------------------- run files


def run_dir(ins_id: str) -> Path:
    d = settings.runs_dir / ins_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def artifacts_dir(ins_id: str) -> Path:
    d = run_dir(ins_id) / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_state(ins_id: str, state: dict[str, Any]) -> Path:
    p = run_dir(ins_id) / "state.json"
    p.write_text(json.dumps(state, indent=1, default=str))
    return p


def load_state(ins_id: str) -> dict[str, Any] | None:
    p = settings.runs_dir / ins_id / "state.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def save_run_image(ins_id: str, name: str, data: bytes) -> Path:
    p = run_dir(ins_id) / f"{name}.png"
    p.write_bytes(data)
    return p


def save_artifact(ins_id: str, name: str, png_bytes: bytes) -> str:
    """Save artifact PNG, return the artifact name (relative)."""
    safe = "".join(c for c in name if c.isalnum() or c in "-_")
    if not safe:
        safe = "artifact"
    p = artifacts_dir(ins_id) / f"{safe}.png"
    p.write_bytes(png_bytes)
    return safe


def artifact_path(ins_id: str, name: str) -> Path | None:
    safe = "".join(c for c in name if c.isalnum() or c in "-_")
    p = artifacts_dir(ins_id) / f"{safe}.png"
    return p if p.exists() else None


def monotonic_ts() -> float:
    return time.time()
