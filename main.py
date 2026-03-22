"""
Best Trade - Main Application
Complete backend with email magic link authentication
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
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

# ============================================================================
# ROOT ROUTES
# ============================================================================

@app.get("/")
async def read_root():
    return FileResponse("frontend/index.html")

@app.get("/dashboard")
async def dashboard_redirect():
    """Redirect old /dashboard to new email login"""
    return RedirectResponse(url="/dashboard-login.html")

# ============================================================================
# EMAIL MAGIC LINK AUTHENTICATION (NEW!)
# ============================================================================

@app.post("/api/auth/send-magic-link")
async def send_magic_link(request: Request):
    """
    Send email-based magic link for dashboard access
    More secure than SMS - no URL blocking, better token security
    """
    try:
        data = await request.json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Find tradesperson by email
        cursor.execute("""
            SELECT id, trading_name, subscription_status
            FROM tradespeople
            WHERE LOWER(email) = %s
        """, (email,))
        
        result = cursor.fetchone()
        
        if not result:
            # Don't reveal if email exists (security best practice)
            return {
                "success": True,
                "message": "If that email is registered, we've sent you a login link."
            }
        
        tradesperson_id, trading_name, subscription_status = result
        
        # Check if subscription is active
        if subscription_status != 'active':
            raise HTTPException(
                status_code=403,
                detail="Your subscription is not active. Please contact support."
            )
        
        # Generate secure random token
        token = secrets.token_urlsafe(32)  # 256-bit security
        
        # Hash token for storage (defense in depth)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Token expires in 15 minutes (short-lived for security)
        expires_at = datetime.utcnow() + timedelta(minutes=15)
        
        # Get request info for audit
        ip_address = request.client.host
        user_agent = request.headers.get('user-agent', '')
        
        # Store token
        cursor.execute("""
            INSERT INTO magic_link_tokens (
                tradesperson_id, token, email, expires_at,
                ip_address, user_agent
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            tradesperson_id,
            token_hash,
            email,
            expires_at,
            ip_address,
            user_agent
        ))
        
        conn.commit()
        
        # Create magic link URL
        app_url = os.getenv('APP_URL', 'https://besttrade.uk')
        magic_link = f"{app_url}/auth/verify?token={token}"
        
        # Send email
        try:
            notification_service.email_service.send_email(
                to_email=email,
                subject="Your Best Trade Dashboard Login Link",
                html_content=f"""
                <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: #1e3a5f; padding: 30px; text-align: center;">
                        <h1 style="color: white; margin: 0;">Best Trade</h1>
                    </div>
                    
                    <div style="padding: 40px 30px;">
                        <h2 style="color: #1e3a5f;">Hi {trading_name},</h2>
                        
                        <p style="font-size: 16px; line-height: 1.6; color: #333;">
                            Click the button below to securely access your dashboard:
                        </p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{magic_link}" 
                               style="display: inline-block; background: #1e3a5f; color: white; 
                                      padding: 16px 40px; text-decoration: none; border-radius: 6px;
                                      font-weight: 600; font-size: 16px;">
                                Access Dashboard
                            </a>
                        </div>
                        
                        <p style="font-size: 14px; color: #666; line-height: 1.6;">
                            <strong>Security Note:</strong><br>
                            • This link expires in 15 minutes<br>
                            • Can only be used once<br>
                            • If you didn't request this, please ignore
                        </p>
                        
                        <p style="font-size: 12px; color: #999; margin-top: 30px;">
                            Or copy this link: {magic_link}
                        </p>
                    </div>
                    
                    <div style="background: #f9fafb; padding: 20px; text-align: center; 
                                font-size: 12px; color: #666;">
                        © 2025 Best Trade. All rights reserved.
                    </div>
                </body>
                </html>
                """
            )
            
        except Exception as e:
            print(f"Error sending magic link email: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to send email. Please try again."
            )
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "message": "Check your email for the login link!"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in send_magic_link: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/verify")
async def verify_magic_link(token: str, request: Request):
    """
    Verify magic link token and create session
    """
    try:
        if not token:
            raise HTTPException(status_code=400, detail="Invalid token")
        
        # Hash token for lookup
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Find valid token
        cursor.execute("""
            SELECT ml.id, ml.tradesperson_id, t.trading_name, t.email,
                   t.subscription_tier, ml.used_at, ml.expires_at
            FROM magic_link_tokens ml
            JOIN tradespeople t ON ml.tradesperson_id = t.id
            WHERE ml.token = %s
        """, (token_hash,))
        
        result = cursor.fetchone()
        
        if not result:
            return HTMLResponse(content="""
                <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #991b1b;">Invalid or Expired Link</h1>
                    <p>This login link is invalid or has expired.</p>
                    <p><a href="/dashboard-login.html">Request a new login link</a></p>
                </body>
                </html>
            """)
        
        token_id, tradesperson_id, trading_name, email, tier, used_at, expires_at = result
        
        # Check if already used
        if used_at:
            return HTMLResponse(content="""
                <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #991b1b;">Link Already Used</h1>
                    <p>This link has already been used.</p>
                    <p><a href="/dashboard-login.html">Request a new login link</a></p>
                </body>
                </html>
            """)
        
        # Check if expired
        if datetime.utcnow() > expires_at:
            return HTMLResponse(content="""
                <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #991b1b;">Link Expired</h1>
                    <p>This link has expired (15 minute limit).</p>
                    <p><a href="/dashboard-login.html">Request a new login link</a></p>
                </body>
                </html>
            """)
        
        # Mark token as used
        cursor.execute("""
            UPDATE magic_link_tokens
            SET used_at = NOW()
            WHERE id = %s
        """, (token_id,))
        
        conn.commit()
        
        # Create session token (long-lived, 30 days)
        session_token = secrets.token_urlsafe(32)
        session_expires = datetime.utcnow() + timedelta(days=30)
        
        cursor.execute("""
            INSERT INTO tradesperson_sessions (
                tradesperson_id, session_token, expires_at,
                ip_address, user_agent, created_at
            ) VALUES (%s, %s, %s, %s, %s, NOW())
        """, (
            tradesperson_id,
            session_token,
            session_expires,
            request.client.host,
            request.headers.get('user-agent', '')
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Redirect to dashboard with session cookie
        response = RedirectResponse(url='/tradesperson-dashboard.html')
        response.set_cookie(
            key='session_token',
            value=session_token,
            max_age=30 * 24 * 60 * 60,  # 30 days
            httponly=True,
            secure=True,
            samesite='lax'
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error verifying magic link: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# TRADESPERSON REGISTRATION & SUBSCRIPTION
# ============================================================================

@app.post("/api/register-tradesperson")
async def register_tradesperson(request: Request):
    """Register a new tradesperson"""
    try:
        data = await request.json()
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Insert tradesperson
        cursor.execute("""
            INSERT INTO tradespeople (
                trading_name, contact_name, email, phone, postcode,
                trade_category, subscription_status, subscription_tier,
                can_receive_jobs, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, false, NOW())
            RETURNING id
        """, (
            data.get('business_name'),
            data.get('contact_name'),
            data.get('email'),
            data.get('phone'),
            data.get('postcode'),
            data.get('trade_category'),
            data.get('subscription_tier', 'basic')
        ))
        
        tradesperson_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "tradesperson_id": tradesperson_id
        }
        
    except Exception as e:
        print(f"Error registering tradesperson: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/subscription/create")
async def create_subscription(request: Request):
    """Create Stripe subscription"""
    try:
        data = await request.json()
        tradesperson_id = data.get('tradesperson_id')
        tier = data.get('tier')
        payment_method_id = data.get('payment_method_id')
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Get tradesperson email
        cursor.execute("SELECT email FROM tradespeople WHERE id = %s", (tradesperson_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Tradesperson not found")
        
        email = result[0]
        
        # Price IDs (update these with your actual Stripe price IDs)
        price_ids = {
            'basic': 'price_basic_monthly',
            'pro': 'price_pro_monthly',
            'premium': 'price_premium_yearly'
        }
        
        # Create Stripe customer
        customer = stripe.Customer.create(
            email=email,
            payment_method=payment_method_id,
            invoice_settings={'default_payment_method': payment_method_id}
        )
        
        # Create subscription
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{'price': price_ids.get(tier, 'price_basic_monthly')}],
            expand=['latest_invoice.payment_intent']
        )
        
        # Update database
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


@app.post("/api/tradesperson/create-session")
async def create_tradesperson_session(request: Request, response: Response):
    """Create session cookie for auto-login after registration"""
    try:
        data = await request.json()
        tradesperson_id = data.get('tradesperson_id')
        
        # Create session token
        session_token = secrets.token_urlsafe(32)
        session_expires = datetime.utcnow() + timedelta(days=30)
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tradesperson_sessions (
                tradesperson_id, session_token, expires_at,
                ip_address, user_agent, created_at
            ) VALUES (%s, %s, %s, %s, %s, NOW())
        """, (
            tradesperson_id,
            session_token,
            session_expires,
            request.client.host,
            request.headers.get('user-agent', '')
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Set cookie
        response.set_cookie(
            key='session_token',
            value=session_token,
            max_age=30 * 24 * 60 * 60,
            httponly=True,
            secure=True,
            samesite='lax'
        )
        
        return {"success": True}
        
    except Exception as e:
        print(f"Error creating session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# CUSTOMER JOB POSTING
# ============================================================================

@app.post("/api/customer/post-job")
async def post_job(request: Request):
    """Customer posts a job - creates job and matches to tradespeople"""
    try:
        data = await request.json()
        
        # Validate required fields
        required_fields = ['trade_category', 'job_type', 'description', 'urgency', 
                          'postcode', 'name', 'phone']
        
        for field in required_fields:
            if not data.get(field):
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required field: {field}"
                )
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Insert job into database
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
            data['name'],
            data['phone'],
            data.get('email', '')
        ))
        
        job_id = cursor.fetchone()[0]
        conn.commit()
        
        # Find matching tradespeople
        postcode_area = data['postcode'].split()[0]
        
        cursor.execute("""
            SELECT id, trading_name, phone, email
            FROM tradespeople
            WHERE LOWER(trade_category) = LOWER(%s)
            AND subscription_status = 'active'
            AND can_receive_jobs = true
            AND (postcode LIKE %s OR postcode IS NULL)
            ORDER BY quality_score DESC
            LIMIT 10
        """, (
            data['trade_category'],
            f"{postcode_area}%"
        ))
        
        matched_tradespeople = cursor.fetchall()
        
        # Send notifications to matched tradespeople
        matched_ids = []
        for tradesperson in matched_tradespeople:
            tp_id, name, phone, email = tradesperson
            matched_ids.append(str(tp_id))
            
            # Send SMS notification
            try:
                sms_message = f"""New Job Alert! 🔧

{data['job_type']} in {data['postcode']}

Urgency: {data['urgency'].title()}

View details and send quote:
besttrade.uk/jobs/{job_id}

Best Trade"""
                
                notification_service.sms_service.send_sms(phone, sms_message)
                
            except Exception as e:
                print(f"Error sending SMS to {name}: {str(e)}")
        
        # Update job with matched tradespeople
        cursor.execute("""
            UPDATE jobs 
            SET matched_tradespeople = %s
            WHERE id = %s
        """, (matched_ids, job_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "job_id": job_id,
            "matched_count": len(matched_tradespeople),
            "message": f"Job posted! {len(matched_tradespeople)} tradespeople notified."
        }
        
    except Exception as e:
        print(f"Error posting job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# CONTACT FORM
# ============================================================================

@app.post("/api/contact/submit")
async def submit_contact_form(request: Request):
    """Handle contact form submissions"""
    try:
        data = await request.json()
        
        # Send email to support
        notification_service.email_service.send_email(
            to_email="hello@besttrade.uk",
            subject=f"Contact Form: {data['subject']}",
            html_content=f"""
                <html>
                <body style="font-family: Arial, sans-serif;">
                    <h3>New Contact Form Submission</h3>
                    <p><strong>From:</strong> {data['name']} ({data['email']})</p>
                    <p><strong>Subject:</strong> {data['subject']}</p>
                    <p><strong>Message:</strong></p>
                    <p>{data['message']}</p>
                </body>
                </html>
            """
        )
        
        return {"success": True}
        
    except Exception as e:
        print(f"Error submitting contact form: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Best Trade API"}

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
