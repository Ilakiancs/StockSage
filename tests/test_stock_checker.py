import unittest
import json
import os
import tempfile
from unittest.mock import patch, mock_open, MagicMock
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.stock_checker import get_stock_price, StockPriceResponse


class TestStockChecker(unittest.TestCase):
    """Test cases for stock price checking functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.valid_symbol = "AAPL"
        self.invalid_symbol = ""
        self.mock_current_price = 150.25
        self.mock_previous_close = 148.50

    @patch('lib.stock_checker.yf.Ticker')
    def test_get_stock_price_success(self, mock_ticker):
        """Test successful stock price retrieval"""
        # Mock yfinance Ticker
        mock_stock = MagicMock()
        mock_ticker.return_value = mock_stock
        
        # Mock historical data
        mock_data = MagicMock()
        mock_data.empty = False
        mock_data.__getitem__.return_value.iloc = MagicMock()
        mock_data.__getitem__.return_value.iloc.__getitem__.return_value = self.mock_current_price
        mock_stock.history.return_value = mock_data
        
        # Mock historical data for previous close
        mock_historical = MagicMock()
        mock_historical.dropna.return_value.iloc = MagicMock()
        mock_historical.dropna.return_value.iloc.__getitem__.return_value = self.mock_previous_close
        
        # Set up the mock to return different data for different calls
        def history_side_effect(*args, **kwargs):
            if 'period' in kwargs and kwargs['period'] == "1d":
                return mock_data
            elif 'period' in kwargs and kwargs['period'] == "5d":
                return {"Close": mock_historical}
            return mock_data
            
        mock_stock.history.side_effect = history_side_effect
        
        # Call the function
        result = get_stock_price(self.valid_symbol)
        
        # Assert results
        self.assertIsInstance(result, StockPriceResponse)
        self.assertEqual(result.current_price, self.mock_current_price)
        self.assertEqual(result.previous_close, self.mock_previous_close)

    def test_get_stock_price_invalid_symbol(self):
        """Test error handling for invalid symbol"""
        with self.assertRaises(ValueError):
            get_stock_price(self.invalid_symbol)

    def test_get_stock_price_none_symbol(self):
        """Test error handling for None symbol"""
        with self.assertRaises(ValueError):
            get_stock_price(None)

    @patch('lib.stock_checker.yf.Ticker')
    def test_get_stock_price_api_failure(self, mock_ticker):
        """Test handling of API failures"""
        mock_ticker.side_effect = Exception("API Error")
        
        with self.assertRaises(Exception):
            get_stock_price(self.valid_symbol)

    @patch('lib.stock_checker.yf.Ticker')
    def test_get_stock_price_empty_data(self, mock_ticker):
        """Test handling of empty data response"""
        mock_stock = MagicMock()
        mock_ticker.return_value = mock_stock
        
        # Mock empty historical data
        mock_data = MagicMock()
        mock_data.empty = True
        mock_stock.history.return_value = mock_data
        
        # Mock fast_info fallback
        mock_fast_info = MagicMock()
        mock_fast_info.last_price = self.mock_current_price
        mock_stock.fast_info = mock_fast_info
        
        # Mock historical data for previous close
        mock_historical = MagicMock()
        mock_historical.dropna.return_value.iloc = MagicMock()
        mock_historical.dropna.return_value.iloc.__getitem__.return_value = self.mock_previous_close
        
        def history_side_effect(*args, **kwargs):
            if 'period' in kwargs and kwargs['period'] == "1d":
                return mock_data
            elif 'period' in kwargs and kwargs['period'] == "5d":
                return {"Close": mock_historical}
            return mock_data
            
        mock_stock.history.side_effect = history_side_effect
        
        result = get_stock_price(self.valid_symbol)
        
        self.assertIsInstance(result, StockPriceResponse)
        self.assertEqual(result.current_price, self.mock_current_price)


if __name__ == '__main__':
    unittest.main()
