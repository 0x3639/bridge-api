#!/usr/bin/env python3
"""
Script to create an initial admin user.

Usage:
    python scripts/create_admin.py --username admin --email admin@example.com --password secretpassword

Or interactively:
    python scripts/create_admin.py
"""
import argparse
import asyncio
import getpass
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.core.security import generate_api_token, hash_password
from src.models.token import ApiToken
from src.models.user import User


async def create_admin(username: str, email: str, password: str) -> tuple[User, str]:
    """
    Create an admin user with an API token.

    Returns:
        Tuple of (user, api_token)
    """
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Check if user already exists
        result = await db.execute(
            select(User).where(
                (User.username == username) | (User.email == email)
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError(f"User with username '{username}' or email '{email}' already exists")

        # Create admin user
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            is_admin=True,
            is_active=True,
            rate_limit_per_second=settings.admin_rate_limit_per_second,
            rate_limit_burst=settings.admin_rate_limit_burst,
        )
        db.add(user)
        await db.flush()

        # Create initial API token
        token, token_hash = generate_api_token()
        api_token = ApiToken(
            user_id=user.id,
            token_hash=token_hash,
            name="Initial Admin Token",
        )
        db.add(api_token)

        await db.commit()

        print(f"\n{'=' * 60}")
        print("Admin user created successfully!")
        print(f"{'=' * 60}")
        print(f"Username: {username}")
        print(f"Email: {email}")
        print(f"Admin: True")
        print(f"Rate Limit: {user.rate_limit_per_second}/s (burst: {user.rate_limit_burst})")
        print(f"\n{'=' * 60}")
        print("API TOKEN (save this - it won't be shown again!):")
        print(f"{'=' * 60}")
        print(f"\n{token}\n")
        print(f"{'=' * 60}")

        return user, token

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("--username", "-u", help="Admin username")
    parser.add_argument("--email", "-e", help="Admin email")
    parser.add_argument("--password", "-p", help="Admin password (not recommended, use interactive)")
    args = parser.parse_args()

    # Get username
    username = args.username
    if not username:
        username = input("Enter admin username: ").strip()
        if not username:
            print("Error: Username is required")
            sys.exit(1)

    # Get email
    email = args.email
    if not email:
        email = input("Enter admin email: ").strip()
        if not email:
            print("Error: Email is required")
            sys.exit(1)

    # Get password
    password = args.password
    if not password:
        password = getpass.getpass("Enter admin password: ")
        if not password:
            print("Error: Password is required")
            sys.exit(1)
        if len(password) < 8:
            print("Error: Password must be at least 8 characters")
            sys.exit(1)
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("Error: Passwords do not match")
            sys.exit(1)

    try:
        asyncio.run(create_admin(username, email, password))
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error creating admin: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
