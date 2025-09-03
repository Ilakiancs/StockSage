# Stock Tracker

A simple stock monitoring system that tracks price movements and sends SMS alerts.

## Features

- Monitor selected stocks for price changes
- Send SMS alerts when movements occur
- Accept SMS commands to manage stock list
- FastAPI web service with Twilio integration

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Create `.env` file with your API keys
3. Run: `python main.py`

## Usage

- Add stock: "start tracking AAPL"
- Remove stock: "stop tracking MSFT"
- List stocks: "what stocks am i tracking?"
- Get price: "what is the price of AAPL?"

## Environment Variables

```
OPENAI_API_KEY=your-openai-api-key
TWILIO_PHONE_NUMBER=your_twilio_phone_number
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TARGET_PHONE_NUMBER=your_personal_phone_number
WEBHOOK_URL=your_twilio_webhook_url
```

## Running

```bash
# Start service
python service_control.py start

# Test mode
python main.py -test

# Manual
uvicorn main:app --host 0.0.0.0 --port 8000
```

Made by ilakiancs