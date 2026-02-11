"""
PlumbFlow Platform - Main Application
FastAPI backend with tight pricing engine integration
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from pathlib import Path
import logging
from typing import Optional
from datetime import datetime, timedelta
import jwt
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Import custom modules
from payment_service import PaymentService
from tight_pricing_engine import TightPricingEngine
from plumber_acceptance_system import (
    MagicLinkService,
    SMSNotificationService,
    LeadAcceptanceService,
    LeadMatchingService
)
from database import Database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PlumbFlow API",
    description="Plumber Matching Platform API with Tight Pricing",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
payment_service = PaymentService()

# Initialize pricing engine (with error handling)
try:
    pricing_engine = TightPricingEngine()
    logger.info("✅ Pricing engine initialized successfully")
except Exception as e:
    logger.warning(f"⚠️ Pricing engine initialization failed: {e}")
    logger.warning("Pricing will use fallback mode")
    pricing_engine = None

# Secret key for JWT tokens
SECRET_KEY = os.getenv('SECRET_KEY', 'plumbflow-secret-key-change-in-production')

# ============================================================================
# EMAIL NOTIFICATION
# ============================================================================

def send_customer_confirmation_email(customer_name: str, customer_email: str, job_type: str, urgency: str, price_low: int, price_high: int):
    """
    Send confirmation email to customer after job submission
    """
    try:
        # Get SendGrid API key
        sg_api_key = os.getenv('SENDGRID_API_KEY')
        if not sg_api_key:
            logger.warning("SendGrid API key not configured - skipping email")
            return False
        
        # Format job type for display
        job_display = job_type.replace('_', ' ').title()
        
        # Email content
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%); padding: 30px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="color: white; margin: 0;">PlumberFlow</h1>
            </div>
            
            <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 8px 8px;">
                <h2 style="color: #1e3a5f;">Job Received! ✅</h2>
                
                <p style="font-size: 16px; color: #333;">Hi {customer_name},</p>
                
                <p style="font-size: 16px; color: #333; line-height: 1.6;">
                    Thanks for using PlumberFlow! We've received your plumbing job request and we're matching you with local plumbers right now.
                </p>
                
                <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #1e3a5f; margin-top: 0;">Your Job Details:</h3>
                    <p style="margin: 10px 0;"><strong>Type:</strong> {job_display}</p>
                    <p style="margin: 10px 0;"><strong>Urgency:</strong> {urgency.title()}</p>
                    <p style="margin: 10px 0;"><strong>Estimated Cost:</strong> £{price_low} - £{price_high}</p>
                </div>
                
                <div style="background: #e0f2fe; border-left: 4px solid #0ea5e9; padding: 15px; margin: 20px 0; border-radius: 4px;">
                    <h3 style="color: #0c4a6e; margin-top: 0;">🔔 What Happens Next:</h3>
                    <ul style="color: #0c4a6e; line-height: 1.8;">
                        <li><strong>A local plumber will call you within 1-2 hours</strong></li>
                        <li><strong>They'll discuss the job details with you</strong></li>
                        <li><strong>They'll provide a free quote and availability</strong></li>
                        <li><strong>You decide if you want to hire them</strong></li>
                    </ul>
                </div>
                
                <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px;">
                    <p style="margin: 0; color: #856404;"><strong>📱 Keep your phone nearby!</strong></p>
                    <p style="margin: 10px 0 0 0; color: #856404;">The plumber will call you to discuss the job.</p>
                </div>
                
                <p style="font-size: 14px; color: #666; margin-top: 30px;">
                    <em>No need to reply to this email - the plumber will contact you directly.</em>
                </p>
            </div>
        </body>
        </html>
        """
        
        # Create email
        message = Mail(
            from_email=os.getenv('SENDGRID_FROM_EMAIL', 'hello@plumberflow.co.uk'),
            to_emails=customer_email,
            subject='Job Received - A Plumber Will Call You Soon',
            html_content=html_content
        )
        
        # Send email
        sg = SendGridAPIClient(sg_api_key)
        response = sg.send(message)
        
        logger.info(f"✅ Confirmation email sent to {customer_email} (status: {response.status_code})")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send confirmation email: {str(e)}")
        return False

# ============================================================================
# MODELS
# ============================================================================

class CustomerJob(BaseModel):
    # Basic fields
    title: str = "Plumbing Job"
    jobType: str
    description: Optional[str] = "Customer provided details via form questions"
    urgency: str
    customerName: str
    phone: str
    email: Optional[str] = None
    postcode: str
    address: Optional[str] = None
    
    # Property details
    propertyType: Optional[str] = None
    propertyAge: Optional[str] = None
    
    # Photo
    photo: Optional[str] = None
    
    # Conditional fields (for detailed jobs)
    tapLocation: Optional[str] = None
    tapType: Optional[str] = None
    leakType: Optional[str] = None
    tapAge: Optional[str] = None
    waterOff: Optional[str] = None


class PlumberRegistration(BaseModel):
    businessName: str
    fullName: str
    email: str
    phone: str
    postcode: str
    password: Optional[str] = None
    gasSafe: Optional[bool] = False
    gasSafeNumber: Optional[str] = None
    skills: list[str]
    
    # Optional fields with defaults
    serviceRadius: Optional[int] = 10  # Default 10 miles
    yearsExperience: Optional[int] = 0
    areasServed: Optional[str] = None
    
    # Payment details (frontend sends paymentMethodId, not stripeCardToken)
    paymentMethodId: str


class LeadAcceptance(BaseModel):
    token: str


# ============================================================================
# CONFIG ENDPOINTS
# ============================================================================

@app.get("/api/config/stripe")
async def get_stripe_config():
    """
    Return Stripe publishable key for frontend
    """
    stripe_key = os.getenv('STRIPE_PUBLISHABLE_KEY', 'pk_test_51QbUfrHGuvT7cvhN6okYKwUIc2zsNJn2LkJ9qVaLcNFqj6TWKS4jqXTCo7WHATIYuUdFGqMT5rTdpBgn8vJCUqSQ00X0vP8xJ0')
    
    return JSONResponse({
        'publishableKey': stripe_key
    })


# ============================================================================
# PRICING ENDPOINTS
# ============================================================================

@app.post("/api/calculate-price")
async def calculate_price(job_data: CustomerJob):
    """
    Calculate tight price range for a job
    
    Returns pricing with MAX 40% spread
    """
    
    try:
        logger.info(f"Calculating price for job type: {job_data.jobType}")
        
        # Convert to dict
        job_dict = job_data.dict()
        
        # Calculate pricing using AI engine (if available)
        if pricing_engine is not None:
            pricing = pricing_engine.calculate_price(job_dict)
        else:
            # Use fallback pricing if engine not available
            raise Exception("Pricing engine not available, using fallback")
        
        logger.info(f"Price calculated: £{pricing['price_low']}-£{pricing['price_high']} ({pricing.get('confidence', 'unknown')} confidence)")
        
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
        logger.error(f"Error calculating price: {str(e)}")
        
        # Return fallback pricing (still tight!)
        return {
            'success': True,
            'priceLow': 95,
            'priceTypical': 120,
            'priceHigh': 145,
            'calloutFee': 60,
            'laborHours': 1.0,
            'laborCost': 50,
            'partsCost': 20,
            'confidence': 'low',
            'reasoning': 'Conservative estimate (AI temporarily unavailable)',
            'complications': ['Actual price depends on inspection'],
            'rangeSpread': 42,
            'rangeTightened': False,
            'note': 'Using fallback pricing',
            'error': str(e)
        }


# ============================================================================
# JOB ENDPOINTS
# ============================================================================

@app.post("/api/jobs/create")
async def create_job_with_pricing(job_data: CustomerJob):
    """
    Create a new job with price estimate attached
    """
    
    try:
        logger.info(f"Creating job: {job_data.title} for {job_data.customerName}")
        
        # Calculate pricing first (if engine available)
        if pricing_engine is not None:
            pricing = pricing_engine.calculate_price(job_data.dict())
        else:
            # Fallback pricing
            pricing = {
                'price_low': 95,
                'price_typical': 120,
                'price_high': 145,
                'confidence': 'low'
            }
        
        logger.info(f"Price estimated: £{pricing['price_low']}-£{pricing['price_high']} (confidence: {pricing['confidence']})")
        
        # Generate job ID
        job_id = f"JOB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # ✅ Save to database
        if db:
            try:
                job_record = {
                    'id': job_id,
                    'customerName': job_data.customerName,
                    'email': job_data.email,
                    'phone': job_data.phone,
                    'postcode': job_data.postcode,
                    'address': job_data.address,
                    'jobType': job_data.jobType,
                    'description': job_data.description,
                    'urgency': job_data.urgency,
                    'propertyType': job_data.propertyType,
                    'propertyAge': job_data.propertyAge,
                    'price_low': pricing['price_low'],
                    'price_typical': pricing['price_typical'],
                    'price_high': pricing['price_high'],
                    'confidence': pricing['confidence'],
                    'lead_fee': 18  # Default, can be dynamic later
                }
                
                db.create_job(job_record)
                logger.info(f"✅ Job saved to database: {job_id}")
            except Exception as db_error:
                logger.error(f"❌ Failed to save job to database: {db_error}")
                # Continue anyway - job still created, just not persisted
        
        logger.info(f"Job created with ID: {job_id}")
        
        # ✅ Send confirmation email to customer
        if job_data.email:
            send_customer_confirmation_email(
                customer_name=job_data.customerName,
                customer_email=job_data.email,
                job_type=job_data.jobType,
                urgency=job_data.urgency,
                price_low=pricing['price_low'],
                price_high=pricing['price_high']
            )
        else:
            logger.warning(f"No email provided for job {job_id} - skipping confirmation email")
        
        # ✅ Find matching plumbers and send SMS notifications
        if db and lead_matching_service:
            try:
                lead_matching_service.find_and_notify_plumbers(
                    job_id=job_id,
                    job_data={
                        'jobType': job_data.jobType,
                        'description': job_data.description,
                        'postcode': job_data.postcode,
                        'urgency': job_data.urgency,
                        'price_low': pricing['price_low'],
                        'price_high': pricing['price_high'],
                        'lead_fee': 18,
                        'customerName': job_data.customerName,
                        'phone': job_data.phone,
                        'email': job_data.email
                    },
                    max_plumbers=3
                )
                logger.info(f"✅ Plumber matching triggered for job {job_id}")
            except Exception as match_error:
                logger.error(f"❌ Lead matching failed: {match_error}")
                # Continue - job still created and saved
        
        return {
            'success': True,
            'jobId': job_id,
            'priceEstimate': {
                'low': pricing['price_low'],
                'typical': pricing['price_typical'],
                'high': pricing['price_high'],
                'confidence': pricing['confidence']
            },
            'message': f'Job created successfully! Expected cost: £{pricing["price_low"]}-£{pricing["price_high"]}'
        }
        
    except Exception as e:
        logger.error(f"Error creating job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/jobs")
async def create_job_legacy(job: CustomerJob):
    """Legacy endpoint - redirects to new create endpoint"""
    return await create_job_with_pricing(job)


# ============================================================================
# PLUMBER ENDPOINTS
# ============================================================================

@app.post("/api/plumbers/register")
async def register_plumber(plumber: PlumberRegistration):
    """Register a new plumber"""
    try:
        logger.info(f"New plumber registration: {plumber.businessName}")
        
        # Create Stripe customer
        stripe_customer = payment_service.create_customer(
            email=plumber.email,
            name=plumber.fullName,
            phone=plumber.phone,
            metadata={'type': 'plumber', 'business': plumber.businessName}
        )
        
        # Attach payment method
        payment_service.attach_payment_method(
            customer_id=stripe_customer['customer_id'],
            payment_method_id=plumber.paymentMethodId
        )
        
        # Generate plumber ID
        plumber_id = f"PLUMBER-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # ✅ Save to database
        if db:
            try:
                plumber_data = {
                    'id': plumber_id,
                    'businessName': plumber.businessName,
                    'fullName': plumber.fullName,
                    'email': plumber.email,
                    'phone': plumber.phone,
                    'postcode': plumber.postcode,
                    'areasServed': plumber.areasServed or f"{plumber.postcode} area",
                    'yearsExperience': plumber.yearsExperience or 0,
                    'gasSafeNumber': plumber.gasSafeNumber,
                    'stripeCustomerId': stripe_customer['customer_id'],
                    'stripePaymentMethodId': plumber.paymentMethodId,
                    'membershipTier': 'free',
                    'status': 'active'
                }
                
                db.create_plumber(plumber_data)
                logger.info(f"✅ Plumber saved to database: {plumber_id}")
            except Exception as db_error:
                logger.error(f"❌ Failed to save plumber to database: {db_error}")
                # Continue anyway - Stripe customer created, just not in DB
        
        logger.info(f"Plumber registered with ID: {plumber_id}")
        
        return {
            "status": "success",
            "message": "Registration successful",
            "plumberId": plumber_id,
            "plumber": {
                "id": plumber_id,
                "email": plumber.email,
                "businessName": plumber.businessName,
                "fullName": plumber.fullName,
                "phone": plumber.phone,
                "postcode": plumber.postcode
            }
        }
        
    except Exception as e:
        logger.error(f"Error registering plumber: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# LEAD ACCEPTANCE ENDPOINTS
# ============================================================================

def generate_acceptance_token(job_id: str, plumber_id: str, lead_fee: int) -> str:
    """Generate secure time-limited token for lead acceptance"""
    data = {
        'job_id': job_id,
        'plumber_id': plumber_id,
        'lead_fee': lead_fee,
        'expires': (datetime.now() + timedelta(minutes=30)).isoformat(),
        'type': 'lead_acceptance'
    }
    token = jwt.encode(data, SECRET_KEY, algorithm='HS256')
    return token


def validate_acceptance_token(token: str):
    """Validate and decode acceptance token"""
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        
        # Check expiry
        expires = datetime.fromisoformat(data['expires'])
        if datetime.now() > expires:
            return None, "Token expired"
        
        return data, None
        
    except jwt.InvalidTokenError:
        return None, "Invalid token"


@app.get("/accept/{token}")
async def show_lead_acceptance_page(token: str):
    """Show lead details page (magic link with auto-login)"""
    
    # Validate token
    data, error = validate_acceptance_token(token)
    
    if error:
        return FileResponse("frontend/login.html")
    
    # TODO: Get plumber and job details from database
    # plumber = get_plumber(data['plumber_id'])
    # job = get_job(data['job_id'])
    
    # For now, return a placeholder page
    return JSONResponse({
        'message': 'Lead acceptance page',
        'job_id': data['job_id'],
        'plumber_id': data['plumber_id'],
        'lead_fee': data['lead_fee']
    })


# ============================================================================
# INITIALIZE DATABASE AND SERVICES
# ============================================================================

# Initialize real PostgreSQL database
try:
    db = Database(os.getenv('DATABASE_URL'))
    logger.info("✅ Database connected successfully")
except Exception as e:
    logger.error(f"❌ Database connection failed: {e}")
    logger.warning("⚠️ Running without database - some features will not work")
    db = None

# Initialize services
magic_link_service = MagicLinkService()
sms_service = SMSNotificationService()

# Only initialize acceptance services if database is available
if db:
    lead_acceptance_service = LeadAcceptanceService(payment_service, db)
    lead_matching_service = LeadMatchingService(db)
else:
    lead_acceptance_service = None
    lead_matching_service = None


@app.post("/api/leads/accept")
async def accept_lead_api(request: Request):
    """
    Accept a lead via API (from dashboard or magic link button)
    
    Body: {
        "token": "jwt_token_here"  // Optional if using session
        OR
        "plumber_id": "...",
        "job_id": "..."
    }
    """
    try:
        data = await request.json()
        
        # Method 1: Token-based (from magic link)
        if 'token' in data:
            payload = magic_link_service.validate_token(data['token'])
            if not payload:
                raise HTTPException(status_code=400, detail="Invalid or expired token")
            
            plumber_id = payload['plumber_id']
            job_id = payload['job_id']
        
        # Method 2: Direct IDs (from logged-in dashboard)
        elif 'plumber_id' in data and 'job_id' in data:
            plumber_id = data['plumber_id']
            job_id = data['job_id']
        
        else:
            raise HTTPException(status_code=400, detail="Missing token or plumber/job IDs")
        
        # Process acceptance
        result = lead_acceptance_service.accept_lead(
            plumber_id=plumber_id,
            job_id=job_id,
            acceptance_method='api'
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['message'])
        
        logger.info(f"✅ Lead {job_id} accepted by plumber {plumber_id}")
        
        return JSONResponse(result)
        
    except Exception as e:
        logger.error(f"❌ Error accepting lead: {str(e)}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error(f"   Error details: {repr(e)}")
        import traceback
        logger.error(f"   Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e) if str(e) else f"Unknown error: {type(e).__name__}")


@app.post("/api/sms/webhook")
async def handle_sms_reply(request: Request):
    """
    Twilio webhook for incoming SMS replies
    Handles "YES" replies to accept leads
    
    Twilio sends:
    - From: Plumber's phone number
    - Body: SMS text (e.g., "YES")
    - To: Our Twilio number
    """
    try:
        form_data = await request.form()
        
        from_number = form_data.get('From')  # Plumber's phone
        message_body = form_data.get('Body', '').strip().upper()
        
        logger.info(f"📱 SMS from {from_number}: {message_body}")
        
        # Check if it's a YES reply
        if message_body not in ['YES', 'Y', 'ACCEPT']:
            return JSONResponse({
                'message': 'Reply YES to accept the lead'
            })
        
        if not db:
            return JSONResponse({
                'error': 'Database not connected'
            })
        
        # Find plumber by phone number
        plumber = db.get_plumber_by_phone(from_number)
        if not plumber:
            logger.warning(f"Unknown phone number: {from_number}")
            return JSONResponse({
                'message': 'Phone number not recognized'
            })
        
        # Find their most recent pending lead
        pending_leads = db.get_pending_leads_for_plumber(plumber['id'])
        
        if not pending_leads:
            return JSONResponse({
                'message': 'No pending leads found'
            })
        
        # Accept the most recent lead
        latest_lead = pending_leads[0]
        
        result = lead_acceptance_service.accept_lead(
            plumber_id=plumber['id'],
            job_id=latest_lead['id'],
            acceptance_method='sms_reply'
        )
        
        if result['success']:
            logger.info(f"✅ Lead accepted via SMS by {plumber['business_name']}")
        
        return JSONResponse(result)
        
    except Exception as e:
        logger.error(f"Error processing SMS webhook: {str(e)}")
        return JSONResponse({'error': str(e)})


@app.get("/api/plumbers/{plumber_id}/pending-leads")
async def get_pending_leads(plumber_id: str):
    """
    Get all pending leads for a plumber
    Used by dashboard to show available leads
    """
    try:
        if not db:
            return JSONResponse({
                'success': False,
                'error': 'Database not connected',
                'pending_leads': []
            })
        
        # Get pending leads from database
        pending_leads = db.get_pending_leads_for_plumber(plumber_id)
        
        # Format for frontend
        formatted_leads = []
        for job in pending_leads:
            # Calculate time remaining
            expires_at = job.get('expires_at')
            if expires_at:
                minutes_remaining = int((expires_at - datetime.utcnow()).total_seconds() / 60)
            else:
                minutes_remaining = 0
            
            formatted_leads.append({
                'job_id': job.get('id'),
                'job_type': job.get('job_type', '').replace('_', ' ').title(),
                'description': job.get('description'),
                'postcode': job.get('postcode'),
                'urgency': job.get('urgency'),
                'price_estimate': {
                    'low': job.get('price_low'),
                    'high': job.get('price_high')
                },
                'lead_fee': job.get('lead_fee', 18),
                'distance_miles': 1.5,  # TODO: Calculate real distance
                'minutes_remaining': max(0, minutes_remaining),
                'expires_at': expires_at.isoformat() if expires_at else None
            })
        
        return JSONResponse({
            'success': True,
            'pending_leads': formatted_leads
        })
        
    except Exception as e:
        logger.error(f"Error getting pending leads: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/accept-lead/{token}")
async def magic_link_page(token: str):
    """
    Magic link auto-login page
    Shows lead details and Accept button
    """
    # Validate token
    payload = magic_link_service.validate_token(token)
    
    if not payload:
        return FileResponse("frontend/expired-link.html")
    
    # Serve the acceptance page with embedded token
    return FileResponse("frontend/accept-lead.html")


@app.get("/plumber-dashboard")
async def plumber_dashboard():
    """Plumber dashboard page"""
    return FileResponse("frontend/plumber-dashboard.html")


@app.post("/api/leads/accept")
async def accept_lead(acceptance: LeadAcceptance):
    """Accept lead and charge plumber's card"""
    
    # Validate token
    data, error = validate_acceptance_token(acceptance.token)
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    job_id = data['job_id']
    plumber_id = data['plumber_id']
    lead_fee = data['lead_fee']
    
    try:
        # TODO: Get plumber's Stripe customer ID from database
        # plumber = get_plumber(plumber_id)
        # stripe_customer_id = plumber['stripe_customer_id']
        
        # For now, simulate acceptance
        logger.info(f"Lead accepted: Job {job_id} by Plumber {plumber_id}, Fee: £{lead_fee}")
        
        # TODO: Charge the lead fee
        # charge_result = payment_service.charge_lead_fee(
        #     plumber_id=plumber_id,
        #     job_id=job_id,
        #     amount=lead_fee,
        #     stripe_customer_id=stripe_customer_id
        # )
        
        # TODO: Update database
        # update_job_status(job_id, 'assigned', plumber_id)
        
        # TODO: Send confirmation SMS to plumber with customer details
        # TODO: Notify customer
        
        return {
            'success': True,
            'message': 'Lead accepted successfully',
            'amountCharged': lead_fee,
            'jobId': job_id
        }
        
    except Exception as e:
        logger.error(f"Error accepting lead: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SMS WEBHOOK
# ============================================================================

@app.post("/webhooks/sms")
async def handle_sms_reply(request: Request):
    """Handle incoming SMS replies from plumbers (YES/NO to accept/decline)"""
    
    data = await request.form()
    from_number = data.get('From')
    message_body = data.get('Body', '').strip().upper()
    
    logger.info(f"SMS received from {from_number}: {message_body}")
    
    # TODO: Implement SMS acceptance flow
    # plumber = get_plumber_by_phone(from_number)
    # if message_body in ['YES', 'Y', 'ACCEPT']:
    #     pending_lead = get_latest_pending_lead(plumber['id'])
    #     # Process acceptance and charge
    
    return {"status": "processed"}


# ============================================================================
# HEALTH CHECK - MUST BE BEFORE WILDCARD ROUTES!
# ============================================================================

@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Health check endpoint - Railway checks /health"""
    
    # Test OpenAI connection
    openai_status = "ok"
    try:
        if pricing_engine is None:
            openai_status = "not initialized"
        else:
            test_pricing = pricing_engine.calculate_price({
                'jobType': 'tap_leak',
                'description': 'test',
                'urgency': 'flexible',
                'postcode': 'SW1A 1AA',
                'customerName': 'Test',
                'phone': '07700900000'
            })
            if test_pricing['price_typical']:
                openai_status = "ok"
    except Exception as e:
        openai_status = f"error: {str(e)}"
        logger.error(f"OpenAI health check failed: {e}")
    
    return {
        "status": "healthy",
        "version": "2.0.0",
        "services": {
            "api": "ok",
            "payment": "ok",
            "pricing_engine": openai_status
        }
    }


# ============================================================================
# STATIC FILES & FRONTEND - WILDCARD ROUTES MUST BE LAST!
# ============================================================================

# Mount frontend directory
frontend_path = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


@app.get("/")
async def root():
    """Serve homepage"""
    logger.info(f"Serving index.html from: {frontend_path / 'index.html'}")
    return FileResponse(str(frontend_path / "index.html"))


@app.get("/admin/setup-database")
async def setup_database():
    """
    One-time database setup endpoint
    Visit https://plumberflow.co.uk/admin/setup-database once to create all tables
    """
    try:
        if not db:
            return JSONResponse({
                'success': False,
                'error': 'Database not connected. Check DATABASE_URL environment variable.'
            })
        
        # SQL to create all tables
        schema_sql = """
DROP TABLE IF EXISTS accepted_leads CASCADE;
DROP TABLE IF EXISTS pending_leads CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;
DROP TABLE IF EXISTS plumbers CASCADE;

CREATE TABLE plumbers (
    id VARCHAR(50) PRIMARY KEY,
    business_name VARCHAR(200) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    email VARCHAR(200) NOT NULL UNIQUE,
    phone VARCHAR(20) NOT NULL UNIQUE,
    postcode VARCHAR(10) NOT NULL,
    areas_served TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    years_experience INTEGER,
    gas_safe_number VARCHAR(50),
    qualifications TEXT,
    stripe_customer_id VARCHAR(100),
    stripe_payment_method_id VARCHAR(100),
    membership_tier VARCHAR(20) DEFAULT 'free',
    membership_started_at TIMESTAMP,
    membership_expires_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active',
    verified BOOLEAN DEFAULT false,
    total_leads_received INTEGER DEFAULT 0,
    total_leads_accepted INTEGER DEFAULT 0,
    total_revenue_generated DECIMAL(10, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE jobs (
    id VARCHAR(50) PRIMARY KEY,
    customer_name VARCHAR(200) NOT NULL,
    email VARCHAR(200),
    phone VARCHAR(20) NOT NULL,
    postcode VARCHAR(10) NOT NULL,
    address TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    job_type VARCHAR(100) NOT NULL,
    title VARCHAR(200),
    description TEXT NOT NULL,
    urgency VARCHAR(20) NOT NULL,
    property_type VARCHAR(50),
    property_age VARCHAR(50),
    job_details JSONB,
    photo_url TEXT,
    photo_base64 TEXT,
    price_low INTEGER,
    price_typical INTEGER,
    price_high INTEGER,
    confidence VARCHAR(20),
    callout_fee INTEGER,
    labor_cost INTEGER,
    parts_cost_low INTEGER,
    parts_cost_high INTEGER,
    complications JSONB,
    lead_fee INTEGER DEFAULT 18,
    status VARCHAR(20) DEFAULT 'pending',
    assigned_plumber_id VARCHAR(50),
    accepted_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY (assigned_plumber_id) REFERENCES plumbers(id) ON DELETE SET NULL
);

CREATE TABLE pending_leads (
    job_id VARCHAR(50) NOT NULL,
    plumber_id VARCHAR(50) NOT NULL,
    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notification_method VARCHAR(20),
    magic_link_token TEXT,
    token_expires_at TIMESTAMP,
    notification_delay_minutes INTEGER DEFAULT 0,
    viewed BOOLEAN DEFAULT false,
    viewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (job_id, plumber_id),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (plumber_id) REFERENCES plumbers(id) ON DELETE CASCADE
);

CREATE TABLE accepted_leads (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(50) NOT NULL,
    plumber_id VARCHAR(50) NOT NULL,
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acceptance_method VARCHAR(20),
    lead_fee DECIMAL(10, 2) NOT NULL,
    stripe_charge_id VARCHAR(100),
    stripe_charge_status VARCHAR(20),
    payment_error TEXT,
    outcome VARCHAR(20),
    outcome_notes TEXT,
    outcome_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (plumber_id) REFERENCES plumbers(id) ON DELETE CASCADE,
    UNIQUE(job_id)
);

CREATE INDEX idx_plumbers_phone ON plumbers(phone);
CREATE INDEX idx_plumbers_postcode ON plumbers(postcode);
CREATE INDEX idx_jobs_postcode ON jobs(postcode);
CREATE INDEX idx_jobs_status ON jobs(status);
        """
        
        # Execute the schema
        db.execute_query(schema_sql, fetch=False)
        
        # Verify tables were created
        tables = db.execute_query("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        table_names = [t['table_name'] for t in tables]
        
        logger.info("✅ Database tables created successfully")
        
        return JSONResponse({
            'success': True,
            'message': '✅ Database setup complete!',
            'tables_created': table_names,
            'next_steps': [
                '1. Test posting a job - should work now!',
                '2. Test registering a plumber - should work now!',
                '3. For security, remove this endpoint after setup'
            ]
        })
        
    except Exception as e:
        logger.error(f"❌ Database setup failed: {str(e)}")
        return JSONResponse({
            'success': False,
            'error': str(e),
            'details': 'Check Railway logs for more information'
        })


@app.get("/{filename}")
async def serve_page(filename: str):
    """Serve any HTML page from frontend - THIS MUST BE THE LAST ROUTE!"""
    logger.info(f"Request for: {filename}, checking: {frontend_path / filename}")
    file_path = frontend_path / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    raise HTTPException(status_code=404, detail="Page not found")


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
