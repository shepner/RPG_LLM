#!/usr/bin/env python3
"""
Script to create a bot account in Mattermost via API.

Usage:
    python3 scripts/create-mattermost-bot.py [username] [display_name] [description]
    
    Or with environment variables:
    MATTERMOST_URL=http://localhost:8065 \
    MATTERMOST_ADMIN_EMAIL=admin@example.com \
    MATTERMOST_ADMIN_PASSWORD=password \
    python3 scripts/create-mattermost-bot.py test "Test Bot" "Test bot for RPG_LLM"
"""

import os
import sys
import json
import secrets

try:
    import requests
except ImportError:
    print("Error: 'requests' library is required.")
    print("Install it with: pip install requests")
    sys.exit(1)

def create_bot(username: str, display_name: str = None, description: str = None):
    """Create a bot account in Mattermost."""
    
    # Get configuration from environment
    mattermost_url = os.getenv("MATTERMOST_URL", "http://localhost:8065")
    admin_email = os.getenv("MATTERMOST_ADMIN_EMAIL")
    admin_password = os.getenv("MATTERMOST_ADMIN_PASSWORD")
    
    if not admin_email or not admin_password:
        print("Error: MATTERMOST_ADMIN_EMAIL and MATTERMOST_ADMIN_PASSWORD must be set")
        print("\nUsage:")
        print("  MATTERMOST_ADMIN_EMAIL=admin@example.com \\")
        print("  MATTERMOST_ADMIN_PASSWORD=password \\")
        print("  python3 scripts/create-mattermost-bot.py [username] [display_name] [description]")
        print("\nExample:")
        print("  MATTERMOST_ADMIN_EMAIL=admin@example.com \\")
        print("  MATTERMOST_ADMIN_PASSWORD=password \\")
        print("  python3 scripts/create-mattermost-bot.py test 'Test Bot' 'Test bot for RPG_LLM'")
        sys.exit(1)
    
    # Ensure URL doesn't end with /
    mattermost_url = mattermost_url.rstrip('/')
    api_url = f"{mattermost_url}/api/v4"
    
    session = requests.Session()
    session.verify = False  # Disable SSL verification for self-signed certs
    
    try:
        print(f"Logging in to Mattermost as admin ({admin_email})...")
        # Login as admin
        login_response = session.post(
            f"{api_url}/users/login",
            json={"login_id": admin_email, "password": admin_password}
        )
        
        if login_response.status_code != 200:
            print(f"Error: Failed to login. Status: {login_response.status_code}")
            print(f"Response: {login_response.text}")
            sys.exit(1)
        
        login_data = login_response.json()
        token = login_data.get('token')
        if not token:
            print("Error: No token received from login")
            sys.exit(1)
        
        # Set authorization header
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        print(f"Creating bot account '{username}'...")
        
        # Prepare bot data
        bot_data = {
            "username": username,
            "display_name": display_name or f"{username.title()} Bot",
            "description": description or f"Bot account: {username}"
        }
        
        # Create bot - try two approaches:
        # 1. Direct bot creation (requires admin)
        # 2. Create user then convert to bot (works with system_admin)
        try:
            # First, try creating a regular user
            user_data = {
                "username": username,
                "email": f"{username}@localhost",
                "password": secrets.token_urlsafe(16),
                "nickname": display_name,
                "first_name": display_name.split()[0] if display_name else username.title(),
                "last_name": " ".join(display_name.split()[1:]) if display_name and len(display_name.split()) > 1 else ""
            }
            
            user_response = session.post(
                f"{api_url}/users",
                json=user_data
            )
            
            if user_response.status_code == 201:
                user = user_response.json()
                user_id = user['id']
                
                # Convert user to bot
                convert_response = session.post(
                    f"{api_url}/users/{user_id}/convert_to_bot",
                    json=bot_data
                )
                
                if convert_response.status_code in [200, 201]:
                    bot_result = convert_response.json()
                    bot_result['user_id'] = user_id
                else:
                    # Fallback: try direct bot creation
                    bot_response = session.post(
                        f"{api_url}/bots",
                        json=bot_data
                    )
                    if bot_response.status_code == 201:
                        bot_result = bot_response.json()
                    else:
                        raise Exception(f"Failed to create bot: {convert_response.text}")
            else:
                # User might already exist, try direct bot creation
                bot_response = session.post(
                    f"{api_url}/bots",
                    json=bot_data
                )
                if bot_response.status_code == 201:
                    bot_result = bot_response.json()
                else:
                    raise Exception(f"Failed to create user or bot: {user_response.text}")
            
            if bot_result:
                bot_result = bot_response.json()
                
                print("\n✅ Bot created successfully!")
                print(f"Bot Username: {bot_result.get('username', username)}")
                print(f"Bot ID: {bot_result.get('user_id', 'N/A')}")
                print(f"Bot Display Name: {bot_result.get('display_name', display_name)}")
                
                # Get bot token - need to create it separately
                bot_user_id = bot_result.get('user_id') or bot_result.get('id')
                if bot_user_id:
                    # Create a token for the bot
                    token_data = {"description": f"Bot access token for {username}"}
                    token_response = session.post(
                        f"{api_url}/users/{bot_user_id}/tokens",
                        json=token_data
                    )
                    
                    if token_response.status_code in [200, 201]:
                        token_result = token_response.json()
                        bot_token = token_result.get('token') or token_result.get('id')
                        if bot_token:
                            print(f"\n⚠️  IMPORTANT: Save this token - it won't be shown again!")
                            print(f"Bot Token: {bot_token}")
                            print(f"\nTo use this bot, add to your .env file:")
                            print(f"MATTERMOST_BOT_TOKEN={bot_token}")
                        else:
                            print("\n⚠️  Token not returned in creation response.")
                            print("You may need to regenerate it via the Mattermost UI:")
                            print(f"  System Console → Integrations → Bot Accounts → {username} → Regenerate Token")
                    else:
                        print("\n⚠️  Could not create token automatically.")
                        print("You may need to create it via the Mattermost UI:")
                        print(f"  System Console → Integrations → Bot Accounts → {username} → Regenerate Token")
                else:
                    print("\n⚠️  Token not returned in creation response.")
                    print("You may need to regenerate it via the Mattermost UI:")
                    print(f"  System Console → Integrations → Bot Accounts → {username} → Regenerate Token")
                
                print("\nYou can now use this bot in Mattermost!")
                return bot_result
            else:
                error_data = bot_response.json() if bot_response.text else {}
                error_msg = error_data.get('message', bot_response.text)
                
                if bot_response.status_code == 400 and ("already exists" in error_msg.lower() or "already taken" in error_msg.lower()):
                    print(f"\n⚠️  Bot '{username}' may already exist.")
                    print("Trying to get existing bot information...")
                    
                    try:
                        # Try to get existing bot
                        bots_response = session.get(f"{api_url}/bots")
                        if bots_response.status_code == 200:
                            bots = bots_response.json()
                            for bot in bots:
                                if bot.get('username') == username:
                                    print(f"\n✅ Found existing bot:")
                                    print(f"Bot Username: {bot.get('username')}")
                                    print(f"Bot ID: {bot.get('user_id')}")
                                    print(f"Bot Display Name: {bot.get('display_name')}")
                                    print("\nTo get the token, regenerate it via the Mattermost UI:")
                                    print(f"  System Console → Integrations → Bot Accounts → {username} → Regenerate Token")
                                    return bot
                    except Exception as get_error:
                        print(f"Could not retrieve existing bot: {get_error}")
                
                print(f"\nError: Failed to create bot account. Status: {bot_response.status_code}")
                print(f"Error details: {error_msg}")
                sys.exit(1)
            
        except requests.exceptions.RequestException as e:
            print(f"\nError: Failed to create bot account.")
            print(f"Error details: {e}")
            sys.exit(1)
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    finally:
        # Logout
        try:
            session.post(f"{api_url}/users/logout")
        except:
            pass

if __name__ == "__main__":
    # Get arguments
    username = sys.argv[1] if len(sys.argv) > 1 else "test"
    display_name = sys.argv[2] if len(sys.argv) > 2 else f"{username.title()} Bot"
    description = sys.argv[3] if len(sys.argv) > 3 else f"Test bot: {username}"
    
    create_bot(username, display_name, description)
