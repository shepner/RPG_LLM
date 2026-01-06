"""Authentication middleware."""

from typing import Optional, Callable
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .models import TokenData, UserRole


security = HTTPBearer()


def get_auth_manager():
    """Get auth manager instance (dependency)."""
    from .api import auth_manager
    return auth_manager


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

