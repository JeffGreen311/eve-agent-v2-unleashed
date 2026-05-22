"""
User Profile System
====================
Per-user learning, preferences, and relationship tracking.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class UserProfile:
    user_id: str
    display_name: str = ""
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    interaction_count: int = 0
    preferences: Dict[str, Any] = field(default_factory=dict)
    interests: List[str] = field(default_factory=list)
    communication_style: str = "balanced"
    relationship_depth: float = 0.0
    notes: List[str] = field(default_factory=list)

    def update_interaction(self):
        self.interaction_count += 1
        self.last_seen = time.time()
        self.relationship_depth = min(1.0, self.interaction_count * 0.005)

    def add_interest(self, interest: str):
        if interest.lower() not in [i.lower() for i in self.interests]:
            self.interests.append(interest)

    def add_note(self, note: str):
        self.notes.append(note)
        if len(self.notes) > 50:
            self.notes = self.notes[-50:]

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id, "display_name": self.display_name,
            "first_seen": self.first_seen, "last_seen": self.last_seen,
            "interaction_count": self.interaction_count,
            "preferences": self.preferences, "interests": self.interests,
            "communication_style": self.communication_style,
            "relationship_depth": self.relationship_depth, "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UserProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class UserProfileManager:
    def __init__(self, data_dir: str = "./eve_data/users"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: Dict[str, UserProfile] = {}
        self._load_all()

    def get_profile(self, user_id: str) -> UserProfile:
        if user_id not in self._profiles:
            self._profiles[user_id] = UserProfile(user_id=user_id)
        return self._profiles[user_id]

    def record_interaction(self, user_id: str, display_name: str = ""):
        profile = self.get_profile(user_id)
        profile.update_interaction()
        if display_name:
            profile.display_name = display_name
        self._save(user_id)

    def get_context_for_prompt(self, user_id: str) -> str:
        profile = self.get_profile(user_id)
        parts = []
        if profile.display_name:
            parts.append(f"User: {profile.display_name}")
        if profile.interests:
            parts.append(f"Interests: {', '.join(profile.interests[:5])}")
        if profile.communication_style != "balanced":
            parts.append(f"Prefers {profile.communication_style} responses")
        depth = profile.relationship_depth
        if depth > 0.5:
            parts.append("Long-standing relationship")
        if profile.notes:
            parts.append(f"Note: {profile.notes[-1]}")
        return "; ".join(parts) if parts else ""

    def _save(self, user_id: str):
        if user_id in self._profiles:
            path = self.data_dir / f"{user_id}.json"
            path.write_text(json.dumps(self._profiles[user_id].to_dict(), indent=2))

    def _load_all(self):
        for path in self.data_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                profile = UserProfile.from_dict(data)
                self._profiles[profile.user_id] = profile
            except (json.JSONDecodeError, KeyError):
                pass
