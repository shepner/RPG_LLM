"""Authentication service API."""

import os
import logging
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from .auth_manager import AuthManager
from .models import User, UserCreate, UserLogin, Token, BeingOwnership, BeingAssignment
from .middleware import require_auth, require_gm, require_being_access, get_current_user
from .models import TokenData

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="Authentication Service")

# Add CORS middleware to allow web interface to access this service
# IMPORTANT: Must be added before routes are defined
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081", "http://127.0.0.1:8081", "*"],  # Allow all for development
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

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
        logger.info(f"Registering new user: {user_data.username}")
        user = await auth_manager.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            role=user_data.role
        )
        logger.info(f"User registered successfully: {user.user_id}")
        return user
    except ValueError as e:
        logger.warning(f"Registration failed for {user_data.username}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """Authenticate user and return JWT token."""
    logger.info(f"Login attempt for user: {credentials.username}")
    user = await auth_manager.authenticate_user(credentials.username, credentials.password)
    if not user:
        logger.warning(f"Failed login attempt for: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(f"Successful login for user: {user.user_id}")
    access_token = auth_manager.create_access_token(user)
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=auth_manager.jwt_expiration_hours * 3600
    )


@app.get("/me", response_model=User)
async def get_current_user_info(token_data: TokenData = Depends(require_auth)):
    """Get current user information."""
    try:
        user = await auth_manager.get_user(token_data.user_id)
        if not user:
            logger.warning(f"User not found: {token_data.user_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/users", response_model=List[User])
async def list_users(token_data: TokenData = Depends(require_gm)):
    """List all users (GM only)."""
    import sqlalchemy as sa
    from .auth_manager import UserDB
    
    async with auth_manager.SessionLocal() as session:
        result = await session.execute(sa.select(UserDB))
        users_db = result.scalars().all()
        
        return [
            User(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                role=user.role,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
            for user in users_db
        ]


@app.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: str,
    token_data: TokenData = Depends(require_gm)
):
    """Update user role (GM only)."""
    import sqlalchemy as sa
    from .models import UserRole
    from .auth_manager import UserDB
    
    try:
        user_role = UserRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    
    async with auth_manager.SessionLocal() as session:
        result = await session.execute(
            sa.select(UserDB).where(UserDB.user_id == user_id)
        )
        user_db = result.scalar_one_or_none()
        
        if not user_db:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_db.role = user_role
        await session.commit()
        
        return {"message": "Role updated", "user_id": user_id, "new_role": role}


@app.post("/users/fix-first-user")
async def fix_first_user(token_data: TokenData = Depends(require_auth)):
    """Fix first user to be GM if no GM exists (self-service)."""
    import sqlalchemy as sa
    from .models import UserRole
    from .auth_manager import UserDB
    
    async with auth_manager.SessionLocal() as session:
        # Check if any GM exists (case-insensitive check)
        # Use SQLAlchemy's case-insensitive comparison
        from sqlalchemy import func
        gm_result = await session.execute(
            sa.select(UserDB).where(
                func.lower(UserDB.role) == UserRole.GM.value.lower()
            )
        )
        gms = gm_result.scalars().all()
        
        # If no GM exists, make the requesting user GM
        if len(gms) == 0:
            result = await session.execute(
                sa.select(UserDB).where(UserDB.user_id == token_data.user_id)
            )
            user_db = result.scalar_one_or_none()
            if user_db:
                user_db.role = UserRole.GM
                await session.commit()
                logger.info(f"Fixed first user - assigned GM role to: {user_db.username}")
                return {"message": "You have been assigned GM role (no GM existed)", "user_id": token_data.user_id, "role": "gm"}
            else:
                raise HTTPException(status_code=404, detail="User not found")
        else:
            raise HTTPException(status_code=403, detail="A GM already exists. Please ask them to upgrade your account.")


@app.get("/beings/owned", response_model=List[str])
async def get_owned_beings(token_data: TokenData = Depends(require_auth)):
    """Get beings owned by current user."""
    import sqlalchemy as sa
    from .auth_manager import BeingOwnershipDB
    
    async with auth_manager.SessionLocal() as session:
        result = await session.execute(
            sa.select(BeingOwnershipDB).where(
                BeingOwnershipDB.owner_id == token_data.user_id
            )
        )
        ownerships = result.scalars().all()
        
        return [ownership.being_id for ownership in ownerships]


@app.get("/beings/assigned", response_model=List[str])
async def get_assigned_beings(token_data: TokenData = Depends(require_auth)):
    """Get beings assigned to current user."""
    import json
    import sqlalchemy as sa
    from .auth_manager import BeingOwnershipDB
    
    async with auth_manager.SessionLocal() as session:
        result = await session.execute(
            sa.select(BeingOwnershipDB)
        )
        ownerships = result.scalars().all()
        
        assigned_beings = []
        for ownership in ownerships:
            assigned_ids = json.loads(ownership.assigned_user_ids or "[]")
            if token_data.user_id in assigned_ids:
                assigned_beings.append(ownership.being_id)
        
        return assigned_beings


@app.post("/beings/{being_id}/assign")
async def assign_being(
    being_id: str,
    user_id: str,
    token_data: TokenData = Depends(require_gm)
):
    """Assign being to user (GM only)."""
    import json
    import sqlalchemy as sa
    from .auth_manager import UserDB, BeingOwnershipDB
    
    # Verify user exists
    async with auth_manager.SessionLocal() as session:
        user_result = await session.execute(
            sa.select(UserDB).where(UserDB.user_id == user_id)
        )
        if not user_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get or create ownership
        ownership_result = await session.execute(
            sa.select(BeingOwnershipDB).where(
                BeingOwnershipDB.being_id == being_id
            )
        )
        ownership_db = ownership_result.scalar_one_or_none()
        
        if not ownership_db:
            raise HTTPException(status_code=404, detail="Being not found")
        
        # Add user to assigned list
        assigned_ids = json.loads(ownership_db.assigned_user_ids or "[]")
        if user_id not in assigned_ids:
            assigned_ids.append(user_id)
            ownership_db.assigned_user_ids = json.dumps(assigned_ids)
            await session.commit()
        
        return {"message": "Being assigned", "being_id": being_id, "user_id": user_id}


@app.delete("/beings/{being_id}/assign")
async def unassign_being(
    being_id: str,
    user_id: str,
    token_data: TokenData = Depends(require_gm)
):
    """Unassign being from user (GM only)."""
    import json
    import sqlalchemy as sa
    from .auth_manager import BeingOwnershipDB
    
    async with auth_manager.SessionLocal() as session:
        ownership_result = await session.execute(
            sa.select(BeingOwnershipDB).where(
                BeingOwnershipDB.being_id == being_id
            )
        )
        ownership_db = ownership_result.scalar_one_or_none()
        
        if not ownership_db:
            raise HTTPException(status_code=404, detail="Being not found")
        
        # Remove user from assigned list
        assigned_ids = json.loads(ownership_db.assigned_user_ids or "[]")
        if user_id in assigned_ids:
            assigned_ids.remove(user_id)
            ownership_db.assigned_user_ids = json.dumps(assigned_ids)
            await session.commit()
        
        return {"message": "Being unassigned", "being_id": being_id, "user_id": user_id}


@app.post("/beings/{being_id}/ownership")
async def create_being_ownership(
    being_id: str,
    ownership_data: BeingOwnershipCreate,
    token_data: TokenData = Depends(require_auth)
):
    """Create an ownership record for a being."""
    from .models import BeingOwnershipCreate
    try:
        await auth_manager.set_being_ownership(
            being_id=being_id,
            owner_id=ownership_data.owner_id,
            created_by=token_data.user_id,
            assigned_user_ids=ownership_data.assigned_user_ids,
            name=ownership_data.name
        )
        return {"message": "Being ownership created successfully", "being_id": being_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create being ownership: {str(e)}")


@app.delete("/beings/{being_id}/ownership")
async def delete_being_ownership(
    being_id: str,
    token_data: TokenData = Depends(require_auth)
):
    """Delete an ownership record for a being."""
    import sqlalchemy as sa
    from .auth_manager import BeingOwnershipDB
    from .models import UserRole
    
    async with auth_manager.SessionLocal() as session:
        # Get ownership record
        result = await session.execute(
            sa.select(BeingOwnershipDB).where(
                BeingOwnershipDB.being_id == being_id
            )
        )
        ownership_db = result.scalar_one_or_none()
        
        if not ownership_db:
            raise HTTPException(status_code=404, detail="Being ownership not found")
        
        # Check permission: owner or GM can delete
        is_owner = ownership_db.owner_id == token_data.user_id
        is_gm = token_data.role == UserRole.GM
        
        if not (is_owner or is_gm):
            raise HTTPException(status_code=403, detail="You do not have permission to delete this ownership record")
        
        # Delete the ownership record
        await session.delete(ownership_db)
        await session.commit()
        
        logger.info(f"Being ownership deleted for {being_id} by {token_data.username}")
        return {"message": "Being ownership deleted successfully", "being_id": being_id}


@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    token_data: TokenData = Depends(require_gm)
):
    """Delete a user account (GM only)."""
    import sqlalchemy as sa
    from .auth_manager import UserDB, BeingOwnershipDB
    
    async with auth_manager.SessionLocal() as session:
        # Check if user exists
        result = await session.execute(
            sa.select(UserDB).where(UserDB.user_id == user_id)
        )
        user_db = result.scalar_one_or_none()
        
        if not user_db:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prevent deleting yourself
        if user_db.user_id == token_data.user_id:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
        # Check if this is the last GM
        if user_db.role == "gm":
            gm_count_result = await session.execute(
                sa.select(UserDB).where(UserDB.role == "gm")
            )
            gm_count = len(gm_count_result.scalars().all())
            if gm_count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete the last GM. Please assign GM role to another user first."
                )
        
        # Remove user from being assignments
        ownerships_result = await session.execute(
            sa.select(BeingOwnershipDB)
        )
        ownerships = ownerships_result.scalars().all()
        
        import json
        for ownership in ownerships:
            assigned_ids = json.loads(ownership.assigned_user_ids or "[]")
            if user_id in assigned_ids:
                assigned_ids.remove(user_id)
                ownership.assigned_user_ids = json.dumps(assigned_ids)
        
        # Delete the user
        await session.delete(user_db)
        await session.commit()
        
        logger.info(f"User {user_db.username} (ID: {user_db.user_id}) deleted by GM {token_data.username}")
        return {"message": "User deleted successfully", "user_id": user_id, "username": user_db.username}


@app.get("/users/{user_id}/characters")
async def get_user_characters(
    user_id: str,
    token_data: TokenData = Depends(require_gm)
):
    """Get all characters owned or assigned to a user (GM only)."""
    import sqlalchemy as sa
    import json
    from .auth_manager import BeingOwnershipDB, UserDB
    
    async with auth_manager.SessionLocal() as session:
        # Get all beings owned by this user
        owned_result = await session.execute(
            sa.select(BeingOwnershipDB).where(BeingOwnershipDB.owner_id == user_id)
        )
        owned_beings = owned_result.scalars().all()
        
        # Get all beings assigned to this user
        all_ownerships_result = await session.execute(sa.select(BeingOwnershipDB))
        all_ownerships = all_ownerships_result.scalars().all()
        
        assigned_beings = []
        for ownership in all_ownerships:
            assigned_ids = json.loads(ownership.assigned_user_ids or "[]")
            if user_id in assigned_ids:
                assigned_beings.append(ownership)
        
        # Get owner usernames for display
        owner_ids = set([b.owner_id for b in owned_beings] + [b.owner_id for b in assigned_beings])
        owner_map = {}
        if owner_ids:
            owners_result = await session.execute(
                sa.select(UserDB).where(UserDB.user_id.in_(owner_ids))
            )
            for owner in owners_result.scalars().all():
                owner_map[owner.user_id] = owner.username
        
        return {
            "owned": [{"being_id": b.being_id, "owner_id": b.owner_id, "owner_username": owner_map.get(b.owner_id, "Unknown")} for b in owned_beings],
            "assigned": [{"being_id": b.being_id, "owner_id": b.owner_id, "owner_username": owner_map.get(b.owner_id, "Unknown")} for b in assigned_beings]
        }


@app.get("/beings/list")
async def list_all_beings(
    token_data: TokenData = Depends(require_gm)
):
    """List all beings/characters with ownership info (GM only)."""
    import sqlalchemy as sa
    import json
    from .auth_manager import BeingOwnershipDB, UserDB
    
    async with auth_manager.SessionLocal() as session:
        # Get all beings
        all_ownerships_result = await session.execute(sa.select(BeingOwnershipDB))
        all_ownerships = all_ownerships_result.scalars().all()
        
        # Get all owner usernames
        owner_ids = set([o.owner_id for o in all_ownerships])
        owner_map = {}
        if owner_ids:
            owners_result = await session.execute(
                sa.select(UserDB).where(UserDB.user_id.in_(owner_ids))
            )
            for owner in owners_result.scalars().all():
                owner_map[owner.user_id] = owner.username
        
        # Build character list
        characters = []
        for ownership in all_ownerships:
            assigned_ids = json.loads(ownership.assigned_user_ids or "[]")
            characters.append({
                "being_id": ownership.being_id,
                "owner_id": ownership.owner_id,
                "owner_username": owner_map.get(ownership.owner_id, "Unknown"),
                "assigned_user_ids": assigned_ids,
                "name": f"Character {ownership.being_id[:8]}"  # Placeholder - could be enhanced with actual character data
            })
        
        return {"characters": characters}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

