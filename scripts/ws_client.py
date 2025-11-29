#!/usr/bin/env python3
"""
WebSocket client for Bridge API status updates.

Usage:
    python scripts/ws_client.py --token YOUR_API_TOKEN
    python scripts/ws_client.py --token YOUR_API_TOKEN --url wss://bridgeapi.zenon.info
"""
import argparse
import asyncio
import json
import signal
import sys

try:
    import websockets
except ImportError:
    print("Error: websockets package not installed.")
    print("Install with: pip install websockets")
    sys.exit(1)


async def connect_and_listen(url: str, token: str):
    """Connect to WebSocket and print messages as they arrive."""
    ws_url = f"{url}/api/v1/ws/status?token={token}"

    print(f"Connecting to {url}/api/v1/ws/status ...")

    try:
        async with websockets.connect(ws_url) as ws:
            print("Connected! Waiting for status updates...\n")

            # Start ping task to keep connection alive
            async def ping_task():
                while True:
                    await asyncio.sleep(30)
                    try:
                        await ws.send("ping")
                    except:
                        break

            ping = asyncio.create_task(ping_task())

            try:
                async for message in ws:
                    if message == "pong":
                        continue

                    try:
                        data = json.loads(message)
                        print(json.dumps(data, indent=2, default=str))
                        print("-" * 60)
                    except json.JSONDecodeError:
                        print(f"Raw message: {message}")
            finally:
                ping.cancel()

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"Connection failed: {e}")
        if e.status_code == 401:
            print("Authentication failed. Check your API token.")
        elif e.status_code == 403:
            print("Access forbidden. Token may be revoked or expired.")
    except ConnectionRefusedError:
        print(f"Connection refused. Is the server running at {url}?")
    except Exception as e:
        print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="WebSocket client for Bridge API")
    parser.add_argument(
        "--token", "-t",
        required=True,
        help="API token (ora_xxx...)"
    )
    parser.add_argument(
        "--url", "-u",
        default="wss://bridgeapi.zenon.info",
        help="WebSocket URL (default: wss://bridgeapi.zenon.info)"
    )

    args = parser.parse_args()

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\nDisconnecting...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Run the async client
    asyncio.run(connect_and_listen(args.url, args.token))


if __name__ == "__main__":
    main()
