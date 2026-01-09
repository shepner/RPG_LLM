"""Channel management for Mattermost integration."""

import logging
from typing import Optional, Dict
from mattermostdriver import Driver
from .config import Config

logger = logging.getLogger(__name__)


class ChannelManager:
    """Manages Mattermost channels for characters and sessions."""
    
    def __init__(self, driver: Driver):
        """
        Initialize channel manager.
        
        Args:
            driver: Mattermost driver instance
        """
        self.driver = driver
        self._channel_mapping: Dict[str, str] = {}  # being_id/session_id -> channel_id
        self._reverse_mapping: Dict[str, str] = {}  # channel_id -> being_id/session_id
    
    async def create_character_dm(self, being_id: str, character_name: str, owner_mattermost_id: str, gm_mattermost_id: Optional[str] = None) -> Optional[str]:
        """
        Create a DM channel for a character.
        
        Args:
            being_id: Being/character ID
            character_name: Character name
            owner_mattermost_id: Mattermost user ID of character owner
            gm_mattermost_id: Optional GM Mattermost user ID
            
        Returns:
            Channel ID if created, None otherwise
        """
        try:
            # Create direct channel with bot and owner
            channel_name = f"{Config.CHARACTER_DM_PREFIX}{being_id}"
            
            # Create a group channel (DM) with owner and bot
            user_ids = [owner_mattermost_id]
            if gm_mattermost_id and gm_mattermost_id != owner_mattermost_id:
                user_ids.append(gm_mattermost_id)
            
            # Get bot user ID
            try:
                bot_user = self.driver.users.get_user_by_username(Config.MATTERMOST_BOT_USERNAME)
                if bot_user:
                    user_ids.append(bot_user["id"])
            except Exception:
                pass  # Continue without bot if not found
            
            # Create group channel
            channel = self.driver.channels.create_group_channel(user_ids)
            
            # Store mapping
            channel_id = channel["id"]
            self._channel_mapping[being_id] = channel_id
            self._reverse_mapping[channel_id] = being_id
            
            # Set channel display name
            try:
                self.driver.channels.update_channel(
                    channel_id,
                    {
                        "display_name": character_name or f"Character {being_id[:8]}",
                        "name": channel_name
                    }
                )
            except Exception as e:
                logger.warning(f"Could not set channel display name: {e}")
            
            logger.info(f"Created character DM channel {channel_id} for being {being_id}")
            return channel_id
            
        except Exception as e:
            logger.error(f"Error creating character DM channel: {e}", exc_info=True)
            return None
    
    async def create_session_channel(self, session_id: str, session_name: str, member_mattermost_ids: list) -> Optional[str]:
        """
        Create a group channel for a game session.
        
        Args:
            session_id: Session ID
            session_name: Session name
            member_mattermost_ids: List of Mattermost user IDs to add to channel
            
        Returns:
            Channel ID if created, None otherwise
        """
        try:
            # Get bot user ID
            bot_id = None
            try:
                bot_user = self.driver.users.get_user_by_username(Config.MATTERMOST_BOT_USERNAME)
                bot_id = bot_user["id"] if bot_user else None
            except Exception:
                pass  # Continue without bot if not found
            
            # Add bot to members if not already included
            if bot_id and bot_id not in member_mattermost_ids:
                member_mattermost_ids.append(bot_id)
            
            # Create public or private channel
            channel_name = f"{Config.SESSION_CHANNEL_PREFIX}{session_id}"
            
            team_id = None  # You may need to get the default team ID
            try:
                teams = self.driver.teams.get_teams()
                if teams:
                    team_id = teams[0]["id"]
            except Exception:
                pass
            
            if team_id:
                channel = self.driver.channels.create_channel({
                    "team_id": team_id,
                    "name": channel_name,
                    "display_name": session_name or f"Session {session_id[:8]}",
                    "type": "P"  # Private channel
                })
                
                # Add members to channel
                for user_id in member_mattermost_ids:
                    try:
                        self.driver.channels.add_user(channel["id"], {"user_id": user_id})
                    except Exception as e:
                        logger.warning(f"Could not add user {user_id} to channel: {e}")
            else:
                # Fallback to group channel
                channel = self.driver.channels.create_group_channel(member_mattermost_ids)
            
            # Store mapping
            channel_id = channel["id"]
            self._channel_mapping[session_id] = channel_id
            self._reverse_mapping[channel_id] = session_id
            
            logger.info(f"Created session channel {channel_id} for session {session_id}")
            return channel_id
            
        except Exception as e:
            logger.error(f"Error creating session channel: {e}", exc_info=True)
            return None
    
    def get_being_id_from_channel(self, channel_id: str) -> Optional[str]:
        """
        Get being_id from channel ID.
        
        Args:
            channel_id: Mattermost channel ID
            
        Returns:
            Being ID if channel is a character DM, None otherwise
        """
        being_id = self._reverse_mapping.get(channel_id)
        if being_id and being_id.startswith(Config.CHARACTER_DM_PREFIX):
            return being_id.replace(Config.CHARACTER_DM_PREFIX, "")
        return being_id if being_id and not being_id.startswith(Config.SESSION_CHANNEL_PREFIX) else None
    
    def get_session_id_from_channel(self, channel_id: str) -> Optional[str]:
        """
        Get session_id from channel ID.
        
        Args:
            channel_id: Mattermost channel ID
            
        Returns:
            Session ID if channel is a session channel, None otherwise
        """
        session_id = self._reverse_mapping.get(channel_id)
        if session_id and session_id.startswith(Config.SESSION_CHANNEL_PREFIX):
            return session_id.replace(Config.SESSION_CHANNEL_PREFIX, "")
        return session_id if session_id and session_id.startswith(Config.SESSION_CHANNEL_PREFIX) else None
    
    def get_channel_id_for_being(self, being_id: str) -> Optional[str]:
        """
        Get channel ID for a being.
        
        Args:
            being_id: Being ID
            
        Returns:
            Channel ID if found, None otherwise
        """
        return self._channel_mapping.get(being_id)
    
    def get_channel_id_for_session(self, session_id: str) -> Optional[str]:
        """
        Get channel ID for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Channel ID if found, None otherwise
        """
        return self._channel_mapping.get(session_id)
