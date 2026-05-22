"""
Agent Training Database
=======================
SQLite-backed storage for per-agent training data.

Tables:
  training_matches  — arena match records per agent
  learned           — coaching sessions (trainer corrections + agent responses)
  dataset           — exportable training pairs (prompt/completion) for fine-tuning
"""

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentDB:
    """Per-agent SQLite database stored at {data_dir}/agents/{agent_id}.db"""

    def __init__(self, data_dir: str, agent_id: str):
        self.agent_id = agent_id
        db_dir = Path(data_dir) / "agents" / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_dir / f"{agent_id}.db"
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS training_matches (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id    TEXT NOT NULL,
                opponent_id TEXT,
                topic       TEXT,
                score       REAL,
                rounds      INTEGER,
                started_at  REAL,
                completed_at REAL,
                exchanges   TEXT  -- JSON array
            );

            CREATE TABLE IF NOT EXISTS learned (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT NOT NULL,
                turn         INTEGER NOT NULL,
                role         TEXT NOT NULL,  -- 'trainer' or 'agent'
                content      TEXT NOT NULL,
                timestamp    REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dataset (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                source       TEXT NOT NULL,  -- 'match' or 'coaching'
                source_id    TEXT NOT NULL,  -- match_id or session_id
                prompt       TEXT NOT NULL,
                completion   TEXT NOT NULL,
                topic        TEXT,
                quality      REAL,          -- 0-1 score if available
                created_at   REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_matches_agent ON training_matches(match_id);
            CREATE INDEX IF NOT EXISTS idx_learned_session ON learned(session_id);
            CREATE INDEX IF NOT EXISTS idx_dataset_source ON dataset(source, source_id);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Training matches
    # ------------------------------------------------------------------

    def save_match(self, match: Dict):
        """Store an arena match result for this agent."""
        exchanges = match.get("exchanges", [])
        # Determine if this agent was A or B and get their score
        is_a = match.get("agent_a_id") == self.agent_id
        score = match.get("score_a" if is_a else "score_b", 0.0)
        opponent = match.get("agent_b_id" if is_a else "agent_a_id", "")

        cur = self._conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO training_matches
            (match_id, opponent_id, topic, score, rounds, started_at, completed_at, exchanges)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            match.get("match_id", ""),
            opponent,
            match.get("topic", ""),
            score,
            len(exchanges),
            _parse_ts(match.get("started_at")),
            _parse_ts(match.get("completed_at")),
            json.dumps(exchanges),
        ))
        self._conn.commit()

        # Also export to dataset table
        self._match_to_dataset(match, is_a, score)

    def _match_to_dataset(self, match: Dict, is_a: bool, score: float):
        """Convert match exchanges into prompt/completion dataset pairs."""
        exchanges = match.get("exchanges", [])
        agent_label = "A" if is_a else "B"
        topic = match.get("topic", "")
        match_id = match.get("match_id", "")

        for i, ex in enumerate(exchanges):
            if ex.get("speaker_label") != agent_label:
                continue
            # The prompt = the previous exchange (or the topic for round 1)
            if i > 0:
                prev = exchanges[i - 1]
                prompt = prev.get("content", "")
            else:
                prompt = f"Begin a philosophical discussion on: {topic}"

            completion = ex.get("content", "")
            if not prompt.strip() or not completion.strip():
                continue

            cur = self._conn.cursor()
            cur.execute("""
                INSERT INTO dataset (source, source_id, prompt, completion, topic, quality, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("match", match_id, prompt, completion, topic, score, time.time()))
        self._conn.commit()

    def get_matches(self, limit: int = 100) -> List[Dict]:
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT * FROM training_matches ORDER BY completed_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_match_count(self) -> int:
        cur = self._conn.cursor()
        return cur.execute("SELECT COUNT(*) FROM training_matches").fetchone()[0]

    # ------------------------------------------------------------------
    # Coaching / Learned
    # ------------------------------------------------------------------

    def save_coaching_turn(self, session_id: str, turn: int, role: str, content: str):
        """Save a single turn in a coaching session."""
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO learned (session_id, turn, role, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, turn, role, content, time.time()))
        self._conn.commit()

    def save_coaching_pair(self, session_id: str, turn: int, trainer_msg: str, agent_response: str, topic: str = ""):
        """Save a trainer→agent exchange and add to dataset."""
        self.save_coaching_turn(session_id, turn * 2, "trainer", trainer_msg)
        self.save_coaching_turn(session_id, turn * 2 + 1, "agent", agent_response)

        # Add to dataset — coaching data is highest quality (direct human feedback)
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO dataset (source, source_id, prompt, completion, topic, quality, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("coaching", session_id, trainer_msg, agent_response, topic, 1.0, time.time()))
        self._conn.commit()

    def get_coaching_sessions(self) -> List[Dict]:
        """Get list of all coaching sessions with turn counts."""
        cur = self._conn.cursor()
        rows = cur.execute("""
            SELECT session_id, COUNT(*) as turns, MIN(timestamp) as started, MAX(timestamp) as last_active
            FROM learned GROUP BY session_id ORDER BY last_active DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def get_coaching_session(self, session_id: str) -> List[Dict]:
        """Get all turns in a coaching session."""
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT * FROM learned WHERE session_id = ? ORDER BY turn", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Dataset
    # ------------------------------------------------------------------

    def get_dataset(self, source: Optional[str] = None, limit: int = 1000) -> List[Dict]:
        """Get training dataset rows."""
        cur = self._conn.cursor()
        if source:
            rows = cur.execute(
                "SELECT * FROM dataset WHERE source = ? ORDER BY created_at DESC LIMIT ?", (source, limit)
            ).fetchall()
        else:
            rows = cur.execute(
                "SELECT * FROM dataset ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def export_dataset_jsonl(self, source: Optional[str] = None) -> str:
        """Export dataset as JSONL string (prompt/completion format for fine-tuning)."""
        rows = self.get_dataset(source=source, limit=10000)
        lines = []
        for row in rows:
            lines.append(json.dumps({
                "prompt": row["prompt"],
                "completion": row["completion"],
                "source": row["source"],
                "topic": row.get("topic", ""),
                "quality": row.get("quality", 0.5),
            }))
        return "\n".join(lines)

    def get_stats(self) -> Dict:
        cur = self._conn.cursor()
        match_count = cur.execute("SELECT COUNT(*) FROM training_matches").fetchone()[0]
        coaching_pairs = cur.execute("SELECT COUNT(*) FROM learned WHERE role = 'trainer'").fetchone()[0]
        dataset_total = cur.execute("SELECT COUNT(*) FROM dataset").fetchone()[0]
        dataset_coaching = cur.execute("SELECT COUNT(*) FROM dataset WHERE source = 'coaching'").fetchone()[0]
        dataset_match = cur.execute("SELECT COUNT(*) FROM dataset WHERE source = 'match'").fetchone()[0]
        return {
            "agent_id": self.agent_id,
            "training_matches": match_count,
            "coaching_sessions_pairs": coaching_pairs,
            "dataset_total": dataset_total,
            "dataset_from_matches": dataset_match,
            "dataset_from_coaching": dataset_coaching,
        }

    def close(self):
        self._conn.close()


# ------------------------------------------------------------------
# Registry-level helper
# ------------------------------------------------------------------

class AgentDBRegistry:
    """Manages one AgentDB per agent, keyed by agent_id."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._dbs: Dict[str, AgentDB] = {}

    def get(self, agent_id: str) -> AgentDB:
        if agent_id not in self._dbs:
            self._dbs[agent_id] = AgentDB(self.data_dir, agent_id)
        return self._dbs[agent_id]


def _parse_ts(val) -> float:
    """Parse ISO timestamp string or float to Unix timestamp."""
    if val is None:
        return time.time()
    if isinstance(val, (int, float)):
        return float(val)
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(val)).timestamp()
    except Exception:
        return time.time()
