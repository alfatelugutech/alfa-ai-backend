from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from kiteconnect import KiteConnect
import os

app = FastAPI()

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

kite = KiteConnect(api_key=os.getenv("KITE_API_KEY"))
access_token = None

class TokenRequest(BaseModel):
    request_token: str

@app.get("/")
def home():
    return {"message": "ALFA AI Trading Backend Live"}

@app.post("/api/zerodha/access_token")
def generate_access_token(data: TokenRequest):
    global access_token
    try:
        session = kite.generate_session(data.request_token, api_secret=os.getenv("KITE_API_SECRET"))
        access_token = session["access_token"]
        kite.set_access_token(access_token)
        return {
            "message": "Zerodha access token generated successfully.",
            "user_id": session["user_id"],
            "access_token": session["access_token"],
            "public_token": session["public_token"]
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/zerodha/funds")
def get_funds():
    try:
        if not access_token:
            return {"error": "Access token not set"}
        funds = kite.margins()
        return funds
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/zerodha/positions")
def get_positions():
    try:
        if not access_token:
            return {"error": "Access token not set"}
        positions = kite.positions()
        return positions
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/zerodha/orders")
def get_orders():
    try:
        if not access_token:
            return {"error": "Access token not set"}
        orders = kite.orders()
        return orders
    except Exception as e:
        return {"error": str(e)}
