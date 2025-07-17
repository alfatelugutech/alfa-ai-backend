
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from kiteconnect import KiteConnect
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

kite = KiteConnect(api_key=os.getenv("API_KEY"))
access_token_store = {}

@app.get("/api/zerodha/access_token")
async def generate_access_token(request: Request):
    try:
        request_token = request.query_params.get("request_token")
        data = kite.generate_session(request_token, api_secret=os.getenv("API_SECRET"))
        kite.set_access_token(data["access_token"])
        access_token_store["access_token"] = data["access_token"]
        return {
            "message": "Zerodha access token generated successfully.",
            "user_id": data["user_id"],
            "access_token": data["access_token"],
            "public_token": data["public_token"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/zerodha/funds")
async def get_funds():
    try:
        kite.set_access_token(access_token_store.get("access_token"))
        funds = kite.margins()
        return funds
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/zerodha/positions")
async def get_positions():
    try:
        kite.set_access_token(access_token_store.get("access_token"))
        positions = kite.positions()
        return positions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/zerodha/orders")
async def get_orders():
    try:
        kite.set_access_token(access_token_store.get("access_token"))
        orders = kite.orders()
        return orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
