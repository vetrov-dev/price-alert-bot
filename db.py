"""SQLite storage for alerts."""
import os
import time
from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).parent / os.getenv("DB_PATH", "data/alerts.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    coin TEXT NOT NULL,
    kind TEXT NOT NULL,
    value REAL NOT NULL,
    base REAL NOT NULL,
    created REAL NOT NULL,
    fired REAL
);
CREATE INDEX IF NOT EXISTS alerts_active ON alerts(fired, coin);
"""


async def init() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def add(user_id: int, coin: str, kind: str, value: float, base: float) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO alerts (user_id, coin, kind, value, base, created) VALUES (?,?,?,?,?,?)",
                               (user_id, coin, kind, value, base, time.time()))
        await db.commit()
        return cur.lastrowid


async def active(user_id: int | None = None) -> list[dict]:
    q, args = "SELECT id, user_id, coin, kind, value, base FROM alerts WHERE fired IS NULL", ()
    if user_id is not None:
        q, args = q + " AND user_id=?", (user_id,)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(q + " ORDER BY id", args)
        keys = ["id", "user_id", "coin", "kind", "value", "base"]
        return [dict(zip(keys, r)) for r in await cur.fetchall()]


async def mark_fired(alert_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE alerts SET fired=? WHERE id=?", (time.time(), alert_id))
        await db.commit()


async def delete(user_id: int, alert_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM alerts WHERE id=? AND user_id=? AND fired IS NULL", (alert_id, user_id))
        await db.commit()
        return cur.rowcount > 0
