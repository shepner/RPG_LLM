"""Character conversation handler for Mattermost bot."""

import logging
import httpx
from typing import Optional, Dict
from .config import Config
from .auth_bridge import AuthBridge
from .channel_manager import ChannelManager

logger = logging.getLogger(__name__)


class CharacterHandler:
    """Handles character conversations."""
    
    def __init__(self, auth_bridge: AuthBridge, channel_manager: ChannelManager):
        """
        Initialize character handler.
        
        Args:
            auth_bridge: Auth bridge instance
            channel_manager: Channel manager instance
        """
        self.auth_bridge = auth_bridge
        self.channel_manager = channel_manager
    
    async def handle_message(
        self,
        being_id: str,
        message: str,
        mattermost_user_id: str,
        channel_id: str,
        session_id: Optional[str] = None,
        target_being_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Handle a message to a character.
        
        Args:
            being_id: Being/character ID
            message: User message
            mattermost_user_id: Mattermost user ID
            channel_id: Mattermost channel ID
            session_id: Optional session ID
            target_being_id: Optional target being ID for @mentions
            
        Returns:
            Character response text, or None if error
        """
        try:
            # Get auth headers
            auth_headers = self.auth_bridge.get_auth_headers(mattermost_user_id)
            
            # Prepare query request
            query_data = {
                "query": message,
                "being_id": being_id,
                "session_id": session_id,
                "target_being_id": target_being_id
            }
            
            # Call being service via being_registry (which routes to correct instance)
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{Config.BEING_REGISTRY_URL}/beings/{being_id}/query",
                    json=query_data,
                    headers=auth_headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("response")
                else:
                    logger.error(f"Being service returned {response.status_code}: {response.text}")
                    return f"Error: Could not get response from character (status {response.status_code})"
                    
        except httpx.TimeoutException:
            logger.error("Timeout calling being service")
            return "Error: Request timed out. Please try again."
        except Exception as e:
            logger.error(f"Error handling character message: {e}", exc_info=True)
            return f"Error: {str(e)}"
    
    async def handle_session_message(
        self,
        message: str,
        mattermost_user_id: str,
        channel_id: str,
        session_id: str,
        mentions: list
    ) -> Optional[str]:
        """
        Handle a message in a session channel (with potential @mentions).
        
        Args:
            message: User message
            mattermost_user_id: Mattermost user ID
            channel_id: Mattermost channel ID
            session_id: Session ID
            mentions: List of mentioned being names
            
        Returns:
            Response text if this triggers a being response, None otherwise
        """
        # For now, if there are mentions, route to the mentioned being
        # In the future, this could trigger being-to-being conversations
        if mentions:
            # Try to resolve mention to being_id
            # This would require looking up beings in the session
            # For now, return None (no automatic response)
            pass
        
        return None
