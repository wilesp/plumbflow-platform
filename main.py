"""
Best Trade - UK's #1 All-Trades Marketplace
FastAPI Backend with Subscription System
"""

from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import os
from datetime import datetime, timedelta
import stripe
from database import Database
from notification_service import NotificationService

# Initialize FastAPI app
app = FastAPI(title="Best Trade API", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
db = Database()
notification_service = NotificationService()

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

# Subscription tier configuration
SUBSCRIPTION_TIERS = {
    "basic": {
        "name": "Basic",
        "price": 2000,  # £20.00 in pence
        "currency": "gbp",
        "interval": "month",
        "radius_miles": 10,
        "features": ["Email alerts", "Unlimited quotes", "10-mile radius"]
    },
    "pro": {
        "name": "Pro",
        "price": 3000,  # £30.00 in pence
        "currency": "gbp",
        "interval": "month",
        "radius_miles": 20,
        "features": ["Email + SMS alerts", "Priority listing", "20-mile radius"]
    },
    "premium": {
        "name": "Premium",
        "price": 20000,  # £200.00 in pence (annual)
        "currency": "gbp",
        "interval": "year",
        "radius_miles": 999999,  # UK-wide
        "features": ["UK-wide coverage", "Top listing", "Verified badge", "Featured placement"]
    }
}

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class CustomerJobRequest(BaseModel):
    job_type: str
    description: str
    urgency: str
    name: str
    phone: str
    email: Optional[EmailStr] = None
    postcode: str
    preferred_contact: Optional[str] = "phone"

class TradesPersonRegistration(BaseModel):
    business_name: str
    contact_name: str
    email: EmailStr
    phone: str
    postcode: str
    trade_category: str
    trade_categories: Optional[List[str]] = []
    subscription_tier: str = "basic"

class QuoteRequest(BaseModel):
    job_id: int
    plumber_id: int
    quote_amount: float
    message: str
    estimated_duration: Optional[str] = None

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/")
async def root():
    """Serve homepage"""
    try:
        with open("frontend/index.html", 'r') as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Best Trade - Homepage not found</h1>", status_code=404)

@app.get("/api/health")
async def api_health_check():
    """API Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Best Trade API",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # Test database connection
        db.get_connection()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "database": db_status,
        "stripe": "configured" if stripe.api_key else "not configured",
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================================
# CUSTOMER ENDPOINTS - Job Posting
# ============================================================================

@app.post("/api/customer/post-job")
async def post_job(job: CustomerJobRequest):
    """Customer posts a new job"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Insert job into database
        cursor.execute("""
            INSERT INTO jobs (
                job_type, description, urgency, customer_name, 
                customer_phone, customer_email, customer_postcode,
                job_category, status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            job.job_type,
            job.description,
            job.urgency,
            job.name,
            job.phone,
            job.email,
            job.postcode.upper(),
            job.job_type,  # job_category same as job_type for now
            'pending',
            datetime.utcnow()
        ))
        
        job_id = cursor.fetchone()[0]
        conn.commit()
        
        # Find matching tradespeople based on location and trade type
        cursor.execute("""
            SELECT id, business_name, email, phone, subscription_tier, trade_categories
            FROM plumbers 
            WHERE status = 'active' 
            AND subscription_status = 'active'
            AND (
                trade_category = %s 
                OR %s = ANY(trade_categories)
            )
            ORDER BY created_at DESC
            LIMIT 10
        """, (job.job_type, job.job_type))
        
        matching_trades = cursor.fetchall()
        
        # Notify matching tradespeople
        notification_count = 0
        for tradesperson in matching_trades:
            trade_id, business, email, phone, tier, categories = tradesperson
            
            # Send email notification
            notification_service.send_email(
                to_email=email,
                subject=f"New Job Alert: {job.job_type} in {job.postcode}",
                body=f"""
                New job posted on Best Trade!
                
                Job Type: {job.job_type}
                Location: {job.postcode}
                Urgency: {job.urgency}
                Description: {job.description}
                
                Log in to your dashboard to view details and send a quote:
                https://besttrade.uk/tradesperson-dashboard.html
                
                Best regards,
                Best Trade Team
                """
            )
            
            # Send SMS for Pro and Premium tiers
            if tier in ['pro', 'premium']:
                notification_service.send_sms(
                    to_phone=phone,
                    message=f"New {job.job_type} job in {job.postcode}. Log in to quote: besttrade.uk"
                )
            
            notification_count += 1
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "Job posted successfully",
            "notifications_sent": notification_count
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# ============================================================================
# TRADESPERSON ENDPOINTS - Registration & Management
# ============================================================================

@app.post("/api/register-tradesperson")
async def register_tradesperson(registration: TradesPersonRegistration):
    """Register a new tradesperson (without payment - payment handled separately)"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute("SELECT id FROM plumbers WHERE email = %s", (registration.email,))
        if cursor.fetchone():
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Email already registered"}
            )
        
        # Combine trade categories
        all_categories = [registration.trade_category]
        if registration.trade_categories:
            all_categories.extend(registration.trade_categories)
        
        # Insert tradesperson
        cursor.execute("""
            INSERT INTO plumbers (
                business_name, contact_name, email, phone, postcode,
                trade_category, trade_categories, subscription_tier,
                subscription_status, status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            registration.business_name,
            registration.contact_name,
            registration.email,
            registration.phone,
            registration.postcode.upper(),
            registration.trade_category,
            all_categories,
            registration.subscription_tier,
            'pending',  # Will be activated after payment
            'pending',
            datetime.utcnow()
        ))
        
        tradesperson_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "tradesperson_id": tradesperson_id,
            "message": "Registration successful. Please complete payment to activate your account."
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/tradesperson/{tradesperson_id}/dashboard")
async def get_dashboard_data(tradesperson_id: int):
    """Get dashboard data for tradesperson"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Get tradesperson info
        cursor.execute("""
            SELECT business_name, email, subscription_tier, subscription_status,
                   trade_category, trade_categories
            FROM plumbers WHERE id = %s
        """, (tradesperson_id,))
        
        tradesperson = cursor.fetchone()
        if not tradesperson:
            raise HTTPException(status_code=404, detail="Tradesperson not found")
        
        # Get available jobs
        cursor.execute("""
            SELECT id, job_type, description, urgency, customer_postcode,
                   created_at, status
            FROM jobs 
            WHERE status = 'pending'
            AND (
                job_category = %s 
                OR job_category = ANY(%s)
            )
            ORDER BY created_at DESC
            LIMIT 20
        """, (tradesperson[4], tradesperson[5]))
        
        jobs = cursor.fetchall()
        
        # Get tradesperson's quotes
        cursor.execute("""
            SELECT q.id, q.job_id, q.quote_amount, q.message, q.status,
                   j.job_type, j.customer_name, q.created_at
            FROM quotes q
            JOIN jobs j ON q.job_id = j.id
            WHERE q.plumber_id = %s
            ORDER BY q.created_at DESC
            LIMIT 20
        """, (tradesperson_id,))
        
        quotes = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "tradesperson": {
                "business_name": tradesperson[0],
                "email": tradesperson[1],
                "subscription_tier": tradesperson[2],
                "subscription_status": tradesperson[3],
                "trade_category": tradesperson[4]
            },
            "available_jobs": [
                {
                    "id": j[0],
                    "job_type": j[1],
                    "description": j[2],
                    "urgency": j[3],
                    "postcode": j[4],
                    "created_at": j[5].isoformat() if j[5] else None,
                    "status": j[6]
                }
                for j in jobs
            ],
            "my_quotes": [
                {
                    "id": q[0],
                    "job_id": q[1],
                    "amount": float(q[2]),
                    "message": q[3],
                    "status": q[4],
                    "job_type": q[5],
                    "customer": q[6],
                    "created_at": q[7].isoformat() if q[7] else None
                }
                for q in quotes
            ]
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# ============================================================================
# SUBSCRIPTION SYSTEM
# ============================================================================

@app.post("/api/subscription/create")
async def create_subscription(request: Request):
    """Create a Stripe subscription for a tradesperson"""
    try:
        data = await request.json()
        
        tradesperson_id = data.get('tradesperson_id')
        tier = data.get('tier', 'basic')
        payment_method_id = data.get('payment_method_id')
        
        if tier not in SUBSCRIPTION_TIERS:
            raise HTTPException(status_code=400, detail="Invalid subscription tier")
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Get tradesperson details
        cursor.execute("""
            SELECT email, business_name, stripe_customer_id 
            FROM plumbers WHERE id = %s
        """, (tradesperson_id,))
        
        tradesperson = cursor.fetchone()
        if not tradesperson:
            raise HTTPException(status_code=404, detail="Tradesperson not found")
        
        email, business_name, stripe_customer_id = tradesperson
        
        # Create or retrieve Stripe customer
        if not stripe_customer_id:
            customer = stripe.Customer.create(
                email=email,
                name=business_name,
                metadata={'tradesperson_id': tradesperson_id}
            )
            stripe_customer_id = customer.id
            
            # Update database with Stripe customer ID
            cursor.execute("""
                UPDATE plumbers 
                SET stripe_customer_id = %s 
                WHERE id = %s
            """, (stripe_customer_id, tradesperson_id))
            conn.commit()
        
        # Attach payment method to customer
        stripe.PaymentMethod.attach(
            payment_method_id,
            customer=stripe_customer_id
        )
        
        # Set as default payment method
        stripe.Customer.modify(
            stripe_customer_id,
            invoice_settings={'default_payment_method': payment_method_id}
        )
        
        # Create subscription
        tier_config = SUBSCRIPTION_TIERS[tier]
        
        subscription = stripe.Subscription.create(
            customer=stripe_customer_id,
            items=[{
                'price_data': {
                    'currency': tier_config['currency'],
                    'product_data': {
                        'name': f"Best Trade {tier_config['name']} Subscription",
                        'description': f"{', '.join(tier_config['features'])}"
                    },
                    'unit_amount': tier_config['price'],
                    'recurring': {'interval': tier_config['interval']}
                }
            }],
            metadata={'tradesperson_id': tradesperson_id, 'tier': tier}
        )
        
        # Update tradesperson subscription status
        cursor.execute("""
            UPDATE plumbers 
            SET subscription_tier = %s,
                subscription_status = %s,
                stripe_subscription_id = %s,
                subscription_start_date = %s,
                status = 'active'
            WHERE id = %s
        """, (
            tier,
            'active',
            subscription.id,
            datetime.utcnow(),
            tradesperson_id
        ))
        
        # Log transaction
        cursor.execute("""
            INSERT INTO subscription_transactions (
                plumber_id, transaction_type, amount, currency, 
                stripe_payment_id, status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            tradesperson_id,
            'subscription',
            tier_config['price'] / 100,  # Convert pence to pounds
            tier_config['currency'],
            subscription.id,
            'completed',
            datetime.utcnow()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Send confirmation email
        notification_service.send_email(
            to_email=email,
            subject=f"Welcome to Best Trade {tier_config['name']}!",
            body=f"""
            Welcome to Best Trade!
            
            Your {tier_config['name']} subscription is now active.
            
            Your benefits:
            {chr(10).join(f'• {feature}' for feature in tier_config['features'])}
            
            You can now:
            • Browse and quote on jobs in your area
            • Receive instant job alerts
            • Grow your business with Best Trade
            
            Access your dashboard: https://besttrade.uk/tradesperson-dashboard.html
            
            Best regards,
            Best Trade Team
            """
        )
        
        return {
            "success": True,
            "subscription_id": subscription.id,
            "status": subscription.status,
            "message": "Subscription created successfully"
        }
        
    except stripe.error.StripeError as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(e)}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/jobs/browse")
async def browse_jobs(
    tradesperson_id: int,
    trade_category: Optional[str] = None,
    postcode: Optional[str] = None,
    limit: int = 20
):
    """Browse available jobs (requires active subscription)"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Verify active subscription
        cursor.execute("""
            SELECT subscription_status, subscription_tier, trade_category, trade_categories
            FROM plumbers 
            WHERE id = %s
        """, (tradesperson_id,))
        
        tradesperson = cursor.fetchone()
        if not tradesperson or tradesperson[0] != 'active':
            raise HTTPException(
                status_code=403,
                detail="Active subscription required to browse jobs"
            )
        
        # Build query
        query = """
            SELECT id, job_type, description, urgency, customer_postcode,
                   created_at, status
            FROM jobs 
            WHERE status = 'pending'
        """
        params = []
        
        # Filter by trade category
        if trade_category:
            query += " AND (job_category = %s OR job_category = ANY(%s))"
            params.extend([trade_category, tradesperson[3]])
        else:
            query += " AND (job_category = %s OR job_category = ANY(%s))"
            params.extend([tradesperson[2], tradesperson[3]])
        
        # Filter by postcode if provided
        if postcode:
            query += " AND customer_postcode LIKE %s"
            params.append(f"{postcode.upper()}%")
        
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, params)
        jobs = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "jobs": [
                {
                    "id": j[0],
                    "job_type": j[1],
                    "description": j[2],
                    "urgency": j[3],
                    "postcode": j[4],
                    "created_at": j[5].isoformat() if j[5] else None,
                    "status": j[6]
                }
                for j in jobs
            ]
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/quote/send")
async def send_quote(quote: QuoteRequest):
    """Send a quote for a job (requires active subscription)"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Verify active subscription
        cursor.execute("""
            SELECT subscription_status, business_name, email, phone
            FROM plumbers 
            WHERE id = %s
        """, (quote.plumber_id,))
        
        tradesperson = cursor.fetchone()
        if not tradesperson or tradesperson[0] != 'active':
            raise HTTPException(
                status_code=403,
                detail="Active subscription required to send quotes"
            )
        
        # Check if quote already exists
        cursor.execute("""
            SELECT id FROM quotes 
            WHERE job_id = %s AND plumber_id = %s
        """, (quote.job_id, quote.plumber_id))
        
        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="You have already sent a quote for this job"
            )
        
        # Get job details
        cursor.execute("""
            SELECT job_type, customer_name, customer_email, customer_phone
            FROM jobs WHERE id = %s
        """, (quote.job_id,))
        
        job = cursor.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Insert quote
        cursor.execute("""
            INSERT INTO quotes (
                job_id, plumber_id, quote_amount, message,
                estimated_duration, status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            quote.job_id,
            quote.plumber_id,
            quote.quote_amount,
            quote.message,
            quote.estimated_duration,
            'pending',
            datetime.utcnow()
        ))
        
        quote_id = cursor.fetchone()[0]
        conn.commit()
        
        # Notify customer
        if job[2]:  # If customer has email
            notification_service.send_email(
                to_email=job[2],
                subject=f"New Quote for Your {job[0]} Job",
                body=f"""
                You've received a new quote from {tradesperson[1]}!
                
                Job: {job[0]}
                Quote Amount: £{quote.quote_amount:.2f}
                Estimated Duration: {quote.estimated_duration or 'Not specified'}
                
                Message from tradesperson:
                {quote.message}
                
                Contact: {tradesperson[2]}
                Phone: {tradesperson[3]}
                
                Best regards,
                Best Trade Team
                """
            )
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "quote_id": quote_id,
            "message": "Quote sent successfully"
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/subscription/status/{tradesperson_id}")
async def get_subscription_status(tradesperson_id: int):
    """Get subscription status for a tradesperson"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT subscription_tier, subscription_status, 
                   subscription_start_date, stripe_subscription_id
            FROM plumbers 
            WHERE id = %s
        """, (tradesperson_id,))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Tradesperson not found")
        
        tier, status, start_date, stripe_sub_id = result
        
        # Get Stripe subscription details if exists
        stripe_status = None
        if stripe_sub_id:
            try:
                stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
                stripe_status = {
                    "status": stripe_sub.status,
                    "current_period_end": datetime.fromtimestamp(
                        stripe_sub.current_period_end
                    ).isoformat()
                }
            except:
                pass
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "subscription": {
                "tier": tier,
                "status": status,
                "start_date": start_date.isoformat() if start_date else None,
                "tier_details": SUBSCRIPTION_TIERS.get(tier, {}),
                "stripe_status": stripe_status
            }
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# ============================================================================
# STRIPE WEBHOOK
# ============================================================================

@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Handle the event
    if event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        tradesperson_id = subscription['metadata'].get('tradesperson_id')
        
        if tradesperson_id:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE plumbers 
                SET subscription_status = 'cancelled',
                    subscription_end_date = %s
                WHERE id = %s
            """, (datetime.utcnow(), tradesperson_id))
            conn.commit()
            cursor.close()
            conn.close()
    
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        # Handle payment failure - could send notification
        pass
    
    return {"success": True}

# ============================================================================
# STATIC FILES - Serve Frontend
# ============================================================================

# Mount static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/{filename}")
async def serve_html(filename: str):
    """Serve HTML files from frontend directory"""
    try:
        file_path = f"frontend/{filename}"
        if os.path.exists(file_path) and filename.endswith('.html'):
            with open(file_path, 'r') as f:
                return HTMLResponse(content=f.read())
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=404, detail="File not found")

# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
