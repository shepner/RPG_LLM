"""Rule resolver for dice mechanics and rule resolution."""

import random
import re
from typing import Dict, Any, Optional
from .models import RollResult, Resolution


class RuleResolver:
    """Resolves rules and dice mechanics."""
    
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
    
    def resolve_action(
        self,
        action: str,
        rules: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Resolution:
        """
        Resolve an action using rules.
        
        Args:
            action: Action description
            rules: Available rules
            context: Additional context
            
        Returns:
            Resolution
        """
        # Simple rule lookup (can be enhanced with LLM)
        # TODO: Integrate LLM for rule interpretation
        return Resolution(
            result=None,
            explanation=f"Resolved action: {action}",
            metadata={"action": action, "context": context or {}}
        )

