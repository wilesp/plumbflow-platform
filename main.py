"""
Best Trade - Main Application  
FINAL FIXED VERSION - Health check + Session + Registration
"""

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import stripe
import secrets
import hashlib
from datetime import datetime, timedelta
import psycopg2.extras

from database import db
from notification_service import notification_service

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")

# ============================================================================
# FRONTEND ROUTES
# ============================================================================

@app.get("/tradesperson-sign-in.html", response_class=HTMLResponse)
async def tradesperson_sign_in():
    return FileResponse("frontend/tradesperson-sign-in.html")

@app.get("/tradesperson-dashboard.html", response_class=HTMLResponse)
async def tradesperson_dashboard():
    return FileResponse("frontend/tradesperson-dashboard.html")

@app.get("/tradesperson-register.html", response_class=HTMLResponse)
async def tradesperson_register():
    return FileResponse("frontend/tradesperson-register.html")

@app.get("/pricing.html", response_class=HTMLResponse)
async def pricing_page():
    return FileResponse("frontend/pricing.html")

@app.get("/customer-post-job.html", response_class=HTMLResponse)
async def customer_post_job():
    return FileResponse("frontend/customer-post-job.html")

@app.get("/", response_class=HTMLResponse)
async def home_page():
    return FileResponse("frontend/index.html")

# ============================================================================
# HEALTH CHECK - FIXED FOR RAILWAY
# ============================================================================

@app.get("/health")
async def health_check():
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except:
        return {"status": "healthy", "database": "disconnected"}

# ============================================================================
# TRADESPERSON REGISTRATION
# ============================================================================

@app.post("/api/register-tradesperson")
async def register_tradesperson(request: Request):
    try:
        data = await request.json()
        
        name = data.get('name') or data.get('full_name') or data.get('contact_name')
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
            data.get('subscription_tier', 'basic')
        ))
        
        result = cursor.fetchone()
        tradesperson_id = result['id']
        
        # Create session immediately
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=30)
        
        cursor.execute("""
            INSERT INTO tradesperson_sessions (
                tradesperson_id, session_token, expires_at,
                ip_address, user_agent, created_at
            ) VALUES (%s, %s, %s, %s, %s, NOW())
        """, (
            tradesperson_id, session_token, expires_at,
            request.client.host, request.headers.get('user-agent', '')
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "tradesperson_id": tradesperson_id,
            "session_token": session_token
        }
        
    except Exception as e:
        print(f"Error registering: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GET CURRENT USER
# ============================================================================

@app.get("/api/tradesperson/me")
async def get_current_tradesperson(request: Request):
    try:
        session_token = request.cookies.get("session_token")
        if not session_token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT t.id, t.name, t.trading_name, t.email, t.phone, t.postcode,
                   t.trade_category, t.subscription_tier, t.subscription_status,
                   t.can_receive_jobs
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
            "id": user["id"],
            "name": user["name"],
            "trading_name": user["trading_name"],
            "email": user["email"],
            "phone": user["phone"],
            "postcode": user["postcode"],
            "trade_category": user["trade_category"],
            "subscription_tier": user["subscription_tier"],
            "subscription_status": user["subscription_status"],
            "can_receive_jobs": user["can_receive_jobs"]
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in /api/tradesperson/me: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# SUBSCRIPTION CREATION
# ============================================================================

@app.post("/api/subscription/create")
async def create_subscription(request: Request):
    try:
        data = await request.json()
        tradesperson_id = data.get('tradesperson_id')
        tier = data.get('tier')
        payment_method_id = data.get('payment_method_id')
        
        price_ids = {
            'basic': 'price_1T9RVDIrb6iFFzVYMd2Uslrv',
            'pro': 'price_1T9RpaIrb6iFFzVYCFezjAHq',
            'premium': 'price_1T9RZAIrb6iFFzVYu8p8tdgb'
        }

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("SELECT email FROM tradespeople WHERE id = %s", (tradesperson_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Tradesperson not found")
        
        email = result['email']
        
        customer = stripe.Customer.create(
            email=email,
            payment_method=payment_method_id,
            invoice_settings={'default_payment_method': payment_method_id}
        )
        
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{'price': price_ids.get(tier, price_ids['basic'])}],
            expand=['latest_invoice.payment_intent']
        )
        
        cursor.execute("""
            UPDATE tradespeople
            SET subscription_status = 'active',
                subscription_tier = %s,
                stripe_customer_id = %s,
                stripe_subscription_id = %s,
                can_receive_jobs = true
            WHERE id = %s
        """, (tier, customer.id, subscription.id, tradesperson_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"success": True, "subscription_id": subscription.id}
        
    except Exception as e:
        print(f"Error creating subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
