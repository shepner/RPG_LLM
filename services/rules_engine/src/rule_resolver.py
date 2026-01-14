"""Rule resolver for dice mechanics and rule resolution."""

import random
import re
import json
from typing import Dict, Any, Optional, List
from .models import RollResult, Resolution

# LLM integration
try:
    import os
    from shared.llm_provider import GeminiProvider
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


class RuleResolver:
    """Resolves rules and dice mechanics using LLM and indexed rules."""
    
    def __init__(self, rules_indexer=None):
        """Initialize resolver."""
        self.rules_indexer = rules_indexer
        self.llm_provider = None
        if LLM_AVAILABLE:
            try:
                model = os.getenv("LLM_MODEL", "gemini-2.5-flash")
                self.llm_provider = GeminiProvider(model=model)
            except Exception as e:
                print(f"Warning: LLM provider not available: {e}")
    
    def roll_dice(self, dice_string: str) -> RollResult:
        """
        Roll dice from string like "1d20+5" or "2d6".
        
        Args:
            dice_string: Dice notation string
            
        Returns:
            RollResult
        """
        # Parse dice string
        pattern = r'(\d+)d(\d+)([+-]\d+)?'
        match = re.match(pattern, dice_string.replace(' ', ''))
        
        if not match:
            raise ValueError(f"Invalid dice string: {dice_string}")
        
        num_dice = int(match.group(1))
        die_size = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0
        
        # Roll dice
        rolls = [random.randint(1, die_size) for _ in range(num_dice)]
        total = sum(rolls) + modifier
        
        return RollResult(
            dice=dice_string,
            result=total,
            rolls=rolls,
            modifier=modifier
        )
    
    async def resolve_action(
        self,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Resolution:
        """
        Resolve an action using rules and LLM.
        
        Args:
            action: Action description
            context: Additional context (character stats, game state, etc.)
            
        Returns:
            Resolution with result and explanation
        """
        # If no LLM available, return basic response
        if not self.llm_provider:
            return Resolution(
                result=None,
                explanation=f"Resolved action: {action} (LLM not available)",
                metadata={"action": action, "context": context or {}}
            )
        
        # Search for relevant rules
        relevant_rules = []
        if self.rules_indexer:
            search_results = await self.rules_indexer.search(action, n_results=5)
            relevant_rules = [r["content"] for r in search_results]
        
        # Check if this is a character creation action
        is_character_creation = "create character" in action.lower() or "generate character" in action.lower() or context.get("creation_type") in ["manual", "automatic"]
        
        # Build prompt for LLM
        rules_context = "\n\n".join(relevant_rules) if relevant_rules else "No specific rules found for this action."
        
        if is_character_creation:
            # Special prompt for character creation
            game_system = context.get("game_system") if context else None
            flavor_data = context.get("flavor_data") if context else {}
            
            prompt = f"""You are Ma'at, the Rules Engine for a Tabletop Role-Playing Game system. You are creating a new character based on the provided rules.

AVAILABLE RULES CONTEXT:
{rules_context}

CHARACTER CREATION REQUEST:
{action}

CHARACTER FLAVOR:
{json.dumps(flavor_data, indent=2) if flavor_data else "Auto-generated"}

GAME SYSTEM:
{game_system or "Not specified"}

ADDITIONAL CONTEXT:
{json.dumps({k: v for k, v in (context or {}).items() if k not in ["flavor_data"]}, indent=2)}

Based on the rules provided, you must:
1. Generate appropriate character statistics (stats) according to the game system rules
2. Determine starting skills and skill levels
3. Assign abilities, traits, or special features as per the rules
4. Ensure all mechanics follow the game system's character creation guidelines

Return your response as JSON with this structure:
{{
    "explanation": "Brief explanation of character creation process",
    "stats": {{"stat_name": value, ...}},
    "skills": {{"skill_name": value, ...}},
    "abilities": {{"ability_name": "description", ...}},
    "game_system": "{game_system or "generic"}",
    "notes": "Any important notes about this character"
}}

If the game system is D&D 5e, use standard ability scores (Strength, Dexterity, Constitution, Intelligence, Wisdom, Charisma) with values typically 8-15 for starting characters.
If Pathfinder, use similar ability scores plus additional mechanics.
If no specific system, use generic stats."""
        else:
            # Standard action resolution prompt
            prompt = f"""You are Ma'at, the Rules Engine for a Tabletop Role-Playing Game system. Your role is to interpret and apply game rules accurately.

AVAILABLE RULES CONTEXT:
{rules_context}

ACTION TO RESOLVE:
{action}

ADDITIONAL CONTEXT:
{context or "None"}

Based on the rules provided, determine:
1. What dice rolls (if any) are needed
2. What modifiers apply
3. What the outcome should be
4. Any special conditions or exceptions

Provide a clear explanation of how the rules apply to this action."""

        try:
            # Query LLM
            max_tokens = 2000 if is_character_creation else 500
            # Ma'at should be extremely deterministic by default.
            maat_temperature = float(os.getenv("MAAT_TEMPERATURE", "0.0"))
            response = await self.llm_provider.generate(
                prompt=prompt,
                system_prompt="You are Ma'at, the Rules Engine. You interpret and apply game rules with precision and fairness." + 
                             (" When creating characters, you must return valid JSON with stats, skills, and abilities." if is_character_creation else ""),
                temperature=maat_temperature,
                max_tokens=max_tokens
            )
            
            explanation = response.text
            
            # For character creation, try to parse JSON from response
            if is_character_creation:
                try:
                    # Try to extract JSON from response (might be wrapped in markdown code blocks)
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', explanation, re.DOTALL)
                    if json_match:
                        char_data = json.loads(json_match.group(1))
                    else:
                        # Try to find JSON object directly
                        json_match = re.search(r'\{.*"stats".*\}', explanation, re.DOTALL)
                        if json_match:
                            char_data = json.loads(json_match.group(0))
                        else:
                            # Fallback: try to parse entire response as JSON
                            char_data = json.loads(explanation)
                    
                    # Extract mechanics from parsed JSON
                    stats = char_data.get("stats", {})
                    skills = char_data.get("skills", {})
                    abilities = char_data.get("abilities", {})
                    game_system = char_data.get("game_system") or (context.get("game_system") if context else None)
                    notes = char_data.get("notes", "")
                    
                    return Resolution(
                        rule_id=None,
                        result=True,  # Character creation succeeded
                        explanation=char_data.get("explanation", explanation),
                        metadata={
                            "action": action,
                            "context": context or {},
                            "stats": stats,
                            "skills": skills,
                            "abilities": abilities,
                            "game_system": game_system,
                            "notes": notes,
                            "rules_used": [r.get("metadata", {}).get("filename", "unknown") for r in search_results] if relevant_rules else [],
                            "generated_flavor": char_data.get("generated_flavor", {}) if "generated_flavor" in char_data else None
                        }
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    # If JSON parsing fails, return explanation but log the error
                    print(f"Warning: Could not parse character creation JSON from LLM response: {e}")
                    print(f"Response was: {explanation[:500]}")
            
            # Standard action resolution (non-character creation)
            # Try to extract dice notation from response
            dice_match = re.search(r'(\d+d\d+[+-]\d*)', explanation, re.IGNORECASE)
            dice_string = dice_match.group(1) if dice_match else None
            
            # If dice found, roll them
            dice_result = None
            if dice_string:
                try:
                    dice_result = self.roll_dice(dice_string)
                except:
                    pass
            
            return Resolution(
                rule_id=None,
                result=dice_result.result if dice_result else None,
                explanation=explanation,
                metadata={
                    "action": action,
                    "context": context or {},
                    "dice_rolled": dice_string,
                    "dice_result": dice_result.dict() if dice_result else None,
                    "rules_used": [r.get("metadata", {}).get("filename", "unknown") for r in search_results] if relevant_rules else []
                }
            )
        except Exception as e:
            return Resolution(
                result=None,
                explanation=f"Error resolving action: {str(e)}",
                metadata={"action": action, "error": str(e)}
            )

