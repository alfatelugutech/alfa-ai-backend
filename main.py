
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from kiteconnect import KiteConnect
import os

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

kite = None

class LoginRequest(BaseModel):
    api_key: str
    api_secret: str

class AccessTokenRequest(BaseModel):
    request_token: str
    api_key: str
    api_secret: str

@app.post("/api/zerodha/login")
def login_zerodha(data: LoginRequest):
    global kite
    kite = KiteConnect(api_key=data.api_key)
    login_url = kite.login_url()
    return {"login_url": login_url}

@app.post("/api/zerodha/access_token")
def generate_access_token(data: AccessTokenRequest):
    global kite
    if kite is None:
        kite = KiteConnect(api_key=data.api_key)
    try:
        session_data = kite.generate_session(data.request_token, api_secret=data.api_secret)
        kite.set_access_token(session_data["access_token"])
        return {
            "message": "Zerodha access token generated successfully.",
            "user_id": session_data["user_id"],
            "access_token": session_data["access_token"],
            "public_token": session_data["public_token"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/zerodha/funds")
def get_funds():
    try:
        profile = kite.profile()
        funds = kite.margins()
        return {"profile": profile, "funds": funds}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
