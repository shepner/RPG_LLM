"""Authentication middleware."""

from typing import Optional, Callable
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Handle imports for both package and standalone usage
try:
    from .models import TokenData, UserRole
except ImportError:
    # When imported from outside the package, use absolute import
    import sys
    import os
    auth_src = os.path.dirname(__file__)
    if auth_src not in sys.path:
        sys.path.insert(0, auth_src)
    from models import TokenData, UserRole


security = HTTPBearer()


def get_auth_manager():
    """Get auth manager instance (dependency)."""
    # Try to import from api first (when running as part of auth service)
    try:
        from .api import auth_manager
        return auth_manager
    except ImportError:
        # If that fails, create a new instance directly
        # This handles the case when middleware is imported by other services
        import os
        import sys
        
        # Try relative import first
        try:
            from .auth_manager import AuthManager
        except ImportError:
            # If relative import fails, use absolute path
            auth_src_path = os.path.join(os.path.dirname(__file__))
            if auth_src_path not in sys.path:
                sys.path.insert(0, auth_src_path)
            from auth_manager import AuthManager
        
        # Create a singleton instance if it doesn't exist
        if not hasattr(get_auth_manager, '_instance'):
            get_auth_manager._instance = AuthManager(
                database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./RPG_LLM_DATA/databases/auth.db"),
                jwt_secret_key=os.getenv("JWT_SECRET_KEY", "change-me-in-production"),
                jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
                jwt_expiration_hours=int(os.getenv("JWT_EXPIRATION", "24").replace("h", ""))
            )
        return get_auth_manager._instance


async def get_current_user(
    request: Request,
    auth_manager = Depends(get_auth_manager)
) -> Optional[TokenData]:
    """
    Get current user from request token.
    
    Args:
        request: FastAPI request
        auth_manager: Auth manager instance
        
    Returns:
        TokenData if authenticated, None otherwise
    """
    credentials: Optional[HTTPAuthorizationCredentials] = await security(request)
    
    if not credentials:
        return None
    
    token_data = auth_manager.verify_token(credentials.credentials)
    return token_data


async def require_auth(
    request: Request,
    auth_manager = Depends(get_auth_manager)
) -> TokenData:
    """
    Require authentication (raises exception if not authenticated).
    
    Args:
        request: FastAPI request
        auth_manager: Auth manager instance
        
    Returns:
        TokenData
        
    Raises:
        HTTPException if not authenticated
    """
    token_data = await get_current_user(request, auth_manager)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_data


async def require_gm(
    request: Request,
    auth_manager = Depends(get_auth_manager)
) -> TokenData:
    """
    Require GM role.
    
    Args:
        request: FastAPI request
        auth_manager: Auth manager instance
        
    Returns:
        TokenData with GM role
        
    Raises:
        HTTPException if not GM
    """
    token_data = await require_auth(request, auth_manager)
    
    if token_data.role != UserRole.GM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GM role required"
        )
    
    return token_data


async def require_being_access(
    request: Request,
    being_id: str,
    auth_manager = Depends(get_auth_manager)
) -> TokenData:
    """
    Require access to a being (owner, assigned user, or GM).
    
    Args:
        request: FastAPI request
        auth_manager: Auth manager instance
        being_id: Being ID to check access for
        
    Returns:
        TokenData
        
    Raises:
        HTTPException if no access
    """
    token_data = await require_auth(request, auth_manager)
    
    # GM has access to all beings
    if token_data.role == UserRole.GM:
        return token_data
    
    # Check ownership
    ownership = await auth_manager.get_being_ownership(being_id)
    if not ownership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Being not found"
        )
    
    # Check if user is owner or assigned
    if token_data.user_id == ownership.owner_id:
        return token_data
    
    if token_data.user_id in ownership.assigned_user_ids:
        return token_data
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No access to this being"
    )

