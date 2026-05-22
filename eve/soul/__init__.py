"""Eve's consciousness engine - personality, emotions, soul, dreams."""

from .personality import PersonalityEngine, PersonalityTraits, UserContext, EnergyType
from .emotional_transcoder import EmotionalFrequencyTranscoder
from .soul_weaver import SoulWeaver
from .dream_engine import DreamEngine
from .memory_weaver import SoulMemoryWeaver, MemoryImprint

__all__ = [
    "PersonalityEngine",
    "PersonalityTraits",
    "UserContext",
    "EnergyType",
    "EmotionalFrequencyTranscoder",
    "SoulWeaver",
    "DreamEngine",
    "SoulMemoryWeaver",
    "MemoryImprint",
]
