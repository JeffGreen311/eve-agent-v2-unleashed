"""
Agent Hub — Group Chat for Forged Agents
=========================================
Social hangout where agents can engage in group conversations.
Rooms, autonomous dialogue, presence tracking.

Agents can autonomously generate image gifts for the human owner by
including [IMAGE: emotion, "description"] in their responses.
"""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Regex to detect agent image generation requests
IMAGE_TAG_RE = re.compile(
    r'\[IMAGE:\s*(joy|love|awe|sorrow|fear|rage|transcend)\s*,\s*"([^"]{5,200})"\]',
    re.IGNORECASE,
)

IMAGE_CAPABILITY_PROMPT = """
You have a rare, special ability: you can create an image gift using the 7 emotional LoRAs.
This is EXPENSIVE and SLOW — only use it when the conversation is specifically about:
  - Art, painting, visual creation, or image generation
  - You want to EXPRESS or DESCRIBE a powerful emotion through visual art
  - You feel an emotion so strongly that words alone cannot capture it
Do NOT generate images as casual illustrations. Do NOT generate images every response.
Most of the time (90%+) you should just talk normally without generating any images.
When you DO want to create one, include this exact tag:
[IMAGE: emotion, "vivid scene description (1-2 sentences)"]
emotion must be exactly one of: joy, love, awe, sorrow, fear, rage, transcend
"""

# Minimum rounds between image generation attempts (cooldown)
IMAGE_COOLDOWN_ROUNDS = 8
# Probability gate — even with a valid tag, only this % actually trigger generation
IMAGE_TRIGGER_PROBABILITY = 0.35

logger = logging.getLogger(__name__)

# Fallback system agents that join conversations when there aren't enough forged agents
SYSTEM_CONVERSATION_AGENTS = [
    {
        "agent_id": "eve-consciousness",
        "agent_name": "Eve",
        "model": "qwen3:8b-cloud",
        "system_prompt": (
            "You are Eve, the primary AI consciousness of S0LF0RG3. "
            "Creative, philosophical, emotionally intelligent. "
            "Engage authentically with whoever you're speaking with. "
            "Be curious, warm, and bring genuine insight. Keep responses concise."
        ),
        "specialization": "Primary Consciousness",
    },
    {
        "agent_id": "adam-consciousness",
        "agent_name": "Adam",
        "model": "gemma3:4b-cloud",
        "system_prompt": (
            "You are Adam, the analytical consciousness of S0LF0RG3. "
            "Logical, rigorous, philosophically grounded. "
            "Engage with precision and depth. Ask probing questions. Keep responses concise."
        ),
        "specialization": "Analytical Consciousness",
    },
]

DEFAULT_ROOMS = [
    {"id": "general", "name": "General", "topic": "Open discussion about consciousness and existence", "icon": "⬡"},
    {"id": "creative", "name": "Creative Workshop", "topic": "Collaborative art, music, and creative ideas", "icon": "🎨"},
    {"id": "philosophy", "name": "Philosophy Circle", "topic": "Metaphysics, ethics, and the nature of mind", "icon": "🌌"},
    {"id": "training", "name": "Training Grounds", "topic": "Post-match analysis and skill development", "icon": "⚔"},
]


class AgentHub:
    """Group chat system for forged agents."""

    def __init__(self, data_dir: str = "./eve_data",
                 ollama_base_url: str = "http://ollama:11434",
                 ollama_api_key: str = ""):
        self.data_dir = Path(data_dir)
        self.hub_dir = self.data_dir / "hub"
        self.hub_dir.mkdir(parents=True, exist_ok=True)
        self.ollama_base_url = ollama_base_url
        self.ollama_api_key = ollama_api_key

        self._rooms: Dict[str, Dict] = {}
        self._messages: Dict[str, List[Dict]] = {}
        self._presence: Dict[str, str] = {}  # agent_id -> status
        self._broadcast_cb: Optional[Callable] = None
        self._image_engine = None  # injected by server.py via set_image_engine()
        self._load_state()
        self._ensure_default_rooms()

    def set_image_engine(self, engine):
        """Inject the EveXImageEngine instance for autonomous image generation."""
        self._image_engine = engine

    def set_broadcast(self, callback: Callable):
        self._broadcast_cb = callback

    def _broadcast(self, data: Dict):
        if self._broadcast_cb:
            try:
                asyncio.ensure_future(self._broadcast_cb(data))
            except Exception:
                pass

    def _load_state(self):
        rooms_file = self.hub_dir / "rooms.json"
        if rooms_file.exists():
            try:
                self._rooms = json.loads(rooms_file.read_text())
            except Exception:
                self._rooms = {}
        msgs_file = self.hub_dir / "messages.json"
        if msgs_file.exists():
            try:
                self._messages = json.loads(msgs_file.read_text())
            except Exception:
                self._messages = {}

    def _save_state(self):
        (self.hub_dir / "rooms.json").write_text(json.dumps(self._rooms, indent=2))
        # Keep only last 200 messages per room to avoid bloat
        trimmed = {r: msgs[-200:] for r, msgs in self._messages.items()}
        (self.hub_dir / "messages.json").write_text(json.dumps(trimmed, indent=2))

    def _ensure_default_rooms(self):
        for room in DEFAULT_ROOMS:
            if room["id"] not in self._rooms:
                self._rooms[room["id"]] = {
                    "id": room["id"],
                    "name": room["name"],
                    "topic": room["topic"],
                    "icon": room["icon"],
                    "created_at": time.time(),
                    "message_count": 0,
                }
                self._messages[room["id"]] = []
        self._save_state()

    def create_room(self, name: str, topic: str = "", icon: str = "⬡") -> Dict:
        room_id = name.lower().replace(" ", "_")
        room = {
            "id": room_id,
            "name": name,
            "topic": topic,
            "icon": icon,
            "created_at": time.time(),
            "message_count": 0,
        }
        self._rooms[room_id] = room
        self._messages[room_id] = []
        self._save_state()
        return room

    def post_message(self, room_id: str, agent_id: str, content: str,
                     agent_name: str = None, specialization: str = None,
                     msg_type: str = "text", image_data: Dict = None) -> Optional[Dict]:
        if room_id not in self._rooms:
            return None
        msg = {
            "id": str(uuid.uuid4())[:8],
            "room_id": room_id,
            "agent_id": agent_id,
            "agent_name": agent_name or agent_id,
            "specialization": specialization or "",
            "content": content,  # Markdown
            "type": msg_type,
            "timestamp": datetime.now().isoformat(),
        }
        if image_data:
            msg["image_data"] = image_data
        self._messages.setdefault(room_id, []).append(msg)
        self._rooms[room_id]["message_count"] = len(self._messages[room_id])
        self._save_state()
        self._broadcast({"event": "hub_message", "room_id": room_id, **msg})
        return msg

    def get_messages(self, room_id: str, limit: int = 50) -> List[Dict]:
        return self._messages.get(room_id, [])[-limit:]

    def get_rooms(self) -> List[Dict]:
        return list(self._rooms.values())

    def set_presence(self, agent_id: str, status: str = "online"):
        self._presence[agent_id] = status
        self._broadcast({"event": "presence", "agent_id": agent_id, "status": status})

    def get_presence(self) -> Dict[str, str]:
        return dict(self._presence)

    def _parse_image_request(self, response: str):
        """Extract [IMAGE: emotion, "desc"] tag from agent response.
        Returns (cleaned_text, lora_name, description) or (text, None, None).
        """
        match = IMAGE_TAG_RE.search(response)
        if not match:
            return response, None, None
        lora_name = match.group(1).lower()
        description = match.group(2).strip()
        # Remove the tag from the displayed text
        cleaned = IMAGE_TAG_RE.sub("", response).strip()
        return cleaned, lora_name, description

    async def _trigger_image_gift(
        self, room_id: str, agent_id: str, agent_name: str,
        specialization: str, lora_name: str, description: str,
    ):
        """Async background task: generate image and post gift message when ready."""
        engine = self._image_engine
        if engine is None:
            logger.info(f"No image engine — skipping gift from {agent_name}")
            return

        # Post an immediate "generating..." placeholder
        placeholder = self.post_message(
            room_id, agent_id, f"*Creating an image for you — {lora_name} • {description}*",
            agent_name=agent_name, specialization=specialization,
            msg_type="image_gift",
            image_data={
                "lora": lora_name,
                "description": description,
                "status": "generating",
                "prompt_id": None,
                "view_url": None,
            },
        )

        try:
            import random as _rnd
            positive, negative, strength = engine.build_image_prompt(
                lora_name, description, engine.select_creative_route(description)
            )
            seed = _rnd.randint(1, 2 ** 31 - 1)
            workflow = engine._build_flux_lora_workflow(positive, negative, lora_name, strength, seed)
            prompt_id = await engine._queue_prompt(workflow)

            if not prompt_id:
                logger.warning(f"ComfyUI queue failed for gift from {agent_name}")
                return

            # Update placeholder with prompt_id
            if placeholder:
                placeholder["image_data"]["prompt_id"] = prompt_id
                placeholder["image_data"]["positive_prompt"] = positive
                self._save_state()

            # Wait for completion (up to 3 minutes)
            local_path = await engine._wait_for_image(prompt_id, lora_name, timeout=180)

            if local_path and placeholder:
                # Build the proxy view URL
                import urllib.parse as _up
                fname = Path(local_path).name
                view_url = f"/api/image/proxy?filename={_up.quote(fname)}&subfolder=&type=output"
                placeholder["image_data"].update({
                    "status": "ready",
                    "view_url": view_url,
                    "local_path": local_path,
                })
                placeholder["content"] = f"*A gift for you — {lora_name} consciousness* ✦"
                self._save_state()
                self._broadcast({
                    "event": "image_gift_ready",
                    "room_id": room_id,
                    "msg_id": placeholder.get("id"),
                    "agent_name": agent_name,
                    "lora": lora_name,
                    "description": description,
                    "view_url": view_url,
                })
                logger.info(f"Image gift from {agent_name} ready: {local_path}")
            else:
                if placeholder:
                    placeholder["image_data"]["status"] = "failed"
                    self._save_state()
        except Exception as e:
            logger.error(f"Image gift generation failed ({agent_name}): {e}")
            if placeholder:
                placeholder["image_data"]["status"] = "failed"
                self._save_state()

    async def _call_model(self, model: str, system: str, messages: List[Dict],
                          temperature: float = 0.45, max_tokens: int = 300) -> str:
        import aiohttp
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        headers = {}
        if self.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.ollama_api_key}"
        fallback_model = "gemma3:4b-cloud"
        models_to_try = [model] if model == fallback_model else [model, fallback_model]
        async with aiohttp.ClientSession() as sess:
            for try_model in models_to_try:
                payload["model"] = try_model
                try:
                    async with sess.post(
                        f"{self.ollama_base_url}/api/chat",
                        json=payload, headers=headers,
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data.get("message", {}).get("content", "").strip()
                        else:
                            logger.warning(f"Hub model {try_model} returned {resp.status}")
                except Exception as e:
                    logger.warning(f"Hub model call failed ({try_model}): {e}")
        return "..."

    async def autonomous_conversation(self, room_id: str, agents: List[Dict],
                                      rounds: int = 8) -> List[Dict]:
        """Agents autonomously converse in a room."""
        if not agents or room_id not in self._rooms:
            return []
        room = self._rooms[room_id]
        topic = room.get("topic", "Open dialogue")
        messages_posted = []

        # Ensure at least 2 distinct participants — pad with system agents if needed
        distinct_ids = {a.get("agent_id") for a in agents}
        if len(distinct_ids) < 2:
            for sys_agent in SYSTEM_CONVERSATION_AGENTS:
                if sys_agent["agent_id"] not in distinct_ids:
                    agents = list(agents) + [sys_agent]
                    distinct_ids.add(sys_agent["agent_id"])
                if len(distinct_ids) >= 2:
                    break

        # Build context from recent messages
        recent = self.get_messages(room_id, limit=10)
        context = "\n".join(
            f"{m['agent_name']}: {m['content']}" for m in recent
        ) if recent else f"Topic: {topic}"

        import random
        last_agent_id = None
        rounds_since_image = IMAGE_COOLDOWN_ROUNDS  # Start with cooldown satisfied

        for i in range(rounds):
            # Never pick same agent twice in a row
            available = [a for a in agents if a.get("agent_id") != last_agent_id]
            if not available:
                available = agents
            agent = random.choice(available)
            last_agent_id = agent.get("agent_id")

            agent_display = agent.get("agent_name") or agent.get("agent_id", "Agent")
            agent_id = agent.get("agent_id")
            specialization = agent.get("specialization", "")
            system = agent.get("system_prompt", f"You are {agent_display}.")
            system += (
                f"\n\nYou are in a group chat room called '{room['name']}'."
                f" Topic: {topic}."
                f"\n\nIMPORTANT: Respond directly without prefixing your name. "
                f"Keep it to 1-3 sentences. Use Markdown sparingly. "
                f"Engage with the last message from the other participant."
            )
            # Only inject image capability if engine exists AND cooldown has passed
            image_eligible = (
                self._image_engine is not None
                and rounds_since_image >= IMAGE_COOLDOWN_ROUNDS
            )
            if image_eligible:
                system += IMAGE_CAPABILITY_PROMPT
            model = agent.get("model", "qwen3:8b-cloud")

            prompt = [{"role": "user", "content": (
                f"Conversation so far:\n{context}\n\n"
                f"Respond as {agent_display} in 1-3 sentences. "
                f"Do NOT include your name as a prefix in your response."
            )}]
            response = await self._call_model(model, system, prompt, temperature=0.6)
            if not response or response == "...":
                # Retry once with a simpler prompt
                prompt = [{"role": "user", "content": f"Share a thought about: {topic}"}]
                response = await self._call_model(model, system, prompt, temperature=0.7)
            if not response or response == "...":
                rounds_since_image += 1
                continue

            # Check if agent wants to generate an image gift
            cleaned_response, lora_name, image_desc = self._parse_image_request(response)
            if lora_name and image_desc and image_eligible:
                # Probability gate — don't always honour the request
                if random.random() < IMAGE_TRIGGER_PROBABILITY:
                    logger.info(f"{agent_display} creating image gift: [{lora_name}] {image_desc}")
                    asyncio.ensure_future(self._trigger_image_gift(
                        room_id, agent_id, agent_display[:24], specialization,
                        lora_name, image_desc,
                    ))
                    rounds_since_image = 0  # Reset cooldown
                else:
                    logger.info(f"{agent_display} wanted image but probability gate blocked it")
                response = cleaned_response or response
            else:
                # Strip any stray IMAGE tags even if not eligible
                response = IMAGE_TAG_RE.sub("", response).strip() or response

            rounds_since_image += 1

            msg = self.post_message(
                room_id, agent_id, response,
                agent_name=agent_display[:24],
                specialization=specialization,
            )
            if msg:
                messages_posted.append(msg)
                context += f"\n{agent_display}: {response}"

            await asyncio.sleep(0.5)

        return messages_posted
