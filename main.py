@app.post("/api/customer/post-job")
async def post_job(request: Request):
    try:
        data = await request.json()

        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 1. Insert the job
        cursor.execute("""
            INSERT INTO jobs (
                trade_category, job_type, description, urgency,
                postcode, address, customer_name, customer_phone, customer_email, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')
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

        # 2. Insert pending leads for ALL active tradespeople (simple version for testing)
        cursor.execute("""
            INSERT INTO pending_leads (job_id, plumber_id, notified_at, notification_method)
            SELECT %s, t.id, NOW(), 'dashboard'
            FROM tradespeople t
            WHERE t.can_receive_jobs = true 
              AND t.subscription_status = 'active'
            ON CONFLICT (job_id, plumber_id) DO NOTHING
        """, (job_id,))

        inserted_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()

        print(f"Job {job_id} posted. Inserted {inserted_count} pending leads.")

        return {
            "success": True, 
            "job_id": job_id, 
            "matched_tradespeople": inserted_count
        }

    except Exception as e:
        print(f"Post job error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
