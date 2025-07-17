from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from kiteconnect import KiteConnect
import os

app = FastAPI()

# Middleware for CORS (allow all for now)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Zerodha credentials from environment variables
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")
kite = KiteConnect(api_key=api_key)


@app.get("/api")
def home():
    return {"message": "ALFA AI Trading Backend Running!"}


@app.get("/api/zerodha/login")
def login():
    login_url = kite.login_url()
    return {"login_url": login_url}


@app.get("/api/zerodha/access_token")
def get_access_token(request: Request):
    try:
        request_token = request.query_params.get("request_token")
        if not request_token:
            return {"error": "Missing request_token from URL."}

        print(f"[DEBUG] Received request_token: {request_token}")

        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        public_token = data["public_token"]
        user_id = data["user_id"]

        # Set the access token for session
        kite.set_access_token(access_token)

        return {
            "message": "Zerodha access token generated successfully.",
            "user_id": user_id,
            "access_token": access_token,
            "public_token": public_token
        }

    except Exception as e:
        print(f"[ERROR] {e}")
        return {"error": str(e)}
