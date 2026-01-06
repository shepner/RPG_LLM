"""Rules engine service API."""

import os
import json
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
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

# Rules storage directory
RULES_DIR = Path(os.getenv("RULES_DIR", "./RPG_LLM_DATA/rules"))
RULES_DIR.mkdir(parents=True, exist_ok=True)
RULES_METADATA_FILE = RULES_DIR / "metadata.json"

# In-memory cache of rules metadata
_rules_metadata: Dict[str, Dict[str, Any]] = {}

def load_rules_metadata():
    """Load rules metadata from file."""
    global _rules_metadata
    if RULES_METADATA_FILE.exists():
        try:
            with open(RULES_METADATA_FILE, 'r') as f:
                _rules_metadata = json.load(f)
        except Exception:
            _rules_metadata = {}
    else:
        _rules_metadata = {}

def save_rules_metadata():
    """Save rules metadata to file."""
    try:
        with open(RULES_METADATA_FILE, 'w') as f:
            json.dump(_rules_metadata, f, indent=2)
    except Exception as e:
        print(f"Error saving rules metadata: {e}")

# Load metadata on startup
load_rules_metadata()


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
async def upload_rules(
    file: UploadFile = File(...), 
    token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None
):
    """
    Upload rules file (Markdown, YAML, or JSON).
    
    You can upload unlimited files. Each file is stored with its original filename.
    If a file with the same name already exists, it will be overwritten.
    """
    try:
        # Validate file type
        allowed_extensions = {'.md', '.markdown', '.yaml', '.yml', '.json', '.txt'}
        file_ext = Path(file.filename).suffix.lower() if file.filename else ''
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Generate file hash for deduplication/versioning
        file_hash = hashlib.sha256(content).hexdigest()[:16]
        
        # Save file to disk
        safe_filename = file.filename or f"rules_{file_hash}{file_ext}"
        file_path = RULES_DIR / safe_filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content_str)
        
        # Update metadata
        file_id = file_hash
        _rules_metadata[file_id] = {
            "file_id": file_id,
            "filename": safe_filename,
            "original_filename": file.filename,
            "size": len(content_str),
            "type": file.content_type or "application/octet-stream",
            "extension": file_ext,
            "uploaded_at": datetime.now().isoformat(),
            "uploaded_by": token_data.user_id if token_data else None
        }
        save_rules_metadata()
        
        return {
            "message": "Rules uploaded successfully",
            "file_id": file_id,
            "filename": safe_filename,
            "size": len(content_str),
            "type": file.content_type,
            "uploaded_at": _rules_metadata[file_id]["uploaded_at"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload rules: {str(e)}")


@app.get("/rules/list")
async def list_rules(token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None):
    """List all uploaded rules files."""
    load_rules_metadata()  # Refresh metadata
    rules_list = list(_rules_metadata.values())
    return {
        "rules": rules_list,
        "count": len(rules_list),
        "total_size": sum(r.get("size", 0) for r in rules_list)
    }


@app.get("/rules/{file_id}")
async def get_rule(
    file_id: str,
    token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None
):
    """Get a specific rules file by ID."""
    load_rules_metadata()
    if file_id not in _rules_metadata:
        raise HTTPException(status_code=404, detail="Rules file not found")
    
    metadata = _rules_metadata[file_id]
    file_path = RULES_DIR / metadata["filename"]
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Rules file not found on disk")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return {
        "file_id": file_id,
        "metadata": metadata,
        "content": content
    }


@app.delete("/rules/{file_id}")
async def delete_rule(
    file_id: str,
    token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None
):
    """Delete a rules file (GM only)."""
    if AUTH_AVAILABLE and token_data:
        # Check if user is GM (would need to import require_gm)
        pass  # TODO: Add GM check
    
    load_rules_metadata()
    if file_id not in _rules_metadata:
        raise HTTPException(status_code=404, detail="Rules file not found")
    
    metadata = _rules_metadata[file_id]
    file_path = RULES_DIR / metadata["filename"]
    
    # Delete file
    if file_path.exists():
        file_path.unlink()
    
    # Remove from metadata
    del _rules_metadata[file_id]
    save_rules_metadata()
    
    return {"message": "Rules file deleted", "file_id": file_id}


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

