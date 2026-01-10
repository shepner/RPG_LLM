"""Service handler for routing messages to service bots (Gaia, Thoth, etc.)."""

import logging
import httpx
import asyncio
import time
from typing import Optional, Dict
from collections import defaultdict
from .config import Config
from .auth_bridge import AuthBridge

logger = logging.getLogger(__name__)

# Rate limiting: Track requests per minute per service
# Free tier: 5 requests/minute per model
_rate_limit_tracker = defaultdict(list)  # service_name -> list of request timestamps
_RATE_LIMIT_RPM = 4  # Conservative limit: 4 requests/minute (leave 1 buffer)
_RATE_LIMIT_WINDOW = 60  # 60 second window


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
        },
        "maat": {
            "name": "Ma'at (Rules Engine Service)",
            "url": Config.RULES_ENGINE_URL,
            "endpoint": "/query"  # Rules Engine query endpoint
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
        session_id: Optional[str] = None,
        mattermost_username: Optional[str] = None
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
            # Check rate limit before making request
            current_time = time.time()
            service_name = bot_username_lower
            
            # Clean old timestamps (older than 60 seconds)
            _rate_limit_tracker[service_name] = [
                ts for ts in _rate_limit_tracker[service_name]
                if current_time - ts < _RATE_LIMIT_WINDOW
            ]
            
            # Check if we're at the rate limit
            if len(_rate_limit_tracker[service_name]) >= _RATE_LIMIT_RPM:
                oldest_request = min(_rate_limit_tracker[service_name])
                wait_time = _RATE_LIMIT_WINDOW - (current_time - oldest_request) + 1
                if wait_time > 0:
                    logger.warning(f"Rate limit reached for {service_name}. Waiting {wait_time:.1f} seconds...")
                    return f"⚠️ Rate limit reached. Please wait {int(wait_time)} seconds before sending another message. (Free tier: 5 requests/minute)"
            
            # Get auth headers (pass username if available to avoid mattermostdriver lookup)
            auth_headers = await self.auth_bridge.get_auth_headers(
                mattermost_user_id,
                mattermost_username=mattermost_username
            )
            
            # Prepare request based on service
            if bot_username_lower == "gaia":
                # Worlds service query endpoint
                query_data = {
                    "query": message,
                    "context": context,
                    "session_id": session_id
                }
                
                # Record this request
                _rate_limit_tracker[service_name].append(current_time)
                
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
                    elif response.status_code == 429:
                        # Rate limit error from API - extract retry time if available
                        try:
                            error_data = response.json()
                            error_msg = error_data.get("error", {}).get("message", "Rate limit exceeded")
                            # Try to extract retry time from error message
                            if "retry in" in error_msg.lower():
                                return f"⚠️ API rate limit exceeded. {error_msg}"
                            return f"⚠️ API rate limit exceeded. Please wait a moment and try again. (Free tier: 5 requests/minute)"
                        except:
                            return f"⚠️ API rate limit exceeded. Please wait ~10 seconds and try again. (Free tier: 5 requests/minute)"
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
                
                # Record this request
                _rate_limit_tracker[service_name].append(current_time)
                
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
                    elif response.status_code == 429:
                        try:
                            error_data = response.json()
                            error_msg = error_data.get("error", {}).get("message", "Rate limit exceeded")
                            if "retry in" in error_msg.lower():
                                return f"⚠️ API rate limit exceeded. {error_msg}"
                            return f"⚠️ API rate limit exceeded. Please wait a moment and try again. (Free tier: 5 requests/minute)"
                        except:
                            return f"⚠️ API rate limit exceeded. Please wait ~10 seconds and try again. (Free tier: 5 requests/minute)"
                    else:
                        logger.error(f"Game Master service returned {response.status_code}: {response.text}")
                        error_data = response.json() if response.text else {}
                        error_msg_detail = error_data.get("error", {}).get("message", error_data.get("message", response.text))
                        error_msg = f"Error from {service_info['name']}: {error_msg_detail}"
                        return error_msg
            
            elif bot_username_lower == "maat":
                # Rules Engine service query endpoint
                query_data = {
                    "query": message,
                    "context": context,
                    "session_id": session_id
                }
                
                # Record this request
                _rate_limit_tracker[service_name].append(current_time)
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{service_url}{endpoint}",
                        json=query_data,
                        headers=auth_headers
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        # Rules Engine service returns response in "response" field
                        response_text = data.get("response")
                        if response_text:
                            return response_text
                        # Check for error field if response is None
                        error_msg = data.get("error")
                        if error_msg:
                            return f"Error from {service_info['name']}: {error_msg}"
                        # Fallback to other fields
                        return data.get("text") or data.get("message") or "No response from Rules Engine service"
                    elif response.status_code == 429:
                        try:
                            error_data = response.json()
                            error_msg = error_data.get("error", {}).get("message", "Rate limit exceeded")
                            if "retry in" in error_msg.lower():
                                return f"⚠️ API rate limit exceeded. {error_msg}"
                            return f"⚠️ API rate limit exceeded. Please wait a moment and try again. (Free tier: 5 requests/minute)"
                        except:
                            return f"⚠️ API rate limit exceeded. Please wait ~10 seconds and try again. (Free tier: 5 requests/minute)"
                    else:
                        logger.error(f"Rules Engine service returned {response.status_code}: {response.text}")
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
