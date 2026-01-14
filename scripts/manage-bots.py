#!/usr/bin/env python3
"""
Script to manage Mattermost bot accounts in the registry.

Usage:
    python3 scripts/manage-bots.py list                    # List all bots
    python3 scripts/manage-bots.py add <username> <token> [display_name] [description]  # Add bot
    python3 scripts/manage-bots.py remove <username>     # Remove bot
    python3 scripts/manage-bots.py update <username> [--token TOKEN] [--display-name NAME] [--description DESC] [--active/--inactive]  # Update bot
    python3 scripts/manage-bots.py create <username> [display_name] [description]  # Create new bot in Mattermost and add to registry
"""

import sys
import os
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.bot_registry import BotRegistry, BotInfo


def list_bots(registry: BotRegistry, active_only: bool = False):
    """List all bots in the registry."""
    bots = registry.list_bots(active_only=active_only)
    
    if not bots:
        print("No bots found in registry.")
        return
    
    print(f"\n{'Username':<20} {'Display Name':<20} {'Active':<10} {'User ID':<30} {'Created'}")
    print("-" * 100)
    
    for bot in bots:
        status = "✓" if bot.is_active else "✗"
        user_id = bot.user_id[:27] + "..." if bot.user_id and len(bot.user_id) > 30 else (bot.user_id or "N/A")
        created = bot.created_at[:10] if bot.created_at else "N/A"
        print(f"{bot.username:<20} {bot.display_name or 'N/A':<20} {status:<10} {user_id:<30} {created}")
    
    print(f"\nTotal: {len(bots)} bot(s)")


def add_bot(registry: BotRegistry, username: str, token: str, display_name: str = None, description: str = None):
    """Add a bot to the registry."""
    try:
        bot = registry.add_bot(
            username=username,
            token=token,
            display_name=display_name,
            description=description
        )
        print(f"✅ Bot '{username}' added to registry")
        print(f"   Display Name: {bot.display_name}")
        if bot.description:
            print(f"   Description: {bot.description}")
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def remove_bot(registry: BotRegistry, username: str):
    """Remove a bot from the registry."""
    if registry.remove_bot(username):
        print(f"✅ Bot '{username}' removed from registry")
    else:
        print(f"❌ Bot '{username}' not found in registry")
        sys.exit(1)


def update_bot(registry: BotRegistry, username: str, **kwargs):
    """Update a bot in the registry."""
    try:
        bot = registry.update_bot(username, **kwargs)
        print(f"✅ Bot '{username}' updated")
        print(f"   Display Name: {bot.display_name}")
        print(f"   Active: {bot.is_active}")
        if bot.description:
            print(f"   Description: {bot.description}")
    except KeyError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def create_bot(registry: BotRegistry, username: str, display_name: str = None, description: str = None):
    """Create a new bot in Mattermost and add to registry."""
    try:
        import httpx
        import secrets
    except ImportError:
        print("Error: 'httpx' library is required.")
        sys.exit(1)
    
    # Get rpg-bot token from environment or registry
    rpg_bot_token = os.getenv("MATTERMOST_BOT_TOKEN")
    if not rpg_bot_token:
        primary_bot = registry.get_primary_bot()
        if primary_bot:
            rpg_bot_token = primary_bot.token
        else:
            print("❌ Error: No bot token available. Set MATTERMOST_BOT_TOKEN or add rpg-bot to registry.")
            sys.exit(1)
    
    mattermost_url = os.getenv("MATTERMOST_URL", "http://localhost:8065")
    api_url = f"{mattermost_url}/api/v4"
    headers = {"Authorization": f"Bearer {rpg_bot_token}"}
    
    display_name = display_name or f"{username.title()} Bot"
    description = description or f"Bot account: {username}"
    
    try:
        # Step 1: Create user
        print(f"Creating user '{username}'...")
        user_data = {
            "username": username,
            "email": f"{username}@localhost",
            "password": secrets.token_urlsafe(16),
            "nickname": display_name,
            "first_name": display_name.split()[0] if display_name else username.title(),
            "last_name": " ".join(display_name.split()[1:]) if display_name and len(display_name.split()) > 1 else ""
        }
        
        with httpx.Client(timeout=10.0, verify=False) as client:
            user_response = client.post(
                f"{api_url}/users",
                headers=headers,
                json=user_data,
            )
        
        if user_response.status_code != 201:
            if user_response.status_code == 400:
                # User might already exist, try to get it
                with httpx.Client(timeout=10.0, verify=False) as client:
                    get_response = client.get(
                        f"{api_url}/users/username/{username}",
                        headers=headers,
                    )
                if get_response.status_code == 200:
                    user = get_response.json()
                    user_id = user["id"]
                    print(f"User '{username}' already exists, converting to bot...")
                else:
                    print(f"❌ Error creating user: {user_response.text}")
                    sys.exit(1)
            else:
                print(f"❌ Error creating user: {user_response.text}")
                sys.exit(1)
        else:
            user = user_response.json()
            user_id = user["id"]
        
        # Step 2: Convert to bot
        print(f"Converting user to bot...")
        bot_data = {
            "username": username,
            "display_name": display_name,
            "description": description
        }
        
        with httpx.Client(timeout=10.0, verify=False) as client:
            convert_response = client.post(
                f"{api_url}/users/{user_id}/convert_to_bot",
                headers=headers,
                json=bot_data,
            )
        
        if convert_response.status_code not in [200, 201]:
            print(f"❌ Error converting to bot: {convert_response.text}")
            sys.exit(1)
        
        # Step 3: Create token
        print(f"Creating bot token...")
        token_data = {"description": f"Bot access token for {username}"}
        with httpx.Client(timeout=10.0, verify=False) as client:
            token_response = client.post(
                f"{api_url}/users/{user_id}/tokens",
                headers=headers,
                json=token_data,
            )
        
        if token_response.status_code not in [200, 201]:
            print(f"⚠️  Warning: Could not create token automatically: {token_response.text}")
            print("You may need to create it manually via the Mattermost UI")
            token = None
        else:
            token_result = token_response.json()
            token = token_result.get("token") or token_result.get("id")
        
        if not token:
            print("❌ Error: Could not get bot token. Please create it manually and add to registry.")
            sys.exit(1)
        
        # Step 4: Add to registry
        bot = registry.add_bot(
            username=username,
            token=token,
            display_name=display_name,
            description=description,
            user_id=user_id
        )
        
        print(f"\n✅ Bot '{username}' created and added to registry!")
        print(f"   Display Name: {bot.display_name}")
        print(f"   User ID: {bot.user_id}")
        # Don't print secrets in full
        token_tail = bot.token[-4:] if bot.token else "????"
        print(f"   Token: ****{token_tail} (saved to registry)")
        print(f"\n⚠️  Token is stored in your local bot registry (do not commit it).")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Manage Mattermost bot accounts")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all bots")
    list_parser.add_argument("--all", action="store_true", help="Show inactive bots too")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a bot to registry")
    add_parser.add_argument("username", help="Bot username")
    add_parser.add_argument("token", help="Bot access token")
    add_parser.add_argument("display_name", nargs="?", help="Bot display name")
    add_parser.add_argument("description", nargs="?", help="Bot description")
    
    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a bot from registry")
    remove_parser.add_argument("username", help="Bot username")
    
    # Update command
    update_parser = subparsers.add_parser("update", help="Update a bot in registry")
    update_parser.add_argument("username", help="Bot username")
    update_parser.add_argument("--token", help="New bot token")
    update_parser.add_argument("--display-name", help="New display name")
    update_parser.add_argument("--description", help="New description")
    update_parser.add_argument("--active", action="store_true", help="Mark bot as active")
    update_parser.add_argument("--inactive", action="store_true", help="Mark bot as inactive")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create new bot in Mattermost and add to registry")
    create_parser.add_argument("username", help="Bot username")
    create_parser.add_argument("display_name", nargs="?", help="Bot display name")
    create_parser.add_argument("description", nargs="?", help="Bot description")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    registry = BotRegistry()
    
    if args.command == "list":
        list_bots(registry, active_only=not args.all)
    elif args.command == "add":
        add_bot(registry, args.username, args.token, args.display_name, args.description)
    elif args.command == "remove":
        remove_bot(registry, args.username)
    elif args.command == "update":
        kwargs = {}
        if args.token:
            kwargs["token"] = args.token
        if args.display_name:
            kwargs["display_name"] = args.display_name
        if args.description:
            kwargs["description"] = args.description
        if args.active:
            kwargs["is_active"] = True
        if args.inactive:
            kwargs["is_active"] = False
        update_bot(registry, args.username, **kwargs)
    elif args.command == "create":
        create_bot(registry, args.username, args.display_name, args.description)


if __name__ == "__main__":
    main()
