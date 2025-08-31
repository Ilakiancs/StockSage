from agents import Agent, Runner, WebSearchTool
from lib.tools import get_stock_price_info, add_stock_to_tracker, remove_stock_from_tracker, get_stock_tracker_list
from lib.sms import send_sms


message_handler_agent = Agent(
  name="Message Handler Agent",
  instructions="Handle incoming messages from the user and determine the appropriate actions to take. If a message is requesting edits to the tracker list, alwaysr retreive the tracker list first using the 'get_stock_tracker_list' tool to double check for spelling and grammar errors. Respond to the user in a friendly manner. Try to respond in under 160 characters.",
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
  model="gpt-4.1"
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
  print("running agent: ", message)
  response = await Runner.run(message_handler_agent, message)

  return response.final_output

async def run_research_pipeline(stock_symbol: str, current_price: float, previous_close: float) -> str:
  print("running research pipeline: ", stock_symbol)
  response = await Runner.run(stock_research_agent, stock_symbol)

  print("research pipeline response: ", response)

  message_to_summariser = f"""
  {stock_symbol} {current_price / previous_close - 1:.2%}: {response.final_output}
  """

  summariser_response = await Runner.run(summariser_agent, message_to_summariser)

  print("summariser response: ", summariser_response)

  final_output = summariser_response.final_output

  send_sms(final_output)