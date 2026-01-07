"""Rules engine service API."""

import os
import json
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .rule_resolver import RuleResolver
from .models import RollResult, Resolution
from .rules_parser import RulesParser
from .rules_indexer import RulesIndexer

# Import auth middleware (optional)
try:
    import sys
    sys.path.insert(0, '/app/services/auth/src')
    from middleware import require_auth, require_gm, get_current_user, TokenData
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    def require_auth():
        return None
    def require_gm():
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

# Initialize rules parser and indexer
RULES_DIR = Path(os.getenv("RULES_DIR", "./RPG_LLM_DATA/rules"))
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./RPG_LLM_DATA/vector_stores/rules")
RULES_DIR.mkdir(parents=True, exist_ok=True)
RULES_METADATA_FILE = RULES_DIR / "metadata.json"

# Initialize components
try:
    rules_parser = RulesParser(RULES_DIR)
    rules_indexer = RulesIndexer(CHROMA_DB_PATH, RULES_DIR)
    resolver = RuleResolver(rules_indexer=rules_indexer)
except Exception as e:
    print(f"Warning: Error initializing rules components: {e}")
    rules_parser = None
    rules_indexer = None
    resolver = RuleResolver()

# In-memory cache of rules metadata
_rules_metadata: Dict[str, Dict[str, Any]] = {}

def load_rules_metadata():
    """Load rules metadata from file."""
    global _rules_metadata
    if RULES_METADATA_FILE.exists():
        try:
            with open(RULES_METADATA_FILE, 'r') as f:
                _rules_metadata = json.load(f)
            # Verify files still exist on disk and remove from metadata if missing
            for file_id, metadata in list(_rules_metadata.items()):
                file_path = RULES_DIR / metadata.get("filename", "")
                if not file_path.exists():
                    print(f"Warning: File {metadata.get('filename')} not found on disk, removing from metadata")
                    del _rules_metadata[file_id]
                    save_rules_metadata()
        except Exception as e:
            print(f"Error loading rules metadata: {e}")
            _rules_metadata = {}
    else:
        _rules_metadata = {}
    
    # Also scan directory for files that might not be in metadata (recovery)
    if RULES_DIR.exists():
        for file_path in RULES_DIR.iterdir():
            if file_path.is_file() and file_path.name != "metadata.json":
                # Check if this file is in metadata
                found = False
                for metadata in _rules_metadata.values():
                    if metadata.get("filename") == file_path.name:
                        found = True
                        break
                
                if not found:
                    # Add orphaned file to metadata
                    print(f"Found orphaned file: {file_path.name}, adding to metadata")
                    file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]
                    file_ext = file_path.suffix.lower()
                    is_text = file_ext in {'.md', '.markdown', '.yaml', '.yml', '.json', '.txt'}
                    is_image = file_ext in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}
                    is_pdf = file_ext == '.pdf'
                    is_epub = file_ext == '.epub'
                    file_category = "text" if is_text else ("image" if is_image else "document")
                    
                    _rules_metadata[file_hash] = {
                        "file_id": file_hash,
                        "filename": file_path.name,
                        "original_filename": file_path.name,
                        "size": file_path.stat().st_size,
                        "type": "application/octet-stream",
                        "extension": file_ext,
                        "category": file_category,
                        "is_text": is_text,
                        "is_image": is_image,
                        "is_pdf": is_pdf,
                        "is_epub": is_epub,
                        "is_document": file_ext in {'.pdf', '.epub'},
                        "uploaded_at": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                        "uploaded_by": None,
                        "indexing_status": "pending",
                        "indexed_at": None,
                        "indexing_error": None
                    }
                    save_rules_metadata()

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


class ResolveRequest(BaseModel):
    """Request model for resolve endpoint."""
    action: str
    context: Optional[Dict[str, Any]] = None

@app.post("/resolve", response_model=Resolution)
async def resolve_action(request: ResolveRequest):
    """Resolve an action using rules and LLM."""
    result = await resolver.resolve_action(request.action, request.context)
    return result


@app.post("/rules/upload")
async def upload_rules(
    file: UploadFile = File(...), 
    token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None,
    background_tasks: BackgroundTasks = BackgroundTasks()
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
            "uploaded_by": token_data.user_id if token_data else None,
            "indexing_status": "pending",  # pending, indexing, indexed, failed
            "indexed_at": None,
            "indexing_error": None,
            "indexing_progress": None  # {current, total, percentage, stage}
        }
        save_rules_metadata()
        
        # Extract and index content for LLM use (async, non-blocking)
        if rules_parser and rules_indexer:
            try:
                extracted = rules_parser.extract_content(file_path, file_ext)
                if extracted.get("content"):
                    # Index in background task (don't block upload response)
                    if background_tasks:
                        background_tasks.add_task(
                            _index_file_background,
                            rules_indexer,
                            file_id,
                            safe_filename,
                            extracted["content"],
                            {
                                "file_id": file_id,
                                "filename": safe_filename,
                                "original_filename": file.filename,
                                "type": file_category,
                                "extension": file_ext
                            }
                        )
            except Exception as e:
                print(f"Warning: Failed to index file {safe_filename}: {e}")
                # Don't fail the upload if indexing fails
        
        return {
            "message": "File uploaded successfully",
            "file_id": file_id,
            "filename": safe_filename,
            "size": file_size,
            "type": file.content_type,
            "category": file_category,
            "uploaded_at": _rules_metadata[file_id]["uploaded_at"],
            "indexed": True
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@app.get("/rules/list")
async def list_rules(token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None):
    """List all uploaded rules files."""
    load_rules_metadata()  # Refresh metadata
    
    # Check indexing status for files that should be indexed
    if rules_indexer:
        try:
            indexed_files = set(rules_indexer.get_all_indexed_files())
            for file_id, metadata in _rules_metadata.items():
                # Only check indexing for files that can be indexed (text, PDF, EPUB)
                if metadata.get("is_text") or metadata.get("is_pdf") or metadata.get("is_epub"):
                    if file_id in indexed_files:
                        if metadata.get("indexing_status") != "indexed":
                            metadata["indexing_status"] = "indexed"
                            if not metadata.get("indexed_at"):
                                metadata["indexed_at"] = datetime.now().isoformat()
                    elif metadata.get("indexing_status") not in ["indexing", "failed"]:
                        # If not indexed and not currently indexing/failed, mark as pending
                        if not metadata.get("indexing_status"):
                            metadata["indexing_status"] = "pending"
            save_rules_metadata()
        except Exception as e:
            print(f"Warning: Error checking indexing status: {e}")
    
    # Include indexing progress in response
    rules_list = []
    for file_id, metadata in _rules_metadata.items():
        rule_data = metadata.copy()
        if "indexing_progress" in metadata:
            rule_data["indexing_progress"] = metadata["indexing_progress"]
        rules_list.append(rule_data)
    
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
    token_data: Optional[TokenData] = Depends(require_gm) if AUTH_AVAILABLE else None
):
    """Delete a rules file from disk, index, and metadata (GM only)."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="GM role required to delete rules")
    
    load_rules_metadata()
    if file_id not in _rules_metadata:
        raise HTTPException(status_code=404, detail="Rules file not found")
    
    metadata = _rules_metadata[file_id]
    file_path = RULES_DIR / metadata["filename"]
    
    deleted_items = []
    
    # Delete file from disk
    if file_path.exists():
        try:
            file_path.unlink()
            deleted_items.append("file")
        except Exception as e:
            print(f"Warning: Failed to delete file from disk: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete file from disk: {str(e)}")
    
    # Remove from index
    if rules_indexer:
        try:
            rules_indexer.delete_file_index(file_id)
            deleted_items.append("index")
        except Exception as e:
            print(f"Warning: Failed to remove file from index: {e}")
            # Don't fail the delete if index removal fails, but log it
    
    # Remove from metadata
    try:
        del _rules_metadata[file_id]
        save_rules_metadata()
        deleted_items.append("metadata")
    except Exception as e:
        print(f"Warning: Failed to remove file from metadata: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove file from metadata: {str(e)}")
    
    return {
        "message": "Rules file deleted successfully",
        "file_id": file_id,
        "filename": metadata.get("filename", "unknown"),
        "deleted_from": deleted_items
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}


# Background task helper
async def _index_file_background(
    indexer: RulesIndexer,
    file_id: str,
    filename: str,
    content: str,
    metadata: Dict[str, Any]
):
    """Background task to index a file with progress tracking."""
    
    def update_progress(current: int, total: int, stage: str):
        """Update progress in metadata."""
        load_rules_metadata()
        if file_id in _rules_metadata:
            _rules_metadata[file_id]["indexing_status"] = "indexing"
            _rules_metadata[file_id]["indexing_progress"] = {
                "current": current,
                "total": total,
                "percentage": int((current / total * 100)) if total > 0 else 0,
                "stage": stage
            }
            save_rules_metadata()
    
    try:
        # Update metadata to show indexing in progress
        load_rules_metadata()
        if file_id in _rules_metadata:
            _rules_metadata[file_id]["indexing_status"] = "indexing"
            _rules_metadata[file_id]["indexed_at"] = None
            _rules_metadata[file_id]["indexing_progress"] = {
                "current": 0,
                "total": 0,
                "percentage": 0,
                "stage": "starting"
            }
            save_rules_metadata()
        
        # Perform indexing with progress callback
        await indexer.index_file(file_id, filename, content, metadata, progress_callback=update_progress)
        
        # Update metadata to show indexing complete
        load_rules_metadata()
        if file_id in _rules_metadata:
            _rules_metadata[file_id]["indexing_status"] = "indexed"
            _rules_metadata[file_id]["indexed_at"] = datetime.now().isoformat()
            # Keep progress info but mark as complete
            if "indexing_progress" in _rules_metadata[file_id]:
                _rules_metadata[file_id]["indexing_progress"]["stage"] = "complete"
            save_rules_metadata()
    except Exception as e:
        print(f"Error in background indexing: {e}")
        # Update metadata to show indexing failed
        load_rules_metadata()
        if file_id in _rules_metadata:
            _rules_metadata[file_id]["indexing_status"] = "failed"
            _rules_metadata[file_id]["indexing_error"] = str(e)
            if "indexing_progress" in _rules_metadata[file_id]:
                _rules_metadata[file_id]["indexing_progress"]["stage"] = "error"
            save_rules_metadata()

