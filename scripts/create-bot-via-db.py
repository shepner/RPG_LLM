#!/usr/bin/env python3
"""
Script to create a bot account in Mattermost via database.
This is a workaround when API permissions are restricted.
"""

import os
import sys
import secrets
import hashlib
import time

def create_bot_via_db(username: str, display_name: str = None, description: str = None):
    """Create a bot account by directly inserting into the database."""
    
    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError:
        print("Error: psycopg2 is required. Install with: pip install psycopg2-binary")
        sys.exit(1)
    
    # Database connection from docker-compose
    db_host = os.getenv("DB_HOST", "mattermost_db")
    db_user = os.getenv("DB_USER", "mmuser")
    db_password = os.getenv("MATTERMOST_DB_PASSWORD", "mmuser_password")
    db_name = os.getenv("DB_NAME", "mattermost")
    
    display_name = display_name or f"{username.title()} Bot"
    description = description or f"Test bot: {username}"
    
    try:
        conn = psycopg2.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name
        )
        cur = conn.cursor()
        
        # Check if user already exists
        cur.execute("SELECT id, username FROM users WHERE username = %s", (username,))
        existing_user = cur.fetchone()
        
        if existing_user:
            user_id = existing_user[0]
            print(f"⚠️  User '{username}' already exists with ID: {user_id}")
            
            # Check if it's already a bot
            cur.execute("SELECT userid FROM bots WHERE userid = %s", (user_id,))
            existing_bot = cur.fetchone()
            
            if existing_bot:
                print(f"✅ User '{username}' is already a bot.")
                # Try to get token
                cur.execute("SELECT token FROM tokens WHERE userid = %s AND token LIKE '%%bot%%' LIMIT 1", (user_id,))
                token_row = cur.fetchone()
                if token_row:
                    print(f"Bot Token: {token_row[0]}")
                else:
                    print("Token not found. You may need to regenerate it via the UI.")
                conn.close()
                return
            
            print("Converting existing user to bot...")
        else:
            # Create new user
            print(f"Creating user '{username}'...")
            user_id = f"{secrets.token_urlsafe(22)}"
            email = f"{username}@localhost"
            now = int(time.time() * 1000)
            
            cur.execute("""
                INSERT INTO users (id, createat, updateat, username, email, nickname, firstname, lastname, 
                                 roles, locale, deleteat, authservice, authdata, position, props)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, now, now, username, email, display_name, display_name, "",
                "system_user", "en", 0, "", "", "", "{}"
            ))
        
        # Create bot entry
        print(f"Creating bot entry for '{username}'...")
        now = int(time.time() * 1000)
        
        # Get rpg-bot's owner ID as the owner
        cur.execute("SELECT id FROM users WHERE username = 'rpg-bot'")
        owner_result = cur.fetchone()
        owner_id = owner_result[0] if owner_result else user_id
        
        cur.execute("""
            INSERT INTO bots (userid, description, ownerid, createat, updateat, deleteat, lasticonupdate)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (userid) DO UPDATE SET description = %s, updateat = %s
        """, (user_id, description, owner_id, now, now, 0, 0, description, now))
        
        # Generate bot token
        print("Generating bot token...")
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        cur.execute("""
            INSERT INTO tokens (token, userid, type, createat)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (token) DO NOTHING
        """, (token_hash, user_id, "bot", now))
        
        conn.commit()
        conn.close()
        
        print("\n✅ Bot created successfully!")
        print(f"Bot Username: {username}")
        print(f"Bot ID: {user_id}")
        print(f"Bot Display Name: {display_name}")
        print(f"\n⚠️  IMPORTANT: Save this token - it won't be shown again!")
        print(f"Bot Token: {token}")
        print(f"\nTo use this bot, add to your .env file:")
        print(f"MATTERMOST_BOT_TOKEN={token}")
        
        return token
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "test"
    display_name = sys.argv[2] if len(sys.argv) > 2 else f"{username.title()} Bot"
    description = sys.argv[3] if len(sys.argv) > 3 else f"Test bot: {username}"
    
    create_bot_via_db(username, display_name, description)
