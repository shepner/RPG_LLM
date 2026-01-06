"""Redis caching layer."""

import json
import pickle
from typing import Optional, Any, Union
try:
    import redis.asyncio as redis
except ImportError:
    import redis
    # Fallback for sync redis if async not available
from datetime import timedelta


class RedisCache:
    """Redis-based caching layer."""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        default_ttl: int = 3600,
        decode_responses: bool = False
    ):
        """
        Initialize Redis cache.
        
        Args:
            redis_url: Redis connection URL
            default_ttl: Default time-to-live in seconds
            decode_responses: Whether to decode responses as strings
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.decode_responses = decode_responses
        self._client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis."""
        if not self._client:
            self._client = await redis.from_url(
                self.redis_url,
                decode_responses=self.decode_responses
            )
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if not self._client:
            await self.connect()
        
        try:
            value = await self._client.get(key)
            if value is None:
                return None
            
            # Try to deserialize JSON, fall back to pickle
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return pickle.loads(value)
        except Exception:
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
            
        Returns:
            True if successful
        """
        if not self._client:
            await self.connect()
        
        try:
            # Try to serialize as JSON, fall back to pickle
            try:
                serialized = json.dumps(value)
            except (TypeError, ValueError):
                serialized = pickle.dumps(value)
            
            ttl = ttl or self.default_ttl
            await self._client.setex(key, ttl, serialized)
            return True
        except Exception:
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key was deleted
        """
        if not self._client:
            await self.connect()
        
        try:
            result = await self._client.delete(key)
            return result > 0
        except Exception:
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists
        """
        if not self._client:
            await self.connect()
        
        try:
            result = await self._client.exists(key)
            return result > 0
        except Exception:
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration for a key.
        
        Args:
            key: Cache key
            ttl: Time-to-live in seconds
            
        Returns:
            True if expiration was set
        """
        if not self._client:
            await self.connect()
        
        try:
            return await self._client.expire(key, ttl)
        except Exception:
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching a pattern.
        
        Args:
            pattern: Redis key pattern (e.g., "cache:*")
            
        Returns:
            Number of keys deleted
        """
        if not self._client:
            await self.connect()
        
        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await self._client.delete(*keys)
            return 0
        except Exception:
            return 0
    
    async def get_or_set(
        self,
        key: str,
        callable_func,
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get value from cache, or compute and cache if not found.
        
        Args:
            key: Cache key
            callable_func: Async function to compute value if not cached
            ttl: Time-to-live in seconds
            
        Returns:
            Cached or computed value
        """
        value = await self.get(key)
        if value is not None:
            return value
        
        # Compute value
        if callable(callable_func):
            value = await callable_func() if hasattr(callable_func, '__call__') else callable_func
        else:
            value = callable_func
        
        # Cache it
        await self.set(key, value, ttl)
        return value

