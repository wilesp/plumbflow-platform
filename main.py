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

# ====================== DISTANCE HELPER ======================
def calculate_distance_miles(lat1, lon1, lat2, lon2):
    if not all([lat1, lon1, lat2, lon2]):
        return 9999  # fallback
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

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

        # Create session
        session_token = secrets.token_urlsafe(32)
        cursor.execute("""
            INSERT INTO tradesperson_sessions (tradesperson_id, session_token, expires_at)
            VALUES (%s, %s, NOW() + INTERVAL '30 days')
        """, (tradesperson_id, session_token))

        conn.commit()
        cursor.close()
        conn.close()

        response = Response(content='{"success": true, "tradesperson_id": ' + str(tradesperson_id) + '}', media_type="application/json")
        response.set_cookie(key="session_token", value=session_token, max_age=30*24*60*60, httponly=True, samesite="lax")
        return response

    except Exception as e:
        print(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====================== SUBSCRIPTION CREATE (FIXED) ======================
@app.post("/api/subscription/create")
async def create_subscription(request: Request):
    try:
        data = await request.json()
        tradesperson_id = data.get('tradesperson_id')
        tier = data.get('tier')
        payment_method_id = data.get('payment_method_id')

        if not all([tradesperson_id, tier, payment_method_id]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        # Create Stripe Customer + Subscription
        customer = stripe.Customer.create(
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
            items=[{'price': price_id}],
            expand=['latest_invoice.payment_intent']
        )

        # Update database
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

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Subscription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====================== POST JOB WITH LEAD MATCHING ======================
@app.post("/api/customer/post-job")
async def post_job(request: Request):
    try:
        data = await request.json()

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Insert job
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

        # Match to eligible tradespeople (temporary simple logic - will improve with real coords)
        cursor.execute("""
            SELECT id FROM tradespeople 
            WHERE can_receive_jobs = true 
              AND subscription_status = 'active'
        """)
        trades = cursor.fetchall()

        for t in trades:
            cursor.execute("""
                INSERT INTO pending_leads (job_id, plumber_id, notified_at, notification_method)
                VALUES (%s, %s, NOW(), 'dashboard')
            """, (job_id, t['id']))

        conn.commit()
        cursor.close()
        conn.close()

        return {"success": True, "job_id": job_id}

    except Exception as e:
        print(f"Post job error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
