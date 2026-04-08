from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import stripe
import secrets
from datetime import datetime, timedelta
import psycopg2.extras

from database import db

app = FastAPI(title="Best Trade")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")

# ====================== PAGE ROUTES ======================

@app.get("/", response_class=HTMLResponse)
async def home():
    return FileResponse("frontend/index.html")

@app.get("/tradesperson-register.html", response_class=HTMLResponse)
async def register_page():
    return FileResponse("frontend/tradesperson-register.html")

@app.get("/tradesperson-dashboard.html", response_class=HTMLResponse)
async def dashboard_page():
    return FileResponse("frontend/tradesperson-dashboard.html")

@app.get("/tradesperson-sign-in.html", response_class=HTMLResponse)
async def signin_page():
    return FileResponse("frontend/tradesperson-sign-in.html")

@app.get("/pricing.html", response_class=HTMLResponse)
async def pricing_page():
    return FileResponse("frontend/pricing.html")

@app.get("/customer-post-job.html", response_class=HTMLResponse)
async def post_job_page():
    return FileResponse("frontend/customer-post-job.html")

@app.get("/job-submitted.html", response_class=HTMLResponse)
async def job_submitted():
    return FileResponse("frontend/job-submitted.html")

# ====================== HEALTH ======================

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ====================== REGISTRATION ======================

@app.post("/api/register-tradesperson")
async def register_tradesperson(request: Request):
    try:
        data = await request.json()
        
        name = data.get('name') or data.get('full_name')
        trading_name = data.get('trading_name') or data.get('business_name')

        if not name or not trading_name:
            raise HTTPException(status_code=400, detail="Name and business name required")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            INSERT INTO tradespeople (
                name, trading_name, contact_name, email, phone, postcode,
                trade_category, subscription_status, subscription_tier,
                can_receive_jobs, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s, false, NOW())
            RETURNING id
        """, (
            name, trading_name, name, data.get('email'), data.get('phone'),
            data.get('postcode'), data.get('trade_category'),
            data.get('subscription_tier', 'pro')
        ))

        result = cursor.fetchone()
        tradesperson_id = result['id']

        # Clean old sessions
        cursor.execute("DELETE FROM tradesperson_sessions WHERE tradesperson_id = %s", (tradesperson_id,))

        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=30)

        cursor.execute("""
            INSERT INTO tradesperson_sessions (
                tradesperson_id, session_token, expires_at,
                ip_address, user_agent, created_at
            ) VALUES (%s, %s, %s, %s, %s, NOW())
        """, (tradesperson_id, session_token, expires_at, request.client.host, request.headers.get('user-agent', '')))

        conn.commit()
        cursor.close()
        conn.close()

        response = Response(content='{"success": True, "tradesperson_id": ' + str(tradesperson_id) + '}', media_type="application/json")
        response.set_cookie(
            key="session_token",
            value=session_token,
            max_age=30*24*60*60,
            httponly=True,
            secure=False,
            samesite="lax"
        )
        return response

    except Exception as e:
        print(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================== SIGN IN - FIXED ======================

@app.post("/api/auth/signin")
async def simple_signin(request: Request):
    try:
        data = await request.json()
        email = data.get('email', '').strip().lower()
        
        print(f"Signin attempt for email: '{email}'")

        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Simple query using the 'email' column
        cursor.execute("""
            SELECT id, trading_name 
            FROM tradespeople 
            WHERE LOWER(email) = %s
        """, (email,))
        
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            print(f"User not found for email: {email}")
            raise HTTPException(status_code=404, detail="Email not found. Please register first.")

        tradesperson_id = user['id']
        print(f"User found - ID: {tradesperson_id}")

        # Create new session
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=30)

        cursor.execute("""
            INSERT INTO tradesperson_sessions (
                tradesperson_id, session_token, expires_at,
                ip_address, user_agent, created_at
            ) VALUES (%s, %s, %s, %s, %s, NOW())
        """, (tradesperson_id, session_token, expires_at, request.client.host, request.headers.get('user-agent', '')))

        conn.commit()
        cursor.close()
        conn.close()

        response = Response(content='{"success": True}', media_type="application/json")
        response.set_cookie(
            key="session_token",
            value=session_token,
            max_age=30*24*60*60,
            httponly=True,
            secure=False,
            samesite="lax"
        )
        return response

    except Exception as e:
        print(f"Signin error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================== DASHBOARD DATA ======================

@app.get("/api/tradesperson/me")
async def get_current_tradesperson(request: Request):
    try:
        session_token = request.cookies.get("session_token")
        if not session_token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT t.trading_name, t.subscription_tier, t.subscription_status
            FROM tradesperson_sessions s
            JOIN tradespeople t ON s.tradesperson_id = t.id
            WHERE s.session_token = %s AND s.expires_at > NOW()
        """, (session_token,))

        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            raise HTTPException(status_code=401, detail="Session expired")

        return {
            "success": True,
            "trading_name": user["trading_name"] or "Trader",
            "subscription_tier": user["subscription_tier"],
            "subscription_status": user["subscription_status"]
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Dashboard me error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
