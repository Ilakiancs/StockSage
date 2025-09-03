import unittest
import json
import os
import tempfile
from unittest.mock import patch, mock_open, MagicMock
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.sms import send_sms


class TestSMS(unittest.TestCase):
    """Test cases for SMS functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_message = "Test message"
        self.long_message = "x" * 1700  # Exceeds Twilio limit
        
        # Mock environment variables
        self.env_vars = {
            'TARGET_PHONE_NUMBER': '+1234567890',
            'TWILIO_PHONE_NUMBER': '+0987654321',
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token'
        }

    @patch.dict(os.environ, {
        'TARGET_PHONE_NUMBER': '+1234567890',
        'TWILIO_PHONE_NUMBER': '+0987654321',
        'TWILIO_ACCOUNT_SID': 'test_sid',
        'TWILIO_AUTH_TOKEN': 'test_token'
    })
    @patch('lib.sms.Client')
    def test_send_sms_success(self, mock_client):
        """Test successful SMS sending"""
        # Mock Twilio client
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        
        mock_message = MagicMock()
        mock_message.sid = "test_sid_123"
        mock_client_instance.messages.create.return_value = mock_message
        
        result = send_sms(self.test_message)
        
        self.assertTrue(result)
        mock_client_instance.messages.create.assert_called_once()

    def test_send_sms_empty_message(self):
        """Test error handling for empty message"""
        result = send_sms("")
        self.assertFalse(result)

    def test_send_sms_none_message(self):
        """Test error handling for None message"""
        result = send_sms(None)
        self.assertFalse(result)

    @patch.dict(os.environ, {}, clear=True)
    def test_send_sms_missing_config(self):
        """Test error handling for missing configuration"""
        result = send_sms(self.test_message)
        self.assertFalse(result)

    @patch.dict(os.environ, {
        'TARGET_PHONE_NUMBER': '+1234567890',
        'TWILIO_PHONE_NUMBER': '+0987654321',
        'TWILIO_ACCOUNT_SID': 'test_sid',
        'TWILIO_AUTH_TOKEN': 'test_token'
    })
    @patch('lib.sms.Client')
    def test_send_sms_long_message(self, mock_client):
        """Test message truncation for long messages"""
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        
        mock_message = MagicMock()
        mock_message.sid = "test_sid_123"
        mock_client_instance.messages.create.return_value = mock_message
        
        result = send_sms(self.long_message)
        
        self.assertTrue(result)
        # Verify the message was truncated
        call_args = mock_client_instance.messages.create.call_args
        sent_message = call_args[1]['body']
        self.assertLessEqual(len(sent_message), 1600)
        self.assertTrue(sent_message.endswith("..."))

    @patch.dict(os.environ, {
        'TARGET_PHONE_NUMBER': '+1234567890',
        'TWILIO_PHONE_NUMBER': '+0987654321',
        'TWILIO_ACCOUNT_SID': 'test_sid',
        'TWILIO_AUTH_TOKEN': 'test_token'
    })
    @patch('lib.sms.Client')
    def test_send_sms_twilio_exception(self, mock_client):
        """Test handling of Twilio exceptions"""
        from twilio.base.exceptions import TwilioException
        
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        mock_client_instance.messages.create.side_effect = TwilioException("Twilio error")
        
        result = send_sms(self.test_message)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
