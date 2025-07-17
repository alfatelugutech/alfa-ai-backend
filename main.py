
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ALFA Backend Live"}

@app.post("/api/zerodha/login")
async def login():
    return {"message": "Zerodha login POST route working"}

@app.get("/api/zerodha/funds")
async def funds():
    return {"funds": "₹1,00,000"}

@app.get("/api/zerodha/orders")
async def orders():
    return {"orders": []}

@app.get("/api/zerodha/positions")
async def positions():
    return {"positions": []}
