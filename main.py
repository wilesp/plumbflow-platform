from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import stripe
import secrets
import math
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

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ====================== REGISTRATION ======================
@app.post("/api/register-tradesperson")
async def register_tradesperson(request: Request):
    try:
        data = await request.json()
        
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            INSERT INTO tradespeople (
                trading_name, contact_name, email, phone, postcode,
                trade_category, subscription_tier, subscription_status,
                can_receive_jobs, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', false, NOW())
            RETURNING id
        """, (
            data.get('trading_name'),
            data.get('contact_name'),
            data.get('email'),
            data.get('phone'),
            data.get('postcode'),
            data.get('trade_category'),
            data.get('subscription_tier', 'pro')
        ))
        
        tradesperson_id = cursor.fetchone()['id']

        session_token = secrets.token_urlsafe(32)
        cursor.execute("""
            INSERT INTO tradesperson_sessions (tradesperson_id, session_token, expires_at)
            VALUES (%s, %s, NOW() + INTERVAL '30 days')
        """, (tradesperson_id, session_token))

        conn.commit()
        cursor.close()
        conn.close()

        response = Response(
            content=f'{{"success": true, "tradesperson_id": "{tradesperson_id}"}}', 
            media_type="application/json"
        )
        response.set_cookie(key="session_token", value=session_token, max_age=30*24*60*60, httponly=True, samesite="lax")
        return response

    except Exception as e:
        print(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====================== SIGN IN ======================
@app.post("/api/auth/signin")
async def simple_signin(request: Request):
    try:
        data = await request.json()
        email = data.get('email', '').strip().lower()
        print(f"Signin attempt for email: '{email}'")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
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

        session_token = secrets.token_urlsafe(32)
        cursor.execute("""
            INSERT INTO tradesperson_sessions (tradesperson_id, session_token, expires_at)
            VALUES (%s, %s, NOW() + INTERVAL '30 days')
        """, (tradesperson_id, session_token))

        conn.commit()
        cursor.close()
        conn.close()

        response = Response(content='{"success": true}', media_type="application/json")
        response.set_cookie(key="session_token", value=session_token, max_age=30*24*60*60, httponly=True, samesite="lax")
        return response

    except Exception as e:
        print(f"Signin error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====================== DASHBOARD ME ======================
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
            "trading_name": user.get("trading_name") or "Trader",
            "subscription_tier": user.get("subscription_tier"),
            "subscription_status": user.get("subscription_status")
        }

    except Exception as e:
        print(f"Dashboard me error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ====================== SUBSCRIPTION CREATE ======================
@app.post("/api/subscription/create")
async def create_subscription(request: Request):
    try:
        data = await request.json()
        tradesperson_id = str(data.get('tradesperson_id'))
        tier = data.get('tier')
        payment_method_id = data.get('payment_method_id')

        if not all([tradesperson_id, tier, payment_method_id]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT trading_name, email FROM tradespeople WHERE id = %s", (tradesperson_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            raise HTTPException(status_code=404, detail="Tradesperson not found")

        customer = stripe.Customer.create(
            name=user['trading_name'],
            email=user['email'],
            payment_method=payment_method_id,
            invoice_settings={'default_payment_method': payment_method_id}
        )

        price_id = {
            'basic': 'price_1T9RVDIrb6iFFzVYMd2Uslrv',
            'pro': 'price_1T9RpaIrb6iFFzVYCFezjAHq',
            'premium': 'price_1T9RZAIrb6iFFzVYu8p8tdgb'
        }.get(tier.lower())

        if not price_id:
            raise HTTPException(status_code=400, detail="Invalid tier")

        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{'price': price_id}]
        )

        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tradespeople 
            SET stripe_customer_id = %s,
                stripe_subscription_id = %s,
                subscription_status = 'active',
                subscription_start_date = NOW()
            WHERE id = %s
        """, (customer.id, subscription.id, tradesperson_id))
        conn.commit()
        cursor.close()
        conn.close()

        return {"success": True}

    except Exception as e:
        print(f"Subscription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====================== POST JOB - FIXED ======================
@app.post("/api/customer/post-job")
async def post_job(request: Request):
    try:
        data = await request.json()

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Insert the job
        cursor.execute("""
            INSERT INTO jobs (
                trade_category, job_type, description, urgency,
                postcode, address, customer_name, customer_phone, customer_email, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')
            RETURNING id
        """, (
            data.get('trade_category'),
            data.get('job_type'),
            data.get('description'),
            data.get('urgency'),
            data.get('postcode'),
            data.get('address'),
            data.get('customer_name'),
            data.get('phone'),
            data.get('email')
        ))

        job_id = cursor.fetchone()['id']

        # Insert pending leads for all active tradespeople
        cursor.execute("""
            INSERT INTO pending_leads (job_id, plumber_id, notified_at, notification_method)
            SELECT %s, t.id, NOW(), 'dashboard'
            FROM tradespeople t
            WHERE t.can_receive_jobs = true 
              AND t.subscription_status = 'active'
            ON CONFLICT (job_id, plumber_id) DO NOTHING
        """, (job_id,))

        inserted_count = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        print(f"Job {job_id} posted successfully. Inserted {inserted_count} pending leads.")

        return {
            "success": True, 
            "job_id": job_id, 
            "matched_tradespeople": inserted_count
        }

    except Exception as e:
        print(f"Post job error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
