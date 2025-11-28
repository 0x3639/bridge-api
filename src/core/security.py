import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(password)


def generate_api_token() -> tuple[str, str]:
    """
    Generate an API token and its hash.

    Returns:
        tuple: (token, token_hash) - token is shown to user once, hash is stored
    """
    random_bytes = secrets.token_urlsafe(32)
    token = f"{settings.api_token_prefix}{random_bytes}"
    token_hash = hash_token(token)
    return token, token_hash


def hash_token(token: str) -> str:
    """Hash a token for storage/lookup using SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_session_jwt(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a short-lived JWT for session authentication.

    Args:
        user_id: The user's UUID as a string
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "session",
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_session_jwt(token: str) -> Optional[dict]:
    """
    Decode and validate a session JWT.

    Args:
        token: The JWT string to decode

    Returns:
        The decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])

        # Verify it's a session token
        if payload.get("type") != "session":
            return None

        return payload
    except JWTError:
        return None
