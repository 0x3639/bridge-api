"""
Tests for security utilities.
"""
import pytest
from datetime import timedelta

from src.core.security import (
    create_session_jwt,
    decode_session_jwt,
    generate_api_token,
    hash_password,
    hash_token,
    verify_password,
)
from src.config import settings


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "test_password_123"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "test_password_123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "test_password_123"
        hashed = hash_password(password)

        assert verify_password("wrong_password", hashed) is False

    def test_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        hash1 = hash_password("password1")
        hash2 = hash_password("password2")

        assert hash1 != hash2

    def test_same_password_different_hashes(self):
        """Test that same password produces different hashes (salt)."""
        password = "test_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Hashes should be different due to salt
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestTokenGeneration:
    """Tests for API token generation."""

    def test_generate_api_token(self):
        """Test API token generation."""
        token, token_hash = generate_api_token()

        assert token.startswith(settings.api_token_prefix)
        assert len(token) > len(settings.api_token_prefix)
        assert token_hash != token
        assert len(token_hash) == 64  # SHA-256 hex length

    def test_hash_token(self):
        """Test token hashing."""
        token = "ora_test_token_12345"
        hashed = hash_token(token)

        assert hashed != token
        assert len(hashed) == 64  # SHA-256 hex length

    def test_hash_token_deterministic(self):
        """Test that token hashing is deterministic."""
        token = "ora_test_token_12345"

        hash1 = hash_token(token)
        hash2 = hash_token(token)

        assert hash1 == hash2

    def test_different_tokens_different_hashes(self):
        """Test that different tokens produce different hashes."""
        hash1 = hash_token("ora_token1")
        hash2 = hash_token("ora_token2")

        assert hash1 != hash2


class TestJWT:
    """Tests for JWT functions."""

    def test_create_session_jwt(self):
        """Test creating a session JWT."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        token = create_session_jwt(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_session_jwt(self):
        """Test decoding a valid session JWT."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        token = create_session_jwt(user_id)

        payload = decode_session_jwt(token)

        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["type"] == "session"

    def test_decode_invalid_jwt(self):
        """Test decoding an invalid JWT."""
        payload = decode_session_jwt("invalid_token")

        assert payload is None

    def test_decode_expired_jwt(self):
        """Test decoding an expired JWT."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        # Create token that expires immediately
        token = create_session_jwt(user_id, expires_delta=timedelta(seconds=-1))

        payload = decode_session_jwt(token)

        assert payload is None

    def test_jwt_with_custom_expiry(self):
        """Test creating JWT with custom expiry."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        token = create_session_jwt(user_id, expires_delta=timedelta(hours=1))

        payload = decode_session_jwt(token)

        assert payload is not None
        assert payload["sub"] == user_id
