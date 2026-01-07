"""Rule resolver for dice mechanics and rule resolution."""

import random
import re
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
                model = os.getenv("LLM_MODEL", "gemini-pro")
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
        
        # Build prompt for LLM
        rules_context = "\n\n".join(relevant_rules) if relevant_rules else "No specific rules found for this action."
        
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
            response = await self.llm_provider.generate(
                prompt=prompt,
                system_prompt="You are Ma'at, the Rules Engine. You interpret and apply game rules with precision and fairness.",
                temperature=0.3,  # Lower temperature for more consistent rule interpretation
                max_tokens=500
            )
            
            explanation = response.text
            
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

