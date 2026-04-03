"""
Best Trade - Main Application  
UPDATED: Correct Stripe Price IDs + Fixed Registration + Dashboard Support
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
        
        name = data.get('name') or data.get('full_name') or data.get('contact_name')
        trading_name = data.get('trading_name') or data.get('business_name')
        
        if not name:
            raise HTTPException(status_code=400, detail="Full name is required")
        if not trading_name:
            raise HTTPException(status_code=400, detail="Business name is required")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            INSERT INTO tradespeople (
                name,
                trading_name,
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
                %s, %s, %s, %s, %s, %s, %s, 'pending', %s, false, NOW()
            )
            RETURNING id
        """, (
            name,
            trading_name,
            name,
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
# GET CURRENT TRADESPERSON (for dashboard)
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
                   t.can_receive_jobs, t.created_at
            FROM tradesperson_sessions s
            JOIN tradespeople t ON s.tradesperson_id = t.id
            WHERE s.session_token = %s 
              AND s.expires_at > NOW()
        """, (session_token,))

        user = cursor.fetchone()

        if not user:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=401, detail="Session expired")

        cursor.close()
        conn.close()

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
# SUBSCRIPTION CREATION - FIXED WITH YOUR REAL PRICE IDs
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

        # Your actual Price IDs
        price_ids = {
            'basic': 'price_1T9RVDIrb6iFFzVYMd2Uslrv',   # Best Trade Basic
            'pro': 'price_1T9RpaIrb6iFFzVYCFezjAHq',     # Best Trade Pro
            'premium': 'price_1T9RZAIrb6iFFzVYu8p8tdgb'  # Best Trade Premium
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
# MAGIC LINK AUTHENTICATION (Your original restored)
# ============================================================================

@app.post("/api/auth/send-magic-link")
async def send_magic_link(request: Request):
    try:
        data = await request.json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            SELECT id, trading_name, subscription_status
            FROM tradespeople
            WHERE LOWER(email) = %s
        """, (email,))
        
        result = cursor.fetchone()
        
        if not result:
            return {"success": True, "message": "If that email is registered, we've sent you a login link."}
        
        tradesperson_id = result['id']
        trading_name = result.get('trading_name', 'there')
        subscription_status = result.get('subscription_status')
        
        if subscription_status != 'active':
            raise HTTPException(status_code=403, detail="Your subscription is not active. Please contact support.")
        
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(minutes=15)
        
        ip_address = request.client.host
        user_agent = request.headers.get('user-agent', '')
        
        cursor.execute("""
            INSERT INTO magic_link_tokens (
                tradesperson_id, token, email, expires_at,
                ip_address, user_agent
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (tradesperson_id, token_hash, email, expires_at, ip_address, user_agent))
        
        conn.commit()
        
        app_url = os.getenv('APP_URL', 'https://besttrade.uk')
        magic_link = f"{app_url}/auth/verify?token={token}"
        
        try:
            notification_service.email_service.send_email(
                to_email=email,
                subject="Your Best Trade Dashboard Login Link",
                html_content=f"""
                <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: #1e3a5f; padding: 30px; text-align: center;">
                        <h1 style="color: white; margin: 0;">Best Trade</h1>
                    </div>
                    <div style="padding: 40px 30px;">
                        <h2 style="color: #1e3a5f;">Hi {trading_name},</h2>
                        <p style="font-size: 16px; line-height: 1.6; color: #333;">
                            Click the button below to securely access your dashboard:
                        </p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{magic_link}" style="display: inline-block; background: #1e3a5f; color: white; padding: 16px 40px; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                                Access Dashboard
                            </a>
                        </div>
                    </div>
                </body></html>
                """
            )
        except Exception as e:
            print(f"Error sending email: {str(e)}")
        
        cursor.close()
        conn.close()
        
        return {"success": True, "message": "Check your email for the login link!"}
        
    except Exception as e:
        print(f"Error in send_magic_link: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/verify")
async def verify_magic_link(token: str, request: Request):
    try:
        if not token:
            raise HTTPException(status_code=400, detail="Invalid token")
        
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            SELECT ml.id, ml.tradesperson_id, t.trading_name, t.email,
                   t.subscription_tier, ml.used_at, ml.expires_at
            FROM magic_link_tokens ml
            JOIN tradespeople t ON ml.tradesperson_id = t.id
            WHERE ml.token = %s
        """, (token_hash,))
        
        result = cursor.fetchone()
        
        if not result:
            return HTMLResponse(content="<h1>Invalid or Expired Link</h1><p><a href='/dashboard-login.html'>Request new link</a></p>")
        
        if result.get('used_at') or (result.get('expires_at') and datetime.utcnow() > result['expires_at']):
            return HTMLResponse(content="<h1>Link Expired or Used</h1><p><a href='/dashboard-login.html'>Request new link</a></p>")
        
        cursor.execute("UPDATE magic_link_tokens SET used_at = NOW() WHERE id = %s", (result['id'],))
        conn.commit()
        
        session_token = secrets.token_urlsafe(32)
        cursor.execute("""
            INSERT INTO tradesperson_sessions (tradesperson_id, session_token, expires_at, ip_address, user_agent, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (result['tradesperson_id'], session_token, datetime.utcnow() + timedelta(days=30), request.client.host, request.headers.get('user-agent', '')))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        response = RedirectResponse(url='/tradesperson-dashboard.html')
        response.set_cookie(key='session_token', value=session_token, max_age=30*24*60*60, httponly=True, secure=True, samesite='lax')
        return response
        
    except Exception as e:
        print(f"Error verifying magic link: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# CUSTOMER JOB POSTING
# ============================================================================

@app.post("/api/customer/post-job")
async def post_job(request: Request):
    try:
        data = await request.json()
        
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            INSERT INTO jobs (
                trade_category, job_type, description, urgency,
                postcode, address, customer_name, customer_phone, customer_email,
                status, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', NOW()
            )
            RETURNING id
        """, (
            data['trade_category'],
            data['job_type'],
            data['description'],
            data['urgency'],
            data['postcode'].upper(),
            data.get('address', ''),
            data.get('name', ''),
            data.get('phone', ''),
            data.get('email', '')
        ))
        
        result = cursor.fetchone()
        job_id = result['id']
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"success": True, "job_id": job_id}
        
    except Exception as e:
        print(f"Error posting job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Best Trade API"}

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
