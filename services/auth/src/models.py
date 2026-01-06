"""Authentication service models."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from enum import Enum


class UserRole(str, Enum):
    """User roles."""
    
    GM = "gm"
    PLAYER = "player"


class User(BaseModel):
    """User model."""
    
    user_id: str
    username: str
    email: EmailStr
    role: UserRole = UserRole.PLAYER
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class UserCreate(BaseModel):
    """User creation model."""
    
    username: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.PLAYER


class UserLogin(BaseModel):
    """User login model."""
    
    username: str
    password: str


class Token(BaseModel):
    """JWT token model."""
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Token data model."""
    
    user_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[UserRole] = None


class BeingOwnership(BaseModel):
    """Being ownership model."""
    
    being_id: str
    owner_id: str
    assigned_user_ids: List[str] = Field(default_factory=list)
    created_by: str
    created_at: datetime = Field(default_factory=datetime.now)


class BeingAssignment(BaseModel):
    """Being assignment model."""
    
    being_id: str
    user_id: str
    assigned_at: datetime = Field(default_factory=datetime.now)

