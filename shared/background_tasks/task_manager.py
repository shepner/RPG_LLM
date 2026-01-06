"""Background task manager for async embedding generation and other tasks."""

import asyncio
from typing import Callable, Any, Optional
from fastapi import BackgroundTasks
from concurrent.futures import ThreadPoolExecutor


class BackgroundTaskManager:
    """Manages background tasks for async processing."""
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize background task manager.
        
        Args:
            max_workers: Maximum number of worker threads
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.background_tasks: Optional[BackgroundTasks] = None
    
    def set_background_tasks(self, background_tasks: BackgroundTasks):
        """Set FastAPI BackgroundTasks instance."""
        self.background_tasks = background_tasks
    
    def add_task(self, func: Callable, *args, **kwargs):
        """
        Add a background task.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        if self.background_tasks:
            self.background_tasks.add_task(func, *args, **kwargs)
        else:
            # Fallback: run in executor
            asyncio.create_task(self._run_in_executor(func, *args, **kwargs))
    
    async def _run_in_executor(self, func: Callable, *args, **kwargs):
        """Run function in thread pool executor."""
        loop = asyncio.get_event_loop()
        if asyncio.iscoroutinefunction(func):
            await func(*args, **kwargs)
        else:
            await loop.run_in_executor(self.executor, func, *args, **kwargs)
    
    async def run_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Run an async function in the background.
        
        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Task handle
        """
        return asyncio.create_task(func(*args, **kwargs))
    
    def shutdown(self):
        """Shutdown the task manager."""
        self.executor.shutdown(wait=True)

