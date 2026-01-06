"""Authentication service API."""

import os
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .auth_manager import AuthManager, SessionLocal
from .models import User, UserCreate, UserLogin, Token, BeingOwnership, BeingAssignment
from .middleware import require_auth, require_gm, require_being_access, get_current_user
from .models import TokenData

app = FastAPI(title="Authentication Service")

# Initialize auth manager
auth_manager = AuthManager(
    database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./RPG_LLM_DATA/databases/auth.db"),
    jwt_secret_key=os.getenv("JWT_SECRET_KEY", "change-me-in-production"),
    jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
    jwt_expiration_hours=int(os.getenv("JWT_EXPIRATION", "24").replace("h", ""))
)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    await auth_manager.init_db()


@app.post("/register", response_model=User)
async def register(user_data: UserCreate):
    """Register a new user."""
    try:
        user = await auth_manager.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            role=user_data.role
        )
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """Authenticate user and return JWT token."""
    user = await auth_manager.authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_manager.create_access_token(user)
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=auth_manager.jwt_expiration_hours * 3600
    )


@app.get("/me", response_model=User)
async def get_current_user_info(token_data: TokenData = Depends(require_auth)):
    """Get current user information."""
    user = await auth_manager.get_user(token_data.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@app.get("/users", response_model=List[User])
async def list_users(token_data: TokenData = Depends(require_gm)):
    """List all users (GM only)."""
    # TODO: Implement user listing
    return []


@app.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: str,
    token_data: TokenData = Depends(require_gm)
):
    """Update user role (GM only)."""
    # TODO: Implement role update
    return {"message": "Role updated"}


@app.get("/beings/owned", response_model=List[str])
async def get_owned_beings(token_data: TokenData = Depends(require_auth)):
    """Get beings owned by current user."""
    # TODO: Implement owned beings query
    return []


@app.get("/beings/assigned", response_model=List[str])
async def get_assigned_beings(token_data: TokenData = Depends(require_auth)):
    """Get beings assigned to current user."""
    # TODO: Implement assigned beings query
    return []


@app.post("/beings/{being_id}/assign")
async def assign_being(
    being_id: str,
    user_id: str,
    token_data: TokenData = Depends(require_gm)
):
    """Assign being to user (GM only)."""
    # TODO: Implement being assignment
    return {"message": "Being assigned"}


@app.delete("/beings/{being_id}/assign")
async def unassign_being(
    being_id: str,
    user_id: str,
    token_data: TokenData = Depends(require_gm)
):
    """Unassign being from user (GM only)."""
    # TODO: Implement being unassignment
    return {"message": "Being unassigned"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

