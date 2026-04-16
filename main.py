from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import secrets
import psycopg2.extras
import stripe

from database import db

app = FastAPI(title="Best Trade")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

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
                can_receive_jobs, created_at, postcode_area
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', true, NOW(), UPPER(SPLIT_PART(%s, ' ', 1)))
            RETURNING id
        """, (
            data.get('trading_name'),
            data.get('contact_name'),
            data.get('email'),
            data.get('phone'),
            data.get('postcode'),
            data.get('trade_category'),
            data.get('subscription_tier', 'pro'),
            data.get('postcode')
        ))

        tradesperson = cursor.fetchone()
        tradesperson_id = str(tradesperson['id'])

        session_token = secrets.token_urlsafe(32)
        cursor.execute("""
            INSERT INTO tradesperson_sessions (tradesperson_id, session_token, expires_at)
            VALUES (%s, %s, NOW() + INTERVAL '30 days')
        """, (tradesperson_id, session_token))

        conn.commit()
        cursor.close()
        conn.close()

        return {"success": True, "tradesperson_id": tradesperson_id}

    except Exception as e:
        print(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

# ====================== SUBSCRIPTION CREATE ======================
@app.post("/api/subscription/create")
async def create_subscription(request: Request):
    try:
        data = await request.json()
        tradesperson_id = data.get("tradesperson_id")
        price_id = data.get("price_id")
        tier = data.get("tier")

        if not tradesperson_id or not price_id:
            raise HTTPException(status_code=400, detail="Missing tradesperson_id or price_id")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT trading_name, email FROM tradespeople WHERE id = %s", (tradesperson_id,))
        tradesperson = cursor.fetchone()

        if not tradesperson:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Tradesperson not found")

        customer = stripe.Customer.create(
            name=tradesperson["trading_name"],
            email=tradesperson["email"],
            metadata={"tradesperson_id": tradesperson_id}
        )

        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": price_id}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )

        cursor.execute("""
            UPDATE tradespeople 
            SET stripe_customer_id = %s, 
                stripe_subscription_id = %s, 
                subscription_status = 'active',
                subscription_tier = %s
            WHERE id = %s
        """, (customer.id, subscription.id, tier, tradesperson_id))

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "success": True,
            "clientSecret": subscription.latest_invoice.payment_intent.client_secret,
            "subscriptionId": subscription.id
        }

    except Exception as e:
        print(f"Subscription create error: {e}")
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
        
        cursor.execute("SELECT id, trading_name FROM tradespeople WHERE LOWER(email) = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            print(f"User not found for email: {email}")
            raise HTTPException(status_code=404, detail="User not found")

        tradesperson_id = str(user['id'])
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

# ====================== ME ======================
@app.get("/api/tradesperson/me")
async def get_current_tradesperson(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = db.get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT trading_name, subscription_tier, subscription_status 
        FROM tradesperson_sessions s 
        JOIN tradespeople t ON s.tradesperson_id = t.id 
        WHERE s.session_token = %s AND s.expires_at > NOW()
    """, (session_token,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "success": True,
        "trading_name": user.get("trading_name") or "Trader",
        "subscription_tier": user.get("subscription_tier"),
        "subscription_status": user.get("subscription_status")
    }

# ====================== PENDING LEADS ======================
@app.get("/api/tradesperson/pending-leads")
async def get_pending_leads(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return {"success": True, "leads": []}

    try:
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT j.id, j.trade_category, j.job_type, j.description, j.postcode, j.urgency, j.created_at
            FROM pending_leads p
            JOIN jobs j ON p.job_id = j.id
            WHERE p.plumber_id = (
                SELECT tradesperson_id 
                FROM tradesperson_sessions 
                WHERE session_token = %s AND expires_at > NOW()
            )
            ORDER BY j.created_at DESC
        """, (session_token,))
        leads = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"success": True, "leads": leads}
    except Exception as e:
        print(f"Pending leads error: {e}")
        return {"success": True, "leads": []}

# ====================== MANAGED JOBS ======================
@app.get("/api/tradesperson/managed-jobs")
async def get_managed_jobs(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return {"success": True, "jobs": []}

    try:
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT j.id, j.trade_category, j.job_type, j.description, j.postcode, j.urgency, j.created_at, m.accepted_at, m.status
            FROM managed_jobs m
            JOIN jobs j ON m.job_id = j.id
            WHERE m.tradesperson_id = (
                SELECT tradesperson_id 
                FROM tradesperson_sessions 
                WHERE session_token = %s AND expires_at > NOW()
            )
            ORDER BY m.accepted_at DESC
        """, (session_token,))
        jobs = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"success": True, "jobs": jobs}
    except Exception as e:
        print(f"Managed jobs error: {e}")
        return {"success": True, "jobs": []}

# ====================== ACCEPT LEAD (Multiple Accepts Enabled) ======================
@app.post("/api/tradesperson/accept-lead")
async def accept_lead(request: Request):
    try:
        data = await request.json()
        job_id = data.get('job_id')

        if not job_id:
            raise HTTPException(status_code=400, detail="Job ID is required")

        session_token = request.cookies.get("session_token")
        if not session_token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT tradesperson_id::text as tradesperson_id
            FROM tradesperson_sessions 
            WHERE session_token = %s AND expires_at > NOW()
        """, (session_token,))
        session = cursor.fetchone()

        if not session or not session['tradesperson_id']:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=401, detail="Session expired")

        tradesperson_id = session['tradesperson_id']

        # Remove ONLY from this tradesperson's pending leads (others can still see it)
        cursor.execute("""
            DELETE FROM pending_leads 
            WHERE job_id = %s AND plumber_id = %s
        """, (job_id, tradesperson_id))

        # Add to their managed jobs
        cursor.execute("""
            INSERT INTO managed_jobs (job_id, tradesperson_id, status)
            VALUES (%s, %s, 'active')
            ON CONFLICT (job_id, tradesperson_id) DO NOTHING
        """, (job_id, tradesperson_id))

        conn.commit()
        cursor.close()
        conn.close()

        print(f"✅ Lead {job_id} accepted by tradesperson {tradesperson_id} (multiple accepts allowed)")
        return {"success": True, "message": f"Lead {job_id} accepted successfully"}

    except Exception as e:
        print(f"Accept lead error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to accept lead")

# ====================== POST JOB ======================
@app.post("/api/customer/post-job")
async def post_job(request: Request):
    try:
        data = await request.json()
        job_trade_category = data.get('trade_category')
        postcode = (data.get('postcode') or '').strip().upper()
        job_postcode_area = postcode.split()[0] if postcode else ''

        if not job_trade_category:
            raise HTTPException(status_code=400, detail="Trade category is required")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            INSERT INTO jobs (trade_category, job_type, description, urgency, postcode, address, customer_name, customer_phone, customer_email, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')
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

        # Trade Category + Postcode Matching
        cursor.execute("""
            INSERT INTO pending_leads (job_id, plumber_id, notified_at, notification_method)
            SELECT %s, t.id, NOW(), 'dashboard'
            FROM tradespeople t
            WHERE t.can_receive_jobs = true 
              AND t.subscription_status = 'active'
              AND t.trade_category = %s
              AND (
                  t.subscription_tier = 'premium'
                  OR COALESCE(t.postcode_area, '') = %s
                  OR (t.subscription_tier = 'pro' AND COALESCE(t.postcode_area, '') LIKE %s)
              )
            ON CONFLICT (job_id, plumber_id) DO NOTHING
        """, (job_id, job_trade_category, job_postcode_area, job_postcode_area + '%'))

        conn.commit()
        cursor.close()
        conn.close()

        print(f"Job {job_id} posted successfully with trade '{job_trade_category}'.")
        return {"success": True, "job_id": job_id}

    except Exception as e:
        print(f"Post job error: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit job")

# ====================== STATIC PAGES ======================
@app.get("/", response_class=HTMLResponse)
@app.get("/tradesperson-register.html", response_class=HTMLResponse)
@app.get("/tradesperson-dashboard.html", response_class=HTMLResponse)
@app.get("/tradesperson-sign-in.html", response_class=HTMLResponse)
@app.get("/pricing.html", response_class=HTMLResponse)
@app.get("/customer-post-job.html", response_class=HTMLResponse)
@app.get("/job-submitted.html", response_class=HTMLResponse)
async def serve_page(request: Request):
    path = request.url.path
    if path == "/" or path == "":
        return FileResponse("frontend/index.html")
    try:
        return FileResponse(f"frontend{path}")
    except:
        return FileResponse("frontend/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
