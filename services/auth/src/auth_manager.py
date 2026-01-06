"""Authentication and authorization manager."""

import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, DateTime, Enum as SQLEnum
import sqlalchemy as sa

from .models import User, UserRole, TokenData, BeingOwnership

Base = declarative_base()


class UserDB(Base):
    """User database model."""
    
    __tablename__ = "users"
    
    user_id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.PLAYER)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class BeingOwnershipDB(Base):
    """Being ownership database model."""
    
    __tablename__ = "being_ownership"
    
    being_id = Column(String, primary_key=True)
    owner_id = Column(String, nullable=False)
    assigned_user_ids = Column(String)  # JSON string
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class AuthManager:
    """Manages authentication and authorization."""
    
    def __init__(
        self,
        database_url: str,
        jwt_secret_key: str,
        jwt_algorithm: str = "HS256",
        jwt_expiration_hours: int = 24
    ):
        """
        Initialize auth manager.
        
        Args:
            database_url: Database connection URL
            jwt_secret_key: Secret key for JWT signing
            jwt_algorithm: JWT algorithm
            jwt_expiration_hours: Token expiration in hours
        """
        self.database_url = database_url
        self.jwt_secret_key = jwt_secret_key
        self.jwt_algorithm = jwt_algorithm
        self.jwt_expiration_hours = jwt_expiration_hours
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # Initialize database
        self.engine = create_async_engine(database_url, echo=False)
        self.SessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def init_db(self):
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return self.pwd_context.hash(password)
    
    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.PLAYER
    ) -> User:
        """Create a new user."""
        import uuid
        
        async with self.SessionLocal() as session:
            # Check if user exists
            result = await session.execute(
                sa.select(UserDB).where(
                    (UserDB.username == username) | (UserDB.email == email)
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                raise ValueError("User already exists")
            
            # Create user
            user_id = str(uuid.uuid4())
            password_hash = self.get_password_hash(password)
            
            user_db = UserDB(
                user_id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
                role=role
            )
            
            session.add(user_db)
            await session.commit()
            await session.refresh(user_db)
            
            return User(
                user_id=user_db.user_id,
                username=user_db.username,
                email=user_db.email,
                role=user_db.role,
                created_at=user_db.created_at,
                updated_at=user_db.updated_at
            )
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(UserDB).where(UserDB.username == username)
            )
            user_db = result.scalar_one_or_none()
            
            if not user_db:
                return None
            
            if not self.verify_password(password, user_db.password_hash):
                return None
            
            return User(
                user_id=user_db.user_id,
                username=user_db.username,
                email=user_db.email,
                role=user_db.role,
                created_at=user_db.created_at,
                updated_at=user_db.updated_at
            )
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(UserDB).where(UserDB.user_id == user_id)
            )
            user_db = result.scalar_one_or_none()
            
            if not user_db:
                return None
            
            return User(
                user_id=user_db.user_id,
                username=user_db.username,
                email=user_db.email,
                role=user_db.role,
                created_at=user_db.created_at,
                updated_at=user_db.updated_at
            )
    
    def create_access_token(self, user: User) -> str:
        """Create JWT access token."""
        expire = datetime.utcnow() + timedelta(hours=self.jwt_expiration_hours)
        to_encode = {
            "sub": user.user_id,
            "username": user.username,
            "role": user.role.value,
            "exp": expire
        }
        encoded_jwt = jwt.encode(to_encode, self.jwt_secret_key, algorithm=self.jwt_algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.jwt_secret_key, algorithms=[self.jwt_algorithm])
            user_id: str = payload.get("sub")
            username: str = payload.get("username")
            role: str = payload.get("role")
            
            if user_id is None:
                return None
            
            return TokenData(
                user_id=user_id,
                username=username,
                role=UserRole(role) if role else None
            )
        except JWTError:
            return None
    
    async def get_being_ownership(self, being_id: str) -> Optional[BeingOwnership]:
        """Get being ownership information."""
        import json
        
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(BeingOwnershipDB).where(BeingOwnershipDB.being_id == being_id)
            )
            ownership_db = result.scalar_one_or_none()
            
            if not ownership_db:
                return None
            
            assigned_ids = json.loads(ownership_db.assigned_user_ids) if ownership_db.assigned_user_ids else []
            
            return BeingOwnership(
                being_id=ownership_db.being_id,
                owner_id=ownership_db.owner_id,
                assigned_user_ids=assigned_ids,
                created_by=ownership_db.created_by,
                created_at=ownership_db.created_at
            )
    
    async def set_being_ownership(
        self,
        being_id: str,
        owner_id: str,
        created_by: str,
        assigned_user_ids: Optional[list] = None
    ):
        """Set being ownership."""
        import json
        
        async with self.SessionLocal() as session:
            ownership_db = BeingOwnershipDB(
                being_id=being_id,
                owner_id=owner_id,
                assigned_user_ids=json.dumps(assigned_user_ids or []),
                created_by=created_by
            )
            session.add(ownership_db)
            await session.commit()

