import os
import html
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from lib.tracker import track_stocks
from lib.agent import handle_incoming_message, run_research_pipeline
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from lib.stock_checker import get_stock_price
from lib.sms import send_sms
import sys
import json
from twilio.request_validator import RequestValidator
from dotenv import load_dotenv
import logging
import time
from datetime import datetime, date

# Load environment first
load_dotenv()

# Setup comprehensive logging
from lib.logging_config import setup_logging, log_system_info, RequestLogger
from lib.service_manager import lifespan, get_service_manager, get_scheduler_manager, monitor_service_health

setup_logging(
    log_level=logging.INFO if os.getenv("DEBUG") != "true" else logging.DEBUG,
    log_file="logs/stock_tracker.log"
)

logger = logging.getLogger(__name__)
request_logger = RequestLogger()

# Log system information on startup
log_system_info()

# fastapi configuration with lifespan management
app = FastAPI(
    title="Stock Tracker", 
    description="AI-powered stock monitoring system",
    lifespan=lifespan
)

# Add rate limiting middleware
from lib.rate_limiting import rate_limit_middleware

@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    """Apply rate limiting to all requests"""
    return await rate_limit_middleware(request, call_next)

# Service lifecycle events
@app.on_event("startup")
async def startup_event():
    """Additional startup tasks"""
    # Start health monitoring
    service_manager = get_service_manager()
    health_task = asyncio.create_task(monitor_service_health())
    service_manager.add_background_task(health_task)
    
    logger.info("Application startup completed")

TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TARGET_PHONE_NUMBER = os.getenv("TARGET_PHONE_NUMBER")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Validate required environment variables
required_env_vars = {
    "TWILIO_AUTH_TOKEN": TWILIO_AUTH_TOKEN,
    "TARGET_PHONE_NUMBER": TARGET_PHONE_NUMBER,
    "WEBHOOK_URL": WEBHOOK_URL
}

missing_vars = [var for var, value in required_env_vars.items() if not value]
if missing_vars:
    logger.error(f"Missing required environment variables: {missing_vars}")

@app.post("/receive-message")
async def receive_message(request: Request):
    """Handle incoming Twilio webhook messages with comprehensive error handling"""
    start_time = time.time()
    
    try:
        # Log incoming request
        request_logger.log_request("POST", "/receive-message", dict(request.headers))
        
        # Validate Twilio signature
        signature = request.headers.get("X-Twilio-Signature", "")
        
        if not TWILIO_AUTH_TOKEN:
            logger.error("Twilio auth token not configured")
            raise HTTPException(status_code=500, detail="Server configuration error")
            
        try:
            form = await request.form()
        except Exception as e:
            logger.error(f"Error parsing form data: {e}")
            raise HTTPException(status_code=400, detail="Invalid form data")
            
        validator = RequestValidator(TWILIO_AUTH_TOKEN)
        params = dict(form)
        
        # Validate webhook signature
        if not WEBHOOK_URL:
            logger.error("Webhook URL not configured")
            raise HTTPException(status_code=500, detail="Server configuration error")
            
        if not validator.validate(WEBHOOK_URL, params, signature):
            logger.warning(f"Invalid Twilio signature from {request.client.host if request.client else 'unknown'}")
            raise HTTPException(status_code=403, detail="Invalid signature")

        from_number = form.get("From", "")
        to_number = form.get("To", "")
        body = form.get("Body", "")

        # Validate phone numbers
        if to_number != os.getenv("TWILIO_PHONE_NUMBER"):
            logger.warning(f"Message sent to unauthorized number: {to_number}")
            raise HTTPException(status_code=403, detail="Unauthorized")

        if from_number != TARGET_PHONE_NUMBER:
            logger.warning(f"Message from unauthorized number: {from_number}")
            raise HTTPException(status_code=403, detail="Unauthorized")

        # Sanitize and validate message body
        if not body:
            logger.warning("Received empty message body")
            request_logger.log_response(200, time.time() - start_time)
            return Response(content="OK", status_code=200)
            
        safe_body = html.escape(body.strip())
        
        if not safe_body:
            logger.warning("Received message with no content after sanitization")
            request_logger.log_response(200, time.time() - start_time)
            return Response(content="OK", status_code=200)

        logger.info(f"Processing message from {from_number[-4:]}****: {safe_body}")

        # Process the message
        try:
            response_text = await handle_incoming_message(safe_body)
            
            if not response_text:
                response_text = "Sorry, I couldn't process your message."
                
            logger.info(f"Sending response: {response_text[:50]}...")
            
            # Send the response back to the user
            if not send_sms(response_text):
                logger.error("Failed to send SMS response")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            try:
                send_sms("Sorry, I encountered an error processing your message.")
            except Exception as sms_e:
                logger.error(f"Failed to send error SMS: {sms_e}")

        request_logger.log_response(200, time.time() - start_time)
        return Response(content="OK", status_code=200)
        
    except HTTPException as e:
        request_logger.log_response(e.status_code, time.time() - start_time)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in receive_message: {e}")
        request_logger.log_response(500, time.time() - start_time)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        from lib.service_manager import health_checker
        
        # Run comprehensive health checks
        health_status = await health_checker.run_health_checks()
        
        # Add basic service info
        service_info = {
            "service": "stock-tracker",
            "version": "1.0.0",
            "environment": {
                "twilio_configured": bool(TWILIO_AUTH_TOKEN),
                "webhook_configured": bool(WEBHOOK_URL),
                "target_phone_configured": bool(TARGET_PHONE_NUMBER)
            }
        }
        
        # Combine health status with service info
        response = {**health_status, **service_info}
        
        # Return appropriate status code
        status_code = 200 if health_status["overall_status"] == "healthy" else 503
        
        return Response(
            content=json.dumps(response, indent=2),
            media_type="application/json",
            status_code=status_code
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        error_response = {
            "overall_status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        return Response(
            content=json.dumps(error_response, indent=2),
            media_type="application/json",
            status_code=503
        )

@app.get("/metrics")
async def get_metrics():
    """Get application metrics for monitoring"""
    try:
        from lib.tools import _read_tracker_list
        from lib.tracker import _read_json_file
        
        tracker_list = _read_tracker_list()
        alert_history = _read_json_file("resources/alert_history.json", {})
        
        # Calculate metrics
        total_alerts = sum(len(dates) for dates in alert_history.values())
        today = str(date.today())
        today_alerts = sum(1 for dates in alert_history.values() if dates and dates[-1] == today)
        
        metrics = {
            "tracked_stocks_count": len(tracker_list),
            "total_alerts_sent": total_alerts,
            "alerts_today": today_alerts,
            "unique_stocks_alerted": len(alert_history),
            "last_updated": datetime.now().isoformat()
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving metrics")

@app.get("/config")
async def get_configuration():
    """Get current configuration settings"""
    try:
        from lib.config_manager import get_config_manager
        config_manager = get_config_manager()
        
        return config_manager.get_all_configs()
        
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving configuration")

@app.post("/config/stock/{symbol}")
async def update_stock_config(symbol: str, request: Request):
    """Update configuration for a specific stock"""
    try:
        from lib.config_manager import get_config_manager
        config_manager = get_config_manager()
        
        body = await request.json()
        
        # Validate input
        allowed_fields = ['threshold_percent', 'enabled', 'max_alerts_per_day', 'custom_message_prefix', 'priority']
        config_updates = {k: v for k, v in body.items() if k in allowed_fields}
        
        if not config_updates:
            raise HTTPException(status_code=400, detail="No valid configuration fields provided")
        
        success = config_manager.update_stock_config(symbol, **config_updates)
        
        if success:
            logger.info(f"Updated configuration for {symbol}: {config_updates}")
            return {"message": f"Configuration updated for {symbol}", "updates": config_updates}
        else:
            raise HTTPException(status_code=500, detail="Failed to update configuration")
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error updating stock config for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Error updating configuration")

@app.post("/config/global")
async def update_global_config(request: Request):
    """Update global configuration settings"""
    try:
        from lib.config_manager import get_config_manager
        config_manager = get_config_manager()
        
        body = await request.json()
        
        # Validate input
        allowed_fields = [
            'default_threshold_percent', 'max_message_length', 'rate_limit_per_hour',
            'tracking_enabled', 'debug_mode', 'alert_cooldown_hours', 'sms_enabled',
            'high_priority_threshold', 'low_priority_threshold', 'max_tracked_stocks'
        ]
        config_updates = {k: v for k, v in body.items() if k in allowed_fields}
        
        if not config_updates:
            raise HTTPException(status_code=400, detail="No valid configuration fields provided")
        
        success = config_manager.update_global_config(**config_updates)
        
        if success:
            logger.info(f"Updated global configuration: {config_updates}")
            return {"message": "Global configuration updated", "updates": config_updates}
        else:
            raise HTTPException(status_code=500, detail="Failed to update global configuration")
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error updating global config: {e}")
        raise HTTPException(status_code=500, detail="Error updating global configuration")

# for testing purposes only
async def chat_terminal():
    """Terminal chat interface for testing with error handling"""
    print("Chat mode activated. Type 'exit' to quit.")
    try:
        while True:
            try:
                user_input = input("You: ")
                if user_input.lower() == "exit":
                    print("Exiting chat.")
                    break
                    
                if not user_input.strip():
                    print("Please enter a message.")
                    continue
                    
                response = await handle_incoming_message(user_input)
                print(f"Bot: {response}")
                
            except KeyboardInterrupt:
                print("\nExiting chat.")
                break
            except EOFError:
                print("\nExiting chat.")
                break
            except Exception as e:
                logger.error(f"Error in chat terminal: {e}")
                print("Bot: Sorry, I encountered an error.")
                
    except Exception as e:
        logger.error(f"Fatal error in chat terminal: {e}")

def ensure_resources():
    """Ensure required resource files exist"""
    try:
        if not os.path.exists("resources"):
            os.makedirs("resources")
            logger.info("Created resources directory")

        if not os.path.exists("resources/alert_history.json"):
            with open("resources/alert_history.json", "w") as f:
                json.dump({}, f)
            logger.info("Created alert_history.json")

        if not os.path.exists("resources/tracker_list.json"):
            with open("resources/tracker_list.json", "w") as f:
                json.dump([], f)
            logger.info("Created tracker_list.json")
            
        # Ensure logs directory exists
        if not os.path.exists("logs"):
            os.makedirs("logs")
            logger.info("Created logs directory")
            
    except Exception as e:
        logger.error(f"Error setting up resources: {e}")
        raise

# run the project
async def main():
    """Main application entry point"""
    try:
        # Setup resources and logging
        ensure_resources()
        
        service_manager = get_service_manager()
        scheduler_manager = get_scheduler_manager()
        
        if "-test" in sys.argv:
            if "-research" in sys.argv:
                try:
                    stock_symbol = sys.argv[sys.argv.index("-research") + 1]
                    logger.info(f"Running research for {stock_symbol}")
                    
                    stock_price = get_stock_price(stock_symbol)
                    
                    await run_research_pipeline(
                        stock_symbol, 
                        stock_price.current_price, 
                        stock_price.previous_close
                    )
                    
                except IndexError:
                    logger.error("Please provide a stock symbol after -research")
                    print("Usage: python main.py -test -research AAPL")
                except Exception as e:
                    logger.error(f"Error in research mode: {e}")
                    
            else:
                # Test mode with more frequent tracking
                logger.info("Starting test mode with terminal chat")
                
                # Initialize service manager
                await service_manager.start()
                
                # Start scheduler with frequent checks
                scheduler_manager.start()
                scheduler_manager.add_job(track_stocks, 'interval', minutes=1)
                
                try:
                    await chat_terminal()
                finally:
                    await service_manager.shutdown()
                    
        else:
            # Production mode - let FastAPI handle the lifecycle
            logger.info("Starting production mode with FastAPI")
            
            # The FastAPI app will handle startup/shutdown via lifespan
            # Start scheduler for stock tracking
            scheduler_manager.start()
            scheduler_manager.add_job(track_stocks, 'interval', hours=1)
            
            # Run FastAPI server
            uvicorn.run(
                "main:app",
                host=os.getenv("HOST", "0.0.0.0"),
                port=int(os.getenv("PORT", "8000")),
                reload=False,  # Disable reload in production for better service management
            )
                
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Fatal error in application: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error starting application: {e}")
        sys.exit(1)