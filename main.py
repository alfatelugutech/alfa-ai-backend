
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import datetime

app = FastAPI()

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "Backend is running!"}

@app.get("/api/positions")
def get_positions():
    return [{"symbol": "RELIANCE", "qty": 10, "pnl": 1200}, {"symbol": "TCS", "qty": 5, "pnl": -350}]

@app.get("/api/trades")
def get_trades():
    return [{"id": "T001", "symbol": "RELIANCE", "type": "BUY", "pnl": 1200},
            {"id": "T002", "symbol": "TCS", "type": "SELL", "pnl": -350}]

@app.get("/api/scanner")
def market_scanner():
    return [{"symbol": "WIPRO", "signal": "BUY"}, {"symbol": "HDFCBANK", "signal": "SELL"}]

@app.post("/api/order/place")
async def place_order(data: Request):
    body = await data.json()
    return {"status": "order placed", "symbol": body.get("symbol", ""), "side": body.get("side", "BUY")}

@app.get("/api/zerodha/generate_token")
def gen_token():
    return {"token": "example_zerodha_token", "status": "success"}

@app.get("/api/token/refresh")
def refresh_token():
    return {"status": "refreshed", "time": datetime.datetime.now().isoformat()}
