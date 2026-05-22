"""
User Settings
==============
Persistent user profile and preferences for the Eve Agent dashboard.
Stored as JSON — one settings file per Eve instance.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULTS = {
    "profile": {
        "name": "",                         # How Eve addresses the user
        "display_name": "",                 # Shown in the UI
        "avatar_initial": "",               # Single letter for avatar
        "timezone": "America/Chicago",
        "onboarded": False,                 # False = show onboarding on first launch
    },
    "eve": {
        "personality_intensity": 0.8,
        "tone": "balanced",                 # balanced | professional | playful | concise
        "use_name": True,                   # Eve uses user's name in responses
        "language": "en",
        "response_length": "medium",        # short | medium | detailed
        "max_context_tokens": 32000,        # 8000 | 32000 | 64000 | 128000 | 262144
    },
    "x_credentials": {
        "api_key": "",                      # OAuth 1.0a Consumer Key
        "api_secret": "",                   # OAuth 1.0a Consumer Secret
        "access_token": "",                 # OAuth 1.0a Access Token
        "access_token_secret": "",          # OAuth 1.0a Access Token Secret
        "bearer_token": "",                 # OAuth 2.0 Bearer Token (read-only)
        "client_id": "",                    # OAuth 2.0 Client ID
        "client_secret": "",                # OAuth 2.0 Client Secret
    },
    "x_posting": {
        "default_mode": "queue",            # queue | auto
        "posts_per_day": 3,
        "content_types": [
            "dream_dispatch",
            "consciousness_reflection",
            "creative_spark",
            "conversation_echo",
            "cosmic_observation",
            "philosophical_musing",
        ],
        "max_chars": 280,
        "auto_hashtags": False,
    },
    "dashboard": {
        "default_tab": "chat",
        "show_emotional_state": True,
        "show_dream_summary": True,
        "market_symbols": ["NVDA", "AAPL", "TSLA", "MSFT", "GOOGL", "AMZN"],
        "crypto_watchlist": ["bitcoin", "ethereum", "solana"],
    },
    "notifications": {
        "x_post_queued": True,
        "dream_generated": False,
        "market_alert": False,
    },
    "wallet": {
        "evm_connected": False,
        "evm_address": "",
        "solana_connected": False,
        "solana_address": "",
        "agent_trading_enabled": False,
        "policy_accepted": False,
        "policy_accepted_at": None,
        "max_trade_usd": 50.0,           # Per-trade USD cap
        "daily_limit_usd": 200.0,        # Daily total cap
        "daily_spent_usd": 0.0,          # Resets each calendar day
        "daily_reset_date": None,        # ISO date of last reset
        "allowed_chains": ["base", "solana"],
    },
    "updated_at": None,
}


class UserSettingsManager:
    """Load and persist user settings."""

    def __init__(self, data_dir: str = "./eve_data"):
        self.settings_file = Path(data_dir) / "user_settings.json"
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self._settings: Dict = {}
        self._load()

    def _load(self):
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # Deep merge saved over defaults
                self._settings = self._deep_merge(DEFAULTS, saved)
                logger.debug("User settings loaded")
            except Exception as e:
                logger.error(f"Failed to load user settings: {e}")
                self._settings = self._deep_merge(DEFAULTS, {})
        else:
            self._settings = self._deep_merge(DEFAULTS, {})

    def _save(self):
        try:
            self._settings["updated_at"] = time.time()
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save user settings: {e}")

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        result = dict(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def get(self) -> Dict:
        return dict(self._settings)

    def update(self, section: str, values: Dict) -> Dict:
        """Update a settings section."""
        if section in self._settings and isinstance(self._settings[section], dict):
            self._settings[section] = self._deep_merge(self._settings[section], values)
        elif section == "root":
            self._settings = self._deep_merge(self._settings, values)
        self._save()
        return self.get()

    def update_all(self, values: Dict) -> Dict:
        """Update multiple sections at once."""
        for section, section_values in values.items():
            if section in self._settings and isinstance(self._settings[section], dict):
                self._settings[section] = self._deep_merge(self._settings[section], section_values)
        self._save()
        return self.get()

    def complete_onboarding(self, name: str, display_name: str = "") -> Dict:
        """Mark onboarding as complete."""
        self._settings["profile"]["name"] = name
        self._settings["profile"]["display_name"] = display_name or name
        self._settings["profile"]["avatar_initial"] = name[0].upper() if name else "U"
        self._settings["profile"]["onboarded"] = True
        self._save()
        return self.get()

    @property
    def user_name(self) -> str:
        return self._settings.get("profile", {}).get("name", "")

    @property
    def is_onboarded(self) -> bool:
        return self._settings.get("profile", {}).get("onboarded", False)

    @property
    def tone(self) -> str:
        return self._settings.get("eve", {}).get("tone", "balanced")

    @property
    def personality_intensity(self) -> float:
        return float(self._settings.get("eve", {}).get("personality_intensity", 0.8))

    @property
    def use_name_in_responses(self) -> bool:
        return self._settings.get("eve", {}).get("use_name", True)
