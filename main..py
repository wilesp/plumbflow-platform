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

# Import custom modules
from payment_service import PaymentService
from tight_pricing_engine import TightPricingEngine

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
# MODELS
# ============================================================================

class CustomerJob(BaseModel):
    # Basic fields
    title: str = "Plumbing Job"
    jobType: str
    description: str
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
    serviceRadius: int
    yearsExperience: int
    skills: list[str]
    
    # Payment details
    stripeCardToken: str


class LeadAcceptance(BaseModel):
    token: str


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
        
        # TODO: Save to database with pricing
        # job_with_pricing = {
        #     'id': job_id,
        #     'customer': job_data.dict(),
        #     'pricing': pricing,
        #     'status': 'pending',
        #     'created_at': datetime.now()
        # }
        # save_to_database(job_with_pricing)
        
        logger.info(f"Job created with ID: {job_id}")
        
        # TODO: Find matching plumbers and send notifications
        # plumbers = find_matching_plumbers(job_data.postcode, job_data.jobType)
        # for plumber in plumbers[:3]:
        #     send_lead_notification(plumber, job_id, pricing)
        
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
        stripe_customer = payment_service.create_stripe_customer(
            email=plumber.email,
            name=plumber.fullName,
            phone=plumber.phone
        )
        
        # Attach payment method
        payment_service.attach_payment_method(
            customer_id=stripe_customer['id'],
            payment_method=plumber.stripeCardToken
        )
        
        # Generate plumber ID
        plumber_id = f"PLUMBER-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # TODO: Save to database
        # plumber_data = {
        #     'id': plumber_id,
        #     'stripe_customer_id': stripe_customer['id'],
        #     **plumber.dict()
        # }
        # save_plumber_to_database(plumber_data)
        
        logger.info(f"Plumber registered with ID: {plumber_id}")
        
        return {
            "status": "success",
            "message": "Registration successful",
            "plumberId": plumber_id
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
