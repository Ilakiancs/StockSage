import json
import os
from lib.agent import run_research_pipeline
import asyncio
from datetime import date

from lib.stock_checker import get_stock_price

def track_stocks():
  print("tracking stocks started...")

  with open("resources/tracker_list.json", "r") as f:
    tracker_list = json.load(f)

  print("Tracking stocks: ", tracker_list)

  for symbol in tracker_list:
    stock_info = get_stock_price(symbol)

    # if the stock price is 5% + or - from the previous close, run the research pipeline
    if (stock_info.current_price > stock_info.previous_close * 1.01) or (stock_info.current_price < stock_info.previous_close * 0.99):
      # check if we have already alerted the user today

      with open("resources/alert_history.json", "r") as f:
        alert_history = json.load(f)

      if symbol not in alert_history:
        alert_history[symbol] = []

      # check if we have already alerted the user today
      if alert_history[symbol] and alert_history[symbol][-1] == str(date.today()):
        print(f"Already alerted user about {symbol} today.")
      else:
        alert_history[symbol].append(str(date.today()))
        with open("resources/alert_history.json", "w") as f:
          json.dump(alert_history, f)

        asyncio.run(run_research_pipeline(symbol, stock_info.current_price, stock_info.previous_close))