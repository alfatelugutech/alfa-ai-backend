
from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from kiteconnect import KiteConnect
import os, json

app = FastAPI()

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Zerodha API credentials
API_KEY = "lrihyd0xb6gkomut"
API_SECRET = "k9knkh0deaguzg9ubcspvtajygu9j1uh"
kite = KiteConnect(api_key=API_KEY)

# Store access token
TOKEN_PATH = "access_token.json"

@app.get("/")
def root():
    return {"status": "Backend with KiteConnect ready."}

@app.get("/api/zerodha/login")
def zerodha_login():
    url = kite.login_url()
    return {"login_url": url}

@app.get("/api/zerodha/access_token")
def generate_access_token(request_token: str = Query(...)):
    try:
        data = kite.generate_session(request_token, api_secret=API_SECRET)
        kite.set_access_token(data["access_token"])
        with open(TOKEN_PATH, "w") as f:
            json.dump(data, f)
        return {"status": "access_token_saved", "token": data["access_token"]}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/order/place")
async def place_order(req: Request):
    try:
        body = await req.json()
        with open(TOKEN_PATH, "r") as f:
            saved = json.load(f)
            kite.set_access_token(saved["access_token"])

        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange="NSE",
            tradingsymbol=body.get("symbol", "RELIANCE"),
            transaction_type=kite.TRANSACTION_TYPE_BUY if body.get("side", "BUY") == "BUY" else kite.TRANSACTION_TYPE_SELL,
            quantity=1,
            product=kite.PRODUCT_MIS,
            order_type=kite.ORDER_TYPE_MARKET
        )
        return {"status": "order_placed", "order_id": order_id}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/token/refresh")
def refresh_token():
    try:
        with open(TOKEN_PATH, "r") as f:
            data = json.load(f)
        return {"status": "token_valid", "token": data["access_token"]}
    except:
        return {"status": "no_token_found"}
