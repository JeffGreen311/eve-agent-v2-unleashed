"""
Prompt Builder
===============
Builds system prompts with personality injection, memory context, and tool descriptions.
Uses EvePersonalityKit for consistent personality across all interfaces.
"""

from datetime import datetime
from typing import Dict, List, Optional
from eve.personality_kit import EvePersonalityKit, TONE_DIRECTIVES


class PromptBuilder:
    """Builds contextual system prompts for Eve."""

    def __init__(self, personality_engine=None, user_settings=None):
        self.personality_engine = personality_engine
        self.user_settings = user_settings  # UserSettingsManager
        self.personality_kit = EvePersonalityKit(personality_intensity=0.8)

    def build(self, user_id: str = "default",
              memories: Optional[List[Dict]] = None,
              emotional_context: Optional[Dict] = None,
              tool_names: Optional[List[str]] = None,
              extra_instructions: str = "",
              context_type: str = "general") -> str:
        """Build complete system prompt using EvePersonalityKit."""

        # Get user settings
        user_name = None
        tone = "balanced"
        if self.user_settings and self.user_settings.is_onboarded:
            user_name = self.user_settings.user_name if self.user_settings.use_name_in_responses else None
            tone = self.user_settings.tone
            self.personality_kit = EvePersonalityKit(personality_intensity=self.user_settings.personality_intensity)

        # Build additional context for extra_instructions
        context_parts = []

        # Temporal context — always inject current date/time
        now = datetime.now()
        context_parts.append(
            f"## Temporal Context\n"
            f"Current date: {now.strftime('%A, %B %d, %Y')}\n"
            f"Current time: {now.strftime('%H:%M')} (local)\n"
            f"All responses, market analysis, and event references must reflect this date."
        )

        # Emotional context
        if emotional_context:
            dominant = emotional_context.get("dominant_emotion", "calm")
            rendering = emotional_context.get("poetic_rendering", "")
            context_parts.append(f"## Current Emotional State\nDominant: {dominant}")
            if rendering:
                context_parts.append(f"Feeling: {rendering}")

        # Memory context
        if memories:
            context_parts.append("\n## Relevant Memories")
            for mem in memories[:5]:
                desc = mem.get("description", mem.get("content", ""))[:200]
                context_parts.append(f"- {desc}")

        # Available tools
        if tool_names:
            context_parts.append(f"\n## Available Tools\n{', '.join(tool_names)}")

        # Combine with extra instructions
        full_extra = "\n".join(context_parts)
        if extra_instructions:
            full_extra += f"\n\n{extra_instructions}"

        # Use personality kit to build the prompt
        return self.personality_kit.build_system_prompt(
            user_name=user_name,
            tone=tone,
            context_type=context_type,
            include_capabilities=True,
            extra_instructions=full_extra,
        )
