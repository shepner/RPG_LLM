"""Rules engine service API."""

import os
from typing import List
from fastapi import FastAPI, HTTPException
from .rule_resolver import RuleResolver
from .models import RollResult, Resolution

app = FastAPI(title="Rules Engine Service")

resolver = RuleResolver()


@app.post("/roll", response_model=RollResult)
async def roll_dice(dice: str):
    """Roll dice."""
    try:
        result = resolver.roll_dice(dice)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/resolve", response_model=Resolution)
async def resolve_action(action: str, context: dict = None):
    """Resolve an action using rules."""
    # TODO: Load rules and implement full resolution
    result = resolver.resolve_action(action, {}, context)
    return result


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

