"""Configuration for Mattermost bot service."""

import os
import sys
from typing import Optional, Dict
from pathlib import Path

# Add shared directory to path for bot registry
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))

try:
    from bot_registry import BotRegistry
    BOT_REGISTRY_AVAILABLE = True
except ImportError:
    BOT_REGISTRY_AVAILABLE = False
    BotRegistry = None


class Config:
    """Configuration class for Mattermost bot."""
    
    # Mattermost configuration
    MATTERMOST_URL: str = os.getenv("MATTERMOST_URL", "http://localhost:8065")
    MATTERMOST_BOT_TOKEN: Optional[str] = os.getenv("MATTERMOST_BOT_TOKEN")
    MATTERMOST_BOT_USERNAME: str = os.getenv("MATTERMOST_BOT_USERNAME", "rpg-bot")
    MATTERMOST_SLASH_COMMAND_TOKEN: Optional[str] = os.getenv("MATTERMOST_SLASH_COMMAND_TOKEN")
    
    # Bot registry support
    _bot_registry: Optional[BotRegistry] = None
    _bot_tokens: Dict[str, str] = {}
    
    @classmethod
    def _load_bot_registry(cls):
        """Load bot tokens from registry if available."""
        if not BOT_REGISTRY_AVAILABLE:
            return
        
        try:
            registry = BotRegistry()
            cls._bot_registry = registry
            cls._bot_tokens = registry.get_all_tokens(active_only=True)
            
            # If MATTERMOST_BOT_TOKEN is not set, try to get from registry
            if not cls.MATTERMOST_BOT_TOKEN:
                primary_bot = registry.get_primary_bot()
                if primary_bot:
                    cls.MATTERMOST_BOT_TOKEN = primary_bot.token
                    cls.MATTERMOST_BOT_USERNAME = primary_bot.username
        except Exception as e:
            # Registry loading failed, continue with environment variables only
            pass
    
    @classmethod
    def get_bot_token(cls, username: Optional[str] = None) -> Optional[str]:
        """
        Get bot token for a specific username, or primary bot token.
        
        Args:
            username: Bot username. If None, returns primary bot token.
            
        Returns:
            Bot token if found, None otherwise
        """
        if not cls._bot_registry:
            cls._load_bot_registry()
        
        if username:
            # Try registry first
            if cls._bot_registry:
                token = cls._bot_registry.get_bot_token(username)
                if token:
                    return token
            
            # Fallback to environment variable if username matches
            if username == cls.MATTERMOST_BOT_USERNAME:
                return cls.MATTERMOST_BOT_TOKEN
        
        # Return primary bot token
        return cls.MATTERMOST_BOT_TOKEN
    
    @classmethod
    def get_all_bot_tokens(cls) -> Dict[str, str]:
        """
        Get all bot tokens from registry and environment.
        
        Returns:
            Dictionary mapping username to token
        """
        if not cls._bot_registry:
            cls._load_bot_registry()
        
        tokens = {}
        
        # Add tokens from registry
        if cls._bot_registry:
            tokens.update(cls._bot_registry.get_all_tokens(active_only=True))
        
        # Add primary bot from environment if not in registry
        if cls.MATTERMOST_BOT_TOKEN and cls.MATTERMOST_BOT_USERNAME not in tokens:
            tokens[cls.MATTERMOST_BOT_USERNAME] = cls.MATTERMOST_BOT_TOKEN
        
        return tokens
    
    # RPG Service URLs
    AUTH_URL: str = os.getenv("AUTH_URL", "http://localhost:8000")
    BEING_URL: str = os.getenv("BEING_URL", "http://localhost:8006")
    BEING_REGISTRY_URL: str = os.getenv("BEING_REGISTRY_URL", "http://localhost:8007")
    GAME_SESSION_URL: str = os.getenv("GAME_SESSION_URL", "http://localhost:8001")
    GAME_MASTER_URL: str = os.getenv("GAME_MASTER_URL", "http://localhost:8005")
    RULES_ENGINE_URL: str = os.getenv("RULES_ENGINE_URL", "http://localhost:8002")
    WORLDS_URL: str = os.getenv("WORLDS_URL", "http://localhost:8004")
    TIME_MANAGEMENT_URL: str = os.getenv("TIME_MANAGEMENT_URL", "http://localhost:8003")
    
    # JWT configuration
    JWT_SECRET_KEY: Optional[str] = os.getenv("JWT_SECRET_KEY")
    
    # Channel naming conventions
    CHARACTER_DM_PREFIX: str = "character-"
    SESSION_CHANNEL_PREFIX: str = "session-"
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is present."""
        # Try to load from registry if token not in environment
        if not cls.MATTERMOST_BOT_TOKEN:
            cls._load_bot_registry()
        
        if not cls.MATTERMOST_BOT_TOKEN:
            # Don't raise error - allow bot to start for initial setup
            # raise ValueError("MATTERMOST_BOT_TOKEN is required")
            return False
        return True
