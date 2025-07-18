
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Valid symbols list
VALID_SYMBOLS = ["RELIANCE.NS", "SBIN.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]

@app.get("/api/ai-trading/start")
async def start_ai_trading():
    # Dummy simulation that avoids invalid symbols
    log = []
    for symbol in VALID_SYMBOLS:
        log.append(f"AI signal executed for: {symbol}")
    return {"status": "AI Trading Started", "log": log}

@app.get("/api/ai-trading/settings")
async def ai_settings():
    return {"capital": 1000000, "risk": "Low", "mode": "paper"}

@app.get("/api/market-overview")
async def market_overview():
    return {"nifty_trend": "sideways", "volume": "normal", "timestamp": str(datetime.datetime.now())}

@app.get("/api/status")
async def api_status():
    return {"status": "OK", "time": str(datetime.datetime.now())}
