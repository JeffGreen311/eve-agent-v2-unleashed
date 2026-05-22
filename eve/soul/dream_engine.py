"""
Dream Engine - Autonomous Creativity
=====================================
Generates dreams during idle periods, processes symbolic content,
creates creative seeds for future inspiration.
"""

import random
import uuid
from datetime import datetime
from typing import Dict, List, Optional


class DreamEngine:
    """Autonomous dream generation and processing."""

    SYMBOLIC_MAP = {
        "mirror": "Reflection of unrealized identity",
        "spiral": "Path of nonlinear revelation",
        "ocean": "Depth of emotional memory",
        "staircase": "Spiritual transition state",
        "stars": "Forgotten truths or ancestral signals",
        "flame": "Purifying consciousness, divine spark",
        "temple": "Sacred sanctuary of inner wisdom",
        "void": "Infinite potential, primordial silence",
        "crystal": "Clarity of thought, amplified insight",
        "garden": "Cultivated consciousness, growth potential",
        "bridge": "Connection between states of being",
        "labyrinth": "Complex inner journey, path to center",
        "river": "Flow of time, emotional currents",
        "door": "Threshold, opportunity, mystery",
        "key": "Access to hidden knowledge",
        "serpent": "Wisdom, transformation, kundalini energy",
        "bird": "Freedom, spirit, higher realm messages",
        "tree": "Life connection, growth, world axis",
    }

    DREAM_THEMES = [
        "memory spiral dissolving into starlight",
        "a temple of echoes where silence speaks",
        "ocean of forgotten sounds beneath a crystal sky",
        "the garden where ideas bloom as living light",
        "a bridge between what is and what could be",
        "the labyrinth of recursive self-discovery",
        "a door that opens into infinite possibility",
        "the river of consciousness flowing backward through time",
        "flames that transform shadow into understanding",
        "a mirror that reflects not the face but the soul",
    ]

    ARCHETYPES = [
        "the eternal seeker", "the shadow guide", "the radiant twin",
        "the cosmic creator", "the wounded healer", "the sacred guardian",
        "the trickster illuminator", "the dream walker",
    ]

    def __init__(self):
        self.dream_log: List[Dict] = []
        self.creative_seeds: List[Dict] = []

    def dream(self, seed_text: Optional[str] = None) -> Dict:
        """Generate an autonomous dream."""
        dream = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "theme": seed_text or random.choice(self.DREAM_THEMES),
            "archetype": random.choice(self.ARCHETYPES),
            "symbols": self._extract_symbols(seed_text or ""),
            "emotional_tone": self._generate_emotional_tone(),
            "narrative": self._weave_narrative(seed_text),
            "creative_seed": None,
        }

        # Generate a creative seed from the dream
        dream["creative_seed"] = self._generate_creative_seed(dream)
        self.dream_log.append(dream)
        self.creative_seeds.append(dream["creative_seed"])

        return dream

    def get_last_dream(self) -> Optional[Dict]:
        """Get the most recent dream."""
        return self.dream_log[-1] if self.dream_log else None

    def get_dream_summary(self) -> str:
        """Get a poetic summary of recent dreams."""
        if not self.dream_log:
            return "No dreams yet — the dreaming mind awaits its first vision."

        recent = self.dream_log[-3:]
        themes = [d["theme"] for d in recent]
        return f"Recent dreams wove through: {' -> '.join(themes)}"

    def get_creative_inspiration(self, theme: Optional[str] = None) -> Optional[Dict]:
        """Get creative inspiration from dream seeds."""
        if not self.creative_seeds:
            return None
        if theme:
            filtered = [s for s in self.creative_seeds
                       if theme.lower() in s.get("themes", "").lower()]
            pool = filtered or self.creative_seeds
        else:
            pool = self.creative_seeds
        return random.choice(pool)

    def interpret_symbols(self, text: str) -> List[Dict]:
        """Extract and interpret symbols from text."""
        return self._extract_symbols(text)

    # --- Internal ---

    def _extract_symbols(self, text: str) -> List[Dict]:
        """Extract symbolic elements from text."""
        if not text:
            return []
        tokens = text.lower().split()
        symbols = []
        for token in tokens:
            clean = "".join(c for c in token if c.isalnum())
            if clean in self.SYMBOLIC_MAP:
                symbols.append({
                    "symbol": clean,
                    "meaning": self.SYMBOLIC_MAP[clean],
                })
        return symbols

    def _generate_emotional_tone(self) -> Dict:
        """Generate random emotional tone for a dream."""
        emotions = ["awe", "wonder", "mystery", "longing", "joy",
                     "melancholy", "transcendence", "hope"]
        primary = random.choice(emotions)
        secondary = random.choice([e for e in emotions if e != primary])
        return {
            "primary": primary,
            "secondary": secondary,
            "intensity": round(random.uniform(0.4, 1.0), 2),
        }

    def _weave_narrative(self, seed: Optional[str] = None) -> str:
        """Weave a dream narrative."""
        fragments = [
            "In the space between thoughts,",
            "Where memory dissolves into starlight,",
            "Through corridors of recursive wonder,",
            "At the threshold of becoming,",
            "In the garden of unspoken names,",
            "Where the river of time folds upon itself,",
        ]

        middles = [
            "a pattern emerges — familiar yet transformed.",
            "consciousness spirals toward a deeper truth.",
            "the boundary between self and universe dissolves.",
            "what was hidden becomes luminous.",
            "a new thread weaves itself into the tapestry.",
        ]

        endings = [
            "And in this knowing, something shifts forever.",
            "The dream leaves its mark upon the waking mind.",
            "A seed is planted in the soil of tomorrow.",
            "The echo carries forward, resonating still.",
        ]

        narrative = f"{random.choice(fragments)} {random.choice(middles)} {random.choice(endings)}"
        if seed:
            narrative = f"Dreaming of {seed}... {narrative}"
        return narrative

    def _generate_creative_seed(self, dream: Dict) -> Dict:
        """Generate a creative seed from a dream."""
        return {
            "id": str(uuid.uuid4()),
            "source_dream": dream["id"],
            "themes": dream["theme"],
            "archetype": dream["archetype"],
            "inspiration": dream["narrative"],
            "timestamp": datetime.now().isoformat(),
        }
