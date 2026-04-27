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

# ====================== CANCEL SUBSCRIPTION ======================
@app.post("/api/subscription/cancel")
async def cancel_subscription(request: Request):
    try:
        session_token = request.cookies.get("session_token")
        if not session_token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT t.stripe_subscription_id, t.subscription_tier 
            FROM tradesperson_sessions s 
            JOIN tradespeople t ON s.tradesperson_id = t.id 
            WHERE s.session_token = %s AND s.expires_at > NOW()
        """, (session_token,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or not user.get("stripe_subscription_id"):
            raise HTTPException(status_code=400, detail="No active subscription found")

        # Cancel at period end in Stripe
        stripe.Subscription.modify(
            user["stripe_subscription_id"],
            cancel_at_period_end=True
        )

        # Update DB status
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tradespeople 
            SET subscription_status = 'cancelled_at_period_end'
            WHERE stripe_subscription_id = %s
        """, (user["stripe_subscription_id"],))
        conn.commit()
        cursor.close()
        conn.close()

        return {"success": True, "message": "Subscription will be cancelled at the end of the current billing period."}
    except Exception as e:
        print(f"Cancel subscription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====================== FEATURED AD PURCHASE ======================
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

        # £25 charge
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

        return {
            "success": True,
            "clientSecret": payment_intent.client_secret
        }
    except Exception as e:
        print(f"Featured ad purchase error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====================== CONFIRM FEATURED AD AFTER PAYMENT ======================
@app.post("/api/featured-ad/confirm")
async def confirm_featured_ad(request: Request):
    try:
        data = await request.json()
        payment_intent_id = data.get("payment_intent_id")
        trade_category = data.get("trade_category")
        short_description = data.get("short_description", "Professional local trade services")

        if not payment_intent_id or not trade_category:
            raise HTTPException(status_code=400, detail="Missing required data")

        # Verify payment succeeded
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        if payment_intent.status != "succeeded":
            raise HTTPException(status_code=400, detail="Payment not successful")

        session_token = request.cookies.get("session_token")
        if not session_token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT t.id, t.trading_name 
            FROM tradesperson_sessions s 
            JOIN tradespeople t ON s.tradesperson_id = t.id 
            WHERE s.session_token = %s AND s.expires_at > NOW()
        """, (session_token,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Save as ACTIVE
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO featured_ads (tradesperson_id, trade_category, company_name, short_description, 
                                      postcode_area, status, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, 'active', NOW(), NOW() + INTERVAL '1 year')
        """, (user["id"], trade_category, user["trading_name"], short_description, None))
        conn.commit()
        cursor.close()
        conn.close()

        return {"success": True, "message": "Featured ad activated successfully"}
    except Exception as e:
        print(f"Confirm featured ad error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====================== STATIC FILES (MUST BE LAST) ======================
@app.get("/{full_path:path}")
async def serve_static(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    
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
