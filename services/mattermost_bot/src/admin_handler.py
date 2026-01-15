"""Administrative command handler for Mattermost bot."""

import logging
import httpx
from typing import Optional, Dict, List
from .config import Config
from .auth_bridge import AuthBridge
from .runtime_settings import RuntimeSettings, parse_scalar

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
        self.runtime_settings = RuntimeSettings()
    
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
            # Runtime tuning
            "config": self._handle_config,
            # Prompt management
            "prompt": self._handle_prompt,
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

    async def _handle_config(self, args: list, auth_headers: Dict, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Dict:
        """
        Runtime settings commands.

        Usage:
          /rpg config show
          /rpg config get <path>
          /rpg config set <path> <value>

        Examples:
          /rpg config set channel_collab.base_response_prob 0.4
          /rpg config set channel_collab.reply_in_thread false
          /rpg config set bot_temperatures.thoth 1.3
        """
        if not args:
            return {"text": "Usage: `/rpg config show|get|set ...`", "response_type": "ephemeral"}

        sub = args[0].lower()
        data = self.runtime_settings.get()

        if sub == "show":
            import json
            return {
                "text": f"Runtime settings (`RPG_LLM_DATA/mattermost_bot/settings.json`):\n```json\n{json.dumps(data, indent=2, sort_keys=True)}\n```",
                "response_type": "ephemeral",
            }

        if sub == "get":
            if len(args) < 2:
                return {"text": "Usage: `/rpg config get <path>`", "response_type": "ephemeral"}
            path = args[1]
            cur = data
            for part in [p for p in path.split(".") if p]:
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    cur = None
                    break
            return {"text": f"`{path}` = `{cur}`", "response_type": "ephemeral"}

        if sub == "set":
            if len(args) < 3:
                return {"text": "Usage: `/rpg config set <path> <value>`", "response_type": "ephemeral"}
            path = args[1]
            value = parse_scalar(" ".join(args[2:]))
            self.runtime_settings.set_path(path, value)
            return {"text": f"Set `{path}` = `{value}`", "response_type": "ephemeral"}

        return {"text": "Usage: `/rpg config show|get|set ...`", "response_type": "ephemeral"}

    async def _handle_prompt(self, args: list, auth_headers: Dict, mattermost_user_id: str, mattermost_username: Optional[str] = None, mattermost_email: Optional[str] = None) -> Dict:
        """
        Prompt management (GM only; enforced by downstream services).

        Usage:
          /rpg prompt list <gaia|thoth|maat> [session_id]
          /rpg prompt add <gaia|thoth|maat> <title> <global|session> <content...>
          /rpg prompt update <gaia|thoth|maat> <prompt_id> <title|content|scope|session_ids|game_system> <value...>
          /rpg prompt delete <gaia|thoth|maat> <prompt_id>
        """
        if len(args) < 2:
            return {"text": "Usage: `/rpg prompt list|add|update|delete <gaia|thoth|maat> ...`", "response_type": "ephemeral"}

        sub = args[0].lower()
        service = args[1].lower()
        service_url = {
            "gaia": Config.WORLDS_URL,
            "thoth": Config.GAME_MASTER_URL,
            "maat": Config.RULES_ENGINE_URL,
        }.get(service)
        if not service_url:
            return {"text": "Service must be one of: gaia, thoth, maat", "response_type": "ephemeral"}

        async with httpx.AsyncClient(timeout=20.0) as client:
            if sub == "list":
                session_id = args[2] if len(args) > 2 else None
                params = {"include_global": "true"}
                if session_id:
                    params["session_id"] = session_id
                r = await client.get(f"{service_url}/prompts", headers=auth_headers, params=params)
                if r.status_code != 200:
                    return {"text": f"Error listing prompts: {r.status_code} {r.text[:400]}", "response_type": "ephemeral"}
                prompts = r.json()
                lines = []
                for p in prompts[:25]:
                    lines.append(f"- `{p.get('prompt_id')}` [{p.get('scope')}] {p.get('title')}")
                more = "" if len(prompts) <= 25 else f"\n… and {len(prompts) - 25} more"
                return {"text": f"Prompts for {service}:\n" + "\n".join(lines) + more, "response_type": "ephemeral"}

            if sub == "add":
                if len(args) < 5:
                    return {"text": "Usage: `/rpg prompt add <service> <title> <global|session> <content...>`", "response_type": "ephemeral"}
                title = args[2]
                scope = args[3].lower()
                content = " ".join(args[4:])
                payload = {"title": title, "content": content, "scope": scope}
                r = await client.post(f"{service_url}/prompts", headers=auth_headers, json=payload)
                if r.status_code != 200:
                    return {"text": f"Error creating prompt: {r.status_code} {r.text[:400]}", "response_type": "ephemeral"}
                p = r.json()
                return {"text": f"Created prompt `{p.get('prompt_id')}` for {service}.", "response_type": "ephemeral"}

            if sub == "update":
                if len(args) < 5:
                    return {"text": "Usage: `/rpg prompt update <service> <prompt_id> <field> <value...>`", "response_type": "ephemeral"}
                prompt_id = args[2]
                field = args[3]
                value = " ".join(args[4:])
                payload = {field: value}
                r = await client.patch(f"{service_url}/prompts/{prompt_id}", headers=auth_headers, json=payload)
                if r.status_code != 200:
                    return {"text": f"Error updating prompt: {r.status_code} {r.text[:400]}", "response_type": "ephemeral"}
                return {"text": f"Updated prompt `{prompt_id}` ({field}).", "response_type": "ephemeral"}

            if sub == "delete":
                if len(args) < 3:
                    return {"text": "Usage: `/rpg prompt delete <service> <prompt_id>`", "response_type": "ephemeral"}
                prompt_id = args[2]
                r = await client.delete(f"{service_url}/prompts/{prompt_id}", headers=auth_headers)
                if r.status_code != 200:
                    return {"text": f"Error deleting prompt: {r.status_code} {r.text[:400]}", "response_type": "ephemeral"}
                return {"text": f"Deleted prompt `{prompt_id}`.", "response_type": "ephemeral"}

        return {"text": "Usage: `/rpg prompt list|add|update|delete ...`", "response_type": "ephemeral"}
    
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
