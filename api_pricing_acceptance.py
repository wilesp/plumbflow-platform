"""
API Integration for Tight Pricing + Plumber Acceptance Flow

Add these endpoints to your main.py
"""

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
import jwt
from datetime import datetime, timedelta
import secrets
from tight_pricing_engine import TightPricingEngine
import os

app = FastAPI()

# Initialize pricing engine
pricing_engine = TightPricingEngine()

# Secret key for JWT tokens
SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-in-production')

# ============================================================================
# MODELS
# ============================================================================

class JobData(BaseModel):
    jobType: str
    description: str
    urgency: str
    postcode: str
    propertyType: str
    propertyAge: str
    customerName: Optional[str] = None
    customerPhone: Optional[str] = None
    address: Optional[str] = None
    photo: Optional[str] = None
    # Conditional fields
    tapLocation: Optional[str] = None
    tapType: Optional[str] = None
    leakType: Optional[str] = None
    tapAge: Optional[str] = None
    waterOff: Optional[str] = None

class LeadAcceptance(BaseModel):
    token: str

# ============================================================================
# ENDPOINT 1: CALCULATE TIGHT PRICE
# ============================================================================

@app.post("/api/calculate-price")
async def calculate_price(job_data: JobData):
    """
    Calculate tight price range for a job
    
    Returns pricing with MAX 40% spread
    """
    
    try:
        # Convert to dict
        job_dict = job_data.dict()
        
        # Calculate pricing
        pricing = pricing_engine.calculate_price(job_dict)
        
        # Return formatted response
        return {
            'success': True,
            'priceLow': pricing['price_low'],
            'priceTypical': pricing['price_typical'],
            'priceHigh': pricing['price_high'],
            'calloutFee': pricing['callout_fee'],
            'laborHours': pricing['labor_hours'],
            'laborCost': pricing['labor_cost'],
            'partsCost': pricing['parts_cost'],
            'confidence': pricing['confidence'],
            'reasoning': pricing.get('reasoning', ''),
            'complications': pricing.get('complications', []),
            'rangeSpread': pricing.get('spread_pct', 0),
            'rangeTightened': pricing.get('range_tightened', False)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ENDPOINT 2: CREATE JOB WITH PRICING
# ============================================================================

@app.post("/api/jobs/create")
async def create_job(job_data: JobData):
    """
    Create a new job with price estimate attached
    """
    
    try:
        # Calculate pricing first
        pricing = pricing_engine.calculate_price(job_data.dict())
        
        # Save to database
        job_id = save_job_to_database(job_data.dict(), pricing)
        
        # Find matching plumbers
        plumbers = find_matching_plumbers(job_data.postcode, job_data.jobType)
        
        # Send notifications
        for plumber in plumbers[:3]:  # Send to top 3 matches
            send_lead_notification(plumber, job_id, pricing)
        
        return {
            'success': True,
            'jobId': job_id,
            'priceEstimate': f"£{pricing['price_low']}-{pricing['price_high']}",
            'plumbersNotified': len(plumbers[:3])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ENDPOINT 3: GENERATE MAGIC LINK FOR PLUMBER ACCEPTANCE
# ============================================================================

def generate_acceptance_token(job_id: str, plumber_id: str, lead_fee: int) -> str:
    """
    Generate secure time-limited token for lead acceptance
    """
    
    data = {
        'job_id': job_id,
        'plumber_id': plumber_id,
        'lead_fee': lead_fee,
        'expires': (datetime.now() + timedelta(minutes=30)).isoformat(),
        'type': 'lead_acceptance'
    }
    
    token = jwt.encode(data, SECRET_KEY, algorithm='HS256')
    return token

def validate_acceptance_token(token: str) -> dict:
    """
    Validate and decode acceptance token
    """
    
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        
        # Check expiry
        expires = datetime.fromisoformat(data['expires'])
        if datetime.now() > expires:
            return None, "Token expired"
        
        return data, None
        
    except jwt.InvalidTokenError:
        return None, "Invalid token"

# ============================================================================
# ENDPOINT 4: SHOW LEAD DETAILS (MAGIC LINK PAGE)
# ============================================================================

@app.get("/accept/{token}")
async def show_lead_acceptance_page(token: str):
    """
    Show lead details page (auto-logged in via magic link)
    """
    
    # Validate token
    data, error = validate_acceptance_token(token)
    
    if error:
        return RedirectResponse("/login?error=token_expired")
    
    # Get plumber and job details
    plumber = get_plumber(data['plumber_id'])
    job = get_job(data['job_id'])
    pricing = job['price_estimate']
    
    # Return HTML page with details
    return render_lead_details_page(plumber, job, pricing, data['lead_fee'], token)

# ============================================================================
# ENDPOINT 5: ACCEPT LEAD (CHARGE PLUMBER)
# ============================================================================

@app.post("/api/leads/accept")
async def accept_lead(acceptance: LeadAcceptance):
    """
    Accept lead and charge plumber's card
    """
    
    # Validate token
    data, error = validate_acceptance_token(acceptance.token)
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    job_id = data['job_id']
    plumber_id = data['plumber_id']
    lead_fee = data['lead_fee']
    
    try:
        # Get plumber's Stripe customer ID
        plumber = get_plumber(plumber_id)
        stripe_customer_id = plumber['stripe_customer_id']
        
        # Charge the lead fee
        from payment_service import PaymentService
        payment_service = PaymentService()
        
        charge_result = payment_service.charge_lead_fee(
            plumber_id=plumber_id,
            job_id=job_id,
            amount=lead_fee,
            stripe_customer_id=stripe_customer_id
        )
        
        if not charge_result['success']:
            raise HTTPException(status_code=402, detail="Payment failed: " + charge_result['error'])
        
        # Update database
        update_job_status(job_id, 'assigned', plumber_id)
        record_lead_acceptance(job_id, plumber_id, lead_fee, charge_result['charge_id'])
        
        # Get customer details
        customer = get_customer_from_job(job_id)
        
        # Send confirmation SMS to plumber
        send_acceptance_confirmation_sms(plumber, customer, job_id, lead_fee)
        
        # Notify customer
        notify_customer_plumber_assigned(customer, plumber)
        
        return {
            'success': True,
            'message': 'Lead accepted successfully',
            'chargeId': charge_result['charge_id'],
            'amountCharged': lead_fee,
            'customer': {
                'name': customer['name'],
                'phone': customer['phone'],
                'address': customer['address'],
                'postcode': customer['postcode']
            },
            'job': get_job(job_id)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ENDPOINT 6: SMS WEBHOOK (HANDLE YES/NO REPLIES)
# ============================================================================

@app.post("/webhooks/sms")
async def handle_sms_reply(request: Request):
    """
    Handle incoming SMS replies from plumbers
    
    When plumber texts "YES" or "NO" to accept/decline lead
    """
    
    data = await request.form()
    from_number = data.get('From')
    message_body = data.get('Body', '').strip().upper()
    
    # Find plumber by phone number
    plumber = get_plumber_by_phone(from_number)
    
    if not plumber:
        return {"status": "unknown_number"}
    
    # Check if YES/NO response
    if message_body in ['YES', 'Y', 'ACCEPT']:
        # Find most recent pending lead for this plumber
        pending_lead = get_latest_pending_lead(plumber['id'])
        
        if pending_lead and not pending_lead['expired']:
            # Process acceptance
            try:
                # Charge plumber
                from payment_service import PaymentService
                payment_service = PaymentService()
                
                charge_result = payment_service.charge_lead_fee(
                    plumber_id=plumber['id'],
                    job_id=pending_lead['job_id'],
                    amount=pending_lead['lead_fee'],
                    stripe_customer_id=plumber['stripe_customer_id']
                )
                
                if charge_result['success']:
                    # Update database
                    update_job_status(pending_lead['job_id'], 'assigned', plumber['id'])
                    record_lead_acceptance(pending_lead['job_id'], plumber['id'], 
                                          pending_lead['lead_fee'], charge_result['charge_id'])
                    
                    # Get customer details
                    customer = get_customer_from_job(pending_lead['job_id'])
                    
                    # Send customer details to plumber
                    confirmation_sms = f"""✅ LEAD ACCEPTED!

You've been charged £{pending_lead['lead_fee']}

CUSTOMER DETAILS:
Name: {customer['name']}
Phone: {customer['phone']}
Address: {customer['address']}
Postcode: {customer['postcode']}

Job: {pending_lead['title']}
{pending_lead['description']}

Call them now to arrange!

View full: plumberflow.co.uk/job/{pending_lead['job_id']}
"""
                    send_sms(plumber['phone'], confirmation_sms)
                    
                    # Notify customer
                    notify_customer_plumber_assigned(customer, plumber)
                    
                    return {"status": "accepted"}
                    
                else:
                    # Payment failed
                    error_sms = f"""❌ Payment failed - please update your card

Visit: plumberflow.co.uk/update-payment

The lead is still available for 10 more minutes.
"""
                    send_sms(plumber['phone'], error_sms)
                    return {"status": "payment_failed"}
                    
            except Exception as e:
                print(f"Error processing acceptance: {e}")
                return {"status": "error"}
        else:
            # No pending lead or expired
            send_sms(plumber['phone'], "No active leads to accept. Check your dashboard for new opportunities!")
            
    elif message_body in ['NO', 'N', 'DECLINE']:
        # Mark lead as declined
        pending_lead = get_latest_pending_lead(plumber['id'])
        if pending_lead:
            decline_lead(pending_lead['id'], plumber['id'])
            send_sms(plumber['phone'], "Lead declined. We'll send the next match!")
    
    return {"status": "processed"}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def send_lead_notification(plumber: dict, job_id: str, pricing: dict):
    """
    Send SMS + Email notification to plumber with magic link
    """
    
    job = get_job(job_id)
    lead_fee = calculate_lead_fee(job, pricing)
    
    # Generate magic link token
    token = generate_acceptance_token(job_id, plumber['id'], lead_fee)
    magic_link = f"https://plumberflow.co.uk/accept/{token}"
    
    # Calculate distance
    distance = calculate_distance(plumber['postcode'], job['postcode'])
    
    # SMS notification
    sms_message = f"""NEW LEAD - {job['title']}

📍 {job['postcode']} ({distance:.1f} miles)
💰 Est: £{pricing['price_low']}-£{pricing['price_high']} | Fee: £{lead_fee}
⏰ {job['urgency']}

{job['short_description']}

ACCEPT:
1. Click: {magic_link}
2. Or reply YES

Expires in 30 mins
"""
    
    send_sms(plumber['phone'], sms_message)
    
    # Email notification (with more detail)
    send_email(
        to=plumber['email'],
        subject=f"New Lead: {job['title']} in {job['postcode']}",
        html=render_lead_email(plumber, job, pricing, lead_fee, magic_link)
    )

def calculate_lead_fee(job: dict, pricing: dict) -> int:
    """
    Calculate lead fee based on job value and urgency
    
    Base: £15
    Emergency: £25
    Premium jobs: +£5
    London: +£3
    """
    
    base_fee = 15
    
    # Urgency premium
    urgency_premiums = {
        'emergency': 10,
        'today': 5,
        'this_week': 0,
        'flexible': -3
    }
    fee = base_fee + urgency_premiums.get(job['urgency'], 0)
    
    # Premium job types
    premium_types = ['boiler', 'bathroom', 'shower_install']
    if any(t in job['jobType'] for t in premium_types):
        fee += 5
    
    # London premium
    london_postcodes = ['E', 'EC', 'N', 'NW', 'SE', 'SW', 'W', 'WC']
    if any(job['postcode'].upper().startswith(p) for p in london_postcodes):
        fee += 3
    
    # Cap at £25
    return min(fee, 25)

# ============================================================================
# DATABASE FUNCTIONS (TO BE IMPLEMENTED)
# ============================================================================

def save_job_to_database(job_data: dict, pricing: dict) -> str:
    """Save job to database and return job_id"""
    # TODO: Implement
    pass

def get_job(job_id: str) -> dict:
    """Get job from database"""
    # TODO: Implement
    pass

def get_plumber(plumber_id: str) -> dict:
    """Get plumber from database"""
    # TODO: Implement
    pass

def get_plumber_by_phone(phone: str) -> dict:
    """Get plumber by phone number"""
    # TODO: Implement
    pass

def get_customer_from_job(job_id: str) -> dict:
    """Get customer details from job"""
    # TODO: Implement
    pass

def find_matching_plumbers(postcode: str, job_type: str) -> List[dict]:
    """Find plumbers matching location and job type"""
    # TODO: Implement
    pass

def update_job_status(job_id: str, status: str, plumber_id: str):
    """Update job status in database"""
    # TODO: Implement
    pass

def record_lead_acceptance(job_id: str, plumber_id: str, fee: int, charge_id: str):
    """Record lead acceptance in database"""
    # TODO: Implement
    pass

def get_latest_pending_lead(plumber_id: str) -> dict:
    """Get most recent pending lead for plumber"""
    # TODO: Implement
    pass

def decline_lead(lead_id: str, plumber_id: str):
    """Mark lead as declined"""
    # TODO: Implement
    pass

def send_sms(phone: str, message: str):
    """Send SMS via Twilio"""
    # TODO: Implement
    pass

def send_email(to: str, subject: str, html: str):
    """Send email via SendGrid"""
    # TODO: Implement
    pass

def notify_customer_plumber_assigned(customer: dict, plumber: dict):
    """Notify customer that plumber has been assigned"""
    # TODO: Implement
    pass

def calculate_distance(postcode1: str, postcode2: str) -> float:
    """Calculate distance between two postcodes in miles"""
    # TODO: Implement using existing Haversine function
    pass
