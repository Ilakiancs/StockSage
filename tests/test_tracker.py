import unittest
import json
import os
import tempfile
import asyncio
from unittest.mock import patch, mock_open, MagicMock, AsyncMock
from datetime import date
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.tracker import track_stocks, _read_json_file, _write_json_file


class TestTracker(unittest.TestCase):
    """Test cases for stock tracking functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_symbols = ["AAPL", "MSFT"]
        self.temp_dir = tempfile.mkdtemp()
        self.tracker_file = os.path.join(self.temp_dir, "tracker_list.json")
        self.alert_file = os.path.join(self.temp_dir, "alert_history.json")

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_json_file_success(self):
        """Test reading JSON file successfully"""
        test_data = {"test": "data"}
        with open(self.tracker_file, 'w') as f:
            json.dump(test_data, f)
        
        result = _read_json_file(self.tracker_file, {})
        self.assertEqual(result, test_data)

    def test_read_json_file_not_exists(self):
        """Test reading non-existent JSON file"""
        result = _read_json_file("nonexistent.json", {"default": True})
        self.assertEqual(result, {"default": True})

    def test_write_json_file_success(self):
        """Test writing JSON file successfully"""
        test_data = {"test": "data"}
        
        result = _write_json_file(self.tracker_file, test_data)
        self.assertTrue(result)
        
        # Verify file contents
        with open(self.tracker_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data, test_data)

    @patch('lib.tracker._read_json_file')
    def test_track_stocks_empty_list(self, mock_read):
        """Test tracking with empty stock list"""
        mock_read.return_value = []
        
        # Should complete without errors
        track_stocks()
        mock_read.assert_called()

    @patch('lib.tracker._read_json_file')
    @patch('lib.tracker.get_stock_price')
    def test_track_stocks_no_significant_movement(self, mock_get_price, mock_read_json):
        """Test tracking stocks with no significant price movement"""
        mock_read_json.return_value = ["AAPL"]
        
        # Mock stock price with minimal change (< 1%)
        mock_price_response = MagicMock()
        mock_price_response.current_price = 100.5  # 0.5% change
        mock_price_response.previous_close = 100.0
        mock_get_price.return_value = mock_price_response
        
        track_stocks()
        
        mock_get_price.assert_called_once_with("AAPL")

    @patch('lib.tracker._read_json_file')
    @patch('lib.tracker._write_json_file')
    @patch('lib.tracker.get_stock_price')
    @patch('lib.tracker.asyncio.run')
    def test_track_stocks_significant_movement_new_alert(self, mock_asyncio, mock_get_price, mock_write_json, mock_read_json):
        """Test tracking stocks with significant movement and new alert"""
        # Mock tracker list
        mock_read_json.side_effect = [
            ["AAPL"],  # tracker list
            {}  # empty alert history
        ]
        mock_write_json.return_value = True
        
        # Mock stock price with significant change (> 1%)
        mock_price_response = MagicMock()
        mock_price_response.current_price = 102.0  # 2% change
        mock_price_response.previous_close = 100.0
        mock_get_price.return_value = mock_price_response
        
        # Mock successful pipeline
        mock_asyncio.return_value = True
        
        track_stocks()
        
        # Verify alert history was updated
        mock_write_json.assert_called()
        mock_asyncio.assert_called_once()

    @patch('lib.tracker._read_json_file')
    @patch('lib.tracker.get_stock_price')
    def test_track_stocks_significant_movement_duplicate_alert(self, mock_get_price, mock_read_json):
        """Test tracking stocks with significant movement but duplicate alert prevention"""
        today = str(date.today())
        
        # Mock tracker list and alert history with today's date
        mock_read_json.side_effect = [
            ["AAPL"],  # tracker list
            {"AAPL": [today]}  # alert history with today's date
        ]
        
        # Mock stock price with significant change
        mock_price_response = MagicMock()
        mock_price_response.current_price = 102.0
        mock_price_response.previous_close = 100.0
        mock_get_price.return_value = mock_price_response
        
        track_stocks()
        
        # Should not trigger new alert since already alerted today
        mock_get_price.assert_called_once_with("AAPL")

    @patch('lib.tracker._read_json_file')
    @patch('lib.tracker.get_stock_price')
    def test_track_stocks_invalid_symbol(self, mock_get_price, mock_read_json):
        """Test tracking with invalid symbol in list"""
        mock_read_json.return_value = ["", None, "AAPL"]
        
        mock_price_response = MagicMock()
        mock_price_response.current_price = 100.0
        mock_price_response.previous_close = 100.0
        mock_get_price.return_value = mock_price_response
        
        # Should handle invalid symbols gracefully
        track_stocks()
        
        # Only valid symbol should be processed
        mock_get_price.assert_called_once_with("AAPL")

    @patch('lib.tracker._read_json_file')
    @patch('lib.tracker.get_stock_price')
    def test_track_stocks_api_error(self, mock_get_price, mock_read_json):
        """Test tracking with API error"""
        mock_read_json.return_value = ["AAPL"]
        mock_get_price.side_effect = Exception("API Error")
        
        # Should handle API errors gracefully
        track_stocks()
        
        mock_get_price.assert_called_once_with("AAPL")


if __name__ == '__main__':
    unittest.main()
