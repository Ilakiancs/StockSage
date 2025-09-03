import yfinance as yf
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class StockPriceResponse(BaseModel):
  current_price: float
  previous_close: float

def get_stock_price(symbol: str) -> StockPriceResponse:
  try:
    if not symbol or not isinstance(symbol, str):
      raise ValueError(f"Invalid symbol: {symbol}")
    
    symbol = symbol.strip().upper()
    stock = yf.Ticker(symbol)
    
    # get the current stock price and the previous close price
    try:
      data = stock.history(period="1d", interval="1m")
      
      if not data.empty:
        current_price = float(data["Close"].iloc[-1])  # most recent minute
      else:
        # fallback to fast_info
        try:
          current_price = float(stock.fast_info.last_price)
        except Exception as e:
          logger.warning(f"Could not get fast_info for {symbol}: {e}")
          raise ValueError(f"Could not retrieve current price for {symbol}")
      
      # Get previous close with error handling
      try:
        historical_data = stock.history(period="5d")["Close"].dropna()
        if len(historical_data) < 2:
          raise ValueError(f"Insufficient historical data for {symbol}")
        previous_close = float(historical_data.iloc[-2])
      except Exception as e:
        logger.warning(f"Could not get historical data for {symbol}: {e}")
        # Try alternative method
        try:
          info = stock.info
          previous_close = float(info.get('previousClose', 0))
          if previous_close == 0:
            raise ValueError(f"Could not retrieve previous close for {symbol}")
        except Exception as info_e:
          logger.error(f"Failed to get previous close for {symbol}: {info_e}")
          raise ValueError(f"Could not retrieve previous close for {symbol}")

      if current_price <= 0 or previous_close <= 0:
        raise ValueError(f"Invalid price data for {symbol}: current={current_price}, previous={previous_close}")

      return StockPriceResponse(
        current_price=current_price,
        previous_close=previous_close
      )
      
    except Exception as e:
      logger.error(f"Error retrieving stock data for {symbol}: {e}")
      raise
      
  except Exception as e:
    logger.error(f"Failed to get stock price for {symbol}: {e}")
    raise