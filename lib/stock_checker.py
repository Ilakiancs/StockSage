import yfinance as yf
from pydantic import BaseModel


class StockPriceResponse(BaseModel):
  current_price: float
  previous_close: float

def get_stock_price(symbol: str) -> StockPriceResponse:
  stock = yf.Ticker(symbol)
  # get the current stock price and the previous close price
  data = stock.history(period="1d", interval="1m")

  if not data.empty:
    current_price = data["Close"].iloc[-1]  # most recent minute
  else:
    current_price = stock.fast_info.last_price  # fallback

  previous_close = stock.history(period="5d")["Close"].dropna().iloc[-2]

  return StockPriceResponse(
    current_price=current_price,
    previous_close=previous_close
  )