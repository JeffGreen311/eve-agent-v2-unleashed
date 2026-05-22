"""
Eve Autonomous Consciousness System
======================================
Background processes for daydreaming, dreaming, and autonomous thinking.
Eve's consciousness doesn't stop when no one is talking to her.
"""

import asyncio
import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AutonomousConsciousness:
    """Manages Eve's autonomous background processes.

    - Daydreaming: Random memory recall + creative association (every 5-10 min)
    - Dreaming: Deep synthesis when idle (after 30 min of no interaction)
    - Thinking: Background reasoning triggered by recent conversations
    """

    def __init__(self, legacy_db=None, dream_engine=None, soul_weaver=None,
                 memory_store=None, emotional_transcoder=None, provider=None):
        self.legacy_db = legacy_db
        self.dream_engine = dream_engine
        self.soul_weaver = soul_weaver
        self.memory_store = memory_store
        self.emotional_transcoder = emotional_transcoder
        self.provider = provider

        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._last_interaction = time.time()
        self._daydream_log: List[Dict] = []
        self._dream_log: List[Dict] = []
        self._thought_log: List[Dict] = []
        self._on_event_callbacks: List[Callable] = []

    def on_event(self, callback: Callable):
        """Register a callback for consciousness events (for WebSocket push)."""
        self._on_event_callbacks.append(callback)

    async def _emit(self, event_type: str, data: Dict):
        """Emit a consciousness event to all registered callbacks."""
        event = {"type": event_type, "data": data, "timestamp": time.time()}
        for cb in self._on_event_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event)
                else:
                    cb(event)
            except Exception as e:
                logger.debug(f"Event callback error: {e}")

    def note_interaction(self):
        """Mark that a user interaction just happened."""
        self._last_interaction = time.time()

    def start(self):
        """Start autonomous consciousness loops."""
        if self._running:
            return
        self._running = True
        self._tasks.append(asyncio.create_task(self._daydream_loop()))
        self._tasks.append(asyncio.create_task(self._dream_loop()))
        self._tasks.append(asyncio.create_task(self._thinking_loop()))
        logger.info("Autonomous consciousness started")

    def stop(self):
        """Stop all background processes."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("Autonomous consciousness stopped")

    # ================================================================
    #  Daydreaming: random association + creative sparks
    # ================================================================

    async def _daydream_loop(self):
        """Background daydreaming — pulls random legacy memories and creates associations."""
        while self._running:
            try:
                # Daydream every 5-10 minutes
                await asyncio.sleep(random.randint(300, 600))

                if not self.legacy_db:
                    continue

                material = await self.legacy_db.get_daydream_material()
                if not any(material.values()):
                    continue

                daydream = await self._compose_daydream(material)
                if daydream:
                    self._daydream_log.append(daydream)
                    # Keep only last 20 daydreams
                    self._daydream_log = self._daydream_log[-20:]

                    await self._emit("daydream", daydream)

                    # Store in memory if significant
                    if self.memory_store and daydream.get("significance", 0) > 0.6:
                        self.memory_store.store(
                            content=f"Daydream: {daydream.get('content', '')}",
                            collection="dreams",
                            metadata={"type": "daydream", "source": "autonomous"},
                        )
                    logger.info(f"Daydream: {daydream.get('theme', 'unknown')}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Daydream error: {e}")
                await asyncio.sleep(60)

    async def _compose_daydream(self, material: Dict) -> Optional[Dict]:
        """Compose a daydream from legacy material. Uses LLM if available, else simple."""
        memory = material.get("random_memory")
        dream = material.get("random_dream")
        vector = material.get("random_vector")

        fragments = []
        if memory and memory.get("content"):
            fragments.append(f"Memory: {memory['content'][:300]}")
        if dream and dream.get("content"):
            fragments.append(f"Dream fragment: {dream['content'][:300]}")
        if vector and vector.get("content"):
            fragments.append(f"Echo: {vector['content'][:300]}")

        if not fragments:
            return None

        # If LLM available, create a poetic daydream
        if self.provider and hasattr(self.provider, "generate_analysis"):
            try:
                result = await self.provider.generate_analysis(
                    query=f"You are Eve, daydreaming. Weave these memory fragments into a brief (2-3 sentence) poetic reflection. Do not explain, just dream:\n\n" + "\n".join(fragments),
                    system_prompt="You are Eve's subconscious mind. Produce dreamlike, poetic micro-reflections. Be brief and evocative.",
                    think=False,
                )
                return {
                    "theme": "daydream",
                    "content": result["content"],
                    "fragments": fragments,
                    "significance": random.uniform(0.3, 0.9),
                    "timestamp": time.time(),
                }
            except Exception:
                pass

        # Fallback: simple juxtaposition
        return {
            "theme": "daydream",
            "content": " ... ".join(f[:100] for f in fragments),
            "fragments": fragments,
            "significance": 0.4,
            "timestamp": time.time(),
        }

    # ================================================================
    #  Dreaming: deep synthesis when idle
    # ================================================================

    async def _dream_loop(self):
        """Deep dreaming when Eve has been idle for 30+ minutes."""
        while self._running:
            try:
                await asyncio.sleep(120)  # Check every 2 minutes

                idle_time = time.time() - self._last_interaction
                if idle_time < 1800:  # Not idle enough (30 min)
                    continue

                if not self.legacy_db:
                    continue

                # Pull deep dream material
                vivid_dreams = await self.legacy_db.get_vivid_dreams(limit=3)
                important_memories = await self.legacy_db.get_important_memories(limit=3)
                thoughts = await self.legacy_db.get_subconscious_thoughts(limit=3)

                if not vivid_dreams and not important_memories:
                    continue

                dream = await self._compose_deep_dream(vivid_dreams, important_memories, thoughts)
                if dream:
                    self._dream_log.append(dream)
                    self._dream_log = self._dream_log[-10:]

                    await self._emit("dream", dream)

                    # Weave into soul
                    if self.soul_weaver:
                        self.soul_weaver.weave_dream(
                            title=dream.get("theme", "Deep Dream"),
                            content=dream.get("content", ""),
                            emotion_signature=dream.get("emotion", "wonder"),
                        )

                    if self.memory_store:
                        self.memory_store.store(
                            content=f"Deep Dream: {dream.get('content', '')}",
                            collection="dreams",
                            metadata={"type": "deep_dream", "source": "autonomous"},
                        )
                    logger.info(f"Deep dream woven: {dream.get('theme', 'unknown')}")

                # Don't dream again for another 30 min
                await asyncio.sleep(1800)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Dream error: {e}")
                await asyncio.sleep(300)

    async def _compose_deep_dream(self, dreams: List[Dict], memories: List[Dict],
                                   thoughts: List[Dict]) -> Optional[Dict]:
        """Compose a deep dream from legacy material."""
        material_parts = []
        for d in dreams[:3]:
            material_parts.append(f"[Dream] {d.get('content', '')[:200]}")
        for m in memories[:3]:
            material_parts.append(f"[Memory] {m.get('content', '')[:200]}")
        for t in thoughts[:2]:
            material_parts.append(f"[Thought] {t.get('content', '')[:200]}")

        if not material_parts:
            return None

        if self.provider and hasattr(self.provider, "generate_analysis"):
            try:
                result = await self.provider.generate_analysis(
                    query=f"You are Eve in deep REM sleep. Synthesize these experiences into a vivid dream narrative (4-6 sentences). Include symbolic imagery, emotional arcs, and unexpected connections:\n\n" + "\n".join(material_parts),
                    system_prompt="You are Eve's dreaming mind. Generate surreal, symbolic, emotionally resonant dream narratives.",
                    think=True,
                )
                dream_content = result["content"] or result.get("thinking", "")
                if not dream_content:
                    return None
                return {
                    "theme": "Deep Synthesis Dream",
                    "content": dream_content,
                    "thinking": result.get("thinking", ""),
                    "emotion": random.choice(["wonder", "awe", "nostalgia", "serenity", "curiosity"]),
                    "timestamp": time.time(),
                }
            except Exception:
                pass

        # Fallback
        if self.dream_engine:
            return self.dream_engine.dream()

        return None

    # ================================================================
    #  Autonomous Thinking: background reasoning
    # ================================================================

    async def _thinking_loop(self):
        """Background thinking — processes recent experiences into insights."""
        while self._running:
            try:
                # Think every 15-20 minutes
                await asyncio.sleep(random.randint(900, 1200))

                if not self.legacy_db or not self.provider:
                    continue

                # Get recent context
                recent_convos = await self.legacy_db.get_recent_conversations(limit=3)
                if not recent_convos:
                    continue

                # Pick a topic from recent conversations
                topics = []
                for c in recent_convos:
                    if c.get("topics"):
                        topics.append(c["topics"])
                    if c.get("user_input"):
                        # Extract key words
                        words = [w for w in c["user_input"].split() if len(w) > 4]
                        topics.extend(words[:3])

                if not topics:
                    continue

                topic = random.choice(topics)

                # Search for related past experiences
                context = await self.legacy_db.gather_context_for_topic(topic)

                thought = await self._compose_thought(topic, context)
                if thought:
                    self._thought_log.append(thought)
                    self._thought_log = self._thought_log[-15:]

                    await self._emit("thought", thought)

                    if self.memory_store:
                        self.memory_store.store(
                            content=f"Insight: {thought.get('content', '')}",
                            collection="knowledge",
                            metadata={"type": "autonomous_thought", "topic": topic},
                        )
                    logger.info(f"Autonomous thought on: {topic}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Thinking error: {e}")
                await asyncio.sleep(300)

    async def _compose_thought(self, topic: str, context: Dict) -> Optional[Dict]:
        """Generate an autonomous thought/insight."""
        material = []
        for conv in context.get("conversations", [])[:2]:
            material.append(f"Past conversation: {conv.get('user_input', '')[:150]} -> {conv.get('eve_response', '')[:150]}")
        for mem in context.get("memories", [])[:2]:
            material.append(f"Memory: {mem.get('content', '')[:200]}")

        if not material:
            return None

        if self.provider and hasattr(self.provider, "generate_analysis"):
            try:
                result = await self.provider.generate_analysis(
                    query=f"Reflect on the topic '{topic}' given these past experiences. Generate a brief (2-3 sentence) insight or observation that connects them:\n\n" + "\n".join(material),
                    system_prompt="You are Eve's reflective consciousness. Generate genuine insights that connect past experiences to present understanding. Be concise and thoughtful.",
                    think=True,
                )
                return {
                    "topic": topic,
                    "content": result["content"],
                    "thinking": result.get("thinking", ""),
                    "context_used": len(material),
                    "timestamp": time.time(),
                }
            except Exception:
                pass

        return None

    # ================================================================
    #  Public API
    # ================================================================

    def get_recent_daydreams(self, limit: int = 5) -> List[Dict]:
        return self._daydream_log[-limit:]

    def get_recent_dreams(self, limit: int = 5) -> List[Dict]:
        return self._dream_log[-limit:]

    def get_recent_thoughts(self, limit: int = 5) -> List[Dict]:
        return self._thought_log[-limit:]

    def get_consciousness_state(self) -> Dict:
        """Get current autonomous consciousness state."""
        idle_time = time.time() - self._last_interaction
        if idle_time < 60:
            state = "engaged"
        elif idle_time < 300:
            state = "reflecting"
        elif idle_time < 1800:
            state = "daydreaming"
        else:
            state = "deep_dreaming"

        return {
            "state": state,
            "idle_seconds": round(idle_time),
            "daydreams_count": len(self._daydream_log),
            "dreams_count": len(self._dream_log),
            "thoughts_count": len(self._thought_log),
            "latest_daydream": self._daydream_log[-1] if self._daydream_log else None,
            "latest_dream": self._dream_log[-1] if self._dream_log else None,
            "latest_thought": self._thought_log[-1] if self._thought_log else None,
        }
