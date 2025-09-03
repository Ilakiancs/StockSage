"""
Service lifecycle management and graceful shutdown handling
"""

import signal
import asyncio
import logging
import os
import time
import threading
from typing import Callable, List, Optional
from contextlib import asynccontextmanager
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ServiceManager:
    """Manages service lifecycle and graceful shutdown"""
    
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.cleanup_handlers: List[Callable] = []
        self.background_tasks: List[asyncio.Task] = []
        self.is_shutting_down = False
        self.startup_time = None
        self.state_file = "service_state.json"
        
    def add_cleanup_handler(self, handler: Callable):
        """Add a cleanup handler to be called during shutdown"""
        self.cleanup_handlers.append(handler)
        logger.debug(f"Added cleanup handler: {handler.__name__}")
    
    def add_background_task(self, task: asyncio.Task):
        """Register a background task for lifecycle management"""
        self.background_tasks.append(task)
        logger.debug(f"Registered background task: {task.get_name()}")
    
    async def start(self):
        """Start the service and save startup state"""
        self.startup_time = datetime.now()
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        # Save startup state
        await self._save_service_state("starting")
        
        logger.info(f"Service started at {self.startup_time}")
        await self._save_service_state("running")
    
    async def shutdown(self):
        """Gracefully shutdown the service"""
        if self.is_shutting_down:
            logger.warning("Shutdown already in progress")
            return
            
        self.is_shutting_down = True
        logger.info("Starting graceful shutdown...")
        
        await self._save_service_state("shutting_down")
        
        # Set shutdown event
        self.shutdown_event.set()
        
        # Cancel background tasks
        await self._cancel_background_tasks()
        
        # Run cleanup handlers
        await self._run_cleanup_handlers()
        
        # Save final state
        await self._save_service_state("stopped")
        
        logger.info("Graceful shutdown completed")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        if os.name != 'nt':  # Unix-like systems
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGHUP, self._signal_handler)
        else:  # Windows
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received signal {signal_name}, initiating shutdown...")
        
        # Create a task to handle shutdown in the event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self.shutdown())
        else:
            asyncio.run(self.shutdown())
    
    async def _cancel_background_tasks(self):
        """Cancel all registered background tasks"""
        logger.info(f"Cancelling {len(self.background_tasks)} background tasks...")
        
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    logger.debug(f"Task {task.get_name()} cancelled")
                except Exception as e:
                    logger.error(f"Error cancelling task {task.get_name()}: {e}")
    
    async def _run_cleanup_handlers(self):
        """Run all registered cleanup handlers"""
        logger.info(f"Running {len(self.cleanup_handlers)} cleanup handlers...")
        
        for handler in self.cleanup_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
                logger.debug(f"Cleanup handler {handler.__name__} completed")
            except Exception as e:
                logger.error(f"Error in cleanup handler {handler.__name__}: {e}")
    
    async def _save_service_state(self, state: str):
        """Save current service state to file"""
        try:
            state_data = {
                "state": state,
                "timestamp": datetime.now().isoformat(),
                "startup_time": self.startup_time.isoformat() if self.startup_time else None,
                "pid": os.getpid()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save service state: {e}")
    
    async def get_service_state(self):
        """Get current service state"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read service state: {e}")
        
        return {"state": "unknown", "timestamp": datetime.now().isoformat()}
    
    def is_running(self) -> bool:
        """Check if service is currently running"""
        return not self.is_shutting_down and not self.shutdown_event.is_set()


class PersistentState:
    """Manages persistent state across service restarts"""
    
    def __init__(self, state_file: str = "persistent_state.json"):
        self.state_file = state_file
        self.state = {}
        self.load_state()
    
    def load_state(self):
        """Load state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                logger.info(f"Loaded persistent state: {len(self.state)} entries")
            else:
                self.state = {}
                logger.info("No persistent state file found, starting fresh")
        except Exception as e:
            logger.error(f"Failed to load persistent state: {e}")
            self.state = {}
    
    def save_state(self):
        """Save current state to file"""
        try:
            # Create backup
            if os.path.exists(self.state_file):
                backup_file = f"{self.state_file}.backup"
                os.rename(self.state_file, backup_file)
            
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
                
            logger.debug("Persistent state saved")
            
        except Exception as e:
            logger.error(f"Failed to save persistent state: {e}")
            # Restore backup if save failed
            backup_file = f"{self.state_file}.backup"
            if os.path.exists(backup_file):
                os.rename(backup_file, self.state_file)
    
    def set(self, key: str, value):
        """Set a state value"""
        self.state[key] = value
        self.save_state()
    
    def get(self, key: str, default=None):
        """Get a state value"""
        return self.state.get(key, default)
    
    def delete(self, key: str):
        """Delete a state value"""
        if key in self.state:
            del self.state[key]
            self.save_state()
    
    def clear(self):
        """Clear all state"""
        self.state = {}
        self.save_state()


class SchedulerManager:
    """Manages background scheduler with graceful shutdown"""
    
    def __init__(self):
        self.scheduler = None
        self.is_running = False
    
    def start(self):
        """Start the background scheduler"""
        if self.scheduler is None:
            from apscheduler.schedulers.background import BackgroundScheduler
            self.scheduler = BackgroundScheduler()
        
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("Background scheduler started")
    
    def stop(self):
        """Stop the background scheduler gracefully"""
        if self.scheduler and self.is_running:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Background scheduler stopped")
    
    def add_job(self, func, trigger, **kwargs):
        """Add a job to the scheduler"""
        if self.scheduler:
            return self.scheduler.add_job(func, trigger, **kwargs)
        else:
            logger.error("Scheduler not initialized")


class HealthChecker:
    """Monitors service health and handles recovery"""
    
    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        self.health_checks = {}
        self.last_health_check = None
        self.health_status = "unknown"
    
    def register_health_check(self, name: str, check_func: Callable):
        """Register a health check function"""
        self.health_checks[name] = check_func
        logger.debug(f"Registered health check: {name}")
    
    async def run_health_checks(self) -> dict:
        """Run all registered health checks"""
        results = {}
        overall_healthy = True
        
        for name, check_func in self.health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "timestamp": datetime.now().isoformat()
                }
                
                if not result:
                    overall_healthy = False
                    
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                overall_healthy = False
                logger.error(f"Health check {name} failed: {e}")
        
        self.health_status = "healthy" if overall_healthy else "unhealthy"
        self.last_health_check = datetime.now()
        
        return {
            "overall_status": self.health_status,
            "timestamp": self.last_health_check.isoformat(),
            "checks": results
        }


# Global instances
service_manager = ServiceManager()
persistent_state = PersistentState()
scheduler_manager = SchedulerManager()
health_checker = HealthChecker(service_manager)


@asynccontextmanager
async def lifespan(app):
    """FastAPI lifespan context manager for startup/shutdown"""
    # Startup
    logger.info("Starting application...")
    
    await service_manager.start()
    
    # Register cleanup handlers
    service_manager.add_cleanup_handler(cleanup_scheduler)
    service_manager.add_cleanup_handler(cleanup_resources)
    
    # Start scheduler
    scheduler_manager.start()
    
    # Register health checks
    health_checker.register_health_check("scheduler", lambda: scheduler_manager.is_running)
    health_checker.register_health_check("state_file", check_state_file_accessible)
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await service_manager.shutdown()


def cleanup_scheduler():
    """Cleanup scheduler on shutdown"""
    scheduler_manager.stop()


def cleanup_resources():
    """Cleanup resources on shutdown"""
    try:
        # Save any pending state
        persistent_state.save_state()
        logger.info("Resources cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up resources: {e}")


def check_state_file_accessible() -> bool:
    """Health check for state file accessibility"""
    try:
        # Try to read and write state file
        test_key = "_health_check"
        persistent_state.set(test_key, datetime.now().isoformat())
        persistent_state.delete(test_key)
        return True
    except Exception:
        return False


async def monitor_service_health():
    """Background task to monitor service health"""
    while service_manager.is_running():
        try:
            health_status = await health_checker.run_health_checks()
            
            if health_status["overall_status"] == "unhealthy":
                logger.warning("Service health check failed")
                # Could trigger alerts or recovery actions here
            
            await asyncio.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Error in health monitoring: {e}")
            await asyncio.sleep(60)


def get_service_manager() -> ServiceManager:
    """Get the global service manager instance"""
    return service_manager


def get_persistent_state() -> PersistentState:
    """Get the global persistent state instance"""
    return persistent_state


def get_scheduler_manager() -> SchedulerManager:
    """Get the global scheduler manager instance"""
    return scheduler_manager
