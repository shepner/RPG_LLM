"""Message routing for Mattermost bot."""

import logging
import re
from typing import Optional, Dict, Tuple
from .channel_manager import ChannelManager

logger = logging.getLogger(__name__)


class MessageRouter:
    """Routes messages to appropriate handlers."""
    
    def __init__(self, channel_manager: ChannelManager):
        """
        Initialize message router.
        
        Args:
            channel_manager: Channel manager instance
        """
        self.channel_manager = channel_manager
        self.command_prefix = "/rpg-"
    
    def is_command(self, message: str) -> bool:
        """
        Check if message is a command.
        
        Args:
            message: Message text
            
        Returns:
            True if message starts with command prefix
        """
        return message.strip().startswith(self.command_prefix)
    
    def parse_command(self, message: str) -> Tuple[str, list]:
        """
        Parse command and arguments.
        
        Args:
            message: Command message
            
        Returns:
            Tuple of (command_name, arguments)
        """
        message = message.strip()
        if not message.startswith(self.command_prefix):
            return ("", [])
        
        parts = message[len(self.command_prefix):].split()
        if not parts:
            return ("", [])
        
        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        
        return (command, args)
    
    def extract_mentions(self, message: str) -> list:
        """
        Extract @mentions from message.
        
        Args:
            message: Message text
            
        Returns:
            List of mentioned usernames (without @)
        """
        mention_pattern = r'@(\w+)'
        mentions = re.findall(mention_pattern, message)
        return mentions
    
    def get_channel_type(self, channel_id: str) -> str:
        """
        Get channel type (character_dm, session_channel, or unknown).
        
        Args:
            channel_id: Mattermost channel ID
            
        Returns:
            Channel type string
        """
        being_id = self.channel_manager.get_being_id_from_channel(channel_id)
        if being_id:
            return "character_dm"
        
        session_id = self.channel_manager.get_session_id_from_channel(channel_id)
        if session_id:
            return "session_channel"
        
        return "unknown"
    
    def get_target_being_id(self, channel_id: str, message: str) -> Optional[str]:
        """
        Get target being_id from channel and message context.
        
        Args:
            channel_id: Mattermost channel ID
            message: Message text
            
        Returns:
            Being ID if found, None otherwise
        """
        # First check if channel is a character DM
        being_id = self.channel_manager.get_being_id_from_channel(channel_id)
        if being_id:
            return being_id
        
        # If in session channel, check for @mentions
        # For now, we'll handle this in character_handler
        return None
