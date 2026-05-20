import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("/app/data/history.db")


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS game_sessions (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id           TEXT    NOT NULL,
                created_at        TEXT    NOT NULL,
                ended_at          TEXT    NOT NULL,
                num_hands         INTEGER DEFAULT 0,
                small_blind       INTEGER,
                big_blind         INTEGER,
                starting_stack    INTEGER,
                players_json      TEXT,
                hand_history_json TEXT
            )
        """)
        # migrate existing DBs that pre-date the hand_history_json column
        try:
            con.execute("ALTER TABLE game_sessions ADD COLUMN hand_history_json TEXT")
        except Exception:
            pass
        con.commit()
    logger.info(f"History DB ready at {DB_PATH}")


def save_session(room_id: str, created_at: str, num_hands: int,
                 small_blind: int, big_blind: int, starting_stack: int,
                 players: list[dict], hand_history: list[dict] | None = None):
    ended_at = datetime.now(timezone.utc).isoformat()
    with _conn() as con:
        con.execute(
            """INSERT INTO game_sessions
               (room_id, created_at, ended_at, num_hands,
                small_blind, big_blind, starting_stack, players_json, hand_history_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (room_id, created_at, ended_at, num_hands,
             small_blind, big_blind, starting_stack,
             json.dumps(players),
             json.dumps(hand_history or [])),
        )
        con.commit()
    logger.info(f"Session {room_id} saved: {num_hands} hands, {len(players)} players")


def get_history(limit: int = 50) -> list[dict]:
    try:
        with _conn() as con:
            rows = con.execute(
                "SELECT id, room_id, created_at, ended_at, num_hands, "
                "small_blind, big_blind, starting_stack, players_json "
                "FROM game_sessions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["players"] = json.loads(d.pop("players_json") or "[]")
            result.append(d)
        return result
    except Exception as e:
        logger.error(f"get_history error: {e}")
        return []


def get_session(session_id: int) -> dict | None:
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT * FROM game_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["players"] = json.loads(d.pop("players_json") or "[]")
        d["hand_history"] = json.loads(d.pop("hand_history_json") or "[]")
        return d
    except Exception as e:
        logger.error(f"get_session error: {e}")
        return None
