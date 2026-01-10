"""Main FastAPI application for Mattermost bot service."""

import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
from src.bot import MattermostBot
from src.config import Config

# Import bot registry for API endpoints
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))
    from bot_registry import BotRegistry
    BOT_REGISTRY_AVAILABLE = True
except ImportError:
    BOT_REGISTRY_AVAILABLE = False
    BotRegistry = None

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mattermost Bot Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global bot instance
bot: Optional[MattermostBot] = None


# Track last processed post ID per channel per bot
_last_post_ids = {}  # Format: {bot_username: {channel_id: post_id}}

async def poll_dm_messages_for_bot(bot_username: str, bot_token: str):
    """Poll for new DM messages for a specific service bot."""
    import asyncio
    import httpx
    from urllib.parse import urlparse
    
    logger.info(f"Starting DM polling for {bot_username}")
    await asyncio.sleep(2)  # Initial delay
    
    # Use httpx directly instead of mattermostdriver (avoids websocket issues)
    parsed = urlparse(Config.MATTERMOST_URL)
    api_url = f"{parsed.scheme or 'http'}://{parsed.hostname or 'mattermost'}:{parsed.port or 8065}/api/v4"
    headers = {"Authorization": f"Bearer {bot_token}"}
    
    while True:
        try:
            await asyncio.sleep(5)  # Poll every 5 seconds
            
            try:
                # Get this bot's user ID using httpx
                async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                    try:
                        user_response = await client.get(f"{api_url}/users/me", headers=headers)
                        if user_response.status_code != 200:
                            logger.warning(f"{bot_username}: Could not get user info: {user_response.status_code} - {user_response.text[:100]}")
                            await asyncio.sleep(10)
                            continue
                        bot_user = user_response.json()
                        bot_user_id = bot_user["id"]
                        logger.debug(f"{bot_username}: Bot user ID: {bot_user_id}")
                    except Exception as e:
                        logger.error(f"{bot_username}: Error getting bot user: {e}", exc_info=True)
                        await asyncio.sleep(10)
                        continue
                    
                    # Get DM channels for this bot (DMs it receives)
                    try:
                        channels_response = await client.get(f"{api_url}/users/{bot_user_id}/channels", headers=headers)
                        if channels_response.status_code != 200:
                            logger.warning(f"{bot_username}: Could not get channels: {channels_response.status_code}")
                            dm_channels = []
                        else:
                            all_channels = channels_response.json()
                            logger.debug(f"{bot_username}: Got {len(all_channels)} total channels")
                            # Filter for DM channels
                            dm_channels = [c for c in all_channels if c.get("type") == "D"]
                            if len(dm_channels) > 0:
                                logger.info(f"{bot_username}: Found {len(dm_channels)} DM channels")
                                for dm in dm_channels:
                                    logger.debug(f"{bot_username}: DM channel ID: {dm.get('id')}")
                            else:
                                logger.debug(f"{bot_username}: Found {len(dm_channels)} DM channels (no DMs yet)")
                    except Exception as e:
                        logger.error(f"{bot_username}: Error getting DM channels: {e}", exc_info=True)
                        dm_channels = []
                
                    for channel in dm_channels:
                        channel_id = channel.get("id")
                        
                        # Get channel members
                        try:
                            members_response = await client.get(f"{api_url}/channels/{channel_id}/members", headers=headers)
                            if members_response.status_code != 200:
                                logger.debug(f"{bot_username}: Could not get members for {channel_id}")
                                continue
                            members = members_response.json()
                            member_ids = [m.get("user_id") for m in members]
                            
                            # Get recent posts in this channel
                            try:
                                # Get posts since last check
                                last_post_ids = _last_post_ids.get(bot_username, {})
                                last_post_id = last_post_ids.get(channel_id, "")
                                
                                if last_post_id:
                                    posts_response = await client.get(
                                        f"{api_url}/channels/{channel_id}/posts",
                                        headers=headers,
                                        params={"since": last_post_id}
                                    )
                                else:
                                    # First time checking - get last 20 posts
                                    posts_response = await client.get(
                                        f"{api_url}/channels/{channel_id}/posts",
                                        headers=headers,
                                        params={"per_page": 20}
                                    )
                                
                                if posts_response.status_code != 200:
                                    logger.debug(f"{bot_username}: Could not get posts for {channel_id}: {posts_response.status_code}")
                                    continue
                                
                                posts = posts_response.json()
                                post_list = posts.get("posts", {})
                                order = posts.get("order", [])
                            
                            # Process new posts (excluding bot's own posts)
                            # Process in reverse order (newest first) to handle the most recent message
                            for post_id in reversed(order):
                                if post_id == last_post_id:
                                    continue
                                
                                post = post_list.get(post_id, {})
                                post_user_id = post.get("user_id")
                                message = post.get("message", "").strip()
                                
                                # Skip bot's own messages and empty messages
                                if post_user_id == bot_user_id or not message:
                                    if post_user_id == bot_user_id:
                                        logger.debug(f"{bot_username}: Skipping own message {post_id}")
                                    continue
                                
                                # Check if we've already processed this post
                                if last_post_id and post_id == last_post_id:
                                    logger.debug(f"{bot_username}: Already processed post {post_id}")
                                    continue
                                
                                # Get the user who sent the message
                                try:
                                    user_response = await client.get(f"{api_url}/users/{post_user_id}", headers=headers)
                                    if user_response.status_code == 200:
                                        sender_user = user_response.json()
                                        sender_username = sender_user.get("username", "")
                                    else:
                                        sender_username = "unknown"
                                except Exception:
                                    sender_username = "unknown"
                                
                                # Process the message as this service bot
                                logger.info(f"{bot_username}: Processing DM from {sender_username}: {message[:50]}")
                                
                                # Route to service handler
                                if bot and bot.service_handler:
                                    logger.info(f"{bot_username}: Routing to service handler")
                                    try:
                                        response_text = await bot.service_handler.handle_service_message(
                                            bot_username=bot_username,
                                            message=message,
                                            mattermost_user_id=post_user_id
                                        )
                                        
                                        if response_text:
                                            logger.info(f"{bot_username}: Got response: {response_text[:100]}")
                                            # Post response as this bot using httpx
                                            await post_message_as_bot_httpx(
                                                api_url=api_url,
                                                bot_token=bot_token,
                                                channel_id=channel_id,
                                                text=response_text,
                                                bot_username=bot_username
                                            )
                                            logger.info(f"{bot_username}: Posted DM response")
                                        else:
                                            logger.warning(f"{bot_username}: Service handler returned no response")
                                    except Exception as e:
                                        logger.error(f"{bot_username}: Error in service handler: {e}", exc_info=True)
                                else:
                                    logger.warning(f"{bot_username}: Bot or service_handler not available")
                                
                                # Update last processed post ID (use the latest post ID)
                                if bot_username not in _last_post_ids:
                                    _last_post_ids[bot_username] = {}
                                # Track the latest post ID we've seen
                                current_latest = _last_post_ids[bot_username].get(channel_id, "")
                                if not current_latest or post_id > current_latest:
                                    _last_post_ids[bot_username][channel_id] = post_id
                                    logger.debug(f"{bot_username}: Updated last_post_id for {channel_id} to {post_id}")
                                
                        except Exception as e:
                            logger.debug(f"Error processing posts in DM channel {channel_id} for {bot_username}: {e}")
                    except Exception as e:
                        logger.debug(f"Error checking DM channel {channel_id} for {bot_username}: {e}")
                        
            except Exception as e:
                logger.debug(f"Error polling DM messages for {bot_username}: {e}")
                
        except Exception as e:
            logger.error(f"Error in DM polling loop for {bot_username}: {e}")
            await asyncio.sleep(10)  # Wait longer on error


async def post_message_as_bot_httpx(api_url: str, bot_token: str, channel_id: str, text: str, bot_username: str):
    """Post a message as a specific bot using httpx."""
    try:
        import httpx
        
        post_data = {
            "channel_id": channel_id,
            "message": text,
            "override_username": bot_username  # Make it appear as the bot
        }
        
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.post(
                f"{api_url}/posts",
                json=post_data,
                headers={"Authorization": f"Bearer {bot_token}"}
            )
            
            if response.status_code == 201:
                logger.debug(f"{bot_username}: Posted message to channel {channel_id}")
            else:
                logger.error(f"{bot_username}: Error posting message: {response.status_code} - {response.text}")
        
    except Exception as e:
        logger.error(f"Error posting message as {bot_username}: {e}", exc_info=True)


@app.on_event("startup")
async def startup_event():
    """Initialize bot on startup."""
    global bot
    try:
        bot = MattermostBot()
        logger.info("Mattermost bot initialized")
        
        # Start DM polling for each service bot in background
        import asyncio
        
        # Load bot registry and start polling for each service bot
        if BOT_REGISTRY_AVAILABLE:
            try:
                registry = BotRegistry()
                service_bots = ["gaia", "thoth", "maat"]
                
                logger.info(f"Loading bot registry from: {registry.registry_path}")
                for bot_username in service_bots:
                    bot_info = registry.get_bot(bot_username)
                    if bot_info:
                        logger.info(f"Found {bot_username} in registry: active={bot_info.is_active}, has_token={bool(bot_info.token)}")
                        if bot_info.is_active and bot_info.token:
                            logger.info(f"Starting DM polling for {bot_username}")
                            asyncio.create_task(poll_dm_messages_for_bot(bot_username, bot_info.token))
                        else:
                            logger.warning(f"Service bot {bot_username} is inactive or missing token")
                    else:
                        logger.warning(f"Service bot {bot_username} not found in registry")
            except Exception as e:
                logger.error(f"Could not start service bot DM polling: {e}", exc_info=True)
        else:
            logger.warning("Bot registry not available - DM polling for service bots disabled")
        
        logger.info("Started DM message polling for service bots")
    except Exception as e:
        logger.warning(f"Bot initialization had issues: {e}")
        logger.warning("Bot service will start but may not function until Mattermost is configured")
        # Try to create bot anyway - it will handle errors gracefully
        try:
            bot = MattermostBot()
        except Exception:
            logger.error("Could not initialize bot at all")
            bot = None


class MattermostWebhook(BaseModel):
    """Mattermost webhook payload."""
    event: Optional[str] = None
    data: Optional[Dict] = None
    # Slash command format
    command: Optional[str] = None
    text: Optional[str] = None
    user_id: Optional[str] = None
    channel_id: Optional[str] = None
    team_id: Optional[str] = None
    # Outgoing webhook format
    token: Optional[str] = None
    trigger_word: Optional[str] = None


@app.post("/webhook")
async def handle_webhook(request: Request):
    """
    Handle incoming Mattermost webhook or slash command.
    
    Supports:
    - Slash commands
    - Outgoing webhooks
    - Incoming webhooks
    - Direct messages (via incoming webhook from Mattermost)
    """
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        # Try to parse as JSON first
        try:
            body = await request.json()
        except Exception:
            # Try form data
            form = await request.form()
            body = dict(form)
        
        # Check if this is an incoming webhook (has 'text' and 'username' but no 'trigger_word')
        # This handles DMs sent via incoming webhook
        if "text" in body and "username" in body and "trigger_word" not in body and "command" not in body:
            # This might be an incoming webhook for a DM
            logger.info(f"Received incoming webhook: username={body.get('username')}, text={body.get('text')[:50]}")
            
            # Check if it's a DM to a service bot
            channel_id = body.get("channel_id")
            user_id = body.get("user_id") or body.get("user_name")
            message = body.get("text", "").strip()
            
            if channel_id and message:
                # Try to determine if this is a DM with a service bot
                # We'll check by trying to route it
                event_data = {
                    "event": "posted",
                    "data": {
                        "post": {
                            "id": body.get("post_id", "incoming_webhook_post"),
                            "channel_id": channel_id,
                            "user_id": user_id,
                            "message": message
                        }
                    }
                }
                
                response = await bot.handle_post_event(event_data)
                
                if response:
                    channel_id = response.get("channel_id") or channel_id
                    response_text = response.get("text", "")
                    
                    if channel_id and response_text:
                        logger.info(f"Posting DM response to channel {channel_id}")
                        try:
                            # Get bot username from response if available (set by handle_post_event)
                            bot_username_for_posting = response.get("bot_username")
                            
                            # If not in response, try to detect from channel
                            if not bot_username_for_posting and bot.driver:
                                try:
                                    channel_info = bot.driver.channels.get_channel(channel_id)
                                    if channel_info.get("type") == "D":
                                        # Get other user in DM
                                        members = channel_info.get("members", [])
                                        if not members:
                                            try:
                                                channel_members = bot.driver.channels.get_channel_members(channel_id)
                                                members = [m.get("user_id") for m in channel_members]
                                            except Exception:
                                                pass
                                        
                                        for member_id in members:
                                            if member_id != user_id:
                                                try:
                                                    other_user = bot.driver.users.get_user(member_id)
                                                    other_username = other_user.get("username", "").lower()
                                                    if bot.service_handler.is_service_bot(other_username):
                                                        bot_username_for_posting = other_username
                                                        break
                                                except Exception:
                                                    pass
                                except Exception as e:
                                    logger.debug(f"Could not detect bot from channel: {e}")
                            
                            await bot.post_message(
                                channel_id=channel_id,
                                text=response_text,
                                attachments=response.get("attachments"),
                                bot_username=bot_username_for_posting
                            )
                            logger.info(f"DM response posted successfully as {bot_username_for_posting or 'rpg-bot'}")
                        except Exception as e:
                            logger.error(f"Error posting DM response: {e}", exc_info=True)
                
                return {"status": "ok"}
        
        # Validate slash command token if present
        if "command" in body and Config.MATTERMOST_SLASH_COMMAND_TOKEN:
            token = body.get("token")
            if token != Config.MATTERMOST_SLASH_COMMAND_TOKEN:
                logger.warning(f"Invalid slash command token received")
                raise HTTPException(status_code=401, detail="Invalid token")
        
        # Check if it's a slash command
        if "command" in body:
            command = body.get("command", "")
            text = body.get("text", "").strip()
            
            logger.info(f"Received slash command: command='{command}', text='{text}'")
            logger.info(f"DEBUG: Full body keys: {list(body.keys())}")
            logger.info(f"DEBUG: Body user_id: {body.get('user_id')}, user_name: {body.get('user_name')}, username: {body.get('username')}")
            
            # Handle both formats:
            # 1. /rpg-health (command="/rpg-health", text="")
            # 2. /rpg health (command="/rpg", text="health")
            if command == "/rpg" or command.startswith("/rpg-"):
                if command == "/rpg":
                    # Format: /rpg health -> command_name="health"
                    parts = text.split() if text else []
                    command_name = parts[0] if parts else ""
                    args = parts[1:] if len(parts) > 1 else []
                else:
                    # Format: /rpg-health -> command_name="health"
                    command_name = command[5:]  # Remove "/rpg-" prefix
                    args = text.split() if text else []
                
                logger.info(f"Parsed command: command_name='{command_name}', args={args}")
                logger.info(f"TEST: About to get user_id from body")
                
                user_id = body.get("user_id")
                channel_id = body.get("channel_id")
                logger.info(f"TEST: Got user_id={user_id}, channel_id={channel_id}")
                
                # Get Mattermost user info for authentication
                mattermost_username = None
                mattermost_email = None
                
                # First try to get from request body (slash commands include user_name)
                mattermost_username = body.get("user_name") or body.get("username")
                logger.info(f"Username from body: {mattermost_username}, user_id: {user_id}")
                
                # Try to get more info from Mattermost API if driver is available
                if bot and bot.driver and user_id:
                    try:
                        logger.info(f"Attempting to get Mattermost user info for user_id={user_id}")
                        user_info = bot.driver.users.get_user(user_id)
                        mattermost_username = mattermost_username or user_info.get("username")
                        mattermost_email = user_info.get("email")
                        logger.info(f"Got Mattermost user info: username={mattermost_username}, email={mattermost_email}")
                    except Exception as e:
                        logger.warning(f"Could not get Mattermost user info via API: {e}")
                        # Continue with username from body if available
                
                # If still no username, use user_id as fallback
                if not mattermost_username and user_id:
                    mattermost_username = f"mm_user_{user_id[:8]}"
                    logger.info(f"Using fallback username: {mattermost_username}")
                
                logger.info(f"Final auth info: username={mattermost_username}, email={mattermost_email}, user_id={user_id}")
                
                if command_name:
                    try:
                        logger.info(f"Calling handle_command with user_id={user_id}, username={mattermost_username}, email={mattermost_email}")
                        response = await bot.admin_handler.handle_command(
                            command_name, 
                            args, 
                            user_id,
                            mattermost_username=mattermost_username,
                            mattermost_email=mattermost_email
                        )
                        logger.info(f"Command response: {response}")
                    except Exception as e:
                        logger.error(f"Error handling command: {e}", exc_info=True)
                        response = {
                            "text": f"Error executing command: {str(e)}",
                            "response_type": "ephemeral"
                        }
                else:
                    # No subcommand provided - show help
                    response = {
                        "text": "**RPG LLM Commands**\n\nType `/rpg` followed by one of these commands:\n\n" +
                                "**Character Management:**\n" +
                                "• `health` - Check service status\n" +
                                "• `create-character [name]` - Create a new character\n" +
                                "• `list-characters` - List your characters\n" +
                                "• `delete-character <id>` - Delete a character\n\n" +
                                "**Game Sessions:**\n" +
                                "• `create-session [name]` - Create a game session\n" +
                                "• `join-session <id>` - Join a session\n\n" +
                                "**Gameplay:**\n" +
                                "• `roll <dice>` - Roll dice (e.g., `roll 1d20`)\n" +
                                "• `world-event <description>` - Record world event\n" +
                                "• `system-status` - Get system status (GM only)\n\n" +
                                "**Examples:**\n" +
                                "• `/rpg health`\n" +
                                "• `/rpg create-character Gandalf`\n" +
                                "• `/rpg roll 2d6+3`",
                        "response_type": "ephemeral"
                    }
                
                # Return response for Mattermost slash command
                result = {
                    "response_type": response.get("response_type", "ephemeral"),
                    "text": response.get("text", ""),
                }
                if "attachments" in response:
                    result["attachments"] = response.get("attachments", [])
                
                logger.info(f"Returning response: {result}")
                return result
        
        # Check if it's an outgoing webhook (has trigger_word)
        if "trigger_word" in body or ("text" in body and not "command" in body):
            # This is an outgoing webhook from Mattermost
            logger.info(f"Received outgoing webhook: trigger_word={body.get('trigger_word')}, text={body.get('text')}")
            
            # Extract message and channel info
            message = body.get("text", "").strip()
            channel_id = body.get("channel_id")
            user_id = body.get("user_id")
            trigger_word = body.get("trigger_word", "")
            
            # Determine which bot this is for based on trigger word
            bot_username = None
            if trigger_word:
                # Remove @ symbol if present
                bot_username = trigger_word.lstrip("@").lower()
            
            # Also check if message contains @gaia, @thoth, or @maat mention even if trigger_word is just the name
            if not bot_username and message:
                mentions = message.split()
                for word in mentions:
                    if word.lower().startswith("@gaia") or word.lower() == "gaia":
                        bot_username = "gaia"
                        break
                    elif word.lower().startswith("@thoth") or word.lower() == "thoth":
                        bot_username = "thoth"
                        break
                    elif word.lower().startswith("@maat") or word.lower() == "maat" or word.lower().startswith("@ma'at") or word.lower() == "ma'at":
                        bot_username = "maat"
                        break
            
            # Remove trigger word from message if present
            if trigger_word and message.startswith(trigger_word):
                message = message[len(trigger_word):].strip()
            
            if message and bot_username and bot.service_handler:
                # Route directly to service handler for this bot
                logger.info(f"Routing webhook message to service bot: {bot_username}")
                try:
                    response_text = await bot.service_handler.handle_service_message(
                        bot_username=bot_username,
                        message=message,
                        mattermost_user_id=user_id
                    )
                    
                    if response_text:
                        # For outgoing webhooks, return the response directly
                        # Mattermost will post it automatically
                        logger.info(f"Returning webhook response for Mattermost to post")
                        return {
                            "text": response_text,
                            "username": bot_username  # This makes it appear as the bot
                        }
                    else:
                        response = None
                except Exception as e:
                    logger.error(f"Error handling service message: {e}", exc_info=True)
                    return {
                        "text": f"Error processing message: {str(e)}",
                        "username": bot_username
                    }
            elif message:
                # Fallback to regular event handling
                event_data = {
                    "event": "posted",
                    "data": {
                        "post": {
                            "id": body.get("post_id", "webhook_post"),
                            "channel_id": channel_id,
                            "user_id": user_id,
                            "message": message
                        }
                    }
                }
                
                # Handle the event
                response = await bot.handle_post_event(event_data)
            else:
                response = None
        
        # Otherwise, treat as regular webhook event
        else:
            event_data = {
                "event": body.get("event", "posted"),
                "data": body.get("data", body)
            }
            
            # Handle the event
            response = await bot.handle_post_event(event_data)
        
        # If response was already returned (for outgoing webhooks), don't post again
        if isinstance(response, dict) and "username" in response:
            # This is a webhook response that Mattermost will post automatically
            logger.info("Returning webhook response for Mattermost to post automatically")
            return response
        
        if response:
            # Post response back to Mattermost (for other webhook types)
            channel_id = response.get("channel_id") or body.get("channel_id")
            response_text = response.get("text", "")
            
            if channel_id and response_text:
                logger.info(f"Posting response to channel {channel_id}: {response_text[:100]}")
                try:
                    # Use the bot token for the specific service bot if available
                    bot_username_for_posting = None
                    if "trigger_word" in body:
                        trigger_word = body.get("trigger_word", "")
                        bot_username_for_posting = trigger_word.lstrip("@").lower()
                    
                    await bot.post_message(
                        channel_id=channel_id,
                        text=response_text,
                        attachments=response.get("attachments"),
                        bot_username=bot_username_for_posting
                    )
                    logger.info("Response posted successfully")
                except Exception as e:
                    logger.error(f"Error posting response: {e}", exc_info=True)
            else:
                logger.warning(f"Cannot post response - channel_id={channel_id}, response_text={bool(response_text)}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create-character-channel")
async def create_character_channel(
    request: Request
):
    """
    Create a Mattermost channel for a character.
    
    This endpoint is called when a character is created.
    """
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        # Get parameters from query string or JSON body
        try:
            body = await request.json()
            being_id = body.get("being_id") or request.query_params.get("being_id")
            character_name = body.get("character_name") or request.query_params.get("character_name")
            owner_mattermost_id = body.get("owner_mattermost_id") or request.query_params.get("owner_mattermost_id")
        except:
            # Fallback to query params
            being_id = request.query_params.get("being_id")
            character_name = request.query_params.get("character_name")
            owner_mattermost_id = request.query_params.get("owner_mattermost_id", "")
        
        if not being_id:
            raise HTTPException(status_code=400, detail="being_id is required")
        
        channel_id = await bot.create_character_channel(
            being_id=being_id,
            character_name=character_name or f"Character {being_id[:8]}",
            owner_mattermost_id=owner_mattermost_id or ""
        )
        
        if channel_id:
            return {"channel_id": channel_id, "status": "created"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create channel")
            
    except Exception as e:
        logger.error(f"Error creating character channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create-session-channel")
async def create_session_channel(
    request: Request
):
    """
    Create a Mattermost channel for a game session.
    
    This endpoint is called when a session is created.
    """
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        # Get parameters from query string or JSON body
        try:
            body = await request.json()
            session_id = body.get("session_id") or request.query_params.get("session_id")
            session_name = body.get("session_name") or request.query_params.get("session_name")
            member_mattermost_ids = body.get("member_mattermost_ids", [])
        except:
            # Fallback to query params
            session_id = request.query_params.get("session_id")
            session_name = request.query_params.get("session_name")
            member_mattermost_ids = []
        
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        
        channel_id = await bot.create_session_channel(
            session_id=session_id,
            session_name=session_name or f"Session {session_id[:8]}",
            member_mattermost_ids=member_mattermost_ids
        )
        
        if channel_id:
            return {"channel_id": channel_id, "status": "created"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create channel")
            
    except Exception as e:
        logger.error(f"Error creating session channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "bot_initialized": bot is not None
    }


# Bot Registry API endpoints
if BOT_REGISTRY_AVAILABLE:
    @app.get("/api/bots")
    async def list_bots(active_only: bool = True):
        """
        List all bots in the registry.
        
        Args:
            active_only: If True, only return active bots
        """
        try:
            registry = BotRegistry()
            bots = registry.list_bots(active_only=active_only)
            return {
                "bots": [bot.to_dict() for bot in bots],
                "count": len(bots)
            }
        except Exception as e:
            logger.error(f"Error listing bots: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/bots/{username}")
    async def get_bot(username: str):
        """Get a specific bot by username."""
        try:
            registry = BotRegistry()
            bot_info = registry.get_bot(username)
            if not bot_info:
                raise HTTPException(status_code=404, detail=f"Bot '{username}' not found")
            return bot_info.to_dict()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting bot: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/bots/{username}/token")
    async def get_bot_token(username: str):
        """Get a bot's token by username (for internal use)."""
        try:
            registry = BotRegistry()
            token = registry.get_bot_token(username)
            if not token:
                raise HTTPException(status_code=404, detail=f"Bot '{username}' not found or inactive")
            return {"username": username, "token": token}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting bot token: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/bots/tokens/all")
    async def get_all_bot_tokens(active_only: bool = True):
        """Get all bot tokens (for internal use)."""
        try:
            registry = BotRegistry()
            tokens = registry.get_all_tokens(active_only=active_only)
            return {"tokens": tokens, "count": len(tokens)}
        except Exception as e:
            logger.error(f"Error getting all bot tokens: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
