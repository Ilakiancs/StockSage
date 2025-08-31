
from agents import function_tool

import yfinance as yf

from pydantic import BaseModel
import json

from lib.stock_checker import StockPriceResponse, get_stock_price

@function_tool
async def add_stock_to_tracker(symbol: str):
  with open("resources/tracker_list.json", "r") as f:
    tracker_list = json.load(f)

  tracker_list.append(symbol)

  with open("resources/tracker_list.json", "w") as f:
    json.dump(tracker_list, f)

@function_tool
async def remove_stock_from_tracker(symbol: str):
  with open("resources/tracker_list.json", "r") as f:
    tracker_list = json.load(f)

  tracker_list.remove(symbol)

  with open("resources/tracker_list.json", "w") as f:
    json.dump(tracker_list, f)


@function_tool
async def get_stock_tracker_list() -> list:
  with open("resources/tracker_list.json", "r") as f:
    print('getting tracker list')
    tracker_list = json.load(f)
    print(tracker_list)

  return tracker_list

@function_tool
async def get_stock_price_info(symbol: str) -> StockPriceResponse:
  return get_stock_price(symbol)
