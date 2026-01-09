"""Mattermost bot client."""

import logging
from typing import Optional
from mattermostdriver import Driver
from .config import Config
from .auth_bridge import AuthBridge
from .channel_manager import ChannelManager
from .message_router import MessageRouter
from .character_handler import CharacterHandler
from .admin_handler import AdminHandler
from .service_handler import ServiceHandler

logger = logging.getLogger(__name__)


class MattermostBot:
    """Main Mattermost bot class."""
    
    def __init__(self):
        """Initialize Mattermost bot."""
        # Don't validate token here - allow bot to start for initial setup
        if not Config.MATTERMOST_BOT_TOKEN:
            logger.warning("MATTERMOST_BOT_TOKEN not set - bot will not function until configured")
            self.driver = None
            return
        
        # Initialize Mattermost driver
        try:
            # Parse URL to extract components
            from urllib.parse import urlparse
            parsed = urlparse(Config.MATTERMOST_URL)
            
            self.driver = Driver({
                "url": parsed.hostname or "mattermost",
                "token": Config.MATTERMOST_BOT_TOKEN,
                "scheme": parsed.scheme or "http",
                "port": parsed.port or 8065,
                "basepath": "/api/v4",
                "verify": False  # For self-signed certs in development
            })
        except Exception as e:
            logger.warning(f"Could not initialize Mattermost driver: {e}")
            self.driver = None
        
        # Initialize components
        self.auth_bridge = AuthBridge(mattermost_driver=self.driver)
        if self.driver:
            self.channel_manager = ChannelManager(self.driver)
            self.message_router = MessageRouter(self.channel_manager)
            self.character_handler = CharacterHandler(self.auth_bridge, self.channel_manager)
            # Connect to Mattermost
            self._connect()
        else:
            # Create dummy components if driver not available
            self.channel_manager = None
            self.message_router = None
            self.character_handler = None
        
        self.admin_handler = AdminHandler(self.auth_bridge)
        self.service_handler = ServiceHandler(self.auth_bridge)
    
    def _connect(self):
        """Connect to Mattermost."""
        try:
            # Test connection
            user = self.driver.users.get_user_by_username(Config.MATTERMOST_BOT_USERNAME)
            if user:
                logger.info(f"Connected to Mattermost as {user['username']}")
            else:
                logger.warning("Could not find bot user in Mattermost - bot may not be fully configured")
        except Exception as e:
            logger.warning(f"Could not connect to Mattermost: {e}")
            logger.warning("Bot will start but may not function until Mattermost is configured")
            # Don't raise - allow bot to start even if Mattermost isn't ready
    
    async def handle_post_event(self, event_data: dict) -> Optional[dict]:
        """
        Handle a Mattermost post event.
        
        Args:
            event_data: Mattermost event data
            
        Returns:
            Response data for Mattermost, or None
        """
        if not self.driver:
            return {
                "text": "Bot is not configured. Please set MATTERMOST_BOT_TOKEN in environment variables.",
                "response_type": "ephemeral"
            }
        
        try:
            # Extract event information
            event_type = event_data.get("event")
            post_data = event_data.get("data", {}).get("post", {})
            
            if event_type != "posted":
                return None
            
            # Get post details
            post_id = post_data.get("id")
            channel_id = post_data.get("channel_id")
            user_id = post_data.get("user_id")
            message = post_data.get("message", "").strip()
            
            # Ignore bot's own messages
            try:
                bot_user = self.driver.users.get_user_by_username(Config.MATTERMOST_BOT_USERNAME)
                if bot_user and user_id == bot_user["id"]:
                    return None
            except Exception:
                pass  # Continue if we can't check
            
            # Ignore empty messages
            if not message:
                return None
            
            # Check if it's a command
            if self.message_router.is_command(message):
                command, args = self.message_router.parse_command(message)
                response = await self.admin_handler.handle_command(command, args, user_id)
                return response
            
            # Check for @mentions of service bots FIRST (before checking channel type)
            mentions = self.message_router.extract_mentions(message)
            for mentioned_username in mentions:
                if self.service_handler.is_service_bot(mentioned_username.lower()):
                    logger.info(f"Detected mention of service bot: {mentioned_username}")
                    response_text = await self.service_handler.handle_service_message(
                        bot_username=mentioned_username.lower(),
                        message=message,
                        mattermost_user_id=user_id
                    )
                    if response_text:
                        logger.info(f"Service bot response generated: {response_text[:100]}")
                        return {
                            "text": response_text,
                            "channel_id": channel_id
                        }
            
            # Check if message is in a DM with a service bot
            try:
                if self.driver:
                    channel_info = self.driver.channels.get_channel(channel_id)
                    channel_type = channel_info.get("type", "")
                    
                    # Check for DM with service bot
                    if channel_type == "D":
                        # Get other user in DM
                        other_user_id = None
                        # Try to get members from channel info
                        members = channel_info.get("members", [])
                        if not members:
                            # If members not in channel info, try to get them via API
                            try:
                                channel_members = self.driver.channels.get_channel_members(channel_id)
                                members = [m.get("user_id") for m in channel_members]
                            except Exception:
                                pass
                        
                        for member_id in members:
                            if member_id != user_id:
                                other_user_id = member_id
                                break
                        
                        if other_user_id:
                            try:
                                other_user = self.driver.users.get_user(other_user_id)
                                other_username = other_user.get("username", "").lower()
                                
                                # Check if it's a service bot
                                if self.service_handler.is_service_bot(other_username):
                                    logger.info(f"Detected DM with service bot: {other_username}")
                                    response_text = await self.service_handler.handle_service_message(
                                        bot_username=other_username,
                                        message=message,
                                        mattermost_user_id=user_id
                                    )
                                    if response_text:
                                        logger.info(f"Service bot response generated: {response_text[:100]}")
                                        return {
                                            "text": response_text,
                                            "channel_id": channel_id,
                                            "bot_username": other_username  # Include bot username for posting
                                        }
                            except Exception as e:
                                logger.debug(f"Could not check DM user: {e}")
            except Exception as e:
                logger.debug(f"Error checking service bot routing: {e}")
            
            # Otherwise, try to route as character message
            being_id = self.channel_manager.get_being_id_from_channel(channel_id)
            if being_id:
                # This is a character DM
                response_text = await self.character_handler.handle_message(
                    being_id=being_id,
                    message=message,
                    mattermost_user_id=user_id,
                    channel_id=channel_id
                )
                
                if response_text:
                    return {
                        "text": response_text,
                        "channel_id": channel_id
                    }
            
            # Check if it's a session channel with mentions
            session_id = self.channel_manager.get_session_id_from_channel(channel_id)
            if session_id:
                mentions = self.message_router.extract_mentions(message)
                if mentions:
                    # Handle being-to-being conversation
                    # For now, just return None (would need to resolve mentions to being_ids)
                    pass
            
            return None
            
        except Exception as e:
            logger.error(f"Error handling post event: {e}", exc_info=True)
            return {
                "text": f"Error processing message: {str(e)}",
                "response_type": "ephemeral"
            }
    
    async def post_message(self, channel_id: str, text: str, attachments: Optional[list] = None, bot_username: Optional[str] = None):
        """
        Post a message to a Mattermost channel.
        
        Args:
            channel_id: Mattermost channel ID
            text: Message text
            attachments: Optional message attachments
            bot_username: Optional bot username to use for posting (uses that bot's token)
        """
        try:
            import httpx
            from urllib.parse import urlparse
            import os
            import sys
            from pathlib import Path
            
            # Try to use the specific bot's token if provided, fallback to rpg-bot
            bot_token = None
            if bot_username:
                # Try to read token directly from registry JSON file
                try:
                    import json
                    data_dir = os.getenv("RPG_LLM_DATA_DIR", "/app/RPG_LLM_DATA")
                    registry_file = os.path.join(data_dir, "bots", "registry.json")
                    
                    if os.path.exists(registry_file):
                        with open(registry_file, 'r') as f:
                            registry_data = json.load(f)
                            if bot_username in registry_data:
                                bot_data = registry_data[bot_username]
                                if bot_data.get("is_active", True):
                                    bot_token = bot_data.get("token")
                                    if bot_token:
                                        logger.info(f"Using token for bot '{bot_username}' from registry file")
                except Exception as e:
                    logger.debug(f"Could not read token from registry file for {bot_username}: {e}")
            
            # Fallback to rpg-bot token if specific bot token not available
            if not bot_token:
                bot_token = Config.MATTERMOST_BOT_TOKEN
                if bot_token:
                    logger.info(f"Using rpg-bot token as fallback (system_admin permissions)")
            
            if not bot_token:
                logger.warning("Cannot post message - bot token not configured")
                return
            
            # Use HTTP API directly instead of driver (more reliable)
            parsed = urlparse(Config.MATTERMOST_URL)
            api_url = f"{parsed.scheme or 'http'}://{parsed.hostname or 'mattermost'}:{parsed.port or 8065}/api/v4"
            
            post_data = {
                "channel_id": channel_id,
                "message": text
            }
            
            # Override username to make it appear as the service bot
            if bot_username:
                post_data["override_username"] = bot_username
            
            if attachments:
                post_data["props"] = {"attachments": attachments}
            
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.post(
                    f"{api_url}/posts",
                    json=post_data,
                    headers={"Authorization": f"Bearer {bot_token}"}
                )
                
                if response.status_code == 201:
                    logger.info(f"Posted message to channel {channel_id}")
                else:
                    logger.error(f"Error posting message: {response.status_code} - {response.text}")
            
        except Exception as e:
            logger.error(f"Error posting message: {e}", exc_info=True)
    
    async def create_character_channel(self, being_id: str, character_name: str, owner_mattermost_id: str) -> Optional[str]:
        """
        Create a DM channel for a character.
        
        Args:
            being_id: Being ID
            character_name: Character name
            owner_mattermost_id: Mattermost user ID of owner
            
        Returns:
            Channel ID if created, None otherwise
        """
        if not self.channel_manager:
            logger.warning("Cannot create channel - bot not initialized")
            return None
        
        return await self.channel_manager.create_character_dm(
            being_id, character_name, owner_mattermost_id
        )
    
    async def create_session_channel(self, session_id: str, session_name: str, member_mattermost_ids: list) -> Optional[str]:
        """
        Create a channel for a game session.
        
        Args:
            session_id: Session ID
            session_name: Session name
            member_mattermost_ids: List of Mattermost user IDs
            
        Returns:
            Channel ID if created, None otherwise
        """
        if not self.channel_manager:
            logger.warning("Cannot create channel - bot not initialized")
            return None
        
        return await self.channel_manager.create_session_channel(
            session_id, session_name, member_mattermost_ids
        )
