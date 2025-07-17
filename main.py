
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from kiteconnect import KiteConnect
import os

app = FastAPI()

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Zerodha credentials (hardcoded for now)
API_KEY = "q66ifywyb7vuhyd3"
API_SECRET = "ajxv35qaskjvnw6e00mwbwwi1v4os602"
kite = KiteConnect(api_key=API_KEY)
access_token = ""

@app.get("/")
def root():
    return {"status": "Backend is running!"}

@app.get("/api/zerodha/access_token")
def generate_token(action: str, type: str, status: str, request_token: str):
    global access_token
    try:
        session = kite.generate_session(request_token, api_secret=API_SECRET)
        access_token = session["access_token"]
        kite.set_access_token(access_token)
        return {
            "message": "Zerodha access token generated successfully.",
            "user_id": session["user_id"],
            "access_token": session["access_token"],
            "public_token": session["public_token"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/zerodha/funds")
def get_funds():
    try:
        kite.set_access_token(access_token)
        funds = kite.margins()
        return funds
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
