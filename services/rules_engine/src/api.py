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
    Upload rules file or image.
    
    Supported formats:
    - Text: Markdown (.md, .markdown) - PREFERRED for rules
    - Text: YAML (.yaml, .yml), JSON (.json), Text (.txt)
    - Documents: PDF (.pdf), EPUB (.epub) - Common for game modules
    - Images: PNG (.png), JPEG (.jpg, .jpeg), GIF (.gif), WebP (.webp), SVG (.svg)
    
    You can upload unlimited files. Each file is stored with its original filename.
    If a file with the same name already exists, it will be overwritten.
    """
    try:
        # Define allowed file types
        text_extensions = {'.md', '.markdown', '.yaml', '.yml', '.json', '.txt'}
        document_extensions = {'.pdf', '.epub'}
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}
        all_allowed = text_extensions | document_extensions | image_extensions
        
        file_ext = Path(file.filename).suffix.lower() if file.filename else ''
        if file_ext not in all_allowed:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed: Markdown (.md), PDF (.pdf), EPUB (.epub), Images (.png, .jpg, .gif, .webp, .svg), YAML (.yaml), JSON (.json), Text (.txt)"
            )
        
        # Read file content (binary for images/PDFs, text for others)
        content = await file.read()
        
        # Determine file category
        is_text = file_ext in text_extensions
        is_image = file_ext in image_extensions
        is_pdf = file_ext == '.pdf'
        is_epub = file_ext == '.epub'
        is_document = file_ext in document_extensions
        
        # Generate file hash for deduplication/versioning
        file_hash = hashlib.sha256(content).hexdigest()[:16]
        
        # Save file to disk (binary mode for images/PDFs, text mode for text files)
        safe_filename = file.filename or f"rules_{file_hash}{file_ext}"
        file_path = RULES_DIR / safe_filename
        
        if is_text:
            # Save as text
            content_str = content.decode('utf-8')
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content_str)
            file_size = len(content_str)
        else:
            # Save as binary (PDFs, EPUBs, images)
            with open(file_path, 'wb') as f:
                f.write(content)
            file_size = len(content)
        
        # Update metadata
        file_id = file_hash
        file_category = "text" if is_text else ("image" if is_image else "document")
        _rules_metadata[file_id] = {
            "file_id": file_id,
            "filename": safe_filename,
            "original_filename": file.filename,
            "size": file_size,
            "type": file.content_type or "application/octet-stream",
            "extension": file_ext,
            "category": file_category,
            "is_text": is_text,
            "is_image": is_image,
            "is_pdf": is_pdf,
            "is_epub": is_epub,
            "is_document": is_document,
            "uploaded_at": datetime.now().isoformat(),
            "uploaded_by": token_data.user_id if token_data else None
        }
        save_rules_metadata()
        
        return {
            "message": "File uploaded successfully",
            "file_id": file_id,
            "filename": safe_filename,
            "size": file_size,
            "type": file.content_type,
            "category": file_category,
            "uploaded_at": _rules_metadata[file_id]["uploaded_at"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


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
    """Get a specific rules file by ID. Returns content for text files, download URL for binary files."""
    from fastapi.responses import FileResponse
    
    load_rules_metadata()
    if file_id not in _rules_metadata:
        raise HTTPException(status_code=404, detail="Rules file not found")
    
    metadata = _rules_metadata[file_id]
    file_path = RULES_DIR / metadata["filename"]
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Rules file not found on disk")
    
    # For text files, return content as JSON
    if metadata.get("is_text", False):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {
            "file_id": file_id,
            "metadata": metadata,
            "content": content
        }
    else:
        # For binary files (PDFs, images), return file for download/viewing
        return FileResponse(
            path=str(file_path),
            filename=metadata["filename"],
            media_type=metadata["type"]
        )


@app.get("/rules/{file_id}/download")
async def download_rule(
    file_id: str,
    token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None
):
    """Download a rules file (useful for PDFs and images)."""
    from fastapi.responses import FileResponse
    
    load_rules_metadata()
    if file_id not in _rules_metadata:
        raise HTTPException(status_code=404, detail="Rules file not found")
    
    metadata = _rules_metadata[file_id]
    file_path = RULES_DIR / metadata["filename"]
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Rules file not found on disk")
    
    return FileResponse(
        path=str(file_path),
        filename=metadata["original_filename"] or metadata["filename"],
        media_type=metadata["type"]
    )


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

