"""
Plumber Acceptance Flow System
Handles 3 acceptance methods: SMS Reply, Magic Link, Dashboard
"""

import jwt
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
import secrets
from twilio.rest import Client

# Setup logger
logger = logging.getLogger(__name__)

# ============================================================================
# MAGIC LINK TOKEN SYSTEM
# ============================================================================

class MagicLinkService:
    """
    Generate and validate magic link tokens for auto-login
    """
    
    def __init__(self):
        self.secret_key = os.getenv('SECRET_KEY', 'plumbflow-secret-key-change-in-production')
        self.token_expiry_hours = 24
    
    def generate_accept_token(self, plumber_id: str, job_id: str) -> str:
        """
        Generate a secure token for accepting a specific lead
        Token includes plumber_id and job_id, expires in 24 hours
        """
        payload = {
            'plumber_id': plumber_id,
            'job_id': job_id,
            'action': 'accept_lead',
            'exp': datetime.utcnow() + timedelta(hours=self.token_expiry_hours),
            'iat': datetime.utcnow()
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        return token
    
    def validate_token(self, token: str) -> Optional[Dict]:
        """
        Validate token and return payload if valid
        Returns None if invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            
            # Verify it's an accept_lead token
            if payload.get('action') != 'accept_lead':
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def generate_magic_link(self, plumber_id: str, job_id: str, base_url: str = "https://plumberflow.co.uk") -> str:
        """
        Generate complete magic link URL
        """
        token = self.generate_accept_token(plumber_id, job_id)
        return f"{base_url}/accept-lead/{token}"


# ============================================================================
# SMS NOTIFICATION SERVICE
# ============================================================================

class SMSNotificationService:
    """
    Send SMS notifications to plumbers about new leads
    """
    
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
    
    def send_lead_notification(self, plumber_phone: str, plumber_name: str, job_data: Dict, magic_link: str) -> bool:
        """
        Send SMS notification about new lead with all 3 acceptance methods
        
        SMS Format:
        ---
        Hi [Business Name]! 👋
        🔔 NEW LEAD - Kitchen Tap Repair
        
        📍 Location: SW19 2AB (1.2 miles)
        ⏰ Urgency: Today
        💰 Customer expects: £80-180
        
        Lead fee: £18
        
        ✅ ACCEPT NOW:
        • Reply YES to this message
        • Click: plumberflow.co.uk/accept/xyz
        • Dashboard: plumberflow.co.uk/dashboard
        
        Details:
        - Mixer tap dripping constantly
        - 8+ year old tap
        - Customer turned off water
        
        ⚠️ Possible issues:
        - May need tap replacement
        - Valve might be corroded
        
        Expires in 2 hours
        ---
        """
        
        if not self.client:
            logger.error(f"❌ Twilio not configured - would send SMS to {plumber_phone}")
            logger.error(f"   TWILIO_ACCOUNT_SID: {'SET' if self.account_sid else 'MISSING'}")
            logger.error(f"   TWILIO_AUTH_TOKEN: {'SET' if self.auth_token else 'MISSING'}")
            logger.error(f"   TWILIO_PHONE_NUMBER: {'SET' if self.from_number else 'MISSING'}")
            return False
        
        # Format job type for display
        job_type = job_data.get('jobType', 'Plumbing Job').replace('_', ' ').title()
        
        # Build SMS content with personalized greeting
        sms_body = f"""Hi {plumber_name}! 👋

🔔 NEW LEAD - {job_type}

📍 {job_data.get('postcode', 'N/A')}
⏰ {job_data.get('urgency', 'Flexible').title()}
💰 Est: £{job_data.get('price_low', 0)}-£{job_data.get('price_high', 0)}

Lead fee: £{job_data.get('lead_fee', 18)}

✅ ACCEPT:
• Reply YES
• {magic_link}

{job_data.get('description', '')[:100]}

Expires in 2hrs"""
        
        try:
            message = self.client.messages.create(
                body=sms_body,
                from_=self.from_number,
                to=plumber_phone
            )
            
            logger.info(f"✅ SMS sent to {plumber_phone} (SID: {message.sid})")
            logger.info(f"   From: {self.from_number}")
            logger.info(f"   Status: {message.status}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send SMS to {plumber_phone}: {str(e)}")
            logger.error(f"   Error type: {type(e).__name__}")
            return False
    
    def send_acceptance_confirmation(self, plumber_phone: str, customer_name: str, customer_phone: str, job_details: str) -> bool:
        """
        Send confirmation SMS after plumber accepts lead
        Includes customer contact details
        """
        
        if not self.client:
            print(f"✅ Would send acceptance confirmation to {plumber_phone}")
            return False
        
        sms_body = f"""✅ LEAD ACCEPTED!

Customer Details:
👤 {customer_name}
📞 {customer_phone}

{job_details}

💳 £18 charged to your card

NEXT: Call customer ASAP to book appointment!

Good luck! 👍"""
        
        try:
            message = self.client.messages.create(
                body=sms_body,
                from_=self.from_number,
                to=plumber_phone
            )
            
            print(f"✅ Confirmation sent to {plumber_phone}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send confirmation: {str(e)}")
            return False


# ============================================================================
# LEAD ACCEPTANCE SERVICE
# ============================================================================

class LeadAcceptanceService:
    """
    Handle lead acceptance via any of the 3 methods
    """
    
    def __init__(self, payment_service, database):
        self.payment_service = payment_service
        self.db = database  # Now using real Database class
        self.sms_service = SMSNotificationService()
        self.magic_link_service = MagicLinkService()
    
    def accept_lead(self, plumber_id: str, job_id: str, acceptance_method: str) -> Dict:
        """
        Process lead acceptance
        
        Steps:
        1. Verify lead is still available
        2. Charge plumber's card
        3. Mark lead as accepted
        4. Send customer details to plumber
        5. Notify customer that plumber will call
        
        Returns: {
            'success': bool,
            'customer_details': {...},
            'message': str
        }
        """
        
        # Get plumber details from database
        plumber = self.db.get_plumber(plumber_id)
        if not plumber:
            return {
                'success': False,
                'message': 'Plumber not found'
            }
        
        # Get job details from database
        job = self.db.get_job(job_id)
        if not job:
            return {
                'success': False,
                'message': 'Job not found'
            }
        
        # Check if job is still available
        if job.get('status') != 'pending':
            return {
                'success': False,
                'message': 'Job already accepted by another plumber'
            }
        
        # Calculate lead fee based on membership tier
        lead_fee = self._calculate_lead_fee(plumber, job)
        
        # Charge plumber's card
        try:
            charge_result = self.payment_service.charge_lead_fee(
                plumber_id=plumber_id,
                job_id=job_id,
                amount=lead_fee,
                description=f"Lead: {job.get('job_type', 'Plumbing Job')}"
            )
            
            if not charge_result['success']:
                return {
                    'success': False,
                    'message': f"Payment failed: {charge_result.get('error', 'Unknown error')}"
                }
            
            stripe_charge_id = charge_result.get('charge_id')
        
        except Exception as e:
            return {
                'success': False,
                'message': f"Payment error: {str(e)}"
            }
        
        # Mark job as accepted in database
        self.db.update_job_status(
            job_id=job_id,
            status='accepted',
            assigned_plumber_id=plumber_id,
            accepted_at=datetime.utcnow()
        )
        
        # Record accepted lead
        self.db.create_accepted_lead(
            job_id=job_id,
            plumber_id=plumber_id,
            acceptance_method=acceptance_method,
            lead_fee=lead_fee,
            stripe_charge_id=stripe_charge_id
        )
        
        # Update plumber stats
        self.db.update_plumber_stats(
            plumber_id=plumber_id,
            leads_accepted=1,
            revenue=lead_fee
        )
        
        # Send confirmation SMS to plumber with customer details
        job_details = f"{job.get('job_type', 'Job').replace('_', ' ').title()} - {job.get('postcode', '')}"
        
        self.sms_service.send_acceptance_confirmation(
            plumber_phone=plumber.get('phone'),
            customer_name=job.get('customer_name'),
            customer_phone=job.get('phone'),
            job_details=job_details
        )
        
        # TODO: Send notification to customer that plumber will call
        # (This would use your email service)
        
        return {
            'success': True,
            'customer_details': {
                'name': job.get('customer_name'),
                'phone': job.get('phone'),
                'email': job.get('email'),
                'address': job.get('address'),
                'postcode': job.get('postcode'),
                'description': job.get('description'),
                'urgency': job.get('urgency'),
                'price_estimate': {
                    'low': job.get('price_low'),
                    'high': job.get('price_high')
                }
            },
            'lead_fee': lead_fee,
            'message': 'Lead accepted successfully! Customer details sent via SMS.'
        }
    
    def _calculate_lead_fee(self, plumber: Dict, job: Dict) -> float:
        """
        Calculate lead fee based on plumber's membership tier
        
        Free tier: £20-25
        Starter (£60/year): £15-18 (25% discount)
        Professional (£150/year): £10-12 (50% discount)
        Enterprise (£500/year): £5 (75% discount)
        """
        
        membership_tier = plumber.get('membership_tier', 'free')
        base_fee = job.get('lead_fee', 18)
        
        discounts = {
            'free': 1.0,       # No discount
            'starter': 0.75,   # 25% off
            'professional': 0.5,  # 50% off
            'enterprise': 0.25    # 75% off
        }
        
        discount = discounts.get(membership_tier, 1.0)
        return round(base_fee * discount, 2)


# ============================================================================
# LEAD MATCHING SERVICE
# ============================================================================

class LeadMatchingService:
    """
    Find plumbers for jobs and send notifications
    """
    
    def __init__(self, database):
        self.db = database  # Now using real Database class
        self.sms_service = SMSNotificationService()
        self.magic_link_service = MagicLinkService()
    
    def find_and_notify_plumbers(self, job_id: str, job_data: Dict, max_plumbers: int = 3):
        """
        Find matching plumbers and send SMS notifications
        
        Priority order:
        1. Enterprise members (30 min exclusive window)
        2. Professional members (10 min head start)
        3. Starter members (5 min head start)
        4. Free tier
        """
        
        # Find plumbers near job location using database
        matching_plumbers = self.db.find_plumbers_by_postcode(
            postcode=job_data.get('postcode'),
            radius_miles=10,
            job_type=job_data.get('jobType'),
            limit=max_plumbers
        )
        
        if not matching_plumbers:
            logger.warning(f"❌ No plumbers found for {job_data.get('postcode')}")
            return
        
        logger.info(f"✅ Found {len(matching_plumbers)} plumbers for job {job_id}")
        
        # Send notifications with tier-based delays
        for idx, plumber in enumerate(matching_plumbers):
            
            # Generate magic link for this plumber
            magic_link = self.magic_link_service.generate_magic_link(
                plumber_id=plumber['id'],
                job_id=job_id
            )
            
            # Record pending lead in database
            magic_token = self.magic_link_service.generate_accept_token(
                plumber_id=plumber['id'],
                job_id=job_id
            )
            
            self.db.add_pending_lead(
                job_id=job_id,
                plumber_id=plumber['id'],
                magic_link_token=magic_token
            )
            
            # Update plumber stats
            self.db.update_plumber_stats(
                plumber_id=plumber['id'],
                leads_received=1
            )
            
            # Calculate when to send (tier-based priority)
            # NOTE: Tier delays disabled for MVP - all plumbers get instant notifications
            # Re-enable when pricing tiers are designed and scheduler is implemented
            delay_minutes = 0  # Force immediate for now
            # delay_minutes = self._get_notification_delay(plumber, idx)  # Uncomment when tiers ready
            
            # Send immediately
            logger.info(f"📱 Sending SMS to {plumber.get('business_name')} at {plumber.get('phone')}")
            
            self.sms_service.send_lead_notification(
                plumber_phone=plumber.get('phone'),
                plumber_name=plumber.get('business_name'),
                job_data=job_data,
                magic_link=magic_link
            )
            
            logger.info(f"✅ Notified {plumber.get('business_name')} ({plumber.get('membership_tier', 'free')})")
    
    def _get_notification_delay(self, plumber: Dict, index: int) -> int:
        """
        Calculate delay in minutes based on membership tier
        
        Enterprise: Immediate (0 min)
        Professional: 10 min after enterprise
        Starter: 15 min after enterprise (5 min after professional)
        Free: 30 min after enterprise (20 min after professional)
        """
        
        tier = plumber.get('membership_tier', 'free')
        
        delays = {
            'enterprise': 0,
            'professional': 10,
            'starter': 15,
            'free': 30
        }
        
        return delays.get(tier, 30)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    
    # Example: Generate magic link
    magic_service = MagicLinkService()
    token = magic_service.generate_accept_token(
        plumber_id="PLUMBER123",
        job_id="JOB-20260210-001"
    )
    
    magic_link = magic_service.generate_magic_link(
        plumber_id="PLUMBER123",
        job_id="JOB-20260210-001"
    )
    
    print("Magic Link:", magic_link)
    print("Token:", token)
    
    # Validate token
    payload = magic_service.validate_token(token)
    print("Token payload:", payload)
