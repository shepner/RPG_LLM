#!/usr/bin/env python3
"""Automatically configure Mattermost outgoing webhooks for service bots."""

import os
import sys
import json
import httpx
from typing import Optional, Dict

MATTERMOST_URL = os.getenv("MATTERMOST_URL", "http://localhost:8065")
BOT_TOKEN = os.getenv("MATTERMOST_BOT_TOKEN")
ADMIN_EMAIL = os.getenv("MATTERMOST_ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("MATTERMOST_ADMIN_PASSWORD")
WEBHOOK_URL = os.getenv("MATTERMOST_WEBHOOK_URL", "http://mattermost_bot:8008/webhook")

SERVICE_BOTS = [
    {"username": "gaia", "trigger": "@gaia", "display_name": "Gaia Bot Webhook"},
    {"username": "thoth", "trigger": "@thoth", "display_name": "Thoth Bot Webhook"},
    {"username": "maat", "trigger": "@maat", "display_name": "Ma'at Bot Webhook"},
]


async def get_auth_token() -> Optional[str]:
    """Get authentication token, trying bot token first, then admin login."""
    # Try bot token first
    if BOT_TOKEN:
        print("Trying bot token authentication...")
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.get(
                    f"{MATTERMOST_URL}/api/v4/users/me",
                    headers={"Authorization": f"Bearer {BOT_TOKEN}"}
                )
                if response.status_code == 200:
                    user_data = response.json()
                    # Check if user has admin permissions
                    roles = user_data.get("roles", "")
                    if "system_admin" in roles or "system_user" in roles:
                        print("✅ Bot token authentication successful")
                        return BOT_TOKEN
        except Exception as e:
            print(f"Bot token authentication failed: {e}")
    
    # Fall back to admin login
    if ADMIN_EMAIL and ADMIN_PASSWORD:
        print("Trying admin login authentication...")
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.post(
                    f"{MATTERMOST_URL}/api/v4/users/login",
                    json={"login_id": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
                )
                if response.status_code == 200:
                    token = response.json().get("token")
                    if token:
                        print("✅ Admin login authentication successful")
                        return token
        except Exception as e:
            print(f"Admin login authentication failed: {e}")
    
    return None


async def get_team_id(token: str) -> Optional[str]:
    """Get the first team ID."""
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.get(
                f"{MATTERMOST_URL}/api/v4/teams",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                teams = response.json()
                if teams:
                    return teams[0]["id"]
    except Exception as e:
        print(f"Error getting team ID: {e}")
    return None


async def check_webhook_exists(token: str, team_id: str, trigger: str) -> Optional[str]:
    """Check if a webhook with the given trigger already exists."""
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.get(
                f"{MATTERMOST_URL}/api/v4/hooks/outgoing",
                headers={"Authorization": f"Bearer {token}"},
                params={"team_id": team_id, "page": 0, "per_page": 100}
            )
            if response.status_code == 200:
                webhooks = response.json()
                for webhook in webhooks:
                    trigger_words = webhook.get("trigger_words", [])
                    if trigger in trigger_words:
                        return webhook.get("id")
    except Exception as e:
        print(f"Error checking existing webhooks: {e}")
    return None


async def create_webhook(token: str, team_id: str, bot_config: Dict) -> bool:
    """Create an outgoing webhook for a service bot."""
    trigger = bot_config["trigger"]
    display_name = bot_config["display_name"]
    
    # Check if webhook already exists
    existing_id = await check_webhook_exists(token, team_id, trigger)
    if existing_id:
        print(f"⚠️  Webhook for {trigger} already exists (ID: {existing_id})")
        return True
    
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            webhook_data = {
                "team_id": team_id,
                "display_name": display_name,
                "description": f"Webhook for {bot_config['username']} bot interactions",
                "trigger_words": [trigger],
                "trigger_when": 1,  # Start with trigger word
                "callback_urls": [WEBHOOK_URL],
                "content_type": "application/json"
            }
            
            response = await client.post(
                f"{MATTERMOST_URL}/api/v4/hooks/outgoing",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=webhook_data
            )
            
            if response.status_code in [200, 201]:
                webhook_id = response.json().get("id")
                print(f"✅ Created webhook for {trigger} (ID: {webhook_id})")
                return True
            else:
                error_text = response.text[:200]
                print(f"❌ Failed to create webhook for {trigger}: {response.status_code} - {error_text}")
                return False
    except Exception as e:
        print(f"❌ Error creating webhook for {trigger}: {e}")
        return False


async def main():
    """Main function to set up all webhooks."""
    print("=" * 60)
    print("Mattermost Webhook Auto-Configuration")
    print("=" * 60)
    print()
    
    # Get authentication token
    token = await get_auth_token()
    if not token:
        print("❌ Error: Could not authenticate.")
        print("   Please set one of:")
        print("   - MATTERMOST_BOT_TOKEN (with admin permissions)")
        print("   - MATTERMOST_ADMIN_EMAIL and MATTERMOST_ADMIN_PASSWORD")
        sys.exit(1)
    
    # Get team ID
    print("Getting team ID...")
    team_id = await get_team_id(token)
    if not team_id:
        print("❌ Error: Could not get team ID")
        sys.exit(1)
    print(f"✅ Found team ID: {team_id}")
    print()
    
    # Create webhooks for each service bot
    print("Creating webhooks...")
    success_count = 0
    for bot_config in SERVICE_BOTS:
        print(f"Setting up webhook for {bot_config['username']}...")
        if await create_webhook(token, team_id, bot_config):
            success_count += 1
        print()
    
    print("=" * 60)
    if success_count == len(SERVICE_BOTS):
        print("✅ All webhooks configured successfully!")
    else:
        print(f"⚠️  Configured {success_count}/{len(SERVICE_BOTS)} webhooks")
    print()
    print("You can now mention @gaia, @thoth, or @maat in any channel.")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
