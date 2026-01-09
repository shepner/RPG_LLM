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


@app.on_event("startup")
async def startup_event():
    """Initialize bot on startup."""
    global bot
    try:
        bot = MattermostBot()
        logger.info("Mattermost bot initialized")
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
                        response = {
                            "text": response_text,
                            "channel_id": channel_id
                        }
                    else:
                        response = None
                except Exception as e:
                    logger.error(f"Error handling service message: {e}", exc_info=True)
                    response = {
                        "text": f"Error processing message: {str(e)}",
                        "channel_id": channel_id
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
        
        if response:
            # Post response back to Mattermost
            channel_id = response.get("channel_id") or body.get("channel_id")
            response_text = response.get("text", "")
            
            if channel_id and response_text:
                logger.info(f"Posting response to channel {channel_id}: {response_text[:100]}")
                try:
                    await bot.post_message(
                        channel_id=channel_id,
                        text=response_text,
                        attachments=response.get("attachments")
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
