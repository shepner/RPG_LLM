"""Character/being creation workflows."""

import os
import httpx
from typing import Dict, Any, Optional
from .models import BeingRegistry


class CharacterCreator:
    """Handles character/being creation workflows."""
    
    def __init__(self):
        """Initialize character creator."""
        self.rules_engine_url = os.getenv("RULES_ENGINE_URL", "http://rules_engine:8002")
    
    async def _consult_rules_engine(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Consult Rules Engine (Ma'at) for rule validation and mechanics.
        
        Args:
            action: Action description (e.g., "create character with strength-based concept")
            context: Context including character concept, game system, etc.
            
        Returns:
            Rules engine response with validated mechanics
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.rules_engine_url}/resolve",
                    json={
                        "action": action,
                        "context": context
                    }
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Warning: Rules engine returned {response.status_code}: {response.text}")
                    return {"result": None, "explanation": "Rules engine unavailable", "metadata": {}}
        except Exception as e:
            print(f"Warning: Failed to consult rules engine: {e}")
            return {"result": None, "explanation": f"Rules engine error: {str(e)}", "metadata": {}}
    
    async def create_manual(
        self,
        being_id: str,
        owner_id: str,
        flavor_data: Dict[str, Any],
        game_system: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a character manually (player provides flavor, system generates mechanics).
        
        Args:
            being_id: Being ID
            owner_id: Owner user ID
            flavor_data: Player-provided flavor (name, backstory, personality, etc.)
            game_system: Game system type (D&D, Pathfinder, etc.)
            
        Returns:
            Character data with both flavor and mechanics
        """
        # Build action description for rules engine
        name = flavor_data.get("name", "Unknown")
        concept_description = f"Character: {name}"
        if flavor_data.get("backstory"):
            concept_description += f"\nBackstory: {flavor_data['backstory']}"
        if flavor_data.get("personality"):
            concept_description += f"\nPersonality: {flavor_data['personality']}"
        
        action = f"Create character with concept: {concept_description}"
        if game_system:
            action += f" using {game_system} rules"
        
        # Consult Rules Engine (Ma'at) for mechanics generation and validation
        context = {
            "being_id": being_id,
            "owner_id": owner_id,
            "flavor_data": flavor_data,
            "game_system": game_system,
            "creation_type": "manual"
        }
        
        rules_response = await self._consult_rules_engine(action, context)
        
        # Extract mechanics from rules engine response
        mechanics = {
            "validated_by": "maat",
            "rules_engine_response": rules_response,
            "game_system": game_system,
            "stats": rules_response.get("metadata", {}).get("stats", {}),
            "skills": rules_response.get("metadata", {}).get("skills", {}),
            "abilities": rules_response.get("metadata", {}).get("abilities", {}),
            "validation_notes": rules_response.get("explanation", "")
        }
        
        return {
            "being_id": being_id,
            "owner_id": owner_id,
            "flavor": flavor_data,
            "mechanics": mechanics,
            "rules_validation": {
                "consulted": True,
                "status": "validated" if rules_response.get("result") is not None else "warning",
                "message": rules_response.get("explanation", "")
            }
        }
    
    async def create_automatic(
        self,
        owner_id: str,
        context: Optional[Dict[str, Any]] = None,
        game_system: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Automatically generate a character (both flavor and mechanics).
        
        Args:
            owner_id: Owner user ID
            context: Optional context (party composition, story context, etc.)
            game_system: Game system type
            
        Returns:
            Complete character data
        """
        # For automatic generation, we'll create a generic concept
        # In a full implementation, this would use an LLM to generate the concept
        action = "Automatically generate a character"
        if game_system:
            action += f" using {game_system} rules"
        
        # Consult Rules Engine (Ma'at) for automatic character generation
        rules_context = {
            "owner_id": owner_id,
            "game_system": game_system,
            "creation_type": "automatic",
            "context": context or {}
        }
        
        rules_response = await self._consult_rules_engine(action, rules_context)
        
        # Extract generated data from rules engine
        generated_flavor = rules_response.get("metadata", {}).get("generated_flavor", {
            "name": "Auto-Generated Character",
            "backstory": "Generated by system",
            "personality": "To be determined"
        })
        
        mechanics = {
            "validated_by": "maat",
            "rules_engine_response": rules_response,
            "game_system": game_system,
            "stats": rules_response.get("metadata", {}).get("stats", {}),
            "skills": rules_response.get("metadata", {}).get("skills", {}),
            "abilities": rules_response.get("metadata", {}).get("abilities", {}),
            "validation_notes": rules_response.get("explanation", "")
        }
        
        return {
            "owner_id": owner_id,
            "flavor": generated_flavor,
            "mechanics": mechanics,
            "rules_validation": {
                "consulted": True,
                "status": "validated" if rules_response.get("result") is not None else "warning",
                "message": rules_response.get("explanation", "")
            }
        }

