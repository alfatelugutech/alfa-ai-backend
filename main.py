
from fastapi import FastAPI, Request
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

API_KEY = "lrihyd0xb6gkomut"
API_SECRET = "k9knkh0deaguzg9ubcspvtajygu9j1uh"
kite = KiteConnect(api_key=API_KEY)

access_token = None

@app.get("/")
def read_root():
    return {"status": "Backend is running!"}

@app.get("/api/zerodha/login")
def zerodha_login():
    login_url = kite.login_url()
    return {"login_url": login_url}

@app.get("/api/zerodha/access_token")
def get_access_token(request_token: str):
    global access_token
    try:
        session_data = kite.generate_session(request_token, api_secret=API_SECRET)
        access_token = session_data["access_token"]
        kite.set_access_token(access_token)
        return {"message": "Access token acquired", "access_token": access_token}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/order/place")
async def place_order(request: Request):
    if not access_token:
        return {"error": "Access token not set"}
    data = await request.json()
    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NSE,
            tradingsymbol=data["symbol"],
            transaction_type=data["side"],
            quantity=int(data["qty"]),
            product=kite.PRODUCT_MIS,
            order_type=kite.ORDER_TYPE_MARKET,
        )
        return {"message": "Order placed", "order_id": order_id}
    except Exception as e:
        return {"error": str(e)}
