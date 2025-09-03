import unittest
import json
import os
import tempfile
import asyncio
from unittest.mock import patch, mock_open, MagicMock, AsyncMock
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.tools import (
    add_stock_to_tracker, 
    remove_stock_from_tracker, 
    get_stock_tracker_list,
    get_stock_price_info,
    _read_tracker_list,
    _write_tracker_list
)


class TestTools(unittest.TestCase):
    """Test cases for tools functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_symbol = "AAPL"
        self.test_tracker_list = ["AAPL", "MSFT", "GOOGL"]
        self.temp_dir = tempfile.mkdtemp()
        self.tracker_file = os.path.join(self.temp_dir, "tracker_list.json")

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_tracker_list_file_exists(self):
        """Test reading tracker list when file exists"""
        # Create test file
        with open(self.tracker_file, 'w') as f:
            json.dump(self.test_tracker_list, f)
        
        with patch('lib.tools.TRACKER_FILE', self.tracker_file):
            result = _read_tracker_list()
            self.assertEqual(result, self.test_tracker_list)

    def test_read_tracker_list_file_not_exists(self):
        """Test reading tracker list when file doesn't exist"""
        non_existent_file = os.path.join(self.temp_dir, "nonexistent.json")
        
        with patch('lib.tools.TRACKER_FILE', non_existent_file):
            result = _read_tracker_list()
            self.assertEqual(result, [])

    def test_write_tracker_list_success(self):
        """Test writing tracker list successfully"""
        with patch('lib.tools.TRACKER_FILE', self.tracker_file):
            result = _write_tracker_list(self.test_tracker_list)
            self.assertTrue(result)
            
            # Verify file contents
            with open(self.tracker_file, 'r') as f:
                data = json.load(f)
                self.assertEqual(data, self.test_tracker_list)

    @patch('lib.tools._read_tracker_list')
    @patch('lib.tools._write_tracker_list')
    @patch('lib.tools.get_stock_price')
    def test_add_stock_to_tracker_success(self, mock_get_price, mock_write, mock_read):
        """Test successfully adding stock to tracker"""
        mock_read.return_value = []
        mock_write.return_value = True
        
        # Mock successful price check
        mock_price_response = MagicMock()
        mock_price_response.current_price = 150.0
        mock_price_response.previous_close = 148.0
        mock_get_price.return_value = mock_price_response
        
        # Run the async function
        result = asyncio.run(add_stock_to_tracker(self.test_symbol))
        
        self.assertIn("Successfully added", result)
        mock_write.assert_called_once_with([self.test_symbol])

    @patch('lib.tools._read_tracker_list')
    def test_add_stock_to_tracker_already_exists(self, mock_read):
        """Test adding stock that already exists"""
        mock_read.return_value = [self.test_symbol]
        
        result = asyncio.run(add_stock_to_tracker(self.test_symbol))
        
        self.assertIn("already being tracked", result)

    def test_add_stock_to_tracker_invalid_symbol(self):
        """Test adding invalid stock symbol"""
        result = asyncio.run(add_stock_to_tracker(""))
        self.assertIn("Error: Invalid stock symbol", result)
        
        result = asyncio.run(add_stock_to_tracker(None))
        self.assertIn("Error: Invalid stock symbol", result)

    @patch('lib.tools._read_tracker_list')
    @patch('lib.tools._write_tracker_list')
    def test_remove_stock_from_tracker_success(self, mock_write, mock_read):
        """Test successfully removing stock from tracker"""
        mock_read.return_value = [self.test_symbol, "MSFT"]
        mock_write.return_value = True
        
        result = asyncio.run(remove_stock_from_tracker(self.test_symbol))
        
        self.assertIn("Successfully removed", result)
        mock_write.assert_called_once_with(["MSFT"])

    @patch('lib.tools._read_tracker_list')
    def test_remove_stock_from_tracker_not_exists(self, mock_read):
        """Test removing stock that doesn't exist"""
        mock_read.return_value = ["MSFT", "GOOGL"]
        
        result = asyncio.run(remove_stock_from_tracker(self.test_symbol))
        
        self.assertIn("is not being tracked", result)

    @patch('lib.tools._read_tracker_list')
    def test_get_stock_tracker_list_success(self, mock_read):
        """Test getting stock tracker list"""
        mock_read.return_value = self.test_tracker_list
        
        result = asyncio.run(get_stock_tracker_list())
        
        self.assertEqual(result, self.test_tracker_list)

    @patch('lib.tools.get_stock_price')
    def test_get_stock_price_info_success(self, mock_get_price):
        """Test getting stock price info"""
        mock_price_response = MagicMock()
        mock_get_price.return_value = mock_price_response
        
        result = asyncio.run(get_stock_price_info(self.test_symbol))
        
        self.assertEqual(result, mock_price_response)
        mock_get_price.assert_called_once_with(self.test_symbol)

    def test_get_stock_price_info_invalid_symbol(self):
        """Test getting stock price info with invalid symbol"""
        with self.assertRaises(ValueError):
            asyncio.run(get_stock_price_info(""))


if __name__ == '__main__':
    unittest.main()
