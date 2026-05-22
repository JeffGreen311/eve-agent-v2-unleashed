"""
Conversation Memory
====================
Short-term, medium-term, and long-term conversation tracking.
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ConversationTurn:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


class ConversationMemory:
    """Multi-tier conversation memory."""

    def __init__(self, max_short_term: int = 50, max_medium_term: int = 200):
        self.max_short_term = max_short_term
        self.max_medium_term = max_medium_term
        self.short_term: List[ConversationTurn] = []
        self.medium_term: List[Dict] = []
        self.session_id: Optional[str] = None
        self.session_start: float = time.time()
        self.turn_count: int = 0

    def add_turn(self, role: str, content: str, metadata: Optional[Dict] = None):
        turn = ConversationTurn(role=role, content=content, metadata=metadata or {})
        self.short_term.append(turn)
        self.turn_count += 1

        if len(self.short_term) > self.max_short_term:
            overflow = self.short_term[:10]
            self.short_term = self.short_term[10:]
            self.medium_term.append({
                "type": "overflow", "turns": len(overflow),
                "summary": self._summarize(overflow), "timestamp": time.time(),
            })

    def get_context_window(self, max_turns: int = 20) -> List[Dict]:
        recent = self.short_term[-max_turns:]
        return [{"role": t.role, "content": t.content} for t in recent]

    def get_full_history(self) -> List[Dict]:
        return [{"role": t.role, "content": t.content, "timestamp": t.timestamp}
                for t in self.short_term]

    def start_new_session(self, session_id: Optional[str] = None):
        if self.short_term:
            self.medium_term.append({
                "type": "session", "session_id": self.session_id,
                "turns": len(self.short_term),
                "summary": self._summarize(self.short_term[-5:]),
                "start": self.session_start, "end": time.time(),
            })
            if len(self.medium_term) > self.max_medium_term:
                self.medium_term = self.medium_term[-self.max_medium_term:]

        self.short_term = []
        self.session_id = session_id or f"session_{int(time.time())}"
        self.session_start = time.time()
        self.turn_count = 0

    def get_session_summary(self) -> Dict:
        return {
            "session_id": self.session_id,
            "turns": self.turn_count,
            "duration_minutes": round((time.time() - self.session_start) / 60, 1),
        }

    def _summarize(self, turns: List[ConversationTurn]) -> str:
        contents = [t.content[:100] for t in turns if t.role == "user"]
        return " | ".join(contents[:3])
