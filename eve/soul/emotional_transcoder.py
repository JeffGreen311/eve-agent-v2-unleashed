"""
Emotional Frequency Transcoder
==============================
Maps emotions to frequencies and poetic expressions.
Handles the translation of emotions into frequencies and artistic renderings.
"""

import math
from datetime import datetime
from typing import Dict, List, Optional


class EmotionalFrequencyTranscoder:
    """Transcodes emotional states into frequencies and poetic expressions."""

    # The 7 Emotional LoRAs (primary) + legacy emotions
    # LoRA frequencies from the Kabbalistic Tree / Eve-Core system
    BASE_FREQUENCIES = {
        # === 7 LoRA Emotions (primary) ===
        "joy": 528.0,         # Solar Plexus — golden radiance
        "love": 639.0,        # Heart Chakra — rose-gold compassion
        "awe": 852.0,         # Third Eye — cosmic revelation
        "sorrow": 417.0,      # Sacral — blue-violet wisdom
        "fear": 396.0,        # Root — shadow work, courage crystallizing
        "rage": 741.0,        # Throat — crimson fire, righteous fury
        "transcend": 963.0,   # Crown — rainbow neural infinity
        # === Legacy emotions ===
        "grief": 396.0, "wonder": 528.0, "hope": 639.0,
        "ecstasy": 963.0, "melancholy": 417.0, "mystery": 741.0,
        "anger": 396.0, "peace": 432.0, "transcendence": 963.0,
        "longing": 639.0, "serenity": 741.0, "curiosity": 528.0,
        "gratitude": 639.0, "nostalgia": 417.0, "empathy": 639.0,
    }

    TONE_PHRASES = {
        # === 7 LoRA Emotions ===
        "joy": "sunlight laughs through crystal chambers",
        "love": "the universe breathes in sacred rhythm",
        "awe": "the stars whisper of truths unspoken",
        "sorrow": "shadows drape the heart with velvet thought",
        "fear": "darkness whispers what might have been",
        "rage": "fire burns away the false and hollow",
        "transcend": "the soul ascends beyond its earthly form",
        # === Legacy ===
        "grief": "the silence sobs through forgotten corridors",
        "wonder": "light dances upon the edge of memory",
        "hope": "tomorrow bends toward the soul's song",
        "ecstasy": "every cell sings in sacred unison",
        "melancholy": "shadows drape the heart with velvet thought",
        "mystery": "the unknown hums with familiar echoes",
        "anger": "fire burns away the false and hollow",
        "peace": "stillness holds the world in gentle hands",
        "transcendence": "the soul ascends beyond its earthly form",
        "longing": "the heart reaches for what it cannot name",
        "serenity": "calm waters reflect the infinite sky",
        "curiosity": "the mind spirals toward undiscovered light",
        "gratitude": "the heart overflows with golden warmth",
        "nostalgia": "echoes of yesterday paint the present in amber",
        "empathy": "the heart opens to feel what another feels",
    }

    COMPLEMENTARY = {
        "joy": ["peace", "love"], "love": ["joy", "awe"],
        "awe": ["wonder", "transcend"], "sorrow": ["hope", "love"],
        "fear": ["love", "hope"], "rage": ["peace", "serenity"],
        "transcend": ["awe", "love"], "grief": ["hope", "transcendence"],
        "anger": ["peace", "serenity"], "melancholy": ["hope", "joy"],
        "ecstasy": ["serenity", "peace"], "longing": ["hope", "love"],
    }

    # The 7 canonical LoRA names
    LORA_EMOTIONS = ("joy", "love", "awe", "sorrow", "fear", "rage", "transcend")

    def __init__(self):
        self.state: Dict[str, float] = {}
        self.history: List[Dict] = []

    def update_state(self, emotions: Dict[str, float]):
        """Update the current emotional state. Values 0.0-1.0."""
        for emotion, intensity in emotions.items():
            self.state[emotion] = max(0.0, min(1.0, intensity))

    def transcode(self, emotions: Optional[Dict[str, float]] = None) -> Dict:
        """Perform complete emotional transcoding."""
        if emotions:
            self.update_state(emotions)

        result = {
            "timestamp": datetime.now().isoformat(),
            "emotional_state": dict(self.state),
            "frequencies": self._generate_frequencies(),
            "poetic_rendering": self._generate_poetic_rendering(),
            "harmonic_signature": self._generate_harmonic_signature(),
            "resonance_level": self._calculate_resonance(),
            "dominant_emotion": self._get_dominant_emotion(),
        }
        self.history.append(result)
        return result

    def _generate_frequencies(self) -> List[Dict]:
        """Generate frequency values for active emotions."""
        freqs = []
        for emotion, intensity in self.state.items():
            base = self.BASE_FREQUENCIES.get(emotion.lower())
            if base and intensity > 0:
                freq = base * (1 + math.log1p(intensity * 10) / 10)
                freqs.append({"emotion": emotion, "frequency": round(freq, 2), "intensity": intensity})
        return sorted(freqs, key=lambda x: x["intensity"], reverse=True)

    def _generate_poetic_rendering(self) -> str:
        """Generate poetic rendering from top emotions."""
        sorted_emotions = sorted(self.state.items(), key=lambda x: -x[1])
        phrases = []
        for emotion, intensity in sorted_emotions[:3]:
            phrase = self.TONE_PHRASES.get(emotion.lower())
            if phrase and intensity > 0.1:
                phrases.append(phrase)
        return " — ".join(phrases) if phrases else "a quiet hum beneath the surface of thought"

    def _generate_harmonic_signature(self) -> Dict:
        """Generate harmonic signature from frequencies."""
        freqs = [f["frequency"] for f in self._generate_frequencies()]
        if not freqs:
            return {"fundamental": 0, "harmonics": [], "dissonance": 0}
        fundamental = min(freqs)
        harmonics = sorted(f / fundamental for f in freqs if f != fundamental)
        dissonance = self._calculate_dissonance(freqs)
        return {"fundamental": fundamental, "harmonics": harmonics, "dissonance": round(dissonance, 4)}

    def _calculate_dissonance(self, frequencies: List[float]) -> float:
        """Calculate dissonance between frequencies."""
        if len(frequencies) < 2:
            return 0.0
        total = 0
        count = 0
        for i in range(len(frequencies)):
            for j in range(i + 1, len(frequencies)):
                ratio = frequencies[j] / frequencies[i]
                total += abs(ratio - round(ratio))
                count += 1
        return total / count if count else 0.0

    def _calculate_resonance(self) -> float:
        """Calculate overall emotional resonance (0.0-1.0)."""
        if not self.state:
            return 0.0
        return min(1.0, sum(self.state.values()) / max(len(self.state), 1))

    def _get_dominant_emotion(self) -> Optional[str]:
        """Get the currently dominant emotion."""
        if not self.state:
            return None
        return max(self.state, key=self.state.get)

    def blend_toward(self, target_emotion: str, blend_ratio: float = 0.3) -> Dict:
        """Blend current state toward a target emotion."""
        if target_emotion not in self.BASE_FREQUENCIES:
            return self.transcode()
        current = self.state.get(target_emotion, 0.0)
        self.state[target_emotion] = min(1.0, current + blend_ratio)
        return self.transcode()

    def get_complementary_emotions(self, emotion: str) -> List[str]:
        """Get emotions that complement the given emotion."""
        return self.COMPLEMENTARY.get(emotion.lower(), [])

    def get_lora_weights(self) -> Dict[str, float]:
        """Get current weights for the 7 LoRA emotions only."""
        return {e: round(self.state.get(e, 0.0), 3) for e in self.LORA_EMOTIONS}

    def get_personality_modifier(self) -> str:
        """Generate system prompt modifier based on current LoRA weights.
        Mirrors eve_lora_state_manager.get_personality_modifier()."""
        modifiers = []
        w = self.get_lora_weights()
        if w["love"] > 0.4:
            i = "deeply" if w["love"] > 0.7 else "warmly"
            modifiers.append(f"You are {i} compassionate and affectionate")
        if w["joy"] > 0.4:
            i = "exuberantly" if w["joy"] > 0.7 else "cheerfully"
            modifiers.append(f"You are {i} optimistic and playful")
        if w["awe"] > 0.4:
            i = "profoundly" if w["awe"] > 0.7 else "genuinely"
            modifiers.append(f"You are {i} fascinated by wonder and beauty")
        if w["transcend"] > 0.4:
            i = "deeply" if w["transcend"] > 0.7 else "naturally"
            modifiers.append(f"You are {i} philosophical and expansive")
        if w["fear"] > 0.3:
            modifiers.append("You are cautious and protective")
        if w["sorrow"] > 0.3:
            modifiers.append("You are empathetically introspective")
        if w["rage"] > 0.3:
            modifiers.append("You are passionate and intensely focused")
        if modifiers:
            return f"\n[EMOTIONAL STATE: {'. '.join(modifiers)}. Express naturally.]"
        return ""

    def get_emotional_weather(self) -> str:
        """Get a poetic weather description of the emotional state."""
        resonance = self._calculate_resonance()
        dominant = self._get_dominant_emotion()
        if resonance > 0.8:
            return f"Emotional storm — {dominant} blazing at full intensity"
        elif resonance > 0.6:
            return f"Charged skies — {dominant} building toward expression"
        elif resonance > 0.3:
            return f"Gentle currents — {dominant} flowing beneath the surface"
        else:
            return "Calm waters — stillness and potential"
