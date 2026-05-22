"""
Permission System
==================
User permission tiers for Eve Agent.
Maps D1 subscription tiers to tool access levels.
"""

from enum import IntEnum
from typing import Dict, Optional, Set


class PermissionLevel(IntEnum):
    GUEST = 0    # Unauthenticated / unknown
    USER = 1     # Free tier — chat, search, read-only
    PRO = 2      # Pro tier — sandboxed code tools
    OWNER = 3    # Jeff only — unrestricted


# Map D1 subscription_tier to internal permission level
TIER_TO_PERMISSION = {
    "free": PermissionLevel.USER,     # Chat, search, read-only — NO code tools
    "pro": PermissionLevel.PRO,       # + sandbox workspace, file tools, shell, code agent
    "owner": PermissionLevel.OWNER,   # Unrestricted (Jeff only)
}


class PermissionManager:
    """Manages user permissions based on D1 subscription tier."""

    TOOL_PERMISSIONS = {
        PermissionLevel.GUEST: {"web_search", "web_fetch"},
        PermissionLevel.USER: {
            "web_search", "web_fetch", "read_file",
            "stock_quote", "crypto_price", "market_overview", "portfolio_summary",
        },
        PermissionLevel.PRO: {
            "web_search", "web_fetch", "read_file", "write_file",
            "edit_file", "shell", "eve_code_agent", "visual_test",
            "stock_quote", "crypto_price", "market_overview", "portfolio_summary",
            "market_research", "canva_design", "social_post", "x_post",
            "stock_trade", "crypto_trade", "defi_trade", "stock_analysis",
            "eve_generate_image", "email_campaign", "trinity_diagnostics",
            "dj_control", "dj_mixer", "dj_fx", "dj_hotcue", "dj_loop",
            "dj_transition", "dj_state", "dj_browse",
        },
        PermissionLevel.OWNER: None,  # None = all tools
    }

    def __init__(self, owner_id: str = ""):
        self.owner_id = owner_id
        self._user_levels: Dict[str, PermissionLevel] = {}
        if owner_id:
            self._user_levels[owner_id] = PermissionLevel.OWNER

    def set_level(self, user_id: str, level: PermissionLevel):
        self._user_levels[user_id] = level

    def set_level_from_tier(self, user_id: str, subscription_tier: str):
        """Set permission level based on D1 subscription_tier."""
        level = TIER_TO_PERMISSION.get(subscription_tier, PermissionLevel.GUEST)
        self._user_levels[user_id] = level

    def get_level(self, user_id: str) -> PermissionLevel:
        if user_id == self.owner_id:
            return PermissionLevel.OWNER
        # Default to OWNER for local/portal users (single-user deployment)
        # D1-authenticated users get their tier set via set_level_from_tier()
        return self._user_levels.get(user_id, PermissionLevel.OWNER)

    def can_use_tool(self, user_id: str, tool_name: str) -> bool:
        level = self.get_level(user_id)
        allowed = self.TOOL_PERMISSIONS.get(level)
        if allowed is None:
            return True
        return tool_name in allowed

    def get_allowed_tools(self, user_id: str) -> Optional[Set[str]]:
        level = self.get_level(user_id)
        return self.TOOL_PERMISSIONS.get(level)
