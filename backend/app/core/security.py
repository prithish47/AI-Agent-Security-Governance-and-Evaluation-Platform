# =============================================================================
# AgentGuard — Cryptographic Security Utilities
# =============================================================================
# Implements:
# - Argon2id password hashing and verification (OWASP recommended standard)
# - PyJWT token issuance and signature verification (HS256)
# - Deterministic SHA-256 token hashing for revocable refresh tokens
# =============================================================================

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

# Initialize Argon2id password hasher with secure parameters
_ph = PasswordHasher(
    time_cost=3,        # 3 iterations
    memory_cost=65536,  # 64 MiB memory
    parallelism=4,      # 4 parallel threads
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash plaintext password using Argon2id."""
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against stored Argon2id hash."""
    try:
        return _ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def hash_token(token: str) -> str:
    """Generate SHA-256 hash of a refresh token for safe database persistence."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    username: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate short-lived signed JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "username": username,
        "type": "access",
        "iat": now,
        "exp": expire,
        "iss": "agentguard",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: uuid.UUID,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, datetime]:
    """Generate cryptographically secure refresh token string and expiration timestamp."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.refresh_token_expire_days)

    token_str = f"agr_{uuid.uuid4().hex}_{uuid.uuid4().hex}"
    return token_str, expire


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate JWT access token signature, issuer, and expiration.
    Raises UnauthorizedError on invalid, expired, or tampered token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer="agentguard",
        )
        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Access token has expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid or tampered access token")
