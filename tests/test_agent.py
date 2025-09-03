import unittest
import asyncio
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.agent import handle_incoming_message, run_research_pipeline


class TestAgent(unittest.TestCase):
    """Test cases for agent functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_message = "what stocks am i tracking?"
        self.test_symbol = "AAPL"
        self.test_current_price = 150.0
        self.test_previous_close = 148.0

    @patch('lib.agent.Runner.run')
    def test_handle_incoming_message_success(self, mock_runner):
        """Test successful message handling"""
        # Mock agent response
        mock_response = MagicMock()
        mock_response.final_output = "You are tracking: AAPL, MSFT"
        mock_runner.return_value = mock_response
        
        result = asyncio.run(handle_incoming_message(self.test_message))
        
        self.assertEqual(result, "You are tracking: AAPL, MSFT")
        mock_runner.assert_called_once()

    def test_handle_incoming_message_empty(self):
        """Test handling empty message"""
        result = asyncio.run(handle_incoming_message(""))
        self.assertIn("didn't understand", result)
        
        result = asyncio.run(handle_incoming_message(None))
        self.assertIn("didn't understand", result)

    def test_handle_incoming_message_whitespace_only(self):
        """Test handling whitespace-only message"""
        result = asyncio.run(handle_incoming_message("   "))
        self.assertIn("non-empty message", result)

    @patch('lib.agent.Runner.run')
    def test_handle_incoming_message_agent_error(self, mock_runner):
        """Test handling agent error"""
        mock_runner.side_effect = Exception("Agent error")
        
        result = asyncio.run(handle_incoming_message(self.test_message))
        
        self.assertIn("error processing", result)

    @patch('lib.agent.Runner.run')
    def test_handle_incoming_message_no_response(self, mock_runner):
        """Test handling no response from agent"""
        mock_runner.return_value = None
        
        result = asyncio.run(handle_incoming_message(self.test_message))
        
        self.assertIn("having trouble processing", result)

    @patch('lib.agent.send_sms')
    @patch('lib.agent.Runner.run')
    def test_run_research_pipeline_success(self, mock_runner, mock_send_sms):
        """Test successful research pipeline execution"""
        # Mock research agent response
        mock_research_response = MagicMock()
        mock_research_response.final_output = "Strong earnings report driving price increase"
        
        # Mock summariser response
        mock_summary_response = MagicMock()
        mock_summary_response.final_output = "AAPL UP 1.35%: Strong earnings report"
        
        mock_runner.side_effect = [mock_research_response, mock_summary_response]
        mock_send_sms.return_value = True
        
        result = asyncio.run(run_research_pipeline(
            self.test_symbol, 
            self.test_current_price, 
            self.test_previous_close
        ))
        
        self.assertTrue(result)
        self.assertEqual(mock_runner.call_count, 2)  # Research + Summariser
        mock_send_sms.assert_called_once()

    def test_run_research_pipeline_invalid_symbol(self):
        """Test research pipeline with invalid symbol"""
        result = asyncio.run(run_research_pipeline("", 150.0, 148.0))
        self.assertFalse(result)
        
        result = asyncio.run(run_research_pipeline(None, 150.0, 148.0))
        self.assertFalse(result)

    def test_run_research_pipeline_invalid_prices(self):
        """Test research pipeline with invalid prices"""
        result = asyncio.run(run_research_pipeline(self.test_symbol, 0, 148.0))
        self.assertFalse(result)
        
        result = asyncio.run(run_research_pipeline(self.test_symbol, 150.0, -10))
        self.assertFalse(result)

    @patch('lib.agent.send_sms')
    @patch('lib.agent.Runner.run')
    def test_run_research_pipeline_research_agent_error(self, mock_runner, mock_send_sms):
        """Test research pipeline with research agent error"""
        # Mock research agent error
        mock_runner.side_effect = [
            Exception("Research error"),
            MagicMock(final_output="AAPL UP 1.35%: Market research unavailable")
        ]
        mock_send_sms.return_value = True
        
        result = asyncio.run(run_research_pipeline(
            self.test_symbol, 
            self.test_current_price, 
            self.test_previous_close
        ))
        
        self.assertTrue(result)  # Should still succeed with fallback
        mock_send_sms.assert_called_once()

    @patch('lib.agent.send_sms')
    @patch('lib.agent.Runner.run')
    def test_run_research_pipeline_summariser_error(self, mock_runner, mock_send_sms):
        """Test research pipeline with summariser error"""
        # Mock research success but summariser error
        mock_research_response = MagicMock()
        mock_research_response.final_output = "Strong earnings report"
        
        mock_runner.side_effect = [
            mock_research_response,
            Exception("Summariser error")
        ]
        mock_send_sms.return_value = True
        
        result = asyncio.run(run_research_pipeline(
            self.test_symbol, 
            self.test_current_price, 
            self.test_previous_close
        ))
        
        self.assertTrue(result)  # Should succeed with fallback message
        mock_send_sms.assert_called_once()

    @patch('lib.agent.send_sms')
    @patch('lib.agent.Runner.run')
    def test_run_research_pipeline_sms_failure(self, mock_runner, mock_send_sms):
        """Test research pipeline with SMS sending failure"""
        mock_response = MagicMock()
        mock_response.final_output = "Test response"
        mock_runner.return_value = mock_response
        mock_send_sms.return_value = False
        
        result = asyncio.run(run_research_pipeline(
            self.test_symbol, 
            self.test_current_price, 
            self.test_previous_close
        ))
        
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
