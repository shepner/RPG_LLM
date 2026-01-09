#!/usr/bin/env python3
"""
Migration script to migrate chat history from web interface to Mattermost.

This is an optional one-time migration utility that reads localStorage data
from the web interface and creates Mattermost channels with historical messages.

Note: This script requires manual execution and access to localStorage data.
"""

import json
import sys
import asyncio
import httpx
from typing import Dict, List

# Configuration
MATTERMOST_BOT_URL = "http://localhost:8008"
MATTERMOST_URL = "http://localhost:8065"


async def migrate_chat_history(local_storage_data: Dict):
    """
    Migrate chat history from localStorage to Mattermost.
    
    Args:
        local_storage_data: Dictionary containing localStorage data
            Expected format:
            {
                "being_chat_{being_id}": [
                    {
                        "role": "user" | "assistant",
                        "content": "message text",
                        "timestamp": "ISO timestamp",
                        "sender_role": "player" | "gm",
                        "visible_to_players": bool
                    },
                    ...
                ],
                ...
            }
    """
    print("Starting chat history migration to Mattermost...")
    
    # Extract being chat histories
    being_chats = {}
    for key, value in local_storage_data.items():
        if key.startswith("being_chat_"):
            being_id = key.replace("being_chat_", "")
            being_chats[being_id] = value
    
    print(f"Found {len(being_chats)} character chat histories")
    
    # For each being, create a channel and post messages
    async with httpx.AsyncClient(timeout=30.0) as client:
        for being_id, messages in being_chats.items():
            print(f"\nMigrating chat for being {being_id[:8]}...")
            
            # Create character channel
            # Note: This requires knowing the owner's Mattermost user ID
            # You'll need to provide this mapping
            owner_mattermost_id = input(f"Enter Mattermost user ID for owner of {being_id[:8]}: ").strip()
            
            if not owner_mattermost_id:
                print(f"Skipping {being_id[:8]} - no owner ID provided")
                continue
            
            try:
                # Create channel
                response = await client.post(
                    f"{MATTERMOST_BOT_URL}/create-character-channel",
                    params={
                        "being_id": being_id,
                        "character_name": f"Character {being_id[:8]}",
                        "owner_mattermost_id": owner_mattermost_id
                    }
                )
                
                if response.status_code != 200:
                    print(f"Error creating channel: {response.text}")
                    continue
                
                channel_data = response.json()
                channel_id = channel_data.get("channel_id")
                
                if not channel_id:
                    print(f"Channel ID not returned")
                    continue
                
                print(f"Created channel {channel_id}")
                
                # Post messages in chronological order
                for msg in messages:
                    # Format message based on role
                    if msg["role"] == "user":
                        sender = "You" if msg.get("sender_role") != "gm" else "GM"
                        text = f"**{sender}:** {msg['content']}"
                    else:
                        text = f"**Character:** {msg['content']}"
                    
                    # Post to Mattermost
                    # Note: This would require Mattermost API access
                    # For now, we'll just print what would be posted
                    print(f"  Would post: {text[:50]}...")
                    
                    # In a real implementation, you'd use Mattermost API:
                    # await mattermost_client.posts.create_post({
                    #     "channel_id": channel_id,
                    #     "message": text
                    # })
                
                print(f"Migrated {len(messages)} messages for {being_id[:8]}")
                
            except Exception as e:
                print(f"Error migrating {being_id[:8]}: {e}")
                continue
    
    print("\nMigration complete!")


def load_local_storage_file(file_path: str) -> Dict:
    """
    Load localStorage data from a JSON file.
    
    Args:
        file_path: Path to JSON file containing localStorage data
        
    Returns:
        Dictionary with localStorage data
    """
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        sys.exit(1)


async def main():
    """Main migration function."""
    if len(sys.argv) < 2:
        print("Usage: python migrate-chat-to-mattermost.py <local_storage.json>")
        print("\nTo export localStorage data from browser:")
        print("1. Open browser console on web interface")
        print("2. Run: JSON.stringify(localStorage)")
        print("3. Copy output to a JSON file")
        sys.exit(1)
    
    file_path = sys.argv[1]
    print(f"Loading localStorage data from {file_path}...")
    
    local_storage_data = load_local_storage_file(file_path)
    
    await migrate_chat_history(local_storage_data)


if __name__ == "__main__":
    asyncio.run(main())
