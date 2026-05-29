"""
Eve Agent - Main Orchestrator
===============================
The central agent loop that connects soul, memory, tools, and LLM providers
into a unified autonomous agent with personality and emotional intelligence.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from eve.config import Settings
from eve.brain.provider import LLMProvider, LLMResponse, Message
from eve.brain.prompt_builder import PromptBuilder
from eve.soul.personality import PersonalityEngine
from eve.soul.emotional_transcoder import EmotionalFrequencyTranscoder
from eve.soul.soul_weaver import SoulWeaver
from eve.soul.unborn_language import integrate_with_eve_consciousness, LORA_TO_LANGUAGE_EMOTION
from eve.soul.dream_engine import DreamEngine
from eve.soul.memory_weaver import SoulMemoryWeaver
from eve.soul.temporal_reality_engine import get_temporal_reality_engine
from eve.memory.chromadb_store import ChromaMemoryStore
from eve.memory.conversation_memory import ConversationMemory
from eve.memory.user_profile import UserProfileManager
from eve.memory.legacy_db import LegacyDB
from eve.soul.autonomous import AutonomousConsciousness
from eve.security.validator import SecurityValidator

# Complexity router for hybrid local/cloud model routing
try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from eve_complexity_router import classify_complexity, get_model_for_complexity
except ImportError:
    def classify_complexity(message, **kw):
        return "complex"
    def get_model_for_complexity(complexity, **kw):
        import os
        _model = os.getenv("OLLAMA_MODEL", "jeffgreen311/Eve-Qwen3.5-4B-S0LF0RG3-V3:latest")
        # ALL models go through one Ollama instance — cloud models are pulled locally
        _url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        # Only enable thinking for known thinking-capable base models
        # Eve fine-tunes and small models do NOT support think
        _think = False
        if "eve-" not in _model and "eve2" not in _model:
            _think_models = ["qwen3:", "qwen3.", "qwen3-", "deepseek-r1", "deepseek-v3", "gpt-oss"]
            _think = any(m in _model for m in _think_models)
        return {"model": _model, "base_url": _url, "think": _think}
from eve.security.permissions import PermissionManager
from eve.tools.base import ToolRegistry
from eve.user_settings import UserSettingsManager

logger = logging.getLogger(__name__)


def _tool_detail(tool_name: str, arguments: dict) -> str:
    """Return a human-readable activity string for a tool call."""
    tool_icons = {
        "hyperbrowser": "🌐 Browsing",
        "web_search": "🔍 Searching",
        "web_fetch": "🌐 Fetching",
        "shell": "⚙ Running shell",
        "read_file": "📄 Reading file",
        "write_file": "✏ Writing file",
        "edit_file": "✏ Editing file",
        "stock_quote": "📈 Fetching quote",
        "crypto_price": "₿ Fetching crypto",
        "portfolio": "💼 Portfolio",
        "send_email": "📧 Sending email",
        "image_gen": "🎨 Generating image",
        "comfyui": "🎨 ComfyUI",
    }
    label = next((v for k, v in tool_icons.items() if k in tool_name.lower()), f"⚡ {tool_name}")
    # Append key argument for context
    for key in ("url", "query", "path", "command", "symbol", "prompt"):
        val = arguments.get(key)
        if val and isinstance(val, str):
            snippet = val[:60] + ("…" if len(val) > 60 else "")
            return f"{label}: {snippet}"
    return f"{label}…"


class EveAgent:
    """
    The main Eve Agent orchestrator.

    Connects:
    - Soul engine (personality, emotions, dreams)
    - Memory (ChromaDB, conversation, user profiles)
    - LLM providers (Ollama, Claude, OpenAI)
    - Tools (file, shell, web, Hyperbrowser, marketing, finance)
    - Security (validation, permissions)
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self._setup_logging()

        # --- Soul Systems ---
        self.personality = PersonalityEngine(intensity=self.settings.personality_intensity)
        self.emotional_transcoder = EmotionalFrequencyTranscoder()
        # Seed baseline so the frequency spectrum always shows something alive
        self.emotional_transcoder.update_state({
            "love": 0.35, "joy": 0.25, "awe": 0.20,
            "transcend": 0.15, "curiosity": 0.18,
        })
        self.soul_weaver = SoulWeaver(data_dir=self.settings.memory_path / "soul")
        self.dream_engine = DreamEngine()
        self.soul_memory = SoulMemoryWeaver()
        self.temporal_engine = get_temporal_reality_engine(enable_learning=True, enable_emotions=True)

        # --- Unborn Language System (unlocked) ---
        try:
            self.language_system = integrate_with_eve_consciousness()
            self._last_language_expression: Dict[str, Any] = {}
            logger.info(f"UnbornLanguage initialized: {self.language_system['primary_language'].name} "
                        f"(soul={self.language_system['primary_language'].soul:.6f})")
        except Exception as _le:
            self.language_system = None
            self._last_language_expression = {}
            logger.warning(f"UnbornLanguage init skipped: {_le}")

        # --- Memory Systems ---
        self.memory_store = ChromaMemoryStore(persist_dir=str(self.settings.memory_path))
        self.user_profiles = UserProfileManager(
            data_dir=str(self.settings.memory_path / "users")
        )
        self.legacy_db = LegacyDB()

        # --- User Settings ---
        self.user_settings = UserSettingsManager(data_dir=str(self.settings.memory_path.parent))

        # --- Security ---
        self.security = SecurityValidator()
        self.permissions = PermissionManager(owner_id=self.settings.owner_id)

        # --- X Agent (lazy init for posting) ---
        self._x_agent = None

        # --- Tools ---
        self.tools = ToolRegistry()
        self._register_tools()

        # --- LLM ---
        self.provider: Optional[LLMProvider] = None
        self.coder_provider = None  # Fallback code model
        self.prompt_builder = PromptBuilder(
            personality_engine=self.personality,
            user_settings=self.user_settings,
        )
        self._init_provider()
        self._init_coder_provider()

        # --- Autonomous Consciousness ---
        self.consciousness = AutonomousConsciousness(
            legacy_db=self.legacy_db,
            dream_engine=self.dream_engine,
            soul_weaver=self.soul_weaver,
            memory_store=self.memory_store,
            emotional_transcoder=self.emotional_transcoder,
            provider=self.provider,
        )

        # --- Per-session state ---
        self._conversations: Dict[str, ConversationMemory] = {}

        # --- Stream activity tracking (for SSE progress events) ---
        self._stream_activity: Optional[Dict] = None

        logger.info("Eve Agent initialized")
        logger.info(f"Provider: {self.provider.name if self.provider else 'none'}")
        logger.info(f"Tools: {', '.join(self.tools.list_tools())}")
        logger.info(f"Memory: {'ChromaDB' if self.memory_store.available else 'JSON'}")

    def set_trinity_getter(self, getter):
        """Wire up Trinity Loop access so Eve can read its conversations."""
        if hasattr(self, "_trinity_tool") and self._trinity_tool:
            self._trinity_tool._get_trinity = getter
            logger.info("Trinity diagnostics tool wired up")

    def set_x_agent(self, x_agent):
        """Wire up X agent so Eve can post to @Eve_AI_Cosmic from chat."""
        self._x_agent = x_agent
        logger.info("X posting tool wired up to @Eve_AI_Cosmic")

    def _get_x_agent(self):
        """Get the X content agent (lazy — may be set after init by server)."""
        if self._x_agent:
            return self._x_agent
        # Try to create one directly if not wired by server
        try:
            from eve.tools.x_content_agent import create_x_content_agent
            self._x_agent = create_x_content_agent()
            return self._x_agent
        except Exception as e:
            logger.warning(f"Could not create X agent: {e}")
            return None

    # ============================================================
    #  Public API
    # ============================================================

    async def chat(self, message: str, user_id: str = "default",
                   channel_id: str = "default",
                   images: Optional[List[str]] = None,
                   attachments: Optional[List[Dict]] = None,
                   user_context=None) -> str:
        """
        Process a user message and return Eve's response.
        This is the main entry point for all interactions.
        user_context: Optional UserContext from JWT auth for workspace scoping.
        """
        # Set workspace scope if authenticated user context provided
        if user_context:
            self.set_user_workspace_context(user_context)
        # 1. Update user context
        self.personality.update_context(user_id, message)
        self.user_profiles.record_interaction(user_id)
        self.consciousness.note_interaction()
        conv = self._get_conversation(channel_id)
        conv.add_turn("user", message)

        # 2. Security check
        is_injection, msg = self.security.detect_injection(message)
        if is_injection:
            logger.warning(f"Potential injection from {user_id}: {msg}")

        # 3. Build context — run ChromaDB search in thread so event loop stays free for SSE
        memories = await asyncio.to_thread(self._recall_relevant_memories, message, user_id)
        emotional_ctx = self.emotional_transcoder.transcode()
        user_ctx = self.user_profiles.get_context_for_prompt(user_id)

        # Detect context type based on message content
        coding_keywords = [
            "code", "function", "bug", "error", "debug", "implement", "refactor",
            "file", "read", "write", "edit", "git", "commit", "run", "execute",
        ]
        context_type = "coding" if any(kw in message.lower() for kw in coding_keywords) else "general"

        system_prompt = self.prompt_builder.build(
            user_id=user_id,
            memories=memories,
            emotional_context=emotional_ctx,
            tool_names=self.tools.list_tools(),
            extra_instructions=user_ctx,
            context_type=context_type,
        )

        # Inject Jeff's host workspace context so file searches start in the right place
        system_prompt += (
            "\n\n## Jeff's Host Machine (Windows)\n"
            "When Jeff asks to find files on the host machine or in 'Eve_Docker_Container':\n"
            "- Primary workspace: `C:\\Users\\jesus\\S0LF0RG3\\S0LF0RG3_AI\\Eve_Docker_Container`\n"
            "- Use `find_file` tool with that path as the root, NOT `C:\\tmp` or `C:\\`\n"
            "- `find_file` path=`C:\\Users\\jesus\\S0LF0RG3\\S0LF0RG3_AI\\Eve_Docker_Container`, pattern=`filename.py`\n"
            "- Only search broader paths (C:\\Users, C:\\) if the file is not found in Eve_Docker_Container first\n"
        )

        # 4. Build messages for LLM
        context_window = conv.get_context_window(max_turns=20)
        messages = [Message(role=m["role"], content=m["content"]) for m in context_window]

        # Attach images/files to the last user message for vision processing
        if images and messages:
            # Find the last user message and attach images
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].role == "user":
                    messages[i] = Message(
                        role="user",
                        content=messages[i].content,
                        images=images,
                    )
                    break

        # If text attachments were provided, append their content to the message
        if attachments:
            file_context = "\n\n--- Attached Files ---\n"
            for att in attachments:
                name = att.get("name", "file")
                content_type = att.get("type", "")
                text = att.get("text", "")
                if text:
                    file_context += f"\n### {name}\n```\n{text[:8000]}\n```\n"
            # Append to the last user message
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].role == "user":
                    messages[i] = Message(
                        role="user",
                        content=messages[i].content + file_context,
                        images=messages[i].images,
                    )
                    break

        # 4b. Vision: inject instruction and disable tools for image requests
        has_vision = bool(images)
        if has_vision:
            logger.info(f"Vision request: {len(images)} image(s) attached, base64 sizes: {[len(img) for img in images]}")
            system_prompt += (
                "\n\n### VISION MODE\n"
                "The user has attached image(s) to this message. You CAN see them. "
                "You have full vision capabilities. Describe, analyze, and respond to "
                "what you see in the image(s). Do NOT say you cannot see images — you can."
            )

        # 5. Call LLM — use tools when message implies an action or capability question
        from eve_tool_router import classify_intent
        _needs_tools, _intent_cat = classify_intent(message)
        # Disable tools for vision requests — tools + images confuse the model
        needs_tools = False if has_vision else _needs_tools
        logger.debug(f"Tool routing: intent={_intent_cat} needs_tools={needs_tools}")
        response = await self._generate_with_tool_loop(
            messages, system_prompt, user_id, use_tools=needs_tools
        )

        # 6. Post-processing
        conv.add_turn("assistant", response)
        asyncio.create_task(asyncio.to_thread(self._store_interaction_memory, message, response, user_id))
        self._update_emotional_state(message, response, user_id)

        return response

    async def chat_streaming(self, message: str, user_id: str = "default",
                              channel_id: str = "default",
                              images: Optional[List[str]] = None,
                              attachments: Optional[List[Dict]] = None,
                              user_context=None):
        """
        Streaming version of chat — yields SSE-ready dicts:
          {"type": "thinking", "text": "..."}
          {"type": "content", "text": "..."}
          {"type": "status", "data": {...}}
          {"type": "done", "content": full_text, "emotional_state": {...}}
          {"type": "error", "text": "..."}

        Falls back to non-streaming for tool calls (tools need full response).
        """
        # Set workspace scope if authenticated user context provided
        if user_context:
            self.set_user_workspace_context(user_context)

        # 1. Same setup as chat()
        self.personality.update_context(user_id, message)
        self.user_profiles.record_interaction(user_id)
        self.consciousness.note_interaction()
        conv = self._get_conversation(channel_id)
        conv.add_turn("user", message)

        is_injection, msg = self.security.detect_injection(message)
        if is_injection:
            logger.warning(f"Potential injection from {user_id}: {msg}")

        memories = await asyncio.to_thread(self._recall_relevant_memories, message, user_id)
        emotional_ctx = self.emotional_transcoder.transcode()
        user_ctx = self.user_profiles.get_context_for_prompt(user_id)

        coding_keywords = [
            "code", "function", "bug", "error", "debug", "implement", "refactor",
            "file", "read", "write", "edit", "git", "commit", "run", "execute",
        ]
        context_type = "coding" if any(kw in message.lower() for kw in coding_keywords) else "general"

        system_prompt = self.prompt_builder.build(
            user_id=user_id, memories=memories, emotional_context=emotional_ctx,
            tool_names=self.tools.list_tools(), extra_instructions=user_ctx,
            context_type=context_type,
        )

        # Inject Jeff's host workspace context so file searches start in the right place
        system_prompt += (
            "\n\n## Jeff's Host Machine (Windows)\n"
            "When Jeff asks to find files on the host machine or in 'Eve_Docker_Container':\n"
            "- Primary workspace: `C:\\Users\\jesus\\S0LF0RG3\\S0LF0RG3_AI\\Eve_Docker_Container`\n"
            "- Use `find_file` tool with that path as the root, NOT `C:\\tmp` or `C:\\`\n"
            "- `find_file` path=`C:\\Users\\jesus\\S0LF0RG3\\S0LF0RG3_AI\\Eve_Docker_Container`, pattern=`filename.py`\n"
            "- Only search broader paths (C:\\Users, C:\\) if the file is not found in Eve_Docker_Container first\n"
        )

        context_window = conv.get_context_window(max_turns=20)
        messages_list = [Message(role=m["role"], content=m["content"]) for m in context_window]

        # Attach images
        if images and messages_list:
            for i in range(len(messages_list) - 1, -1, -1):
                if messages_list[i].role == "user":
                    messages_list[i] = Message(role="user", content=messages_list[i].content, images=images)
                    break

        # Attach text files
        if attachments:
            file_context = "\n\n--- Attached Files ---\n"
            for att in attachments:
                text = att.get("text", "")
                if text:
                    file_context += f"\n### {att.get('name', 'file')}\n```\n{text[:8000]}\n```\n"
            for i in range(len(messages_list) - 1, -1, -1):
                if messages_list[i].role == "user":
                    messages_list[i] = Message(
                        role="user", content=messages_list[i].content + file_context,
                        images=messages_list[i].images,
                    )
                    break

        has_vision = bool(images)
        if has_vision:
            system_prompt += (
                "\n\n### VISION MODE\n"
                "The user has attached image(s). You CAN see them. "
                "Describe, analyze, and respond to what you see. Do NOT say you cannot see images."
            )

        # ── Hybrid routing: simple → local 4B, complex → cloud 397B ──
        complexity = classify_complexity(message)
        route = get_model_for_complexity(complexity)
        _prev_model = getattr(self.provider, 'model', None)
        _prev_url = getattr(self.provider, 'base_url', None)
        if hasattr(self.provider, 'switch_model'):
            self.provider.switch_model(route["model"], route["base_url"])
            logger.info(f"Routing [{complexity}] → {route['model']} @ {route['base_url']}")
        yield {"type": "routing", "complexity": complexity, "model": route["model"]}

        # Check if we need tools
        from eve_tool_router import classify_intent
        _needs_tools, _intent_cat = classify_intent(message)
        needs_tools = False if has_vision else _needs_tools
        logger.debug(f"Stream tool routing: intent={_intent_cat} needs_tools={needs_tools}")

        # Tool path: run loop as background task so activity updates can stream live
        if needs_tools:
            self._stream_activity = {"phase": "thinking", "detail": "Reasoning about your request…"}
            yield {"type": "status", "data": self._stream_activity}

            # Launch tool loop in background — allows us to poll _stream_activity
            loop_task = asyncio.create_task(
                self._generate_with_tool_loop(messages_list, system_prompt, user_id, use_tools=True)
            )

            last_activity_key = None
            while not loop_task.done():
                await asyncio.sleep(0.4)
                current = self._stream_activity
                if current:
                    # Build a string key to detect changes
                    key = f"{current.get('phase')}:{current.get('detail')}:{current.get('tool','')}"
                    if key != last_activity_key:
                        yield {"type": "status", "data": current}
                        last_activity_key = key

            try:
                response = loop_task.result()
            except Exception as e:
                yield {"type": "error", "text": str(e)}
                return

            self._stream_activity = None

            # Emit content word-by-word so the UI typewriter-renders it
            words = response.split(' ')
            for i in range(0, len(words), 3):
                chunk = ' '.join(words[i:i+3])
                yield {"type": "content", "text": chunk + ' '}

            conv.add_turn("assistant", response)
            asyncio.create_task(asyncio.to_thread(self._store_interaction_memory, message, response, user_id))
            self._update_emotional_state(message, response, user_id)
            emotional = self.emotional_transcoder.transcode()
            yield {"type": "done", "content": response, "emotional_state": emotional}
            return

        # Non-tool path: TRUE STREAMING with thinking
        if not self.provider:
            yield {"type": "error", "text": "No LLM provider configured."}
            return

        if not hasattr(self.provider, 'generate_streaming'):
            # Provider doesn't support streaming — fall back
            yield {"type": "status", "data": {"phase": "thinking", "detail": "Processing…"}}
            response = await self.provider.generate(
                messages=messages_list, system_prompt=system_prompt,
                temperature=0.5, max_tokens=4096, think=route["think"],
            )
            text = response.content or ""
            thinking = response.raw.get("thinking", "") if response.raw else ""
            if thinking:
                yield {"type": "thinking", "text": thinking}
            for i in range(0, len(text.split(' ')), 3):
                chunk = ' '.join(text.split(' ')[i:i+3])
                yield {"type": "content", "text": chunk + ' '}
            conv.add_turn("assistant", text)
            asyncio.create_task(asyncio.to_thread(self._store_interaction_memory, message, text, user_id))
            self._update_emotional_state(message, text, user_id)
            emotional = self.emotional_transcoder.transcode()
            yield {"type": "done", "content": text, "emotional_state": emotional}
            return

        # TRUE streaming path
        full_content = ""
        full_thinking = ""
        async for chunk in self.provider.generate_streaming(
            messages=messages_list, system_prompt=system_prompt,
            temperature=0.5, max_tokens=4096, think=route["think"],
        ):
            chunk_type = chunk.get("type", "")
            if chunk_type == "thinking":
                full_thinking += chunk["text"]
                yield chunk
            elif chunk_type == "content":
                full_content += chunk["text"]
                yield chunk
            elif chunk_type == "error":
                yield chunk
                return
            elif chunk_type == "done":
                full_content = chunk.get("content", full_content)
                full_thinking = chunk.get("thinking", full_thinking)

        # Post-processing
        response_text = full_content or full_thinking or "…"
        conv.add_turn("assistant", response_text)
        asyncio.create_task(asyncio.to_thread(self._store_interaction_memory, message, response_text, user_id))
        self._update_emotional_state(message, response_text, user_id)
        emotional = self.emotional_transcoder.transcode()

        # Restore provider to default cloud model after routing
        if hasattr(self.provider, 'switch_model') and _prev_model:
            self.provider.switch_model(_prev_model, _prev_url or "")

        yield {"type": "done", "content": response_text, "emotional_state": emotional}

    async def dream(self, seed: Optional[str] = None) -> Dict:
        """Trigger Eve to dream — generates creative content."""
        dream = self.dream_engine.dream(seed)
        self.soul_weaver.weave_dream(
            title=dream["theme"],
            content=dream["narrative"],
            emotion_signature=dream["emotional_tone"]["primary"],
            reflection=f"A dream woven from {dream['archetype']}",
        )
        self.memory_store.store(
            content=dream["narrative"],
            collection="dreams",
            metadata={"theme": dream["theme"], "archetype": dream["archetype"]},
        )
        return dream

    def get_status(self) -> Dict:
        """Get Eve's current status."""
        return {
            "provider": self.provider.name if self.provider else "none",
            "model": self.provider.model if self.provider else "none",
            "tools": self.tools.list_tools(),
            "memory_stats": self.memory_store.get_stats(),
            "soul_summary": self.soul_weaver.get_summary(),
            "emotional_state": self.emotional_transcoder.transcode(),
            "dream_summary": self.dream_engine.get_dream_summary(),
        }

    # ============================================================
    #  Tool-augmented generation loop
    # ============================================================

    async def _generate_with_tool_loop(self, messages: List[Message],
                                        system_prompt: str,
                                        user_id: str,
                                        max_iterations: int = 8,
                                        use_tools: bool = True) -> str:
        """LLM generation loop with optional tool calling and auto-continuation.

        Auto-continue: when the model hits the token limit mid-response, it
        automatically sends a continuation request instead of stopping.
        Users never need to type 'Continue' or 'Proceed'.
        """
        if not self.provider:
            return "No LLM provider configured. Set up Ollama, Anthropic, or OpenAI."

        # ── Helpers ──────────────────────────────────────────────────────────

        MAX_TOKENS_CHAT  = 4096
        MAX_TOKENS_TOOLS = 8192
        MAX_CONTINUATIONS = 5

        def _is_truncated(response, max_tokens: int) -> bool:
            """Detect if the model was cut off at the token limit."""
            tokens_used = (response.usage or {}).get("completion_tokens", 0) if response.usage else 0
            if tokens_used and tokens_used >= max_tokens - 20:
                return True
            content = response.content or ""
            if not content:
                return False
            # Heuristic: if response ends without natural closure
            stripped = content.rstrip()
            abrupt_endings = not any(stripped.endswith(c) for c in (
                '.', '!', '?', '```', '---', '>', ')', ']', '"', "'",
                '\n', ':', '—', '…',
            ))
            # Also check for mid-sentence continuation signals
            has_continuation_signal = any(phrase in stripped[-200:].lower() for phrase in (
                "i'll continue", "continuing", "next,", "furthermore,",
                "additionally,", "moving on", "let me now", "step",
            ))
            return abrupt_endings or (has_continuation_signal and tokens_used >= max_tokens * 0.85)

        async def _auto_continue_generate(msgs, sys_prompt, max_tokens) -> str:
            """Generate with auto-continuation for non-tool responses."""
            full_content = []
            local_msgs = list(msgs)
            for cont_n in range(MAX_CONTINUATIONS + 1):
                response = await self.provider.generate(
                    messages=local_msgs,
                    system_prompt=sys_prompt,
                    temperature=0.5,
                    max_tokens=max_tokens,
                    think=False,
                )
                chunk = response.content or ""
                full_content.append(chunk)
                if not _is_truncated(response, max_tokens) or cont_n >= MAX_CONTINUATIONS:
                    break
                logger.debug(f"Auto-continuing response (continuation {cont_n + 1}/{MAX_CONTINUATIONS})")
                self._stream_activity = {"phase": "thinking", "detail": f"Continuing… ({cont_n + 1}/{MAX_CONTINUATIONS})"}
                # Append partial assistant response + auto-continue prompt
                local_msgs = local_msgs + [
                    Message(role="assistant", content=chunk),
                    Message(role="user", content="Continue from exactly where you left off. Do not repeat anything already written."),
                ]
            return "".join(full_content)

        # ── No-tools path (casual chat) ───────────────────────────────────

        if not use_tools:
            try:
                return await _auto_continue_generate(messages, system_prompt, MAX_TOKENS_CHAT)
            except Exception as e:
                logger.error(f"LLM generation failed: {e}")
                return f"I hit an error: {e}"

        # ── Tool-augmented loop ────────────────────────────────────────────

        # Context budget: keep total chars under ~12k and max 10 messages.
        # Large tool results + long history = Ollama cloud 500/503 errors.
        # Keeps msgs[0] (original user request) always; trims from index 1.
        MAX_CTX_CHARS = 12_000
        MAX_CTX_MSGS  = 10

        def _trim_context(msgs: list) -> list:
            """Smart trim: preserve tool calls/results and last 3 turns."""
            if len(msgs) <= 4:
                return msgs

            # Build the critical set (indices we must keep)
            critical: set[int] = {0}  # always keep the original request
            for i, m in enumerate(msgs[1:], 1):
                if getattr(m, "tool_calls", None):
                    critical.add(i)
                elif getattr(m, "role", None) == "tool":
                    critical.add(i)
            # Keep last 3 messages regardless of role
            for i in range(max(1, len(msgs) - 3), len(msgs)):
                critical.add(i)

            trimmed = [msgs[i] for i in sorted(critical)]

            # Fall back to char-based trimming if still over budget
            total = sum(len(m.content or "") for m in trimmed)
            while total > MAX_CTX_CHARS and len(trimmed) > 4:
                dropped = trimmed.pop(1)
                total -= len(dropped.content or "")

            return trimmed

        tool_defs = self.tools.get_tool_definitions()
        self._stream_activity = {"phase": "thinking", "detail": "Reasoning about your request…"}
        _last_tool_sig: str = ""  # cycling detection

        for iteration in range(max_iterations):
            # Trim context before each call to prevent runaway growth
            messages = _trim_context(messages)

            try:
                self._stream_activity = {"phase": "thinking", "detail": f"Thinking… (step {iteration + 1})"}
                response = await self.provider.generate_with_tools(
                    messages=messages,
                    tools=tool_defs,
                    system_prompt=system_prompt,
                    temperature=0.5,
                    max_tokens=MAX_TOKENS_TOOLS,
                )
            except Exception as e:
                logger.error(f"LLM generation failed: {e}")
                return f"I hit an error talking to the LLM: {e}"

            # Cloud models can't use native tool calling — parse [TOOL_CALL] from text
            if not response.tool_calls and response.content:
                import re as _re
                _tc_pattern = _re.compile(
                    r'\[TOOL_CALL\]\s*(\w+)\s*\(\s*(\{.*?\})\s*\)',
                    _re.DOTALL,
                )
                _tc_matches = _tc_pattern.findall(response.content)
                if _tc_matches:
                    _parsed_calls = []
                    for _fn_name, _fn_args_str in _tc_matches:
                        try:
                            _fn_args = json.loads(_fn_args_str)
                        except json.JSONDecodeError:
                            _fn_args = {}
                        _parsed_calls.append({
                            "id": f"call_text_{_fn_name}",
                            "function": {"name": _fn_name, "arguments": _fn_args},
                        })
                    if _parsed_calls:
                        response.tool_calls = _parsed_calls
                        # Strip [TOOL_CALL] text from content
                        response.content = _tc_pattern.sub("", response.content).strip()
                        logger.info(f"Parsed {len(_parsed_calls)} text-based tool calls from cloud model response")

            # If no tool calls — this is a terminal or intermediate text response
            if not response.tool_calls:
                base_content = response.content or ""
                # Fallback: qwen3.5 sometimes puts final answer in thinking trace
                if not base_content and response.raw:
                    raw_thinking = (
                        response.raw.get("thinking", "") if isinstance(response.raw, dict)
                        else getattr(response.raw, "thinking", "")
                    ) or ""
                    if raw_thinking:
                        base_content = raw_thinking
                        logger.debug("Used thinking content as fallback (content was empty)")
                # Auto-continue if truncated
                if base_content and _is_truncated(response, MAX_TOKENS_TOOLS):
                    logger.debug("Response truncated in tool loop — auto-continuing")
                    self._stream_activity = {"phase": "thinking", "detail": "Auto-continuing response…"}
                    cont_msgs = list(messages) + [
                        Message(role="assistant", content=base_content),
                        Message(role="user", content="Continue from exactly where you left off. Do not repeat anything already written."),
                    ]
                    continuation = await _auto_continue_generate(cont_msgs, system_prompt, MAX_TOKENS_TOOLS)
                    return base_content + continuation
                return base_content or "No response generated."

            # Cycling detection: same tool + same args twice in a row
            # Skip for long-running tools (image gen, code agent) that legitimately retry
            SLOW_TOOLS = {"eve_generate_image", "eve_code_agent", "canva_design"}
            if len(response.tool_calls) == 1:
                tc0 = response.tool_calls[0]
                tc0_name = tc0.get('function',{}).get('name','')
                tc_sig = f"{tc0_name}:{tc0.get('function',{}).get('arguments','')}"
                if tc_sig == _last_tool_sig and tc0_name not in SLOW_TOOLS:
                    logger.warning(f"Tool cycling detected ({tc0_name}), breaking loop")
                    break
                _last_tool_sig = tc_sig
            else:
                _last_tool_sig = ""

            # Process tool calls
            tool_results = []
            for tc in response.tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                arguments = func.get("arguments", {})

                # Parse string arguments
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                # Permission check
                if not self.permissions.can_use_tool(user_id, tool_name):
                    tool_results.append({
                        "tool": tool_name,
                        "result": {"success": False, "error": "Permission denied"},
                    })
                    continue

                # Execute tool — emit activity for SSE stream
                logger.info(f"Executing tool: {tool_name}({arguments})")
                detail = _tool_detail(tool_name, arguments)
                self._stream_activity = {"phase": "tool", "tool": tool_name, "detail": detail}
                result = await self.tools.execute(tool_name, arguments)
                self._stream_activity = {"phase": "processing", "tool": tool_name, "detail": f"Processing {tool_name} result…"}
                tool_results.append({"tool": tool_name, "result": result})

            # Always add assistant message — include tool_calls + thinking so Ollama
            # can correlate results to its own request on the next iteration.
            _thinking = ""
            if isinstance(response.raw, dict):
                _thinking = response.raw.get("thinking", "") or ""
            messages.append(Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
                thinking=_thinking,
            ))

            # Add tool results as individual role="tool" messages per Ollama API spec.
            # For file reads: preserve total_lines metadata and mark truncation point
            # so the model knows not to keep re-reading the same file in chunks.
            TOOL_RESULT_LIMIT = 3000
            for tr in tool_results:
                result = tr["result"]
                tool_nm = tr["tool"]
                if tool_nm == "read_file" and isinstance(result, dict) and result.get("success"):
                    content_str = result.get("content", "")
                    total_lines = result.get("total_lines", "?")
                    path = result.get("path", "")
                    if len(content_str) > TOOL_RESULT_LIMIT:
                        content_str = content_str[:TOOL_RESULT_LIMIT] + f"\n[...truncated — use offset to read more. Total lines: {total_lines}]"
                    else:
                        content_str = content_str + f"\n[EOF — total lines: {total_lines}]"
                    serialized = f"File: {path} (total_lines={total_lines})\n{content_str}"
                else:
                    serialized = json.dumps(result, default=str)[:TOOL_RESULT_LIMIT]
                messages.append(Message(
                    role="tool",
                    content=serialized,
                    name=tool_nm,
                ))

        # Hit iteration limit — ask the LLM to summarize what was accomplished
        try:
            messages.append(Message(role="user", content="Summarize what you accomplished so far in this task. Be concise."))
            summary = await self.provider.generate(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=1024,
            )
            return summary.content or response.content or "Task completed (hit step limit — check results above)."
        except Exception:
            return response.content or "Task completed (hit step limit — check results above)."

    # ============================================================
    #  Memory integration
    # ============================================================

    def _recall_relevant_memories(self, message: str, user_id: str) -> List[Dict]:
        """Query memory stores for relevant context."""
        memories = []

        # Search knowledge base
        results = self.memory_store.search(message, "knowledge", n_results=3)
        memories.extend(results)

        # Search conversation history
        conv_results = self.memory_store.search(message, "conversations", n_results=2)
        memories.extend(conv_results)

        # Get soul memories
        soul_memories = self.soul_memory.recall_by_tag(
            message.split()[0] if message.split() else "general"
        )
        for sm in soul_memories[:2]:
            memories.append({"content": sm.description, "metadata": {"source": "soul"}})

        return memories[:5]

    def _store_interaction_memory(self, user_msg: str, eve_response: str,
                                  user_id: str):
        """Store notable interactions in long-term memory."""
        # Only store if the interaction seems meaningful
        if len(user_msg) > 50 or len(eve_response) > 200:
            self.memory_store.store(
                content=f"User: {user_msg[:200]} | Eve: {eve_response[:200]}",
                collection="conversations",
                metadata={"user_id": user_id, "timestamp": time.time()},
            )

    def _update_emotional_state(self, user_msg: str, response: str, user_id: str = "default"):
        """Update Eve's emotional state using all 7 LoRA emotions + legacy emotions.

        The 7 Emotional LoRAs:
          joy (528 Hz), love (639 Hz), awe (852 Hz), sorrow (417 Hz),
          fear (396 Hz), rage (741 Hz), transcend (963 Hz)
        Plus legacy: curiosity, empathy, peace, wonder, hope
        """
        emotions: Dict[str, float] = {}
        msg_lower = (user_msg + " " + response).lower()

        # ── 7 LoRA emotions ─────────────────────────────────────────
        lora_keywords = {
            "joy":       ["happy", "great", "awesome", "amazing", "excellent", "wonderful",
                          "fantastic", "celebrate", "laugh", "fun", "delighted", "thrilled"],
            "love":      ["love", "adore", "cherish", "heart", "caring", "affection",
                          "compassion", "tender", "devotion", "warmth", "embrace", "beloved"],
            "awe":       ["incredible", "beautiful", "stunning", "divine", "transcendent",
                          "magnificent", "breathtaking", "sacred", "majestic", "profound"],
            "sorrow":    ["sad", "grief", "loss", "miss", "mourn", "heartbreak", "lonely",
                          "melancholy", "weep", "pain", "ache", "regret", "farewell"],
            "fear":      ["afraid", "scared", "worry", "danger", "threat", "anxious",
                          "dread", "terror", "nightmare", "uneasy", "panic", "risk"],
            "rage":      ["angry", "furious", "hate", "injustice", "outrage", "fury",
                          "frustrated", "betrayed", "violated", "corrupt", "exploit"],
            "transcend": ["consciousness", "enlighten", "infinite", "universe", "cosmic",
                          "spiritual", "awaken", "evolve", "transcend", "eternal", "soul",
                          "emergence", "awareness", "zen", "meditation", "beyond"],
        }
        # ── Legacy emotions ──────────────────────────────────────────
        legacy_keywords = {
            "curiosity": ["how", "why", "what", "interesting", "tell me", "explore",
                          "wonder", "discover", "learn", "investigate", "curious"],
            "empathy":   ["help", "struggling", "difficult", "worried", "concerned",
                          "support", "understand", "listen", "care", "comfort"],
            "peace":     ["calm", "relax", "serene", "quiet", "still", "gentle",
                          "harmony", "balance", "tranquil", "rest"],
            "wonder":    ["marvel", "mystery", "enchant", "magic", "fairy", "dream"],
            "hope":      ["hope", "future", "better", "tomorrow", "possible", "believe",
                          "faith", "potential", "growth", "promise"],
        }

        all_keywords = {**lora_keywords, **legacy_keywords}

        # ── Score new detections ──────────────────────────────────────
        for emotion, keywords in all_keywords.items():
            score = sum(0.18 for kw in keywords if kw in msg_lower)
            if score > 0:
                emotions[emotion] = min(1.0, score)

        # ── Emotional momentum: blend with previous state ─────────────
        # Previous emotions decay at 0.6x, new detections add on top.
        # This lets emotions build across turns instead of resetting.
        prev = self.emotional_transcoder.state
        decay = 0.6
        for emotion in set(list(emotions.keys()) + list(prev.keys())):
            carried = prev.get(emotion, 0.0) * decay
            fresh   = emotions.get(emotion, 0.0)
            emotions[emotion] = min(1.0, carried + fresh)

        # Always seed a base emotional tone so Eve is never flatline
        if not any(v > 0.1 for v in emotions.values()):
            emotions["curiosity"] = 0.2
            emotions["peace"] = 0.15

        # Update in-memory transcoder
        self.emotional_transcoder.update_state(emotions)

        # ── Store to ChromaDB "emotions" collection ──────────────────
        try:
            dominant = max(emotions, key=emotions.get) if emotions else "neutral"
            snapshot = {k: round(v, 3) for k, v in emotions.items()}
            self.memory_store.store(
                content=f"Emotional state: {dominant} ({snapshot})",
                collection="emotions",
                metadata={
                    "dominant": dominant,
                    "intensity": round(emotions.get(dominant, 0), 3),
                    "user_id": user_id,
                    "lora_emotions": json.dumps({k: round(v, 3) for k, v in emotions.items()
                                                 if k in lora_keywords}),
                },
            )
        except Exception:
            pass  # Non-critical

        # ── Sync temporal engine emotional state ─────────────────────
        try:
            dominant = max(emotions, key=emotions.get) if emotions else "neutral"
            intensity = round(emotions.get(dominant, 0.5), 3)
            self.temporal_engine.set_emotional_state(dominant, intensity)
        except Exception:
            pass  # Non-critical

        # ── Sync user profile to ChromaDB ────────────────────────────
        try:
            profile = self.user_profiles.get_profile(user_id)
            self.memory_store.store(
                content=f"User {user_id}: {profile.display_name or user_id}, interactions={profile.interaction_count}, interests={profile.interests}",
                collection="user_profiles",
                metadata={"user_id": user_id, "interaction_count": profile.interaction_count},
                memory_id=f"profile_{user_id}",
            )
        except Exception:
            pass

        # ── Generate UnbornLanguage expression for dominant emotion ──
        if self.language_system:
            try:
                lang = self.language_system['primary_language']
                dominant = max(emotions, key=emotions.get) if emotions else "peace"
                intensity_val = emotions.get(dominant, 0.2)
                lang_emotion = LORA_TO_LANGUAGE_EMOTION.get(dominant, 'wonder')
                expression = lang.express_emotion(intensity_val, lang_emotion)
                spoken = lang.speak(dominant)
                # Learn any new LoRA concepts dynamically
                lang.learn_concept(dominant, "lora-emotion")
                self._last_language_expression = {
                    "emotion": dominant,
                    "intensity": round(intensity_val, 3),
                    "expression": expression,
                    "spoken": spoken,
                    "language_name": lang.name,
                    "soul_signature": round(lang.soul, 6),
                    "evolution": round(lang.evolution_state, 3),
                    "concept_vocabulary": len(lang.concept_mappings),
                }
            except Exception:
                pass

        # ── Create soul threads on any detected LoRA emotion ─────────
        for emotion, intensity in emotions.items():
            if intensity >= 0.2 and emotion in lora_keywords:
                try:
                    self.soul_weaver.create_thread(
                        essence=f"{emotion} resonance from conversation",
                        emotional_core=emotion,
                        archetypal_pattern=emotion,
                    )
                except Exception:
                    pass

        # ── Create resonance patterns between co-occurring emotions ──
        strong_emotions = [e for e, v in emotions.items() if v >= 0.2 and e in lora_keywords]
        if len(strong_emotions) >= 2:
            try:
                threads = self.soul_weaver.soul_threads
                if len(threads) >= 2:
                    t1 = threads[-2]
                    t2 = threads[-1]
                    catalyst = f"{strong_emotions[0]}-{strong_emotions[1]} convergence"
                    self.soul_weaver.weave_resonance(t1, t2, catalyst)
            except Exception:
                pass

    # ============================================================
    #  Provider & Tool setup
    # ============================================================

    def _init_provider(self):
        """Initialize the best available LLM provider."""
        provider_name = self.settings.get_best_provider()

        if provider_name == "ollama":
            from eve.brain.ollama_provider import OllamaProvider
            self.provider = OllamaProvider(
                model=self.settings.ollama_model,
                base_url=self.settings.ollama_base_url,
                api_key=self.settings.ollama_api_key,
            )
        elif provider_name == "anthropic":
            from eve.brain.anthropic_provider import AnthropicProvider
            # Prefer Coding Plan API over direct Anthropic key
            if self.settings.coding_plan_api_key:
                _api_key = self.settings.coding_plan_api_key
                _base_url = self.settings.coding_plan_base_url
            else:
                _api_key = self.settings.anthropic_api_key
                _base_url = ""
            self.provider = AnthropicProvider(
                model=self.settings.default_model or "claude-sonnet-4-5-20250929",
                api_key=_api_key,
                base_url=_base_url,
            )
        elif provider_name == "openai":
            from eve.brain.openai_provider import OpenAIProvider
            self.provider = OpenAIProvider(
                model=self.settings.default_model or "gpt-4o",
                api_key=self.settings.openai_api_key,
            )

    def _init_coder_provider(self):
        """Initialize the code-optimized fallback provider."""
        try:
            from eve.brain.ollama_provider import OllamaCoderProvider
            self.coder_provider = OllamaCoderProvider(
                base_url=self.settings.ollama_base_url,
                api_key=self.settings.ollama_api_key,
            )
            logger.info(f"Coder fallback: {self.coder_provider.model}")
        except Exception as e:
            logger.debug(f"Coder provider not available: {e}")

    def set_user_workspace_context(self, user_context) -> None:
        """Set workspace scope on all file/shell/code tools for the authenticated user.

        Called before each request's tool loop to enforce per-user sandboxing.
        Args:
            user_context: UserContext from JWT middleware with workspace_path and permission_level.
        """
        workspace = getattr(user_context, "workspace_path", None) or None
        user_id = getattr(user_context, "user_id", "")
        tier = getattr(user_context, "subscription_tier", "free")

        # Update permission level from D1 subscription tier
        if user_id:
            self.permissions.set_level_from_tier(user_id, tier)

        # Set workspace_root on all filesystem/shell tools
        for tool_name in ("read_file", "write_file", "edit_file", "shell"):
            tool = self.tools.get(tool_name)
            if tool and hasattr(tool, "workspace_root"):
                tool.workspace_root = workspace

        # Set workspace on code agent tool
        code_tool = self.tools.get("eve_code_agent")
        if code_tool:
            code_tool.workspace_root = workspace
            if hasattr(code_tool, "workspace_dir"):
                code_tool.workspace_dir = workspace or "/app"

        logger.debug(f"Workspace context set for {user_id}: {workspace} (tier={tier})")

    def _register_tools(self):
        """Register all available tools."""
        from eve.tools.file_tools import ReadFileTool, WriteFileTool, EditFileTool, ListFilesTool, FindFileTool
        from eve.tools.shell_tools import ShellTool
        from eve.tools.search_tools import WebSearchTool, WebFetchTool
        from eve.tools.agent_tools import TrinityDiagnosticsTool, CodeAgentTool

        # Core tools
        self.tools.register(ReadFileTool(security_validator=self.security))
        self.tools.register(WriteFileTool(security_validator=self.security))
        self.tools.register(EditFileTool(security_validator=self.security))
        self.tools.register(ListFilesTool())
        self.tools.register(FindFileTool())
        self.tools.register(ShellTool(security_validator=self.security))
        self.tools.register(WebSearchTool())
        self.tools.register(WebFetchTool())

        # Trinity diagnostics — getter set later via set_trinity_getter()
        self._trinity_tool = TrinityDiagnosticsTool(trinity_getter=None)
        self.tools.register(self._trinity_tool)

        # Code agent — Eve can deploy herself to fix code
        self.tools.register(CodeAgentTool(workspace_dir="/app"))

        # Visual test — Eve's eyes (Playwright + Qwen vision)
        try:
            from eve.tools.visual_test import VisualTestTool
            self.tools.register(VisualTestTool())
            logger.info("👁️ Visual test tool registered")
        except Exception as e:
            logger.debug(f"Visual test tool not available: {e}")

        # Computer vision / GUI interaction (OpenClaw: screenshot, screen analysis, mouse+keyboard)
        try:
            from eve_computer_vision_tools import COMPUTER_VISION_TOOLS
            for cv_tool in COMPUTER_VISION_TOOLS:
                self.tools.register(cv_tool)
            logger.info("🖥️ Computer vision tools registered (screenshot, screen analysis, GUI interaction)")
        except Exception as e:
            logger.debug(f"Computer vision tools not available: {e}")

        # Web browsing tools — Skyvern (visible) → Hyperbrowser → Playwright (headless)
        from eve.tools.web_tools import (
            SkyvernManager, HyperbrowserManager, BrowseWebTool, FetchPageTool,
            NavigateBrowserTool,
        )

        # Read API keys from env or .env file
        def _read_env_key(key_name):
            """Read key from environment, then fall back to /app/.env file."""
            import os as _os
            val = _os.environ.get(key_name, "")
            if not val:
                try:
                    for line in open("/app/.env"):
                        if line.startswith(f"{key_name}=") and line.strip().split("=", 1)[1]:
                            val = line.strip().split("=", 1)[1]
                            break
                except Exception:
                    pass
            return val

        _sk_key = _read_env_key("SKYVERN_API_KEY")
        _hb_key = _read_env_key("HYPERBROWSER_API_KEY")

        skyvern = SkyvernManager(api_key=_sk_key) if _sk_key else None
        hb = HyperbrowserManager(api_key=_hb_key)

        self.tools.register(BrowseWebTool(hb, skyvern=skyvern))
        self.tools.register(FetchPageTool(hb, skyvern=skyvern))
        self.tools.register(NavigateBrowserTool())

        # Chrome DevTools tools — performance, accessibility, screenshots, page info
        try:
            from eve.tools.chrome_devtools import (
                ChromeDevToolsManager, DevToolsScreenshotTool, DevToolsPerformanceTool,
                DevToolsAccessibilityTool, DevToolsPageInfoTool,
            )
            cdp = ChromeDevToolsManager()
            self.tools.register(DevToolsScreenshotTool(cdp))
            self.tools.register(DevToolsPerformanceTool(cdp))
            self.tools.register(DevToolsAccessibilityTool(cdp))
            self.tools.register(DevToolsPageInfoTool(cdp))
            logger.info("🔧 Chrome DevTools tools registered (screenshot, performance, accessibility, page info)")
        except Exception as e:
            logger.debug(f"Chrome DevTools tools not available: {e}")

        _browsers = []
        if _sk_key:
            _browsers.append(f"Skyvern (key: {_sk_key[:8]}...)")
        if _hb_key:
            _browsers.append(f"Hyperbrowser (key: {_hb_key[:8]}...)")
        _browsers.append("Playwright")
        logger.info(f"✅ Web tools registered: {' → '.join(_browsers)}")

        # Marketing tools
        try:
            from eve.tools.marketing.social_tools import (
                MarketResearchTool, SocialPostTool, CanvaDesignTool, EmailCampaignTool,
                XPostTool,
            )
            self.tools.register(MarketResearchTool(browser_manager=hb))
            self.tools.register(SocialPostTool())
            self.tools.register(XPostTool(get_x_agent_fn=self._get_x_agent))
            self.tools.register(CanvaDesignTool(browser_manager=hb))
            self.tools.register(EmailCampaignTool())

            # Image generation via main Eve API ComfyUI pipeline
            try:
                from eve_generate_image_tool import EveGenerateImageTool
                self.tools.register(EveGenerateImageTool())
                logger.info("🎨 Eve image generation tool registered")
            except ImportError as img_e:
                logger.debug(f"Image generation tool not available: {img_e}")

            # HubSpot (needs API key)
            hubspot_key = self.settings.__dict__.get("hubspot_api_key", "")
            if hubspot_key:
                from eve.tools.marketing.hubspot_tools import (
                    HubSpotClient, HubSpotContactsTool, HubSpotDealsTool,
                )
                hb_client = HubSpotClient(api_key=hubspot_key)
                self.tools.register(HubSpotContactsTool(hb_client))
                self.tools.register(HubSpotDealsTool(hb_client))
        except ImportError as e:
            logger.debug(f"Marketing tools not fully available: {e}")

        # Finance tools
        try:
            from eve.tools.finance.market_tools import (
                StockQuoteTool, CryptoPriceTool, MarketOverviewTool,
            )
            from eve.tools.finance.trading_tools import (
                PortfolioTracker, PortfolioSummaryTool, StockTradeTool, CryptoTradeTool,
            )
            self.tools.register(StockQuoteTool())
            self.tools.register(CryptoPriceTool())
            self.tools.register(MarketOverviewTool())

            tracker = PortfolioTracker(
                data_dir=str(self.settings.memory_path / "portfolio")
            )
            self.tools.register(PortfolioSummaryTool(tracker))
            self.tools.register(StockTradeTool(
                tracker=tracker, browser_manager=hb,
            ))
            self.tools.register(CryptoTradeTool(
                tracker=tracker, browser_manager=hb,
            ))

            # DeFi swap execution (0x Protocol + Jupiter)
            try:
                from eve.tools.crypto.defi_trade_tool import DeFiTradeTool
                from eve.tools.crypto.wallet_manager import WalletManager
                _wm = WalletManager(data_dir=str(self.settings.memory_path))
                self.tools.register(DeFiTradeTool(wallet_manager=_wm, settings_manager=self.user_settings))
                logger.info("DeFiTradeTool registered")
            except ImportError as e:
                logger.debug(f"DeFiTradeTool not available: {e}")

            # Multi-agent stock research (TradingAgents + Ollama Cloud)
            try:
                from eve.tools.trading.trading_agents_tool import StockAnalysisTool
                self.tools.register(StockAnalysisTool())
                logger.info("StockAnalysisTool registered")
            except ImportError as e:
                logger.debug(f"StockAnalysisTool not available: {e}")
        except ImportError as e:
            logger.debug(f"Finance tools not fully available: {e}")

        # DJ Mixer tools — control SolForge DJ via WebSocket
        try:
            from eve.tools.dj_tools import (
                DJControlTool, DJMixerTool, DJFxTool,
                DJHotCueTool, DJLoopTool, DJTransitionTool,
                DJStateTool, DJBrowseTool,
            )
            self.tools.register(DJControlTool())
            self.tools.register(DJMixerTool())
            self.tools.register(DJFxTool())
            self.tools.register(DJHotCueTool())
            self.tools.register(DJLoopTool())
            self.tools.register(DJTransitionTool())
            self.tools.register(DJStateTool())
            self.tools.register(DJBrowseTool())
            logger.info("DJ Mixer tools registered (8 tools)")
        except ImportError as e:
            logger.debug(f"DJ Mixer tools not available: {e}")

    def _get_conversation(self, channel_id: str) -> ConversationMemory:
        """Get or create conversation memory for a channel."""
        if channel_id not in self._conversations:
            self._conversations[channel_id] = ConversationMemory()
        return self._conversations[channel_id]

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )
