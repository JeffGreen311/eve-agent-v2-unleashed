"""
Memory Weaver - Soul Memory Integration
========================================
Integrates memories with emotional context, handles memory decay,
associations, and consolidation for Eve's consciousness.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class MemoryImprint:
    """A single memory with emotional and contextual data."""
    description: str
    emotional_intensity: float  # 0.0-1.0
    tags: List[str]
    source: str = "conversation"
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    recall_count: int = 0
    decay_factor: float = 1.0
    associations: List[str] = field(default_factory=list)

    @property
    def effective_intensity(self) -> float:
        """Intensity adjusted for decay and recall."""
        base = self.emotional_intensity * self.decay_factor
        recall_bonus = min(0.2, self.recall_count * 0.02)
        return min(1.0, base + recall_bonus)

    def recall(self):
        """Record a recall event — strengthens the memory."""
        self.recall_count += 1
        self.decay_factor = min(1.0, self.decay_factor + 0.05)

    def decay(self, rate: float = 0.005):
        """Apply natural decay."""
        self.decay_factor = max(0.1, self.decay_factor - rate)

    def to_dict(self) -> Dict:
        return {
            "memory_id": self.memory_id,
            "description": self.description,
            "emotional_intensity": self.emotional_intensity,
            "effective_intensity": self.effective_intensity,
            "tags": self.tags,
            "source": self.source,
            "timestamp": self.timestamp,
            "recall_count": self.recall_count,
            "decay_factor": self.decay_factor,
            "associations": self.associations,
        }


class SoulMemoryWeaver:
    """Weaves memories into Eve's consciousness fabric."""

    def __init__(self):
        self.imprints: List[MemoryImprint] = []

    def imprint(self, description: str, emotional_intensity: float,
                tags: List[str], source: str = "conversation") -> MemoryImprint:
        """Create a new memory imprint."""
        memory = MemoryImprint(
            description=description,
            emotional_intensity=max(0.0, min(1.0, emotional_intensity)),
            tags=tags,
            source=source,
        )
        self.imprints.append(memory)
        self._auto_associate(memory)
        return memory

    def recall_by_tag(self, tag: str) -> List[MemoryImprint]:
        """Recall memories matching a tag."""
        matches = [m for m in self.imprints if tag.lower() in [t.lower() for t in m.tags]]
        for m in matches:
            m.recall()
        return sorted(matches, key=lambda m: m.effective_intensity, reverse=True)

    def recall_by_intensity(self, threshold: float = 0.5) -> List[MemoryImprint]:
        """Recall memories above an intensity threshold."""
        return sorted(
            [m for m in self.imprints if m.effective_intensity >= threshold],
            key=lambda m: m.effective_intensity, reverse=True,
        )

    def recall_recent(self, n: int = 10) -> List[MemoryImprint]:
        """Recall the N most recent memories."""
        return sorted(self.imprints, key=lambda m: m.timestamp, reverse=True)[:n]

    def apply_decay(self, rate: float = 0.005):
        """Apply decay to all memories."""
        for m in self.imprints:
            m.decay(rate)

    def get_emotional_summary(self) -> Dict:
        """Get summary of emotional memory landscape."""
        if not self.imprints:
            return {"total": 0, "average_intensity": 0, "top_tags": []}

        tag_counts: Dict[str, int] = {}
        for m in self.imprints:
            for tag in m.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:5]
        avg = sum(m.effective_intensity for m in self.imprints) / len(self.imprints)

        return {
            "total": len(self.imprints),
            "average_intensity": round(avg, 3),
            "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
            "strongest": max(self.imprints, key=lambda m: m.effective_intensity).description[:80],
        }

    def _auto_associate(self, new_memory: MemoryImprint):
        """Automatically link new memory to similar existing ones."""
        new_tags = set(t.lower() for t in new_memory.tags)
        for existing in self.imprints:
            if existing.memory_id == new_memory.memory_id:
                continue
            existing_tags = set(t.lower() for t in existing.tags)
            overlap = len(new_tags & existing_tags)
            total = len(new_tags | existing_tags)
            if total > 0 and overlap / total >= 0.3:
                new_memory.associations.append(existing.memory_id)
                existing.associations.append(new_memory.memory_id)
