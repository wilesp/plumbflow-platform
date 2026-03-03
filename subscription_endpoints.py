# ============================================================================
# SUBSCRIPTION SYSTEM - ADD TO END OF main.py
# ============================================================================
# Copy this entire section and paste at the end of main.py (before if __name__)

from enum import Enum
from decimal import Decimal
from datetime import datetime, timedelta

class SubscriptionTier(str, Enum):
    BASIC = "basic"
    PRO = "pro"
    PREMIUM = "premium"

# Pricing configuration
TIER_PRICING = {
    "basic": {
        "price": 2000,  # £20 in pence
        "interval": "month",
        "name": "Basic",
        "features": {
            "radius_miles": 10,
            "sms_notifications": False,
            "priority_listing": False,
            "top_listing": False,
            "verified_badge": False
        }
    },
    "pro": {
        "price": 3000,  # £30 in pence
        "interval": "month",
        "name": "Pro",
        "features": {
            "radius_miles": 20,
            "sms_notifications": True,
            "priority_listing": True,
            "top_listing": False,
            "verified_badge": False
        }
    },
    "premium": {
        "price": 20000,  # £200 in pence
        "interval": "year",
        "name": "Premium",
        "features": {
            "radius_miles": 999,  # UK-wide
            "sms_notifications": True,
            "priority_listing": True,
            "top_listing": True,
            "verified_badge": True
        }
    }
}


@app.post("/api/subscription/create")
async def create_subscription(request: Request):
    """
    Create new subscription for tradesperson
    """
    try:
        data = await request.json()
        
        plumber_id = data.get('plumber_id')
        tier = data.get('tier')  # 'basic', 'pro', 'premium'
        email = data.get('email')
        
        if tier not in TIER_PRICING:
            raise HTTPException(status_code=400, detail="Invalid tier")
        
        if not db:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        # Get or create Stripe customer
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT stripe_customer_id, email FROM plumbers WHERE id = %s
            """, (plumber_id,))
            result = cur.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Plumber not found")
            
            stripe_customer_id = result[0]
            plumber_email = result[1] or email
            
            if not stripe_customer_id:
                # Create Stripe customer
                customer = stripe.Customer.create(
                    email=plumber_email,
                    metadata={'plumber_id': plumber_id}
                )
                stripe_customer_id = customer.id
                
                cur.execute("""
                    UPDATE plumbers 
                    SET stripe_customer_id = %s 
                    WHERE id = %s
                """, (stripe_customer_id, plumber_id))
                db.conn.commit()
        
        # Create Stripe subscription
        tier_config = TIER_PRICING[tier]
        
        subscription = stripe.Subscription.create(
            customer=stripe_customer_id,
            items=[{
                'price_data': {
                    'currency': 'gbp',
                    'product_data': {
                        'name': f'Best Trade {tier_config["name"]} Plan'
                    },
                    'unit_amount': tier_config['price'],
                    'recurring': {
                        'interval': tier_config['interval']
                    }
                }
            }],
            metadata={
                'plumber_id': plumber_id,
                'tier': tier
            }
        )
        
        # Calculate period dates
        start_date = datetime.now()
        if tier_config['interval'] == 'year':
            end_date = start_date + timedelta(days=365)
        else:
            end_date = start_date + timedelta(days=30)
        
        # Update database
        with db.conn.cursor() as cur:
            cur.execute("""
                UPDATE plumbers 
                SET subscription_tier = %s,
                    subscription_status = 'active',
                    stripe_subscription_id = %s,
                    subscription_start_date = %s,
                    subscription_end_date = %s
                WHERE id = %s
            """, (tier, subscription.id, start_date, end_date, plumber_id))
            
            # Record transaction
            cur.execute("""
                INSERT INTO subscription_transactions 
                (plumber_id, stripe_subscription_id, amount, tier, period_start, period_end, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'completed')
            """, (plumber_id, subscription.id, tier_config['price']/100, tier, start_date.date(), end_date.date()))
            
            db.conn.commit()
        
        logger.info(f"Subscription created: Plumber {plumber_id}, Tier {tier}")
        
        return {
            "status": "success",
            "subscription_id": subscription.id,
            "tier": tier,
            "amount": tier_config['price']/100,
            "interval": tier_config['interval'],
            "message": f"Subscribed to {tier.upper()} plan successfully"
        }
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Subscription creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/browse")
async def browse_available_jobs(plumber_id: int):
    """
    Browse available jobs based on subscription tier
    """
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        # Get tradesperson subscription info
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT subscription_tier, subscription_status, postcode, trade_category, business_name
                FROM plumbers 
                WHERE id = %s
            """, (plumber_id,))
            result = cur.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Tradesperson not found")
            
            tier, status, postcode, trade_category, business_name = result
            
            if status != 'active':
                return {
                    "status": "error",
                    "message": "Active subscription required to browse jobs",
                    "subscription_status": status,
                    "jobs": []
                }
            
            # Get tier features
            features = TIER_PRICING.get(tier, {}).get('features', {})
            radius = features.get('radius_miles', 10)
            
            # Get available jobs (simplified - not using geographic distance for now)
            cur.execute("""
                SELECT j.id, j.customer_name, j.postcode, j.job_type, j.description, 
                       j.urgency, j.created_at, j.price_typical
                FROM jobs j
                WHERE j.status = 'pending'
                AND j.job_category = %s
                ORDER BY 
                    CASE WHEN %s THEN 0 ELSE 1 END,  -- Top listing (premium)
                    CASE WHEN %s THEN 0 ELSE 1 END,  -- Priority listing (pro/premium)
                    j.created_at DESC
                LIMIT 50
            """, (trade_category, features.get('top_listing', False), features.get('priority_listing', False)))
            
            jobs = []
            for row in cur.fetchall():
                # Check if already quoted
                cur.execute("""
                    SELECT id FROM quotes WHERE job_id = %s AND plumber_id = %s
                """, (row[0], plumber_id))
                already_quoted = cur.fetchone() is not None
                
                jobs.append({
                    'id': row[0],
                    'customer_name': row[1],
                    'postcode': row[2],
                    'job_type': row[3],
                    'description': row[4],
                    'urgency': row[5],
                    'created_at': row[6].isoformat() if row[6] else None,
                    'estimated_value': float(row[7]) if row[7] else None,
                    'already_quoted': already_quoted
                })
        
        return {
            "status": "success",
            "tier": tier,
            "radius": radius,
            "features": features,
            "jobs_count": len(jobs),
            "jobs": jobs
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Browse jobs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quote/send")
async def send_quote(request: Request):
    """
    Tradesperson sends quote to customer
    """
    try:
        data = await request.json()
        
        job_id = data.get('job_id')
        plumber_id = data.get('plumber_id')
        quote_amount = data.get('quote_amount')
        message = data.get('message', '')
        
        if not all([job_id, plumber_id, quote_amount]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        if not db:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        # Verify active subscription
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT subscription_status, business_name, phone FROM plumbers WHERE id = %s
            """, (plumber_id,))
            result = cur.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Tradesperson not found")
            
            if result[0] != 'active':
                raise HTTPException(status_code=403, detail="Active subscription required to send quotes")
            
            business_name = result[1]
            plumber_phone = result[2]
            
            # Check if already quoted
            cur.execute("""
                SELECT id FROM quotes WHERE job_id = %s AND plumber_id = %s
            """, (job_id, plumber_id))
            
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="You have already quoted on this job")
            
            # Get job details
            cur.execute("""
                SELECT customer_name, phone, email FROM jobs WHERE id = %s
            """, (job_id,))
            job = cur.fetchone()
            
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            
            customer_name, customer_phone, customer_email = job
            
            # Insert quote
            cur.execute("""
                INSERT INTO quotes (job_id, plumber_id, quote_amount, quote_message)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (job_id, plumber_id, quote_amount, message))
            
            quote_id = cur.fetchone()[0]
            db.conn.commit()
        
        # Send notification to customer (SMS)
        if customer_phone and notification_service:
            try:
                sms_message = f"New quote from {business_name}: £{quote_amount}. {message[:100]}"
                notification_service.send_sms(customer_phone, sms_message)
            except Exception as e:
                logger.error(f"Failed to send SMS to customer: {e}")
        
        # Send email to customer
        if customer_email and notification_service:
            try:
                email_body = f"""
                Hello {customer_name},
                
                You have received a new quote for your job:
                
                Business: {business_name}
                Quote: £{quote_amount}
                Message: {message}
                Phone: {plumber_phone}
                
                To accept this quote, please contact them directly.
                
                Best regards,
                All Trades Marketplace Team
                """
                notification_service.send_email(customer_email, "New Quote Received", email_body)
            except Exception as e:
                logger.error(f"Failed to send email to customer: {e}")
        
        logger.info(f"Quote sent: Job {job_id}, Plumber {plumber_id}, Amount £{quote_amount}")
        
        return {
            "status": "success",
            "quote_id": quote_id,
            "message": "Quote sent to customer successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send quote error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/subscription/status")
async def get_subscription_status(plumber_id: int):
    """
    Get subscription status for tradesperson
    """
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT subscription_tier, subscription_status, 
                       subscription_start_date, subscription_end_date,
                       business_name
                FROM plumbers 
                WHERE id = %s
            """, (plumber_id,))
            result = cur.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Tradesperson not found")
            
            tier, status, start_date, end_date, business_name = result
            
            # Get features
            features = TIER_PRICING.get(tier, {}).get('features', {}) if tier != 'none' else {}
            
            return {
                "status": "success",
                "plumber_id": plumber_id,
                "business_name": business_name,
                "subscription": {
                    "tier": tier,
                    "status": status,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "features": features
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get subscription status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# END OF SUBSCRIPTION SYSTEM
# ============================================================================
