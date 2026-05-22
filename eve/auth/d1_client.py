"""
D1 User Database Client
========================
Async client wrapping the Cloudflare D1 Worker API for user authentication
and workspace management.
"""

import logging
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class D1UserClient:
    """Async client for the D1 User Database via Cloudflare Worker."""

    def __init__(self, worker_url: str, api_secret: str = ""):
        self.worker_url = worker_url.rstrip("/")
        self.api_secret = api_secret

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_secret:
            headers["Authorization"] = f"Bearer {self.api_secret}"
        return headers

    async def _post(self, path: str, data: Dict) -> Dict:
        """POST to D1 Worker endpoint."""
        url = f"{self.worker_url}{path}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=self._headers(),
                                        timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    result = await resp.json()
                    if resp.status != 200 and not result.get("success"):
                        logger.warning(f"D1 {path} returned {resp.status}: {result}")
                    return result
        except aiohttp.ClientError as e:
            logger.error(f"D1 client error on {path}: {e}")
            return {"success": False, "error": str(e)}

    # ---- Auth endpoints (no Bearer required on Worker side) ----

    async def verify_user(self, username: str) -> Optional[Dict]:
        """Fetch user record by username for credential verification.
        Returns user dict (including password_hash) or None.
        """
        result = await self._post("/auth/verify-user", {"username": username})
        if result.get("success"):
            return result.get("user")
        return None

    async def lookup_user(self, user_id: str) -> Optional[Dict]:
        """Fetch user profile by user_id (no password_hash)."""
        result = await self._post("/auth/lookup-user", {"user_id": user_id})
        if result.get("success"):
            return result.get("user")
        return None

    async def update_login(self, user_id: str) -> bool:
        """Update last_login timestamp and clear failed attempts."""
        result = await self._post("/auth/update-login", {"user_id": user_id})
        return result.get("success", False)

    async def gate_of_destiny_complete(self, user_id: str, nickname: str,
                                        secret_pin: str, secret_question: str,
                                        secret_answer: str) -> bool:
        """Save Gate of Destiny setup data (legacy support)."""
        result = await self._post("/auth/gate-of-destiny-complete", {
            "user_id": user_id,
            "nickname": nickname,
            "secret_pin": secret_pin,
            "secret_question": secret_question,
            "secret_answer": secret_answer,
        })
        return result.get("success", False)

    async def increment_failures(self, user_id: str, failure_type: str) -> bool:
        """Track failed auth attempts. failure_type: 'nickname' or 'recovery'."""
        result = await self._post("/auth/increment-failures", {
            "user_id": user_id,
            "failure_type": failure_type,
        })
        return result.get("success", False)

    # ---- User DB query endpoints (Bearer required) ----

    async def user_query(self, sql: str, params: Optional[List] = None) -> Dict:
        """Execute arbitrary SQL against the User DB via /user/query."""
        data: Dict[str, Any] = {"sql": sql}
        if params:
            data["params"] = params
        return await self._post("/user/query", data)

    async def user_batch(self, statements: List[Dict]) -> Dict:
        """Execute batch SQL against the User DB via /user/batch."""
        return await self._post("/user/batch", {"statements": statements})

    # ---- Workspace helpers ----

    async def get_user_workspace(self, user_id: str,
                                  workspace_name: str = "default") -> Optional[Dict]:
        """Get workspace config for a user."""
        result = await self.user_query(
            "SELECT * FROM user_workspaces WHERE user_id = ? AND workspace_name = ?",
            [user_id, workspace_name],
        )
        if result.get("success") and result.get("results"):
            return result["results"][0]
        return None

    async def create_user_workspace(self, workspace_id: str, user_id: str,
                                     workspace_name: str = "default",
                                     workspace_type: str = "sandbox",
                                     storage_quota_mb: int = 100) -> bool:
        """Create a new workspace record in D1."""
        result = await self.user_query(
            """INSERT INTO user_workspaces (workspace_id, user_id, workspace_name,
               workspace_type, storage_quota_mb) VALUES (?, ?, ?, ?, ?)""",
            [workspace_id, user_id, workspace_name, workspace_type, storage_quota_mb],
        )
        return result.get("success", False)

    async def update_workspace_usage(self, workspace_id: str,
                                      storage_used_mb: float) -> bool:
        """Update storage usage tracking."""
        result = await self.user_query(
            "UPDATE user_workspaces SET storage_used_mb = ?, last_accessed = CURRENT_TIMESTAMP WHERE workspace_id = ?",
            [storage_used_mb, workspace_id],
        )
        return result.get("success", False)
