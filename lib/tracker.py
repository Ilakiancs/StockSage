import json
import os
from lib.agent import run_research_pipeline
import asyncio
from datetime import date
import logging

from lib.stock_checker import get_stock_price
from lib.logging_config import StockTrackingLogger, log_performance
from lib.config_manager import get_config_manager

logger = logging.getLogger(__name__)
stock_logger = StockTrackingLogger()
config_manager = get_config_manager()

TRACKER_FILE = "resources/tracker_list.json"
ALERT_HISTORY_FILE = "resources/alert_history.json"

def _ensure_resources_dir():
    """Ensure resources directory exists"""
    os.makedirs("resources", exist_ok=True)

def _read_json_file(filepath: str, default_value):
    """Safely read JSON file with fallback"""
    try:
        if not os.path.exists(filepath):
            return default_value
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        return default_value

def _write_json_file(filepath: str, data) -> bool:
    """Safely write JSON file"""
    try:
        _ensure_resources_dir()
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error writing {filepath}: {e}")
        return False

@log_performance("stock_tracking")
def track_stocks():
    """Track stocks and trigger alerts for significant price movements"""
    try:
        logger.info("Starting stock tracking cycle...")

        tracker_list = _read_json_file(TRACKER_FILE, [])
        
        if not tracker_list:
            logger.info("No stocks to track")
            return

        logger.info(f"Tracking {len(tracker_list)} stocks: {tracker_list}")

        alerts_triggered = 0
        errors_encountered = 0

        for symbol in tracker_list:
            try:
                if not symbol or not isinstance(symbol, str):
                    logger.warning(f"Invalid symbol in tracker list: {symbol}")
                    errors_encountered += 1
                    continue
                    
                symbol = symbol.strip().upper()
                logger.debug(f"Checking {symbol}...")
                
                stock_info = get_stock_price(symbol)

                # Log price check
                stock_logger.log_price_check(
                    symbol, 
                    stock_info.current_price, 
                    stock_info.previous_close
                )

                # Calculate percentage change
                price_change_percent = (stock_info.current_price - stock_info.previous_close) / stock_info.previous_close * 100
                
                # Get stock-specific configuration
                stock_config = config_manager.get_stock_config(symbol)
                threshold_percent = stock_config.threshold_percent
                
                # Check if the stock price movement exceeds the configured threshold
                if abs(price_change_percent) >= threshold_percent:
                    stock_logger.log_alert_triggered(symbol, price_change_percent)
                    
                    # Use config manager to check if we should send alert
                    if config_manager.should_alert(symbol, price_change_percent):
                        logger.info(f"Triggering research pipeline for {symbol} (threshold: {threshold_percent}%)")
                        
                        # Update last alert date in config
                        today = date.today().isoformat()
                        config_manager.update_stock_config(symbol, last_alert=today)
                        
                        # Update alert history (legacy system)
                        alert_history = _read_json_file(ALERT_HISTORY_FILE, {})
                        if symbol not in alert_history:
                            alert_history[symbol] = []
                        alert_history[symbol].append(str(date.today()))
                        
                        if _write_json_file(ALERT_HISTORY_FILE, alert_history):
                            try:
                                # Get priority level
                                priority = config_manager.get_priority(price_change_percent)
                                logger.info(f"Alert priority for {symbol}: {priority}")
                                
                                success = asyncio.run(run_research_pipeline(
                                    symbol, 
                                    stock_info.current_price, 
                                    stock_info.previous_close,
                                    priority=priority
                                ))
                                if success:
                                    alerts_triggered += 1
                                    logger.info(f"Alert successfully sent for {symbol}")
                                else:
                                    logger.error(f"Failed to send alert for {symbol}")
                                    errors_encountered += 1
                            except Exception as e:
                                logger.error(f"Error running research pipeline for {symbol}: {e}")
                                errors_encountered += 1
                        else:
                            logger.error(f"Could not update alert history for {symbol}")
                            errors_encountered += 1
                    else:
                        logger.info(f"Alert suppressed for {symbol} (config rules)")
                        stock_logger.log_duplicate_alert_prevented(symbol)
                else:
                    logger.debug(f"{symbol} change {price_change_percent:.2%} is below threshold ({threshold_percent}%)")
                    
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                errors_encountered += 1
                continue

        # Log summary
        logger.info(f"Stock tracking cycle completed: {alerts_triggered} alerts sent, {errors_encountered} errors")
        
        if errors_encountered > 0:
            logger.warning(f"Encountered {errors_encountered} errors during tracking cycle")
        
    except Exception as e:
        logger.error(f"Critical error in track_stocks: {e}")
        raise