"""Bot registry for managing multiple Mattermost bot accounts."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class BotInfo:
    """Information about a Mattermost bot."""
    username: str
    token: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[str] = None
    created_at: Optional[str] = None
    is_active: bool = True
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "BotInfo":
        """Create from dictionary."""
        return cls(**data)


class BotRegistry:
    """Registry for managing multiple Mattermost bot accounts."""
    
    def __init__(self, registry_path: Optional[str] = None):
        """
        Initialize bot registry.
        
        Args:
            registry_path: Path to registry JSON file. Defaults to RPG_LLM_DATA/bots/registry.json
        """
        if registry_path is None:
            data_dir = os.getenv("RPG_LLM_DATA_DIR", "./RPG_LLM_DATA")
            registry_path = os.path.join(data_dir, "bots", "registry.json")
        
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._bots: Dict[str, BotInfo] = {}
        self._load()
    
    def _load(self):
        """Load registry from file."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r') as f:
                    data = json.load(f)
                    self._bots = {
                        username: BotInfo.from_dict(bot_data)
                        for username, bot_data in data.items()
                    }
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                # If file is corrupted, start fresh
                print(f"Warning: Could not load bot registry: {e}. Starting with empty registry.")
                self._bots = {}
        else:
            self._bots = {}
    
    def _save(self):
        """Save registry to file."""
        data = {
            username: bot.to_dict()
            for username, bot in self._bots.items()
        }
        
        # Write atomically
        temp_path = self.registry_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        temp_path.replace(self.registry_path)
    
    def add_bot(
        self,
        username: str,
        token: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
        is_active: bool = True
    ) -> BotInfo:
        """
        Add a bot to the registry.
        
        Args:
            username: Bot username
            token: Bot access token
            display_name: Bot display name
            description: Bot description
            user_id: Mattermost user ID
            is_active: Whether bot is active
            
        Returns:
            BotInfo object
            
        Raises:
            ValueError: If bot already exists
        """
        if username in self._bots:
            raise ValueError(f"Bot '{username}' already exists in registry")
        
        bot = BotInfo(
            username=username,
            token=token,
            display_name=display_name or username.title(),
            description=description,
            user_id=user_id,
            created_at=datetime.utcnow().isoformat(),
            is_active=is_active
        )
        
        self._bots[username] = bot
        self._save()
        return bot
    
    def update_bot(
        self,
        username: str,
        token: Optional[str] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> BotInfo:
        """
        Update an existing bot in the registry.
        
        Args:
            username: Bot username
            token: New bot token (optional)
            display_name: New display name (optional)
            description: New description (optional)
            user_id: New user ID (optional)
            is_active: New active status (optional)
            
        Returns:
            Updated BotInfo object
            
        Raises:
            KeyError: If bot doesn't exist
        """
        if username not in self._bots:
            raise KeyError(f"Bot '{username}' not found in registry")
        
        bot = self._bots[username]
        
        if token is not None:
            bot.token = token
        if display_name is not None:
            bot.display_name = display_name
        if description is not None:
            bot.description = description
        if user_id is not None:
            bot.user_id = user_id
        if is_active is not None:
            bot.is_active = is_active
        
        self._save()
        return bot
    
    def remove_bot(self, username: str) -> bool:
        """
        Remove a bot from the registry.
        
        Args:
            username: Bot username
            
        Returns:
            True if bot was removed, False if it didn't exist
        """
        if username in self._bots:
            del self._bots[username]
            self._save()
            return True
        return False
    
    def get_bot(self, username: str) -> Optional[BotInfo]:
        """
        Get a bot by username.
        
        Args:
            username: Bot username
            
        Returns:
            BotInfo if found, None otherwise
        """
        return self._bots.get(username)
    
    def get_bot_token(self, username: str) -> Optional[str]:
        """
        Get a bot's token by username.
        
        Args:
            username: Bot username
            
        Returns:
            Bot token if found, None otherwise
        """
        bot = self._bots.get(username)
        return bot.token if bot and bot.is_active else None
    
    def list_bots(self, active_only: bool = False) -> List[BotInfo]:
        """
        List all bots in the registry.
        
        Args:
            active_only: If True, only return active bots
            
        Returns:
            List of BotInfo objects
        """
        bots = list(self._bots.values())
        if active_only:
            bots = [bot for bot in bots if bot.is_active]
        return bots
    
    def get_all_tokens(self, active_only: bool = True) -> Dict[str, str]:
        """
        Get all bot tokens as a dictionary.
        
        Args:
            active_only: If True, only return active bots
            
        Returns:
            Dictionary mapping username to token
        """
        bots = self.list_bots(active_only=active_only)
        return {bot.username: bot.token for bot in bots}
    
    def get_primary_bot(self) -> Optional[BotInfo]:
        """
        Get the primary bot (rpg-bot or first active bot).
        
        Returns:
            BotInfo if found, None otherwise
        """
        # Try rpg-bot first
        if "rpg-bot" in self._bots:
            bot = self._bots["rpg-bot"]
            if bot.is_active:
                return bot
        
        # Otherwise, return first active bot
        active_bots = self.list_bots(active_only=True)
        return active_bots[0] if active_bots else None
