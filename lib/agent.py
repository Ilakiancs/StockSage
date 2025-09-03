from agents import Agent, Runner, WebSearchTool
from lib.tools import get_stock_price_info, add_stock_to_tracker, remove_stock_from_tracker, get_stock_tracker_list
from lib.sms import send_sms
import logging
from lib.logging_config import StockTrackingLogger, log_performance

logger = logging.getLogger(__name__)
stock_logger = StockTrackingLogger()

message_handler_agent = Agent(
  name="Message Handler Agent",
  instructions="Handle incoming messages from the user and determine the appropriate actions to take. If a message is requesting edits to the tracker list, always retrieve the tracker list first using the 'get_stock_tracker_list' tool to double check for spelling and grammar errors. Respond to the user in a friendly manner. Try to respond in under 160 characters.",
  tools=[
    get_stock_price_info,
    add_stock_to_tracker,
    remove_stock_from_tracker,
    get_stock_tracker_list
  ],
  model="gpt-4o-mini",

)


stock_research_agent = Agent(
  name="Stock Research Agent",
  instructions="""
  You are a Stock Market Researcher. Your job is to research the current news around a specific stock and determine what may have caused recent price movements in the past 24 hours specifically. You have access to be able to retreive the stock price and research via the internet using your tools.

  The stock that you are being asked to research has moved within the past 24 hours which has caused an automation to trigger your research. Make sure you have an explanation for the movement in the stock price.

  You should use the get_stock_price_info tool to check the stock price information for the current price and the previous close to make sure your information is accurate.

  Output: Your final_output should be a short summary of your findings that is no longer than 160 characters.
  """,
  tools=[
    get_stock_price_info,
    WebSearchTool()
  ],
  model="gpt-4o-mini"  # Changed from "gpt-4.1" which doesn't exist
)

summariser_agent = Agent(
  name="Summariser Agent",
  instructions="""
  You are a Summariser Agent. Your job is to summarise the information provided to you in a concise manner. Your summary should be no longer than 160 characters.
  OUTPUT: You should write a message to the user as if you were making them aware of the price change and the potential reasons behind it. The start of your message should be "(symbol) DOWN/UP (percentage change)%: "
  """,
  model="gpt-4o-mini"
)

async def handle_incoming_message(message: str) -> str:
    """
    Handle incoming SMS messages with error handling
    
    Args:
        message: The incoming message text
        
    Returns:
        str: Response message to send back
    """
    try:
        if not message or not isinstance(message, str):
            return "Sorry, I didn't understand that message."
            
        message = message.strip()
        if not message:
            return "Please send a non-empty message."
            
        logger.info(f"Processing message: {message}")
        
        response = await Runner.run(message_handler_agent, message)
        
        if not response or not hasattr(response, 'final_output'):
            logger.error("No valid response from message handler agent")
            return "Sorry, I'm having trouble processing your request right now."
            
        result = response.final_output or "Sorry, I couldn't process your request."
        logger.info(f"Message handler response: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error handling incoming message '{message}': {e}")
        return "Sorry, I encountered an error processing your message."

@log_performance("research_pipeline")
async def run_research_pipeline(stock_symbol: str, current_price: float, previous_close: float, priority: str = "normal") -> bool:
    """
    Run the research pipeline for a stock with error handling
    
    Args:
        stock_symbol: Stock symbol to research
        current_price: Current stock price
        previous_close: Previous close price
        priority: Priority level (low, normal, high)
        
    Returns:
        bool: True if pipeline completed successfully, False otherwise
    """
    try:
        if not stock_symbol or not isinstance(stock_symbol, str):
            logger.error(f"Invalid stock symbol: {stock_symbol}")
            return False
            
        if current_price <= 0 or previous_close <= 0:
            logger.error(f"Invalid prices for {stock_symbol}: current={current_price}, previous={previous_close}")
            return False
            
        stock_symbol = stock_symbol.strip().upper()
        logger.info(f"Running research pipeline for {stock_symbol} (priority: {priority})")
        
        # Log the price information
        stock_logger.log_price_check(stock_symbol, current_price, previous_close)
        
        # Adjust research depth based on priority
        research_instruction = stock_research_agent.instructions
        if priority == "high":
            research_instruction += " This is a HIGH PRIORITY alert with significant price movement. Provide detailed analysis."
        elif priority == "low":
            research_instruction += " This is a low priority alert. Provide brief analysis."
        
        # Temporarily update agent instructions
        original_instructions = stock_research_agent.instructions
        stock_research_agent.instructions = research_instruction
        
        # Run stock research agent
        try:
            logger.debug(f"Starting research agent for {stock_symbol}")
            response = await Runner.run(stock_research_agent, stock_symbol)
            
            if not response or not hasattr(response, 'final_output'):
                logger.error(f"No valid response from research agent for {stock_symbol}")
                return False
                
            research_output = response.final_output
            logger.info(f"Research completed for {stock_symbol}: {research_output[:100]}...")
            
        except Exception as e:
            logger.error(f"Error in research agent for {stock_symbol}: {e}")
            research_output = "Market research unavailable"
        finally:
            # Restore original instructions
            stock_research_agent.instructions = original_instructions

        # Calculate percentage change
        percentage_change = (current_price / previous_close - 1) * 100
        
        # Prepare message for summariser with priority context
        priority_prefix = {
            "high": "🚨 URGENT",
            "normal": "",
            "low": "ℹ️"
        }.get(priority, "")
        
        message_to_summariser = f"""
        {priority_prefix} {stock_symbol} {percentage_change:+.2f}%: {research_output}
        """

        # Run summariser agent
        try:
            logger.debug(f"Starting summariser agent for {stock_symbol}")
            summariser_response = await Runner.run(summariser_agent, message_to_summariser)
            
            if not summariser_response or not hasattr(summariser_response, 'final_output'):
                logger.error(f"No valid response from summariser agent for {stock_symbol}")
                # Fallback message
                direction = "UP" if percentage_change > 0 else "DOWN"
                final_output = f"{priority_prefix} {stock_symbol} {direction} {abs(percentage_change):.1f}%: {research_output[:100]}"
            else:
                final_output = summariser_response.final_output
                
            logger.info(f"Summary generated for {stock_symbol}: {final_output}")
            
        except Exception as e:
            logger.error(f"Error in summariser agent for {stock_symbol}: {e}")
            # Fallback message
            direction = "UP" if percentage_change > 0 else "DOWN"
            final_output = f"{priority_prefix} {stock_symbol} {direction} {abs(percentage_change):.1f}%: Price movement detected"

        # Log alert details
        stock_logger.log_alert_sent(stock_symbol, final_output)

        # Send SMS
        try:
            if send_sms(final_output):
                logger.info(f"Alert sent successfully for {stock_symbol}")
                return True
            else:
                logger.error(f"Failed to send SMS alert for {stock_symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending SMS for {stock_symbol}: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Critical error in research pipeline for {stock_symbol}: {e}")
        return False