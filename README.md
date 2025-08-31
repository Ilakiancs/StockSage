# Stock Tracker

AI-powered stock monitoring system that tracks price movements and sends SMS alerts with market analysis.

## what it does

- monitors selected stocks for significant price changes (>1%)
- sends SMS alerts with AI-generated market analysis when movements occur
- accepts SMS commands to manage your stock list
- runs as a FastAPI web service with Twilio integration

## setup

### requirements
- python 3.11+
- twilio account
- openai api key

### install
```bash
git clone <repo>
cd stock-tracker
pip install -r requirements.txt
```

### environment
create `.env` file:
```env
OPENAI_API_KEY=your-openai-api-key
TWILIO_PHONE_NUMBER=your_twilio_phone_number
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TARGET_PHONE_NUMBER=your_personal_phone_number
WEBHOOK_URL=your_twilio_webhook_url
```

## run

### production
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### test mode
```bash
python main.py -test
```

### research specific stock
```bash
python main.py -test -research AAPL
```

## twilio setup

1. configure twilio webhook to POST to `/receive-message` endpoint
2. set `WEBHOOK_URL` to match your public endpoint URL
3. only messages from `TARGET_PHONE_NUMBER` are processed

## sms commands

- add stock: "start tracking AAPL"
- remove stock: "stop tracking MSFT"  
- list stocks: "what stocks am i tracking?"
- get price: "what is the price of AAPL?"

## docker

```bash
docker build -t stock-tracker .
docker run -p 8000:8000 --env-file .env stock-tracker
```

## how it works

1. background scheduler checks stock prices every hour
2. when price moves >1%, triggers AI research pipeline
3. sends 160-char SMS with market analysis
4. prevents duplicate alerts per day
5. accepts SMS commands to manage stock list

made by ilakiancs