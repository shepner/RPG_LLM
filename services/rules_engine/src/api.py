"""Rules engine service API."""

import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .rule_resolver import RuleResolver
from .models import RollResult, Resolution

# Import auth middleware (optional)
try:
    import sys
    sys.path.insert(0, '/app/services/auth/src')
    from middleware import require_auth, get_current_user, TokenData
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    def require_auth():
        return None
    def get_current_user():
        return None
    TokenData = None

app = FastAPI(title="Rules Engine Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.post("/rules/upload")
async def upload_rules(file: UploadFile = File(...), token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None):
    """Upload rules file (Markdown, YAML, or JSON)."""
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Store rules (simple in-memory for now, can be enhanced with database)
        # TODO: Parse and store rules properly
        return {
            "message": "Rules uploaded successfully",
            "filename": file.filename,
            "size": len(content_str),
            "type": file.content_type
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload rules: {str(e)}")


@app.get("/rules/list")
async def list_rules(token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None):
    """List available rules files."""
    # TODO: Return actual list of rules
    return {"rules": []}


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

