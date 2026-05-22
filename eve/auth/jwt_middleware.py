"""
JWT Middleware
===============
FastAPI JWT validation dependency for authenticating users against the D1 User DB.
"""

import hashlib
import hmac
import json
import base64
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("EVE_JWT_SECRET", "eve-cosmic-jwt-secret-change-me")
JWT_EXPIRY_SECONDS = 7 * 24 * 60 * 60  # 7 days

# Owner username — set EVE_OWNER_USERNAME env var to grant owner-level routing
JEFF_USERNAME = os.environ.get("EVE_OWNER_USERNAME", "")


@dataclass
class UserContext:
    """Authenticated user context passed through request lifecycle."""
    user_id: str
    username: str
    subscription_tier: str = "free"      # "free" | "pro" | "owner"
    workspace_path: str = ""              # resolved Docker path
    permission_level: int = 0             # 0=GUEST, 1=USER, 2=PRO, 3=OWNER
    is_jeff: bool = False
    nickname: str = ""
    email: str = ""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def create_jwt_token(user_id: str, username: str, subscription_tier: str = "free",
                     nickname: str = "", email: str = "",
                     secret: str = JWT_SECRET) -> str:
    """Create a simple HMAC-SHA256 JWT token."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())

    is_jeff = username.lower() == JEFF_USERNAME.lower()

    payload = {
        "user_id": user_id,
        "username": username,
        "subscription_tier": subscription_tier,
        "nickname": nickname,
        "email": email,
        "is_jeff": is_jeff,
        "iat": now,
        "exp": now + JWT_EXPIRY_SECONDS,
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())

    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_jwt_token(token: str, secret: str = JWT_SECRET) -> Optional[dict]:
    """Decode and verify a JWT token. Returns payload dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_b64 = parts

        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            logger.warning("JWT signature verification failed")
            return None

        # Decode payload
        payload = json.loads(_b64url_decode(payload_b64))

        # Check expiry
        if payload.get("exp", 0) < int(time.time()):
            logger.warning(f"JWT expired for user {payload.get('username', 'unknown')}")
            return None

        return payload

    except Exception as e:
        logger.error(f"JWT decode error: {e}")
        return None


def build_user_context(payload: dict, workspace_path: str = "") -> UserContext:
    """Build UserContext from decoded JWT payload."""
    from eve.security.permissions import PermissionLevel

    is_jeff = payload.get("is_jeff", False)
    tier = payload.get("subscription_tier", "free")

    # Map subscription tier to permission level
    if is_jeff:
        perm = PermissionLevel.OWNER
        ws_path = "/app"
    elif tier == "pro":
        perm = PermissionLevel.PRO
        ws_path = workspace_path
    else:
        # Free tier — no code tools, no sandbox
        perm = PermissionLevel.USER
        ws_path = ""

    return UserContext(
        user_id=payload.get("user_id", ""),
        username=payload.get("username", ""),
        subscription_tier=tier,
        workspace_path=ws_path,
        permission_level=perm,
        is_jeff=is_jeff,
        nickname=payload.get("nickname", ""),
        email=payload.get("email", ""),
    )


async def get_current_user(authorization: str = "") -> Optional[UserContext]:
    """Extract and validate JWT from Authorization header.

    Usage in FastAPI:
        @app.post("/api/chat")
        async def chat(request: Request):
            auth = request.headers.get("Authorization", "")
            user_ctx = await get_current_user(auth)
            if not user_ctx:
                raise HTTPException(status_code=401, detail="Not authenticated")
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]  # Strip "Bearer "
    payload = decode_jwt_token(token)
    if not payload:
        return None

    return build_user_context(payload)
