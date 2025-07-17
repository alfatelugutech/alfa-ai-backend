from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kiteconnect import KiteConnect

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

kite = KiteConnect(api_key="q66ifywyb7vuhyd3")

@app.get("/")
def read_root():
    return {"status": "ALFA Backend Live"}

@app.post("/api/zerodha/login")
def login_to_zerodha():
    login_url = kite.login_url()
    return {"login_url": login_url}
