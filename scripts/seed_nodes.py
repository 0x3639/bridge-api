#!/usr/bin/env python3
"""
Script to seed orchestrator nodes from configuration.

Usage:
    python scripts/seed_nodes.py --json nodes.json
    python scripts/seed_nodes.py --mapping-file /path/to/orchestrator_mapping.py
    python scripts/seed_nodes.py --from-env  # Read from ORCHESTRATOR_IP_1, etc.
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import cast, select, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.models.orchestrator import OrchestratorNode


async def seed_nodes_from_mapping(mapping: dict) -> int:
    """
    Seed orchestrator nodes from a pillar mapping dictionary.

    Args:
        mapping: Dict of {ip: {"name": str, "pubkey": str}}

    Returns:
        Number of nodes created
    """
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    created = 0

    async with async_session() as db:
        for ip, info in mapping.items():
            # Check if node already exists
            # Cast INET to text for comparison
            result = await db.execute(
                select(OrchestratorNode).where(
                    (cast(OrchestratorNode.ip_address, String) == ip)
                    | (OrchestratorNode.name == info["name"])
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"Node '{info['name']}' ({ip}) already exists, skipping")
                continue

            node = OrchestratorNode(
                name=info["name"],
                ip_address=ip,
                pubkey=info.get("pubkey"),
                rpc_port=settings.orchestrator_rpc_port,
                is_active=True,
            )
            db.add(node)
            created += 1
            print(f"Created node: {info['name']} ({ip})")

        await db.commit()

    await engine.dispose()
    return created


def load_mapping_from_file(filepath: str) -> dict:
    """Load PILLAR_MAPPING from a Python file."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("mapping", filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "PILLAR_MAPPING"):
        raise ValueError(f"File {filepath} does not define PILLAR_MAPPING")

    return module.PILLAR_MAPPING


def load_mapping_from_json(filepath: str) -> dict:
    """
    Load nodes from a JSON file.

    Expected format (array of nodes):
    [
        {
            "name": "Anvil",
            "ip": "5.161.213.40",
            "pubkey": "optional-pubkey"
        },
        ...
    ]

    Or (object with ip as key):
    {
        "5.161.213.40": {
            "name": "Anvil",
            "pubkey": "optional-pubkey"
        },
        ...
    }
    """
    import json

    with open(filepath, "r") as f:
        data = json.load(f)

    mapping = {}

    # Handle array format
    if isinstance(data, list):
        for node in data:
            if "ip" not in node or "name" not in node:
                raise ValueError(f"Each node must have 'ip' and 'name' fields: {node}")
            mapping[node["ip"]] = {
                "name": node["name"],
                "pubkey": node.get("pubkey"),
            }
    # Handle object format (ip as key)
    elif isinstance(data, dict):
        for ip, info in data.items():
            if isinstance(info, dict) and "name" in info:
                mapping[ip] = {
                    "name": info["name"],
                    "pubkey": info.get("pubkey"),
                }
            else:
                raise ValueError(f"Invalid node format for {ip}: {info}")
    else:
        raise ValueError("JSON must be an array of nodes or an object with IP keys")

    return mapping


def main():
    parser = argparse.ArgumentParser(description="Seed orchestrator nodes")
    parser.add_argument(
        "--json",
        "-j",
        help="Path to nodes.json file",
    )
    parser.add_argument(
        "--mapping-file",
        "-m",
        help="Path to orchestrator_mapping.py file (legacy format)",
    )
    parser.add_argument(
        "--from-env",
        action="store_true",
        help="Read node IPs from environment variables",
    )
    args = parser.parse_args()

    if args.json:
        print(f"Loading nodes from JSON file: {args.json}")
        try:
            mapping = load_mapping_from_json(args.json)
            print(f"Loaded {len(mapping)} nodes from JSON file")
        except Exception as e:
            print(f"Error loading JSON: {e}")
            sys.exit(1)
    elif args.mapping_file:
        print(f"Loading mapping from {args.mapping_file}")
        try:
            mapping = load_mapping_from_file(args.mapping_file)
            print(f"Loaded {len(mapping)} nodes from mapping file")
        except Exception as e:
            print(f"Error loading mapping: {e}")
            sys.exit(1)
    elif args.from_env:
        # Read from environment variables
        import os

        mapping = {}
        for i in range(1, 21):
            ip = os.getenv(f"ORCHESTRATOR_IP_{i}")
            name = os.getenv(f"ORCHESTRATOR_NAME_{i}", f"Node-{i}")
            pubkey = os.getenv(f"ORCHESTRATOR_PUBKEY_{i}")

            if ip:
                mapping[ip] = {"name": name, "pubkey": pubkey}

        if not mapping:
            print("No orchestrator nodes found in environment variables")
            print("Set ORCHESTRATOR_IP_1, ORCHESTRATOR_NAME_1, etc.")
            sys.exit(1)

        print(f"Loaded {len(mapping)} nodes from environment")
    else:
        parser.print_help()
        sys.exit(1)

    try:
        created = asyncio.run(seed_nodes_from_mapping(mapping))
        print(f"\nSeeding complete. Created {created} new nodes.")
    except Exception as e:
        print(f"Error seeding nodes: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
