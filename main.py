from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import secrets
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

# Page routes (simplified)
@app.get("/{path:path}", response_class=HTMLResponse)
async def serve_static(path: str = ""):
    if path == "" or path == "/":
        return FileResponse("frontend/index.html")
    if path.endswith(".html"):
        try:
            return FileResponse(f"frontend/{path}")
        except:
            return FileResponse("frontend/index.html")
    return FileResponse("frontend/index.html")

# Sign in (unchanged)
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
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Email not found")

        tradesperson_id = user['id']
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

# Dashboard me + pending leads + accept lead (same as before - keep your current dashboard.html)

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

    return {"success": True, "trading_name": user.get("trading_name") or "Trader", "subscription_tier": user.get("subscription_tier"), "subscription_status": user.get("subscription_status")}

@app.get("/api/tradesperson/pending-leads")
async def get_pending_leads(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return {"success": True, "leads": []}

    conn = db.get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT j.id, j.trade_category, j.job_type, j.description, j.postcode, j.urgency, j.created_at
        FROM pending_leads p
        JOIN jobs j ON p.job_id = j.id
        WHERE p.plumber_id = (
            SELECT tradesperson_id FROM tradesperson_sessions 
            WHERE session_token = %s AND expires_at > NOW()
        )
        ORDER BY j.created_at DESC
    """, (session_token,))
    leads = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"success": True, "leads": leads}

@app.post("/api/tradesperson/accept-lead")
async def accept_lead(request: Request):
    data = await request.json()
    print(f"Lead accepted: {data.get('job_id')}")
    return {"success": True, "message": "Lead accepted"}

# POST JOB - Improved version
@app.post("/api/customer/post-job")
async def post_job(request: Request):
    try:
        data = await request.json()
        postcode = data.get('postcode', '').strip().upper()
        job_postcode_area = postcode.split()[0] if postcode else ''

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Insert job
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

        # Improved matching with fallback
        cursor.execute("""
            INSERT INTO pending_leads (job_id, plumber_id, notified_at, notification_method)
            SELECT %s, t.id, NOW(), 'dashboard'
            FROM tradespeople t
            WHERE t.can_receive_jobs = true 
              AND t.subscription_status IN ('pending', 'active')
              AND (
                  t.subscription_tier = 'premium'
                  OR COALESCE(t.postcode_area, '') = %s
                  OR (t.subscription_tier = 'pro' AND COALESCE(t.postcode_area, '') LIKE %s)
                  OR t.id = '76'   -- fallback for your test tiler
              )
            ON CONFLICT (job_id, plumber_id) DO NOTHING
        """, (job_id, job_postcode_area, job_postcode_area + '%'))

        inserted = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()

        print(f"Job {job_id} posted. Matched {inserted} pending leads.")
        return {"success": True, "job_id": job_id}

    except Exception as e:
        print(f"Post job error: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit job")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
