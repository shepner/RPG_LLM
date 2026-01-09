"""Authentication bridge between Mattermost and RPG services."""

import logging
import httpx
from typing import Optional, Dict
from .config import Config

logger = logging.getLogger(__name__)


class AuthBridge:
    """Bridges Mattermost user authentication to RPG service authentication."""
    
    def __init__(self, mattermost_driver=None):
        """
        Initialize auth bridge.
        
        Args:
            mattermost_driver: Optional Mattermost driver for user lookup
        """
        self._user_tokens: Dict[str, str] = {}  # mattermost_user_id -> jwt_token
        self._user_mapping: Dict[str, str] = {}  # mattermost_user_id -> rpg_user_id
        self.mattermost_driver = mattermost_driver
    
    async def get_mattermost_user_info(self, mattermost_user_id: str) -> Optional[Dict]:
        """
        Get Mattermost user information.
        
        Args:
            mattermost_user_id: Mattermost user ID
            
        Returns:
            User info dict with username, email, etc., or None
        """
        if not self.mattermost_driver:
            return None
        
        try:
            user = self.mattermost_driver.users.get_user(mattermost_user_id)
            return user
        except Exception as e:
            logger.warning(f"Error getting Mattermost user info: {e}")
            return None
    
    async def get_or_create_rpg_user(self, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Optional[str]:
        """
        Get or create RPG user for Mattermost user.
        
        Args:
            mattermost_user_id: Mattermost user ID
            mattermost_username: Mattermost username
            mattermost_email: Mattermost email
            
        Returns:
            RPG user ID if found/created, None otherwise
        """
        logger.info(f"get_or_create_rpg_user called: user_id={mattermost_user_id}, username={mattermost_username}, email={mattermost_email}")
        
        # Check cache first
        if mattermost_user_id in self._user_mapping:
            logger.info(f"Found cached RPG user ID: {self._user_mapping[mattermost_user_id]}")
            return self._user_mapping[mattermost_user_id]
        
        # Get Mattermost user info if not provided
        if not mattermost_username or not mattermost_email:
            logger.info(f"Getting Mattermost user info for user_id={mattermost_user_id}")
            user_info = await self.get_mattermost_user_info(mattermost_user_id)
            if user_info:
                mattermost_username = mattermost_username or user_info.get("username")
                mattermost_email = mattermost_email or user_info.get("email")
                logger.info(f"Retrieved from Mattermost: username={mattermost_username}, email={mattermost_email}")
        
        if not mattermost_username:
            logger.error(f"Cannot create RPG user without Mattermost username for user {mattermost_user_id}")
            return None
        
        # Use Mattermost username as fallback email if email not provided
        # Use a valid email domain (not .local which is rejected by EmailStr validation)
        if not mattermost_email:
            mattermost_email = f"{mattermost_username}@mattermost.example"
            logger.info(f"Using fallback email: {mattermost_email}")
        
        # Try to register user in auth service (will fail if user exists, which is fine)
        # Use Mattermost user ID as password (users should change this via web interface)
        # Use valid email domain (not .local which is rejected by EmailStr validation)
        email = mattermost_email or f"{mattermost_username}@mattermost.example"
        password = f"mm_{mattermost_user_id}"
        
        logger.info(f"Attempting to register user: username={mattermost_username}, email={email}")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try to register user
                register_response = await client.post(
                    f"{Config.AUTH_URL}/register",
                    json={
                        "username": mattermost_username,
                        "email": email,
                        "password": password,
                        "role": "player"
                    }
                )
                logger.info(f"Register response status: {register_response.status_code}")
                if register_response.status_code != 200:
                    error_text = register_response.text[:300]
                    logger.error(f"Register error ({register_response.status_code}): {error_text}")
                
                if register_response.status_code == 200:
                    # User created
                    user_data = register_response.json()
                    rpg_user_id = user_data.get("user_id")
                    logger.info(f"Created new RPG user {rpg_user_id} for Mattermost user {mattermost_user_id}")
                    self._user_mapping[mattermost_user_id] = rpg_user_id
                    return rpg_user_id
                elif register_response.status_code == 400 or register_response.status_code == 422:
                    # User already exists (400) or validation error (422 - might be user exists)
                    # Try to login
                    logger.info(f"Registration failed ({register_response.status_code}), attempting login for {mattermost_username}")
                    login_response = await client.post(
                        f"{Config.AUTH_URL}/login",
                        json={
                            "username": mattermost_username,
                            "password": f"mm_{mattermost_user_id}"
                        }
                    )
                    
                    if login_response.status_code == 200:
                        # Login successful
                        token_data = login_response.json()
                        token = token_data.get("access_token")
                        if token:
                            # Decode token to get user_id (or call /me endpoint)
                            me_response = await client.get(
                                f"{Config.AUTH_URL}/me",
                                headers={"Authorization": f"Bearer {token}"}
                            )
                            if me_response.status_code == 200:
                                user_data = me_response.json()
                                rpg_user_id = user_data.get("user_id")
                                self._user_mapping[mattermost_user_id] = rpg_user_id
                                self._user_tokens[mattermost_user_id] = token
                                return rpg_user_id
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                # User exists, try login
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        login_response = await client.post(
                            f"{Config.AUTH_URL}/login",
                            json={
                                "username": mattermost_username,
                                "password": f"mm_{mattermost_user_id}"
                            }
                        )
                        if login_response.status_code == 200:
                            token_data = login_response.json()
                            token = token_data.get("access_token")
                            if token:
                                me_response = await client.get(
                                    f"{Config.AUTH_URL}/me",
                                    headers={"Authorization": f"Bearer {token}"}
                                )
                                if me_response.status_code == 200:
                                    user_data = me_response.json()
                                    rpg_user_id = user_data.get("user_id")
                                    self._user_mapping[mattermost_user_id] = rpg_user_id
                                    self._user_tokens[mattermost_user_id] = token
                                    return rpg_user_id
                except Exception as login_error:
                    logger.error(f"Error logging in existing user: {login_error}")
        except Exception as e:
            logger.error(f"Error creating/getting RPG user: {e}", exc_info=True)
        
        return None
    
    async def get_jwt_token(self, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Optional[str]:
        """
        Get or create JWT token for Mattermost user.
        
        Args:
            mattermost_user_id: Mattermost user ID
            mattermost_username: Mattermost username
            mattermost_email: Mattermost email
            
        Returns:
            JWT token if available, None otherwise
        """
        logger.info(f"get_jwt_token called: user_id={mattermost_user_id}, username={mattermost_username}")
        
        # Check cache first
        if mattermost_user_id in self._user_tokens:
            logger.info(f"Found cached token for user {mattermost_user_id}")
            return self._user_tokens[mattermost_user_id]
        
        # Get or create RPG user
        rpg_user_id = await self.get_or_create_rpg_user(mattermost_user_id, mattermost_username, mattermost_email)
        
        if not rpg_user_id:
            logger.error(f"Could not get or create RPG user for Mattermost user {mattermost_user_id}")
            return None
        
        # If we have a token from the registration/login, use it
        if mattermost_user_id in self._user_tokens:
            logger.info(f"Using token from registration/login for user {mattermost_user_id}")
            return self._user_tokens[mattermost_user_id]
        
        # Otherwise, try to login again
        if not mattermost_username:
            logger.info(f"Username not provided, getting from Mattermost")
            user_info = await self.get_mattermost_user_info(mattermost_user_id)
            if user_info:
                mattermost_username = user_info.get("username")
                logger.info(f"Got username from Mattermost: {mattermost_username}")
        
        if mattermost_username:
            password = f"mm_{mattermost_user_id}"
            logger.info(f"Attempting login: username={mattermost_username}")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    login_response = await client.post(
                        f"{Config.AUTH_URL}/login",
                        json={
                            "username": mattermost_username,
                            "password": password
                        }
                    )
                    logger.info(f"Login response status: {login_response.status_code}")
                    if login_response.status_code == 200:
                        token_data = login_response.json()
                        token = token_data.get("access_token")
                        if token:
                            logger.info(f"Login successful, token obtained")
                            self._user_tokens[mattermost_user_id] = token
                            return token
                    else:
                        logger.error(f"Login failed: {login_response.text[:200]}")
            except Exception as e:
                logger.error(f"Error logging in user: {e}", exc_info=True)
        else:
            logger.error(f"Cannot login without username for user {mattermost_user_id}")
        
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
    
    async def get_auth_headers(self, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Dict[str, str]:
        """
        Get authentication headers for API requests.
        
        Args:
            mattermost_user_id: Mattermost user ID
            mattermost_username: Optional Mattermost username (for user creation)
            mattermost_email: Optional Mattermost email (for user creation)
            
        Returns:
            Dictionary with Authorization header if token available
        """
        logger.info(f"get_auth_headers called: user_id={mattermost_user_id}, username={mattermost_username}")
        token = await self.get_jwt_token(mattermost_user_id, mattermost_username, mattermost_email)
        if token:
            logger.info(f"Auth headers generated successfully for user {mattermost_user_id}")
            return {"Authorization": f"Bearer {token}"}
        logger.warning(f"No token available for user {mattermost_user_id}, returning empty headers")
        return {}
