"""
Eve Auth Package
=================
Authentication, JWT, and workspace management via Cloudflare D1 User Database.
"""

from .d1_client import D1UserClient
from .jwt_middleware import UserContext, get_current_user, create_jwt_token
from .workspace_manager import WorkspaceManager

__all__ = [
    "D1UserClient",
    "UserContext",
    "get_current_user",
    "create_jwt_token",
    "WorkspaceManager",
]
