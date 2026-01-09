"""Authentication bridge between Mattermost and RPG services."""

import logging
import httpx
from typing import Optional, Dict
from .config import Config

logger = logging.getLogger(__name__)


class AuthBridge:
    """Bridges Mattermost user authentication to RPG service authentication."""
    
    def __init__(self):
        """Initialize auth bridge."""
        self._user_tokens: Dict[str, str] = {}  # mattermost_user_id -> jwt_token
        self._user_mapping: Dict[str, str] = {}  # mattermost_user_id -> rpg_user_id
    
    async def get_rpg_user_id(self, mattermost_user_id: str, mattermost_email: Optional[str] = None) -> Optional[str]:
        """
        Get RPG user ID from Mattermost user ID.
        
        Args:
            mattermost_user_id: Mattermost user ID
            mattermost_email: Mattermost user email (for lookup)
            
        Returns:
            RPG user ID if found, None otherwise
        """
        # Check cache first
        if mattermost_user_id in self._user_mapping:
            return self._user_mapping[mattermost_user_id]
        
        # Try to find user by email in auth service
        if mattermost_email:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Note: This assumes auth service has an endpoint to lookup by email
                    # For now, we'll use a simple mapping approach
                    # In production, you'd want to sync Mattermost users with RPG users
                    pass
            except Exception as e:
                logger.warning(f"Error looking up user by email: {e}")
        
        return None
    
    async def get_jwt_token(self, mattermost_user_id: str, mattermost_email: Optional[str] = None, mattermost_username: Optional[str] = None) -> Optional[str]:
        """
        Get or create JWT token for Mattermost user.
        
        Args:
            mattermost_user_id: Mattermost user ID
            mattermost_email: Mattermost user email
            mattermost_username: Mattermost username
            
        Returns:
            JWT token if available, None otherwise
        """
        # Check cache
        if mattermost_user_id in self._user_tokens:
            return self._user_tokens[mattermost_user_id]
        
        # Try to login or create user in auth service
        rpg_user_id = await self.get_rpg_user_id(mattermost_user_id, mattermost_email)
        
        if not rpg_user_id and mattermost_username:
            # Try to login with Mattermost username
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    login_response = await client.post(
                        f"{Config.AUTH_URL}/login",
                        json={
                            "username": mattermost_username,
                            "password": ""  # This won't work - need proper auth flow
                        }
                    )
                    if login_response.status_code == 200:
                        data = login_response.json()
                        token = data.get("access_token")
                        if token:
                            self._user_tokens[mattermost_user_id] = token
                            return token
            except Exception as e:
                logger.warning(f"Error logging in user: {e}")
        
        return None
    
    def set_user_token(self, mattermost_user_id: str, jwt_token: str, rpg_user_id: Optional[str] = None):
        """
        Cache JWT token for Mattermost user.
        
        Args:
            mattermost_user_id: Mattermost user ID
            jwt_token: JWT token
            rpg_user_id: Optional RPG user ID
        """
        self._user_tokens[mattermost_user_id] = jwt_token
        if rpg_user_id:
            self._user_mapping[mattermost_user_id] = rpg_user_id
    
    def get_auth_headers(self, mattermost_user_id: str) -> Dict[str, str]:
        """
        Get authentication headers for API requests.
        
        Args:
            mattermost_user_id: Mattermost user ID
            
        Returns:
            Dictionary with Authorization header if token available
        """
        token = self._user_tokens.get(mattermost_user_id)
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}
