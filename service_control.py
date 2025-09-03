#!/usr/bin/env python3
"""
Stock Tracker Service Startup Script
Handles graceful startup, restart, and shutdown
"""

import os
import sys
import time
import signal
import subprocess
import json
import logging
from pathlib import Path

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ServiceControl:
    """Service control for Stock Tracker"""
    
    def __init__(self):
        self.service_name = "stock-tracker"
        self.pid_file = "stock_tracker.pid"
        self.log_file = "logs/service.log"
        self.state_file = "service_state.json"
        
    def is_running(self) -> bool:
        """Check if service is currently running"""
        try:
            if os.path.exists(self.pid_file):
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                # Check if process is actually running
                try:
                    os.kill(pid, 0)  # Signal 0 just checks if process exists
                    return True
                except OSError:
                    # Process doesn't exist, clean up stale PID file
                    os.remove(self.pid_file)
                    return False
            return False
        except Exception as e:
            logger.error(f"Error checking if service is running: {e}")
            return False
    
    def start(self, test_mode=False):
        """Start the service"""
        if self.is_running():
            logger.info("Service is already running")
            return True
        
        logger.info("Starting Stock Tracker service...")
        
        try:
            # Ensure log directory exists
            os.makedirs("logs", exist_ok=True)
            
            # Build command
            cmd = [sys.executable, "main.py"]
            if test_mode:
                cmd.append("-test")
            
            # Start process
            with open(self.log_file, 'a') as log:
                process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid if os.name != 'nt' else None
                )
            
            # Save PID
            with open(self.pid_file, 'w') as f:
                f.write(str(process.pid))
            
            # Wait a moment to see if it starts successfully
            time.sleep(2)
            
            if self.is_running():
                logger.info(f"Service started successfully (PID: {process.pid})")
                return True
            else:
                logger.error("Service failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Error starting service: {e}")
            return False
    
    def stop(self):
        """Stop the service gracefully"""
        if not self.is_running():
            logger.info("Service is not running")
            return True
        
        logger.info("Stopping Stock Tracker service...")
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)
            
            # Wait for graceful shutdown
            for i in range(30):  # Wait up to 30 seconds
                if not self.is_running():
                    logger.info("Service stopped gracefully")
                    return True
                time.sleep(1)
            
            # If still running, force kill
            logger.warning("Service didn't stop gracefully, forcing shutdown...")
            os.kill(pid, signal.SIGKILL)
            
            # Clean up PID file
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
            
            logger.info("Service stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
            return False
    
    def restart(self, test_mode=False):
        """Restart the service"""
        logger.info("Restarting Stock Tracker service...")
        
        if self.is_running():
            if not self.stop():
                return False
        
        # Wait a moment before restarting
        time.sleep(2)
        
        return self.start(test_mode)
    
    def status(self):
        """Get service status"""
        is_running = self.is_running()
        
        status_info = {
            "service": self.service_name,
            "running": is_running,
            "timestamp": time.time()
        }
        
        if is_running:
            try:
                with open(self.pid_file, 'r') as f:
                    status_info["pid"] = int(f.read().strip())
            except:
                pass
        
        # Try to get detailed status from service state file
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state_data = json.load(f)
                status_info.update(state_data)
        except:
            pass
        
        return status_info
    
    def logs(self, lines=50):
        """Show recent log entries"""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    log_lines = f.readlines()
                
                # Show last N lines
                recent_lines = log_lines[-lines:] if len(log_lines) > lines else log_lines
                
                print("Recent log entries:")
                print("-" * 50)
                for line in recent_lines:
                    print(line.rstrip())
            else:
                print("No log file found")
        except Exception as e:
            logger.error(f"Error reading logs: {e}")


def main():
    """Main CLI entry point"""
    service = ServiceControl()
    
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} {{start|stop|restart|status|logs}} [--test]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    test_mode = "--test" in sys.argv
    
    if command == "start":
        success = service.start(test_mode)
        sys.exit(0 if success else 1)
        
    elif command == "stop":
        success = service.stop()
        sys.exit(0 if success else 1)
        
    elif command == "restart":
        success = service.restart(test_mode)
        sys.exit(0 if success else 1)
        
    elif command == "status":
        status = service.status()
        print(json.dumps(status, indent=2))
        
    elif command == "logs":
        lines = 50
        if len(sys.argv) > 2 and sys.argv[2].isdigit():
            lines = int(sys.argv[2])
        service.logs(lines)
        
    else:
        print(f"Unknown command: {command}")
        print(f"Usage: {sys.argv[0]} {{start|stop|restart|status|logs}}")
        sys.exit(1)


if __name__ == "__main__":
    main()
