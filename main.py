from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
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

# ====================== HEALTH CHECK ======================
@app.get("/health")
async def health():
    return {"status": "healthy"}

# ====================== REGISTRATION ======================
@app.post("/api/register-tradesperson")
async def register_tradesperson(request: Request):
    try:
        data = await request.json()
        trade_categories = data.get('trade_categories', [])
        if not isinstance(trade_categories, list) or len(trade_categories) == 0:
            raise HTTPException(status_code=400, detail="At least one trade category is required")

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
            data.get('trading_name'), data.get('contact_name'), data.get('email'),
            data.get('phone'), data.get('postcode'), trade_categories,
            data.get('subscription_tier', 'pro'), data.get('postcode')
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
            SET stripe_customer_id = %s, stripe_subscription_id = %s, 
                subscription_status = 'active', subscription_tier = %s
            WHERE id = %s
        """, (customer.id, subscription.id, tier, tradesperson_id))

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "success": True,
            "clientSecret": subscription.latest_invoice.payment_intent.client_secret
        }
    except Exception as e:
        print(f"Subscription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====================== SIGN IN ======================
@app.post("/api/auth/signin")
async def simple_signin(request: Request):
    try:
        data = await request.json()
        email = data.get('email', '').strip().lower()

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT id, trading_name FROM tradespeople WHERE LOWER(email) = %s", (email,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        tradesperson_id = str(user['id'])
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
        SELECT t.trading_name, t.subscription_tier, t.subscription_status 
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
            SELECT j.id, j.trade_category, j.job_type, j.description, j.postcode, j.urgency, j.created_at,
                   j.customer_name, j.customer_phone, j.customer_email, j.address, m.accepted_at, m.status
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

# ====================== ACCEPT LEAD ======================
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
        if not session:
            raise HTTPException(status_code=401, detail="Session expired")

        tradesperson_id = session['tradesperson_id']

        cursor.execute("DELETE FROM pending_leads WHERE job_id = %s AND plumber_id = %s", (job_id, tradesperson_id))
        cursor.execute("""
            INSERT INTO managed_jobs (job_id, tradesperson_id, status)
            VALUES (%s, %s, 'active')
            ON CONFLICT (job_id, tradesperson_id) DO NOTHING
        """, (job_id, tradesperson_id))

        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "message": "Lead accepted successfully"}
    except Exception as e:
        print(f"Accept lead error: {e}")
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
            data.get('trade_category'), data.get('job_type'), data.get('description'),
            data.get('urgency'), data.get('postcode'), data.get('address'),
            data.get('customer_name'), data.get('phone'), data.get('email')
        ))
        job = cursor.fetchone()
        job_id = job['id']

        cursor.execute("""
            INSERT INTO pending_leads (job_id, plumber_id, notified_at, notification_method)
            SELECT %s, t.id, NOW(), 'dashboard'
            FROM tradespeople t
            WHERE t.can_receive_jobs = true 
              AND t.subscription_status = 'active'
              AND %s = ANY(t.trade_category)
              AND (
                    t.subscription_tier = 'premium'
                OR (t.subscription_tier = 'pro' 
                    AND (COALESCE(t.postcode_area, '') = %s 
                         OR COALESCE(t.postcode_area, '') LIKE %s))
                OR (t.subscription_tier = 'basic' 
                    AND COALESCE(t.postcode_area, '') = %s)
              )
            ON CONFLICT (job_id, plumber_id) DO NOTHING
        """, (job_id, job_trade_category, job_postcode_area, job_postcode_area + '%', job_postcode_area))

        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "job_id": job_id}
    except Exception as e:
        print(f"Post job error: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit job")

# ====================== FEATURED AD PURCHASE (£25) ======================
@app.post("/api/featured-ad/purchase")
async def purchase_featured_ad(request: Request):
    try:
        data = await request.json()
        trade_category = data.get("trade_category")
        short_description = data.get("short_description", "Professional local trade services")

        if not trade_category:
            raise HTTPException(status_code=400, detail="Trade category required")

        session_token = request.cookies.get("session_token")
        if not session_token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT t.id, t.trading_name, t.email 
            FROM tradesperson_sessions s 
            JOIN tradespeople t ON s.tradesperson_id = t.id 
            WHERE s.session_token = %s AND s.expires_at > NOW()
        """, (session_token,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # £25 charge (2500 pence)
        payment_intent = stripe.PaymentIntent.create(
            amount=2500,
            currency="gbp",
            payment_method_types=["card"],
            metadata={
                "tradesperson_id": str(user["id"]),
                "trade_category": trade_category,
                "type": "featured_ad"
            }
        )

        # Save to DB
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO featured_ads (tradesperson_id, trade_category, company_name, short_description, 
                                      postcode_area, status, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, 'pending', NOW(), NOW() + INTERVAL '1 year')
        """, (user["id"], trade_category, user["trading_name"], short_description, None))
        conn.commit()
        cursor.close()
        conn.close()

        return {
            "success": True,
            "clientSecret": payment_intent.client_secret
        }

    except Exception as e:
        print(f"Featured ad purchase error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====================== GET FEATURED ADS ======================
@app.get("/api/featured-ads/{trade_category}")
async def get_featured_ads(trade_category: str):
    try:
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT id, company_name, short_description, postcode_area
            FROM featured_ads
            WHERE trade_category = %s AND status = 'active' AND end_date >= CURRENT_DATE
            LIMIT 6
        """, (trade_category,))
        ads = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"success": True, "ads": ads}
    except Exception as e:
        print(f"Featured ads fetch error: {e}")
        return {"success": True, "ads": []}

# ====================== STATIC FILES (MUST BE LAST) ======================
@app.get("/{full_path:path}")
async def serve_static(full_path: str):
    if full_path == "" or full_path == "/" or full_path.endswith('.html'):
        try:
            if full_path == "" or full_path == "/":
                return FileResponse("frontend/index.html")
            return FileResponse(f"frontend/{full_path}")
        except:
            pass
    try:
        return FileResponse(f"frontend/{full_path}")
    except:
        return FileResponse("frontend/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
