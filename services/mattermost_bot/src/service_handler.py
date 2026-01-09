"""Service handler for routing messages to service bots (Gaia, Thoth, etc.)."""

import logging
import httpx
from typing import Optional, Dict
from .config import Config
from .auth_bridge import AuthBridge

logger = logging.getLogger(__name__)


class ServiceHandler:
    """Handles messages to service bots (Gaia, Thoth, etc.)."""
    
    # Map of bot usernames to service endpoints
    SERVICE_MAP = {
        "gaia": {
            "name": "Gaia (Worlds Service)",
            "url": Config.WORLDS_URL,
            "endpoint": "/query"
        },
        "thoth": {
            "name": "Thoth (Game Master Service)",
            "url": Config.GAME_MASTER_URL,
            "endpoint": "/query"  # Game Master query endpoint
        }
    }
    
    def __init__(self, auth_bridge: AuthBridge):
        """
        Initialize service handler.
        
        Args:
            auth_bridge: Auth bridge instance
        """
        self.auth_bridge = auth_bridge
    
    def is_service_bot(self, username: str) -> bool:
        """
        Check if a username corresponds to a service bot.
        
        Args:
            username: Bot username
            
        Returns:
            True if it's a known service bot
        """
        return username.lower() in self.SERVICE_MAP
    
    async def handle_service_message(
        self,
        bot_username: str,
        message: str,
        mattermost_user_id: str,
        context: Optional[Dict] = None,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Handle a message to a service bot.
        
        Args:
            bot_username: Service bot username (e.g., "gaia")
            message: User message
            mattermost_user_id: Mattermost user ID
            context: Optional context dictionary
            session_id: Optional session ID
            
        Returns:
            Service response text, or None if error
        """
        bot_username_lower = bot_username.lower()
        
        if bot_username_lower not in self.SERVICE_MAP:
            logger.warning(f"Unknown service bot: {bot_username}")
            return None
        
        service_info = self.SERVICE_MAP[bot_username_lower]
        service_url = service_info["url"]
        endpoint = service_info["endpoint"]
        
        try:
            # Get auth headers
            auth_headers = await self.auth_bridge.get_auth_headers(mattermost_user_id)
            
            # Prepare request based on service
            if bot_username_lower == "gaia":
                # Worlds service query endpoint
                query_data = {
                    "query": message,
                    "context": context,
                    "session_id": session_id
                }
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{service_url}{endpoint}",
                        json=query_data,
                        headers=auth_headers
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        # Worlds service returns response in "response" field
                        response_text = data.get("response")
                        if response_text:
                            return response_text
                        # Fallback to error message if present
                        error_msg = data.get("error")
                        if error_msg:
                            return f"Error from {service_info['name']}: {error_msg}"
                        # If no response, return a default message
                        return f"Received query but no response from {service_info['name']}"
                    else:
                        logger.error(f"Worlds service returned {response.status_code}: {response.text}")
                        error_msg = f"Error: Could not get response from {service_info['name']}"
                        if response.status_code == 403:
                            error_msg += " (Authentication required)"
                        return error_msg
                        
            elif bot_username_lower == "thoth":
                # Game Master service query endpoint
                query_data = {
                    "query": message,
                    "context": context,
                    "session_id": session_id
                }
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{service_url}{endpoint}",
                        json=query_data,
                        headers=auth_headers
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        # Game Master service returns response in "response" field
                        response_text = data.get("response")
                        if response_text:
                            return response_text
                        # Check for error field if response is None
                        error_msg = data.get("error")
                        if error_msg:
                            return f"Error from {service_info['name']}: {error_msg}"
                        # Fallback to other fields
                        return data.get("text") or data.get("message") or "No response from Game Master service"
                    else:
                        logger.error(f"Game Master service returned {response.status_code}: {response.text}")
                        error_data = response.json() if response.text else {}
                        error_msg_detail = error_data.get("error", {}).get("message", error_data.get("message", response.text))
                        error_msg = f"Error from {service_info['name']}: {error_msg_detail}"
                        return error_msg
            
            else:
                return f"Service {bot_username} is not yet fully integrated."
                
        except httpx.TimeoutException:
            logger.error(f"Timeout calling {service_info['name']}")
            return f"Error: Request to {service_info['name']} timed out. Please try again."
        except Exception as e:
            logger.error(f"Error handling service message: {e}", exc_info=True)
            return f"Error: {str(e)}"
