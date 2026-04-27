from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import psycopg2.extras
import stripe
import os
from datetime import datetime, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")   # Your test key is already in Railway

def get_db():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# Get current user from session cookie
async def get_current_tradesperson(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT t.* FROM tradespeople t
                JOIN tradesperson_sessions s ON t.id = s.tradesperson_id
                WHERE s.session_token = %s AND s.expires_at > NOW()
            """, (session_token,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=401, detail="Not authenticated")
            return user
    finally:
        conn.close()

# === Existing Registration & Subscription (unchanged - still works) ===
@app.post("/api/register-tradesperson")
async def register_tradesperson(data: dict):
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO tradespeople (trading_name, contact_name, email, phone, postcode,
                    trade_categories, subscription_status, subscription_tier, can_receive_jobs, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, false, NOW())
                RETURNING id
            """, (
                data.get('trading_name'), data.get('contact_name'), data.get('email'),
                data.get('phone'), data.get('postcode'), data.get('trade_categories', []),
                data.get('subscription_tier', 'pro')
            ))
            tradesperson = cur.fetchone()
            conn.commit()
            return {"success": True, "tradesperson_id": tradesperson['id']}
    finally:
        conn.close()

@app.post("/api/subscription/create")
async def create_subscription(data: dict):
    tradesperson_id = data.get("tradesperson_id")
    price_id = data.get("price_id")
    tier = data.get("tier")

    try:
        customer = stripe.Customer.create(
            email=data.get("email"),
            name=data.get("trading_name"),
            metadata={"tradesperson_id": tradesperson_id}
        )

        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": price_id}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )

        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE tradespeople 
                SET stripe_customer_id = %s, stripe_subscription_id = %s,
                    subscription_status = 'active', subscription_tier = %s,
                    can_receive_jobs = true
                WHERE id = %s
            """, (customer.id, subscription.id, tier, tradesperson_id))
            conn.commit()

        return {
            "success": True,
            "clientSecret": subscription.latest_invoice.payment_intent.client_secret
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === NEW: Purchase Featured Ad ===
@app.post("/api/featured-ad/purchase")
async def purchase_featured_ad(request: Request, data: dict):
    user = await get_current_tradesperson(request)
    trade_category = data.get("trade_category")
    short_description = data.get("short_description", "Professional local trade services")

    if not trade_category:
        raise HTTPException(status_code=400, detail="Trade category is required")

    # Price in pence: Premium = free (handled in frontend), Pro = £25, Basic = £35
    price_map = {"pro": 2500, "basic": 3500, "premium": 0}
    amount = price_map.get(user.get("subscription_tier", "pro"), 2500)

    try:
        if amount == 0:  # Premium - free ad
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO featured_ads (tradesperson_id, trade_category, company_name,
                        short_description, postcode_area, status, start_date, end_date)
                    VALUES (%s, %s, %s, %s, %s, 'active', NOW(), NOW() + INTERVAL '1 year')
                """, (user['id'], trade_category, user['trading_name'], short_description, user.get('postcode_area')))
                conn.commit()
            return {"success": True, "message": "Premium featured ad activated for 1 year!"}

        # Paid ad - create PaymentIntent (test mode)
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency="gbp",
            metadata={
                "tradesperson_id": str(user['id']),
                "trade_category": trade_category,
                "type": "featured_ad"
            }
        )

        # Save pending ad
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO featured_ads (tradesperson_id, trade_category, company_name,
                    short_description, postcode_area, status, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, 'pending', NOW(), NOW() + INTERVAL '1 year')
            """, (user['id'], trade_category, user['trading_name'], short_description, user.get('postcode_area')))
            conn.commit()

        return {
            "success": True,
            "clientSecret": payment_intent.client_secret,
            "payment_intent_id": payment_intent.id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === Existing endpoints (pending-leads, managed-jobs, accept-lead, me, signin, etc.) ===
# (These remain unchanged from the stable version you had before)

@app.get("/api/tradesperson/me")
async def get_me(request: Request):
    user = await get_current_tradesperson(request)
    return {
        "success": True,
        "trading_name": user["trading_name"],
        "subscription_tier": user.get("subscription_tier", "pro"),
        "subscription_status": user.get("subscription_status", "active")
    }

@app.get("/api/tradesperson/pending-leads")
async def get_pending_leads(request: Request):
    user = await get_current_tradesperson(request)
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT p.id, j.id as job_id, j.trade_category, j.job_type, j.description, 
                       j.urgency, j.postcode, j.customer_name, j.customer_phone, 
                       j.customer_email, j.address, p.notified_at
                FROM pending_leads p JOIN jobs j ON p.job_id = j.id
                WHERE p.plumber_id = %s ORDER BY p.notified_at DESC
            """, (user['id'],))
            return {"leads": cur.fetchall()}
    finally:
        conn.close()

@app.get("/api/tradesperson/managed-jobs")
async def get_managed_jobs(request: Request):
    user = await get_current_tradesperson(request)
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT m.job_id, j.trade_category, j.job_type, j.description, j.urgency, 
                       j.postcode, j.customer_name, j.customer_phone, j.customer_email, 
                       j.address, m.accepted_at, m.status
                FROM managed_jobs m JOIN jobs j ON m.job_id = j.id
                WHERE m.tradesperson_id = %s ORDER BY m.accepted_at DESC
            """, (user['id'],))
            return {"jobs": cur.fetchall()}
    finally:
        conn.close()

@app.post("/api/tradesperson/accept-lead")
async def accept_lead(request: Request, data: dict):
    user = await get_current_tradesperson(request)
    job_id = data.get("job_id")
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pending_leads WHERE job_id = %s AND plumber_id = %s", (job_id, user['id']))
            cur.execute("""
                INSERT INTO managed_jobs (job_id, tradesperson_id, status, accepted_at)
                VALUES (%s, %s, 'accepted', NOW()) ON CONFLICT DO NOTHING
            """, (job_id, user['id']))
            conn.commit()
        return {"success": True, "message": "Lead accepted successfully!"}
    finally:
        conn.close()

# Static file serving
@app.get("/{full_path:path}")
async def serve_static(full_path: str):
    if full_path in ["", "/"]:
        return FileResponse("index.html")
    try:
        return FileResponse(full_path)
    except:
        return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
