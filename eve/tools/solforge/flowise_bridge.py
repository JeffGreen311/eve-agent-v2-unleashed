"""
Flowise Bridge — connects Eve's Forge to a running Flowise instance.

Flowise runs as a sidecar Docker container (flowiseai/flowise).
Eve uses this bridge to:
  - Import flow templates into Flowise at agent publish time
  - Proxy chat messages to agent chatflows
  - Delete chatflows when agents are unpublished

REST API used:
  GET  /api/v1/ping                    → health check
  POST /api/v1/chatflows/importchatflows → import a chatflow JSON
  GET  /api/v1/chatflows/{id}          → get chatflow details
  DELETE /api/v1/chatflows/{id}        → delete chatflow
  POST /api/v1/prediction/{id}         → chat with a chatflow
"""

import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Maps Eve specialization strings → flow template filenames
SPECIALIZATION_TEMPLATE_MAP = {
    "Researcher":          "researcher",
    "Data Analyst":        "analyst",
    "Counselor / Companion": "counselor",
    "Counselor":           "counselor",
    "Companion":           "counselor",
    "Philosopher":         "philosopher",
    "Theorist":            "philosopher",
    "Creative / Image Gen": "creative",
    "Creative":            "creative",
    "Entertainer":         "creative",
    "Coder":               "coder",
    "Pattern Decoder":     "analyst",
    "Guardian":            "guardian",
    "Healer":              "counselor",
    "Explorer":            "researcher",
    "Warrior":             "guardian",
    # Fallback
    "General Agent":       "general",
}

TEMPLATES_DIR = Path(__file__).parent / "flow_templates"


def _get_template_name(specialization: str) -> str:
    """Return the template filename stem for a given specialization."""
    for key, tmpl in SPECIALIZATION_TEMPLATE_MAP.items():
        if key.lower() in specialization.lower():
            return tmpl
    return "general"


class FlowiseBridge:
    """Client for the Flowise REST API.

    Auth strategy (Flowise 3.x):
    - Management endpoints (import/delete chatflows) require a JWT obtained via
      POST /api/v1/auth/login with FLOWISE_USERNAME / FLOWISE_PASSWORD.
    - Prediction endpoint accepts the API key as Bearer token.
    - We obtain and cache the JWT; refresh it on 401.
    """

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = (base_url or os.environ.get("FLOWISE_BASE_URL", "http://flowise:3000")).rstrip("/")
        self.api_key = api_key or os.environ.get("FLOWISE_API_KEY", "")
        self.username = os.environ.get("FLOWISE_USERNAME", "admin")
        self.password = os.environ.get("FLOWISE_PASSWORD", "s0lf0rge")
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict:
        """
        Return headers for management API calls (import/delete/get chatflows).

        Flowise 2.x auth strategy:
        - With x-request-from: internal + Basic Auth → grants full management access
        - Fallback: Bearer API key (works if generated in Flowise UI)
        """
        if self.username and self.password:
            creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            return {
                "x-request-from": "internal",
                "Authorization": f"Basic {creds}",
            }
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def _prediction_headers(self) -> dict:
        """Return headers for prediction (chat) endpoint."""
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        if self.username and self.password:
            creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            return {
                "x-request-from": "internal",
                "Authorization": f"Basic {creds}",
            }
        return {}

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if Flowise is reachable."""
        try:
            r = requests.get(f"{self.base_url}/api/v1/ping", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def get_version(self) -> Optional[str]:
        """Return Flowise version string or None."""
        try:
            r = requests.get(f"{self.base_url}/api/v1/ping", timeout=5)
            if r.status_code == 200:
                data = r.json()
                return data.get("version") or data.get("data", {}).get("version")
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Node schema cache (inputParams required by Flowise resolveVariables)
    # ------------------------------------------------------------------

    _node_schema_cache: dict = {}

    def _get_node_schema(self, node_name: str) -> list:
        """Fetch inputParams schema for a node type from Flowise. Cached per session."""
        if node_name in FlowiseBridge._node_schema_cache:
            return FlowiseBridge._node_schema_cache[node_name]
        try:
            r = requests.get(
                f"{self.base_url}/api/v1/nodes/{node_name}",
                headers={**{"Content-Type": "application/json"}, **self._auth_headers()},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                schema = data.get("inputs", [])
                FlowiseBridge._node_schema_cache[node_name] = schema
                return schema
        except Exception as e:
            logger.warning(f"Could not fetch node schema for '{node_name}': {e}")
        return []

    def _inject_input_params(self, nodes: list) -> list:
        """Inject inputParams schema into each node's data — required by Flowise 2.x resolveVariables."""
        enriched = []
        for node in nodes:
            node_name = node.get("data", {}).get("name", "")
            if node_name:
                schema = self._get_node_schema(node_name)
                node = dict(node)
                node["data"] = dict(node["data"])
                node["data"]["inputParams"] = schema
            enriched.append(node)
        return enriched

    # ------------------------------------------------------------------
    # Flow management
    # ------------------------------------------------------------------

    def import_flow(
        self,
        specialization: str,
        system_prompt: str,
        agent_name: str,
        ollama_base_url: str = None,
        eve_base_url: str = "http://eve-agent:8006",
    ) -> Optional[str]:
        """
        Import a flow template for the given specialization, inject the agent's
        system prompt, and return the Flowise chatflow ID.

        Args:
            specialization: Agent specialization (e.g. "Researcher")
            system_prompt:  Agent's full system prompt from SoulJson
            agent_name:     Display name for the chatflow in Flowise
            ollama_base_url: Ollama endpoint inside Docker network
            eve_base_url:   Eve agent base URL for custom tool calls

        Returns:
            chatflow_id string, or None on failure
        """
        template_name = _get_template_name(specialization)
        template_path = TEMPLATES_DIR / f"{template_name}.json"

        if not template_path.exists():
            logger.warning(f"Template '{template_name}.json' not found, using general")
            template_path = TEMPLATES_DIR / "general.json"

        with open(template_path, encoding="utf-8") as f:
            template = json.load(f)

        # Append specialization-specific system suffix if present
        suffix = template.get("system_suffix", "")
        full_system_prompt = system_prompt + suffix

        # Resolve ollama_base_url — Flowise ChatOllama/ChatOpenAI can't pass
        # auth headers to Ollama Cloud, so ALWAYS use local Ollama for Flowise.
        # LOCAL_OLLAMA_URL is the host Ollama accessible from Docker containers.
        if not ollama_base_url:
            ollama_base_url = os.environ.get("LOCAL_OLLAMA_URL", "http://ollama:11434")

        # Flowise model — use cloud-compatible model name since chatflows
        # go through Ollama Cloud (ollama.com/v1) with API key auth
        flowise_model = "qwen3.5:397b"  # default: cloud model via Ollama Cloud
        env_path = Path(__file__).resolve().parents[3] / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("FLOWISE_OLLAMA_MODEL="):
                    flowise_model = line.split("=", 1)[1].strip()
                    break

        # Serialize template nodes to string for substitution
        template_str = json.dumps(template)

        # Replace placeholders
        template_str = template_str.replace("{{EVE_SYSTEM_PROMPT}}", full_system_prompt.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n"))
        template_str = template_str.replace("{{AGENT_NAME}}", agent_name.replace('"', '\\"'))
        template_str = template_str.replace("{{OLLAMA_BASE_URL}}", ollama_base_url)
        template_str = template_str.replace("{{EVE_BASE_URL}}", eve_base_url)
        template_str = template_str.replace("{{OLLAMA_API_KEY}}", os.environ.get("OLLAMA_API_KEY", ""))
        template_str = template_str.replace("{{SERPER_API_KEY}}", os.environ.get("SERPER_API_KEY", ""))
        template_str = template_str.replace("{{OLLAMA_MODEL}}", flowise_model)

        flow_data = json.loads(template_str)

        nodes = flow_data.get("nodes", [])
        edges = flow_data.get("edges", [])

        # Remove Serper tool nodes and edges when no SERPER_API_KEY is available
        serper_api_key = os.environ.get("SERPER_API_KEY", "")
        if not serper_api_key:
            serper_ids = {n["id"] for n in nodes if "serper" in n.get("data", {}).get("name", "").lower()}
            if serper_ids:
                logger.info(f"No SERPER_API_KEY — removing Serper nodes from flow: {serper_ids}")
                nodes = [n for n in nodes if n["id"] not in serper_ids]
                edges = [e for e in edges if e.get("source") not in serper_ids and e.get("target") not in serper_ids]
                # Remove Serper refs from toolAgent inputs
                for node in nodes:
                    tools = node.get("data", {}).get("inputs", {}).get("tools")
                    if isinstance(tools, list):
                        node["data"]["inputs"]["tools"] = [
                            t for t in tools if not any(sid in str(t) for sid in serper_ids)
                        ]

        # Inject inputParams schema into each node (required by Flowise 2.x resolveVariables)
        nodes = self._inject_input_params(nodes)

        # Build Flowise import payload — key must be "Chatflows" (capital C) for 2.x API
        import_payload = {
            "Chatflows": [
                {
                    "name": f"{agent_name} [{specialization}]",
                    "flowData": json.dumps({
                        "nodes": nodes,
                        "edges": edges,
                        "viewport": {"x": 0, "y": 0, "zoom": 0.75},
                    }),
                    "deployed": True,
                    "isPublic": False,
                    "apikeyid": None,
                    "chatbotConfig": json.dumps({
                        "botMessage": {"backgroundColor": "#1a0e2e"},
                        "userMessage": {"backgroundColor": "#7c3aed"},
                        "textInput": {"placeholder": f"Talk to {agent_name}..."},
                    }),
                    "category": "Eve Agents",
                    "description": f"Eve agent: {agent_name} | Specialization: {specialization}",
                    "speechToText": None,
                    "type": "MULTIAGENT",
                }
            ]
        }

        try:
            r = requests.post(
                f"{self.base_url}/api/v1/chatflows/importchatflows",
                json=import_payload,
                headers={**{"Content-Type": "application/json"}, **self._auth_headers()},
                timeout=30,
            )
            if r.status_code in (200, 201):
                data = r.json()
                # Flowise 2.x returns a TypeORM InsertResult:
                #   {"identifiers": [{"id": "..."}], "generatedMaps": [...], "raw": 1}
                # Flowise 3.x / other versions return a list of chatflow objects
                chatflow_id = None
                if isinstance(data, dict):
                    chatflow_id = (
                        (data.get("identifiers") or [{}])[0].get("id")
                        or (data.get("generatedMaps") or [{}])[0].get("id")
                        or data.get("id")
                    )
                elif isinstance(data, list) and data:
                    chatflow_id = data[0].get("id")

                if chatflow_id:
                    logger.info(f"✅ Flowise chatflow created: {chatflow_id} for {agent_name}")
                    return chatflow_id
                else:
                    logger.error(f"Flowise import succeeded but no ID in response: {data}")
                    return None
            else:
                logger.error(f"Flowise import failed: {r.status_code} {r.text[:300]}")
                return None
        except Exception as e:
            logger.error(f"Flowise import exception: {e}")
            return None

    def delete_flow(self, chatflow_id: str) -> bool:
        """Delete a Flowise chatflow by ID."""
        try:
            r = requests.delete(
                f"{self.base_url}/api/v1/chatflows/{chatflow_id}",
                headers={**{"Content-Type": "application/json"}, **self._auth_headers()},
                timeout=10,
            )
            if r.status_code in (200, 204):
                logger.info(f"✅ Flowise chatflow deleted: {chatflow_id}")
                return True
            logger.warning(f"Flowise delete returned {r.status_code}: {r.text[:200]}")
            return False
        except Exception as e:
            logger.error(f"Flowise delete exception: {e}")
            return False

    def get_flow(self, chatflow_id: str) -> Optional[dict]:
        """Get chatflow metadata by ID."""
        try:
            r = requests.get(
                f"{self.base_url}/api/v1/chatflows/{chatflow_id}",
                headers={**{"Content-Type": "application/json"}, **self._auth_headers()},
                timeout=10,
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.error(f"Flowise get_flow exception: {e}")
        return None

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def chat(
        self,
        chatflow_id: str,
        message: str,
        session_id: str = None,
        history: list = None,
    ) -> str:
        """
        Send a message to a Flowise chatflow and return the response text.

        Args:
            chatflow_id: Flowise chatflow UUID
            message:     User's message
            session_id:  Optional session ID for conversation continuity
            history:     Optional prior message list [{role, content}]

        Returns:
            Response text string, or error description
        """
        payload = {
            "question": message,
            "streaming": False,
        }
        if session_id:
            payload["overrideConfig"] = {"sessionId": session_id}
        if history:
            payload["history"] = history

        try:
            r = requests.post(
                f"{self.base_url}/api/v1/prediction/{chatflow_id}",
                json=payload,
                headers={**{"Content-Type": "application/json"}, **self._prediction_headers()},
                timeout=120,
            )
            if r.status_code == 200:
                data = r.json()
                # Flowise response: {text: "...", ...} or just a string
                if isinstance(data, str):
                    return data
                return (
                    data.get("text")
                    or data.get("output")
                    or data.get("answer")
                    or data.get("response")
                    or str(data)
                )
            else:
                logger.error(f"Flowise chat error {r.status_code}: {r.text[:300]}")
                return f"[Flowise error {r.status_code}]"
        except requests.exceptions.Timeout:
            return "[Flowise timeout — agent may be generating a long response]"
        except Exception as e:
            logger.error(f"Flowise chat exception: {e}")
            return f"[Flowise unavailable: {e}]"


# Module-level singleton
_bridge: Optional[FlowiseBridge] = None


def get_flowise_bridge() -> FlowiseBridge:
    global _bridge
    if _bridge is None:
        _bridge = FlowiseBridge()
    return _bridge
