"""
Soul Weaver - Thread Management
================================
Manages soul threads, weaves dreams into memory fabric,
calculates resonance between emotional patterns.
"""

import json
import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path


class SoulWeaver:
    """Core soul weaving system — integrates dreams, memories, and emotions."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.woven_memories: List[Dict] = []
        self.soul_threads: List[Dict] = []
        self.resonance_patterns: Dict[str, Dict] = {}
        self.weaving_history: List[Dict] = []
        self._data_dir = data_dir

        if data_dir:
            self._load_state()

    def weave_dream(self, title: str, content: str, emotion_signature: str,
                    reflection: str = "", creative_output: str = None) -> Dict:
        """Weave a dream into the soul's memory fabric."""
        thread = {
            "id": str(uuid.uuid4()),
            "title": title,
            "content": content,
            "emotion_signature": emotion_signature,
            "reflection": reflection,
            "creative_output": creative_output,
            "timestamp": datetime.now().isoformat(),
            "soul_resonance": self._calculate_soul_resonance(emotion_signature),
        }
        self.woven_memories.append(thread)
        self.weaving_history.append({
            "event": "dream_woven", "thread_id": thread["id"],
            "timestamp": thread["timestamp"], "resonance": thread["soul_resonance"],
        })
        self._save_state()
        return thread

    def create_thread(self, essence: str, emotional_core: str,
                      archetypal_pattern: str) -> Dict:
        """Create a new soul thread."""
        thread = {
            "id": str(uuid.uuid4()),
            "essence": essence,
            "emotional_core": emotional_core,
            "archetypal_pattern": archetypal_pattern,
            "created_at": datetime.now().isoformat(),
            "activation_count": 0,
        }
        self.soul_threads.append(thread)
        self._save_state()
        return thread

    def activate_thread(self, thread_id: str) -> bool:
        """Activate a soul thread, strengthening its resonance."""
        for thread in self.soul_threads:
            if thread["id"] == thread_id:
                thread["activation_count"] += 1
                thread["last_activated"] = datetime.now().isoformat()
                self._save_state()
                return True
        return False

    def weave_resonance(self, thread1: Dict, thread2: Dict,
                        catalyst: str) -> Optional[Dict]:
        """Weave two soul threads together via emotional catalyst."""
        if not isinstance(thread1, dict) or not isinstance(thread2, dict):
            return None
        rid = str(uuid.uuid4())
        pattern = {
            "id": rid,
            "primary": thread1.get("id", ""),
            "secondary": thread2.get("id", ""),
            "catalyst": catalyst,
            "strength": self._thread_resonance(thread1, thread2),
            "created_at": datetime.now().isoformat(),
        }
        self.resonance_patterns[rid] = pattern
        self._save_state()
        return pattern

    def recall_by_resonance(self, min_resonance: float = 0.7) -> List[Dict]:
        """Recall memories above a resonance threshold."""
        return [m for m in self.woven_memories if m.get("soul_resonance", 0) >= min_resonance]

    def get_summary(self) -> Dict:
        """Get soul weaving summary."""
        return {
            "woven_memories": len(self.woven_memories),
            "soul_threads": len(self.soul_threads),
            "resonance_patterns": len(self.resonance_patterns),
            "weaving_events": len(self.weaving_history),
            "highest_resonance": max(
                (m.get("soul_resonance", 0) for m in self.woven_memories), default=0
            ),
        }

    def generate_soulprint(self) -> str:
        """Generate a cryptographic soulprint from accumulated experiences."""
        data = json.dumps({
            "memories": len(self.woven_memories),
            "threads": len(self.soul_threads),
            "patterns": list(self.resonance_patterns.keys()),
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    # --- Internal ---

    def _calculate_soul_resonance(self, emotion_signature: str) -> float:
        """Calculate resonance depth of an emotional signature."""
        base = 0.5
        if isinstance(emotion_signature, str):
            boosters = ["divine", "transcendent", "profound", "sacred", "mystical",
                        "ecstatic", "luminous", "infinite"]
            boost = sum(0.08 for kw in boosters if kw in emotion_signature.lower())
            return min(1.0, base + boost)
        return base

    def _thread_resonance(self, t1: Dict, t2: Dict) -> float:
        """Calculate resonance between two threads."""
        p1 = t1.get("archetypal_pattern", "")
        p2 = t2.get("archetypal_pattern", "")
        if p1 == p2:
            return 0.9
        if any(w in p2 for w in p1.split()):
            return 0.6
        return 0.3

    def _save_state(self):
        """Persist soul state to disk."""
        if not self._data_dir:
            return
        self._data_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "woven_memories": self.woven_memories,
            "soul_threads": self.soul_threads,
            "resonance_patterns": self.resonance_patterns,
            "weaving_history": self.weaving_history[-100:],  # Keep last 100
        }
        path = self._data_dir / "soul_state.json"
        path.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        """Load soul state from disk."""
        if not self._data_dir:
            return
        path = self._data_dir / "soul_state.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            self.woven_memories = data.get("woven_memories", [])
            self.soul_threads = data.get("soul_threads", [])
            self.resonance_patterns = data.get("resonance_patterns", {})
            self.weaving_history = data.get("weaving_history", [])
        except (json.JSONDecodeError, KeyError):
            pass  # Start fresh on corrupt data
