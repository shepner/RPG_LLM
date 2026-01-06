"""WebSocket connection manager."""

from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
import json
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        """Initialize WebSocket manager."""
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str = "default"):
        """
        Accept a WebSocket connection and add to channel.
        
        Args:
            websocket: WebSocket connection
            channel: Channel/room name
        """
        await websocket.accept()
        
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        
        self.active_connections[channel].add(websocket)
        logger.info(f"WebSocket connected to channel: {channel}")
    
    def disconnect(self, websocket: WebSocket, channel: str = "default"):
        """
        Remove WebSocket from channel.
        
        Args:
            websocket: WebSocket connection
            channel: Channel/room name
        """
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
            if not self.active_connections[channel]:
                del self.active_connections[channel]
        logger.info(f"WebSocket disconnected from channel: {channel}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Send message to a specific WebSocket connection.
        
        Args:
            message: Message dict to send
            websocket: Target WebSocket connection
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast(self, message: dict, channel: str = "default"):
        """
        Broadcast message to all connections in a channel.
        
        Args:
            message: Message dict to broadcast
            channel: Channel/room name
        """
        if channel not in self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error broadcasting to connection: {e}")
                disconnected.add(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection, channel)
    
    async def broadcast_to_user(self, message: dict, user_id: str):
        """
        Broadcast message to all connections for a specific user.
        
        Args:
            message: Message dict to broadcast
            user_id: User ID
        """
        # TODO: Track user_id -> websocket mappings for user-specific broadcasts
        await self.broadcast(message, f"user_{user_id}")

