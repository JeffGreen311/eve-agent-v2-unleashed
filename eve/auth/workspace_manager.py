"""
Workspace Manager
==================
Per-user sandboxed workspace creation, validation, and quota management.
Pro-tier users get isolated directories inside Docker.
Free-tier users get no workspace (chat only).
Jeff (OWNER) gets full /app access.
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional, Tuple

from .d1_client import D1UserClient

logger = logging.getLogger(__name__)

# Storage quotas by subscription tier (MB)
TIER_QUOTAS = {
    "free": 0,       # No workspace — chat only
    "pro": 500,      # 500 MB sandbox
    "owner": 0,      # Unlimited (0 means no limit)
}

# Max workspaces per tier
TIER_MAX_WORKSPACES = {
    "free": 0,
    "pro": 3,
    "owner": 999,
}


class WorkspaceManager:
    """Creates and manages per-user sandboxed workspaces inside Docker."""

    BASE_DIR = Path("/app/eve_data/user_workspaces")

    def __init__(self, d1_client: Optional[D1UserClient] = None):
        self.d1_client = d1_client
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

    def get_workspace_path(self, user_id: str, workspace_name: str = "default") -> Path:
        """Get the filesystem path for a user's workspace."""
        return self.BASE_DIR / user_id / workspace_name

    async def get_or_create_workspace(self, user_id: str, subscription_tier: str = "pro",
                                       workspace_name: str = "default") -> Optional[Path]:
        """Resolve workspace path. Create dirs + D1 record if missing.
        Returns None if user tier doesn't allow workspaces.
        """
        if subscription_tier == "free":
            return None

        workspace_dir = self.get_workspace_path(user_id, workspace_name)
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Create standard subdirectories
        (workspace_dir / "projects").mkdir(exist_ok=True)
        (workspace_dir / "uploads").mkdir(exist_ok=True)

        # Ensure D1 record exists
        if self.d1_client:
            existing = await self.d1_client.get_user_workspace(user_id, workspace_name)
            if not existing:
                workspace_id = f"ws_{uuid.uuid4().hex[:12]}"
                quota = TIER_QUOTAS.get(subscription_tier, 100)
                ws_type = "owner" if subscription_tier == "owner" else "sandbox"
                await self.d1_client.create_user_workspace(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    workspace_name=workspace_name,
                    workspace_type=ws_type,
                    storage_quota_mb=quota,
                )
                logger.info(f"Created workspace for {user_id}: {workspace_dir}")

        return workspace_dir

    def validate_path_in_workspace(self, path: str, workspace_dir: Path) -> Tuple[bool, str]:
        """Ensure a resolved path is within the user's workspace.
        Prevents path traversal attacks (../../etc/passwd).
        """
        try:
            resolved = Path(path).resolve()
            ws_resolved = workspace_dir.resolve()
            resolved.relative_to(ws_resolved)
            return True, "OK"
        except ValueError:
            return False, f"Access denied: path is outside your workspace"

    def get_storage_usage_mb(self, workspace_dir: Path) -> float:
        """Calculate total storage used in a workspace directory (in MB)."""
        total = 0
        try:
            for root, dirs, files in os.walk(workspace_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
        except Exception as e:
            logger.warning(f"Error calculating storage: {e}")
        return total / (1024 * 1024)

    def check_quota(self, workspace_dir: Path, quota_mb: int) -> Tuple[bool, float]:
        """Check if workspace is within storage quota.
        Returns (within_quota, current_usage_mb).
        quota_mb=0 means unlimited.
        """
        if quota_mb <= 0:
            return True, 0.0

        usage = self.get_storage_usage_mb(workspace_dir)
        return usage < quota_mb, usage
