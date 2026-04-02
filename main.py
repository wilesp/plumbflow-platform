"""
Best Trade - Main Application  
UPDATED: Fixed tradesperson registration to properly handle 'name' column
"""

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import stripe
import secrets
import hashlib
from datetime import datetime, timedelta
import psycopg2.extras

# Import your existing modules
from database import db
from notification_service import notification_service

# Initialize FastAPI
app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stripe configuration
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Mount static files
app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")

# ============================================================================
# FRONTEND PAGE ROUTES
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def home_page():
    try:
        return FileResponse("frontend/index.html")
    except Exception as e:
        return HTMLResponse(f"<h1>Error loading home page</h1><p>{str(e)}</p>", status_code=500)

@app.get("/index.html", response_class=HTMLResponse)
async def index_page():
    return FileResponse("frontend/index.html")

@app.get("/dashboard-login.html", response_class=HTMLResponse)
async def dashboard_login():
    return FileResponse("frontend/dashboard-login.html")

@app.get("/pricing.html", response_class=HTMLResponse)
async def pricing_page():
    return FileResponse("frontend/pricing.html")

@app.get("/about.html", response_class=HTMLResponse)
async def about_page():
    return FileResponse("frontend/about.html")

@app.get("/customer-post-job.html", response_class=HTMLResponse)
async def customer_post_job():
    return FileResponse("frontend/customer-post-job.html")

@app.get("/tradesperson-register.html", response_class=HTMLResponse)
async def tradesperson_register():
    return FileResponse("frontend/tradesperson-register.html")

@app.get("/tradesperson-dashboard.html", response_class=HTMLResponse)
async def tradesperson_dashboard():
    return FileResponse("frontend/tradesperson-dashboard.html")

@app.get("/how-it-works.html", response_class=HTMLResponse)
async def how_it_works():
    return FileResponse("frontend/how-it-works.html")

@app.get("/why-choose-us.html", response_class=HTMLResponse)
async def why_choose_us():
    return FileResponse("frontend/why-choose-us.html")

@app.get("/trust-and-safety.html", response_class=HTMLResponse)
async def trust_and_safety():
    return FileResponse("frontend/trust-and-safety.html")

@app.get("/contact.html", response_class=HTMLResponse)
async def contact_page():
    return FileResponse("frontend/contact.html")

@app.get("/job-submitted.html", response_class=HTMLResponse)
async def job_submitted():
    return FileResponse("frontend/job-submitted.html")

@app.get("/expired-link.html", response_class=HTMLResponse)
async def expired_link():
    return FileResponse("frontend/expired-link.html")

@app.get("/dashboard")
async def dashboard_redirect():
    return RedirectResponse(url="/dashboard-login.html")

# ============================================================================
# TRADESPERSON REGISTRATION - FIXED
# ============================================================================

@app.post("/api/register-tradesperson")
async def register_tradesperson(request: Request):
    try:
        data = await request.json()
        
        # Extract fields with proper fallbacks
        full_name = data.get('name') or data.get('full_name') or data.get('contact_name')
        business_name = data.get('trading_name') or data.get('business_name')
        
        if not full_name:
            raise HTTPException(status_code=400, detail="Full name is required")
        if not business_name:
            raise HTTPException(status_code=400, detail="Business name is required")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            INSERT INTO tradespeople (
                name,                    -- Required NOT NULL column
                trading_name,
                full_name,
                contact_name,
                email,
                phone,
                postcode,
                trade_category,
                subscription_status,
                subscription_tier,
                can_receive_jobs,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, false, NOW()
            )
            RETURNING id
        """, (
            full_name,                    # name
            business_name,                # trading_name
            full_name,                    # full_name
            full_name,                    # contact_name (for compatibility)
            data.get('email'),
            data.get('phone'),
            data.get('postcode'),
            data.get('trade_category'),
            data.get('subscription_tier', 'basic')
        ))
        
        result = cursor.fetchone()
        tradesperson_id = result['id']
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "tradesperson_id": tradesperson_id,
            "message": "Registration successful"
        }
        
    except Exception as e:
        print(f"Error registering tradesperson: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
        
        if not tradesperson_id or not tier or not payment_method_id:
            raise HTTPException(status_code=400, detail="Missing required fields")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("SELECT email FROM tradespeople WHERE id = %s", (tradesperson_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Tradesperson not found")
        
        email = result['email']
        
        price_ids = {
            'basic': 'price_basic_monthly',
            'pro': 'price_pro_monthly',
            'premium': 'price_premium_yearly'
        }
        
        customer = stripe.Customer.create(
            email=email,
            payment_method=payment_method_id,
            invoice_settings={'default_payment_method': payment_method_id}
        )
        
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{'price': price_ids.get(tier, 'price_basic_monthly')}],
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
        
        return {
            "success": True,
            "subscription_id": subscription.id
        }
        
    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error creating subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# OTHER ROUTES (unchanged - kept for completeness)
# ============================================================================

@app.post("/api/auth/send-magic-link")
async def send_magic_link(request: Request):
    # ... your existing magic link code (unchanged)
    pass  # Keep your original implementation

@app.get("/auth/verify")
async def verify_magic_link(token: str, request: Request):
    # ... your existing verify code (unchanged)
    pass

@app.post("/api/customer/post-job")
async def post_job(request: Request):
    # ... your existing post-job code (unchanged)
    pass

@app.post("/api/contact/submit")
async def submit_contact_form(request: Request):
    # ... your existing contact code (unchanged)
    pass

@app.get("/health")
async def health_check():
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "service": "Best Trade API",
        "database": db_status,
        "stripe": "configured" if stripe.api_key else "not configured",
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
