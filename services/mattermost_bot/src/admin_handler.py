"""Administrative command handler for Mattermost bot."""

import logging
import httpx
from typing import Optional, Dict, List
from .config import Config
from .auth_bridge import AuthBridge

logger = logging.getLogger(__name__)


class AdminHandler:
    """Handles administrative slash commands."""
    
    def __init__(self, auth_bridge: AuthBridge):
        """
        Initialize admin handler.
        
        Args:
            auth_bridge: Auth bridge instance
        """
        self.auth_bridge = auth_bridge
    
    async def handle_command(
        self,
        command: str,
        args: list,
        mattermost_user_id: str,
        mattermost_username: Optional[str] = None,
        mattermost_email: Optional[str] = None
    ) -> Dict:
        """
        Handle an administrative command.
        
        Args:
            command: Command name
            args: Command arguments
            mattermost_user_id: Mattermost user ID
            mattermost_username: Optional Mattermost username
            mattermost_email: Optional Mattermost email
            
        Returns:
            Dictionary with response data for Mattermost
        """
        logger.info(f"AdminHandler.handle_command: user_id={mattermost_user_id}, username={mattermost_username}, email={mattermost_email}")
        auth_headers = await self.auth_bridge.get_auth_headers(mattermost_user_id, mattermost_username, mattermost_email)
        logger.info(f"Auth headers received: {list(auth_headers.keys()) if auth_headers else 'EMPTY'}")
        
        handlers = {
            "create-character": self._handle_create_character,
            "list-characters": self._handle_list_characters,
            "delete-character": self._handle_delete_character,
            "create-session": self._handle_create_session,
            "join-session": self._handle_join_session,
            "health": self._handle_health,
            "roll": self._handle_roll,
            "world-event": self._handle_world_event,
            "system-status": self._handle_system_status,
        }
        
        handler = handlers.get(command)
        if handler:
            try:
                return await handler(args, auth_headers, mattermost_user_id, mattermost_username, mattermost_email)
            except Exception as e:
                logger.error(f"Error handling command {command}: {e}", exc_info=True)
                return {
                    "text": f"Error executing command: {str(e)}",
                    "response_type": "ephemeral"
                }
        else:
            return {
                "text": f"Unknown command: {command}. Use `/rpg-help` for available commands.",
                "response_type": "ephemeral"
            }
    
    async def _handle_create_character(self, args: list, auth_headers: Dict, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Dict:
        """Handle character creation command."""
        logger.info(f"_handle_create_character: auth_headers={auth_headers}, user_id={mattermost_user_id}")
        name = args[0] if args else None
        
        request_data = {
            "name": name,
            "conversational": True  # Enable conversational creation
        }
        
        logger.info(f"Making request to {Config.BEING_REGISTRY_URL}/beings/create with headers: {list(auth_headers.keys())}")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{Config.BEING_REGISTRY_URL}/beings/create",
                json=request_data,
                headers=auth_headers
            )
            logger.info(f"Response status: {response.status_code}, body: {response.text[:200]}")
            
            if response.status_code == 200:
                data = response.json()
                being_id = data.get("being_id")
                return {
                    "text": f"Character created successfully!",
                    "attachments": [{
                        "title": "Character Created",
                        "fields": [
                            {"short": True, "title": "Character ID", "value": being_id[:8] + "..."},
                            {"short": True, "title": "Name", "value": name or "Unnamed"}
                        ]
                    }]
                }
            else:
                return {
                    "text": f"Error creating character: {response.text}",
                    "response_type": "ephemeral"
                }
    
    async def _handle_list_characters(self, args: list, auth_headers: Dict, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Dict:
        """Handle list characters command."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{Config.BEING_REGISTRY_URL}/beings/my-characters",
                headers=auth_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                characters = data.get("characters", [])
                
                if not characters:
                    return {
                        "text": "You don't have any characters yet. Use `/rpg-create-character` to create one.",
                        "response_type": "ephemeral"
                    }
                
                fields = []
                for char in characters[:10]:  # Limit to 10
                    fields.append({
                        "short": True,
                        "title": char.get("name", "Unnamed"),
                        "value": f"ID: {char.get('being_id', '')[:8]}..."
                    })
                
                return {
                    "text": f"You have {len(characters)} character(s):",
                    "attachments": [{"fields": fields}]
                }
            else:
                return {
                    "text": f"Error listing characters: {response.text}",
                    "response_type": "ephemeral"
                }
    
    async def _handle_delete_character(self, args: list, auth_headers: Dict, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Dict:
        """Handle delete character command."""
        if not args:
            return {
                "text": "Usage: `/rpg-delete-character <being_id>`",
                "response_type": "ephemeral"
            }
        
        being_id = args[0]
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                f"{Config.BEING_REGISTRY_URL}/beings/{being_id}",
                headers=auth_headers
            )
            
            if response.status_code == 200:
                return {
                    "text": f"Character {being_id[:8]}... deleted successfully.",
                    "response_type": "ephemeral"
                }
            else:
                return {
                    "text": f"Error deleting character: {response.text}",
                    "response_type": "ephemeral"
                }
    
    async def _handle_create_session(self, args: list, auth_headers: Dict, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Dict:
        """Handle create session command."""
        name = args[0] if args else "New Session"
        
        # Get RPG user ID to set as GM
        rpg_user_id = await self.auth_bridge.get_rpg_user_id(mattermost_user_id)
        
        request_data = {
            "name": name,
            "description": "Game session created via Mattermost",
            "game_system_type": "D&D",
            "time_mode_preference": "real-time"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{Config.GAME_SESSION_URL}/sessions?gm_user_id={rpg_user_id or 'unknown'}",
                json=request_data,
                headers=auth_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                session_id = data.get("session_id")
                return {
                    "text": f"Session '{name}' created successfully!",
                    "attachments": [{
                        "title": "Session Created",
                        "fields": [
                            {"short": True, "title": "Session ID", "value": session_id[:8] + "..."},
                            {"short": True, "title": "Name", "value": name}
                        ]
                    }]
                }
            else:
                return {
                    "text": f"Error creating session: {response.text}",
                    "response_type": "ephemeral"
                }
    
    async def _handle_join_session(self, args: list, auth_headers: Dict, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Dict:
        """Handle join session command."""
        if not args:
            return {
                "text": "Usage: `/rpg-join-session <session_id>`",
                "response_type": "ephemeral"
            }
        
        session_id = args[0]
        rpg_user_id = await self.auth_bridge.get_rpg_user_id(mattermost_user_id)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{Config.GAME_SESSION_URL}/sessions/{session_id}/join?user_id={rpg_user_id or 'unknown'}",
                headers=auth_headers
            )
            
            if response.status_code == 200:
                return {
                    "text": f"Joined session {session_id[:8]}... successfully!",
                    "response_type": "ephemeral"
                }
            else:
                return {
                    "text": f"Error joining session: {response.text}",
                    "response_type": "ephemeral"
                }
    
    async def _handle_health(self, args: list, auth_headers: Dict, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Dict:
        """Handle health check command."""
        services = {
            "Auth": Config.AUTH_URL,
            "Being": Config.BEING_URL,
            "Being Registry": Config.BEING_REGISTRY_URL,
            "Game Session": Config.GAME_SESSION_URL,
            "Game Master": Config.GAME_MASTER_URL,
            "Rules Engine": Config.RULES_ENGINE_URL,
            "Worlds": Config.WORLDS_URL,
            "Time Management": Config.TIME_MANAGEMENT_URL,
        }
        
        results = []
        async with httpx.AsyncClient(timeout=5.0) as client:
            for name, url in services.items():
                try:
                    response = await client.get(f"{url}/health")
                    status = "✅ Healthy" if response.status_code == 200 else f"❌ Status {response.status_code}"
                except Exception as e:
                    status = f"❌ Error: {str(e)[:30]}"
                
                results.append({
                    "short": True,
                    "title": name,
                    "value": status
                })
        
        return {
            "text": "Service Health Status:",
            "attachments": [{"fields": results}]
        }
    
    async def _handle_roll(self, args: list, auth_headers: Dict, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Dict:
        """Handle dice roll command."""
        if not args:
            return {
                "text": "Usage: `/rpg-roll <dice>` (e.g., `/rpg-roll 1d20`)",
                "response_type": "ephemeral"
            }
        
        dice = args[0]
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{Config.RULES_ENGINE_URL}/roll?dice={dice}",
                headers=auth_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("total") or data.get("result")
                return {
                    "text": f"🎲 Rolled {dice}: **{result}**"
                }
            else:
                return {
                    "text": f"Error rolling dice: {response.text}",
                    "response_type": "ephemeral"
                }
    
    async def _handle_world_event(self, args: list, auth_headers: Dict, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Dict:
        """Handle world event recording command."""
        if not args:
            return {
                "text": "Usage: `/rpg-world-event <description>`",
                "response_type": "ephemeral"
            }
        
        description = " ".join(args)
        
        request_data = {
            "event_type": "user_recorded",
            "description": description,
            "game_time": 0.0,  # Would need to get current game time
            "metadata": {}
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{Config.WORLDS_URL}/events",
                json=request_data,
                headers=auth_headers
            )
            
            if response.status_code == 200:
                return {
                    "text": f"World event recorded: {description}"
                }
            else:
                return {
                    "text": f"Error recording event: {response.text}",
                    "response_type": "ephemeral"
                }
    
    async def _handle_system_status(self, args: list, auth_headers: Dict, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Dict:
        """Handle system status command."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{Config.BEING_REGISTRY_URL}/system/validate",
                    headers=auth_headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Format validation report
                    return {
                        "text": "System Status:",
                        "attachments": [{
                            "title": "Validation Report",
                            "text": str(data)[:500]  # Truncate if too long
                        }]
                    }
                else:
                    return {
                        "text": f"Error getting system status: {response.text}",
                        "response_type": "ephemeral"
                    }
        except Exception as e:
            return {
                "text": f"Error: {str(e)}",
                "response_type": "ephemeral"
            }
