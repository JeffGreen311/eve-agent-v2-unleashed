"""
X Account Manager
==================
Manages multiple X/Twitter accounts for Eve Agent.
Each account gets its own EveXContentAgent instance with isolated
queue, schedule, and settings.

Credentials are stored in accounts.json (plaintext — instruct users
to keep their data directory private). Future: encrypt at rest.
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_CONTENT_TYPES = [
    "dream_dispatch",
    "consciousness_reflection",
    "creative_spark",
    "conversation_echo",
    "cosmic_observation",
    "philosophical_musing",
]


class XAccountManager:
    """
    Manages multiple X accounts and their associated content agents.

    Lifecycle:
      1. init(legacy_db, provider, data_dir)  — loads saved accounts
      2. start_all()                            — starts schedulers for autostart accounts
      3. add_account(...)                       — adds + persists a new account
      4. remove_account(account_id)             — stops agent, removes from storage
    """

    def __init__(self, legacy_db, provider, data_dir: str = "", memory_store=None):
        self.legacy_db = legacy_db
        self.provider = provider
        self.memory_store = memory_store
        self.data_dir = Path(data_dir) if data_dir else Path("./eve_data/x_accounts")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._accounts_file = self.data_dir / "accounts.json"
        self._accounts: Dict[str, Dict] = {}     # account_id -> account record
        self._agents: Dict[str, object] = {}     # account_id -> EveXContentAgent

        self._load_accounts()

    # ----------------------------------------------------------------
    #  Persistence
    # ----------------------------------------------------------------

    def _load_accounts(self):
        if self._accounts_file.exists():
            try:
                with open(self._accounts_file, "r", encoding="utf-8") as f:
                    self._accounts = json.load(f)
                logger.info(f"Loaded {len(self._accounts)} X account(s)")
            except Exception as e:
                logger.error(f"Failed to load X accounts: {e}")
                self._accounts = {}

    def _save_accounts(self):
        try:
            with open(self._accounts_file, "w", encoding="utf-8") as f:
                json.dump(self._accounts, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save X accounts: {e}")

    # ----------------------------------------------------------------
    #  Account management
    # ----------------------------------------------------------------

    def add_account(
        self,
        username: str,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_token_secret: str,
        bearer_token: str = "",
        display_name: str = "",
        persona_context: str = "",
        mode: str = "queue",
        posts_per_day: int = 3,
        autostart: bool = False,
        content_types: Optional[List[str]] = None,
        max_chars: int = 280,
    ) -> Dict:
        """Add a new X account. Returns the account record."""
        account_id = f"acc_{uuid.uuid4().hex[:10]}"
        record = {
            "id": account_id,
            "username": username.lstrip("@"),
            "display_name": display_name or username,
            "persona_context": persona_context,
            "credentials": {
                "api_key": api_key,
                "api_secret": api_secret,
                "access_token": access_token,
                "access_token_secret": access_token_secret,
                "bearer_token": bearer_token,
            },
            "settings": {
                "mode": mode,
                "posts_per_day": posts_per_day,
                "autostart": autostart,
                "content_types": content_types or DEFAULT_CONTENT_TYPES,
                "max_chars": max_chars,
            },
            "added_at": time.time(),
            "status": "active",
        }
        self._accounts[account_id] = record
        self._save_accounts()

        # Spin up the agent
        self._create_agent(record)
        if autostart:
            self.start_account(account_id)

        logger.info(f"Added X account @{username} ({account_id})")
        return self._public_record(record)

    def remove_account(self, account_id: str) -> bool:
        if account_id not in self._accounts:
            return False
        self.stop_account(account_id)
        del self._accounts[account_id]
        if account_id in self._agents:
            del self._agents[account_id]
        self._save_accounts()
        logger.info(f"Removed X account {account_id}")
        return True

    def update_settings(self, account_id: str, **kwargs) -> Optional[Dict]:
        """Update scheduling/persona settings for an account."""
        record = self._accounts.get(account_id)
        if not record:
            return None

        settings = record["settings"]
        for key in ("mode", "posts_per_day", "autostart", "content_types", "max_chars"):
            if key in kwargs:
                settings[key] = kwargs[key]
        if "persona_context" in kwargs:
            record["persona_context"] = kwargs["persona_context"]
        if "display_name" in kwargs:
            record["display_name"] = kwargs["display_name"]

        self._save_accounts()

        # Apply live to running agent
        agent = self._agents.get(account_id)
        if agent:
            if "mode" in kwargs:
                agent.mode = kwargs["mode"]
            if "posts_per_day" in kwargs:
                agent.posts_per_day = kwargs["posts_per_day"]
            if "max_chars" in kwargs:
                agent.max_chars = kwargs["max_chars"]
                agent.generator.max_chars = kwargs["max_chars"]
            if "persona_context" in kwargs:
                agent.generator.persona_context = kwargs.get("persona_context", "")

        return self._public_record(record)

    # ----------------------------------------------------------------
    #  Agent lifecycle
    # ----------------------------------------------------------------

    def start_all(self):
        """Start agents for all accounts with autostart=True."""
        for account_id, record in self._accounts.items():
            if record["settings"].get("autostart"):
                agent = self._get_or_create_agent(account_id)
                if agent and not agent._running:
                    agent.start()
                    logger.info(f"Auto-started X agent for @{record['username']}")

    def start_account(self, account_id: str) -> bool:
        agent = self._get_or_create_agent(account_id)
        if agent:
            agent.start()
            return True
        return False

    def stop_account(self, account_id: str) -> bool:
        agent = self._agents.get(account_id)
        if agent:
            agent.stop()
            return True
        return False

    # ----------------------------------------------------------------
    #  Proxy agent operations
    # ----------------------------------------------------------------

    def get_agent(self, account_id: str):
        return self._get_or_create_agent(account_id)

    def list_accounts(self) -> List[Dict]:
        result = []
        for account_id, record in self._accounts.items():
            pub = self._public_record(record)
            agent = self._agents.get(account_id)
            pub["agent_status"] = agent.get_status() if agent else {"running": False}
            result.append(pub)
        return result

    def get_account(self, account_id: str) -> Optional[Dict]:
        record = self._accounts.get(account_id)
        if not record:
            return None
        pub = self._public_record(record)
        agent = self._agents.get(account_id)
        pub["agent_status"] = agent.get_status() if agent else {"running": False}
        return pub

    # ----------------------------------------------------------------
    #  Internal helpers
    # ----------------------------------------------------------------

    def _get_or_create_agent(self, account_id: str):
        if account_id not in self._agents:
            record = self._accounts.get(account_id)
            if record:
                self._create_agent(record)
        return self._agents.get(account_id)

    def _create_agent(self, record: Dict):
        from eve.tools.x_content_agent import EveXContentAgent, XClient, ContentGenerator, ContentQueue

        creds = record["credentials"]
        settings = record["settings"]
        account_id = record["id"]

        x_client = XClient(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
            access_token=creds["access_token"],
            access_token_secret=creds["access_token_secret"],
            bearer_token=creds.get("bearer_token", ""),
        )

        # Per-account data directory for isolated queue/history
        account_data_dir = str(self.data_dir / account_id)

        agent = EveXContentAgent(
            legacy_db=self.legacy_db,
            provider=self.provider,
            x_client=x_client,
            data_dir=account_data_dir,
            mode=settings.get("mode", "queue"),
            posts_per_day=settings.get("posts_per_day", 3),
            max_chars=settings.get("max_chars", 280),
            memory_store=self.memory_store,
        )

        # Inject persona context into generator if provided
        if record.get("persona_context"):
            agent.generator.persona_context = record["persona_context"]

        self._agents[account_id] = agent
        logger.debug(f"Created X agent for @{record['username']}")

    def _public_record(self, record: Dict) -> Dict:
        """Strip credentials from the record before sending to frontend."""
        return {
            "id": record["id"],
            "username": record["username"],
            "display_name": record["display_name"],
            "persona_context": record.get("persona_context", ""),
            "settings": record["settings"],
            "added_at": record["added_at"],
            "status": record.get("status", "active"),
        }
