# ALFA AI Backend (Render Ready with app.py)

This version uses `app.py` as the FastAPI entry point for Render deployment.

## To Deploy:
1. Push this repo to GitHub.
2. Connect GitHub repo to Render.
3. It will run `uvicorn app:app` using Python 3.11.9.
4. Compatible `pandas==1.5.3` included (no gcc error).

Check `/` endpoint after deploy to confirm success.
