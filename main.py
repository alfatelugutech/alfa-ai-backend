
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ALFA Backend Live"}

@app.post("/api/zerodha/login")
def zerodha_login():
    # This should redirect to Zerodha login URL with your API key
    api_key = "1rjhyd0xb6gkomut"
    redirect_uri = "https://alfa-ai-trading-dashboard.onrender.com/login"
    login_url = f"https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"
    return {"redirect": login_url}

@app.get("/api/zerodha/funds")
def zerodha_funds():
    return {"funds": "₹1,00,000"}

@app.get("/api/zerodha/positions")
def zerodha_positions():
    return {"positions": []}
