"""Configuration for Mattermost bot service."""

import os
from typing import Optional


class Config:
    """Configuration class for Mattermost bot."""
    
    # Mattermost configuration
    MATTERMOST_URL: str = os.getenv("MATTERMOST_URL", "http://localhost:8065")
    MATTERMOST_BOT_TOKEN: Optional[str] = os.getenv("MATTERMOST_BOT_TOKEN")
    MATTERMOST_BOT_USERNAME: str = os.getenv("MATTERMOST_BOT_USERNAME", "rpg-bot")
    MATTERMOST_SLASH_COMMAND_TOKEN: Optional[str] = os.getenv("MATTERMOST_SLASH_COMMAND_TOKEN")
    
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
        if not cls.MATTERMOST_BOT_TOKEN:
            raise ValueError("MATTERMOST_BOT_TOKEN is required")
        return True
