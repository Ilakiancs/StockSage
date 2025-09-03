
from agents import function_tool

import yfinance as yf

from pydantic import BaseModel
import json
import logging
import os

from lib.stock_checker import StockPriceResponse, get_stock_price
from lib.config_manager import get_config_manager

logger = logging.getLogger(__name__)
config_manager = get_config_manager()

TRACKER_FILE = "resources/tracker_list.json"

def _ensure_resources_dir():
    """Ensure resources directory exists"""
    os.makedirs("resources", exist_ok=True)

def _read_tracker_list() -> list:
    """Safely read tracker list from file"""
    try:
        _ensure_resources_dir()
        if not os.path.exists(TRACKER_FILE):
            return []
        with open(TRACKER_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Error reading tracker list: {e}")
        return []

def _write_tracker_list(tracker_list: list) -> bool:
    """Safely write tracker list to file"""
    try:
        _ensure_resources_dir()
        with open(TRACKER_FILE, "w") as f:
            json.dump(tracker_list, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error writing tracker list: {e}")
        return False

@function_tool
async def add_stock_to_tracker(symbol: str):
    try:
        if not symbol or not isinstance(symbol, str):
            return "Error: Invalid stock symbol"
            
        symbol = symbol.strip().upper()
        tracker_list = _read_tracker_list()
        
        if symbol in tracker_list:
            return f"{symbol} is already being tracked"
            
        # Validate symbol by trying to get its price
        try:
            get_stock_price(symbol)
        except Exception as e:
            logger.warning(f"Could not validate symbol {symbol}: {e}")
            return f"Error: Could not find stock symbol {symbol}"
        
        tracker_list.append(symbol)
        
        if _write_tracker_list(tracker_list):
            # Create configuration for the new stock
            config_manager.get_stock_config(symbol)  # This creates default config
            return f"Successfully added {symbol} to tracker with default settings"
        else:
            return f"Error: Could not save {symbol} to tracker"
            
    except Exception as e:
        logger.error(f"Error adding stock {symbol} to tracker: {e}")
        return f"Error: Could not add {symbol} to tracker"

@function_tool
async def remove_stock_from_tracker(symbol: str):
    try:
        if not symbol or not isinstance(symbol, str):
            return "Error: Invalid stock symbol"
            
        symbol = symbol.strip().upper()
        tracker_list = _read_tracker_list()
        
        if symbol not in tracker_list:
            return f"{symbol} is not being tracked"
            
        tracker_list.remove(symbol)
        
        if _write_tracker_list(tracker_list):
            # Remove configuration for the stock
            config_manager.remove_stock_config(symbol)
            return f"Successfully removed {symbol} from tracker"
        else:
            return f"Error: Could not save changes after removing {symbol}"
            
    except Exception as e:
        logger.error(f"Error removing stock {symbol} from tracker: {e}")
        return f"Error: Could not remove {symbol} from tracker"


@function_tool
async def get_stock_tracker_list() -> list:
    try:
        tracker_list = _read_tracker_list()
        logger.info(f"Retrieved tracker list: {tracker_list}")
        return tracker_list
    except Exception as e:
        logger.error(f"Error getting tracker list: {e}")
        return []

@function_tool
async def get_stock_price_info(symbol: str) -> StockPriceResponse:
    try:
        if not symbol or not isinstance(symbol, str):
            raise ValueError("Invalid stock symbol")
        return get_stock_price(symbol.strip().upper())
    except Exception as e:
        logger.error(f"Error getting stock price for {symbol}: {e}")
        raise
