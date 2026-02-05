"""
UPDATED PAYMENT SYSTEM - PAY-PER-LEAD ON ACCEPTANCE
Charges plumbers instantly when they ACCEPT a lead (not when job completes)

No prepaid credits needed - just charge their card on acceptance
"""

import os
from typing import Dict, Optional
from datetime import datetime
from decimal import Decimal


class PayPerLeadSystem:
    """
    Simple pay-per-lead system
    Charges plumber's card when they accept a lead
    """
    
    def __init__(self):
        self.stripe_enabled = os.getenv('STRIPE_SECRET_KEY') is not None
        
        if self.stripe_enabled:
            try:
                import stripe
                stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
                self.stripe = stripe
            except ImportError:
                print("Stripe not installed - payment simulation mode")
                self.stripe_enabled = False
    
    def save_plumber_payment_method(self, plumber_id: int, stripe_customer_id: str, payment_method_id: str):
        """
        Save plumber's payment method during signup
        
        When plumber signs up, they enter their card details ONCE
        We save the payment method to charge later
        """
        # Save to database
        # UPDATE plumbers SET 
        #   stripe_customer_id = ?, 
        #   stripe_payment_method_id = ?
        # WHERE id = ?
        
        print(f"✓ Payment method saved for plumber {plumber_id}")
        return {
            'plumber_id': plumber_id,
            'stripe_customer_id': stripe_customer_id,
            'payment_method_id': payment_method_id,
            'status': 'active'
        }
    
    def charge_on_lead_acceptance(
        self,
        plumber_id: int,
        job_id: int,
        lead_fee: Decimal,
        job_title: str,
        stripe_customer_id: str,
        payment_method_id: str
    ) -> Dict:
        """
        Charge plumber immediately when they accept a lead
        
        Args:
            plumber_id: ID of plumber accepting lead
            job_id: ID of job
            lead_fee: Amount to charge (£10-25)
            job_title: Description for charge
            stripe_customer_id: Plumber's Stripe customer ID
            payment_method_id: Their saved payment method
        
        Returns:
            Dict with charge status
        """
        
        if not self.stripe_enabled:
            # Simulation mode
            print(f"\n💳 PAYMENT SIMULATION")
            print(f"   Plumber: {plumber_id}")
            print(f"   Job: {job_title}")
            print(f"   Amount: £{lead_fee:.2f}")
            print(f"   Status: ✓ CHARGED")
            
            return {
                'success': True,
                'charge_id': f'ch_sim_{int(datetime.now().timestamp())}',
                'amount': float(lead_fee),
                'status': 'succeeded',
                'simulated': True
            }
        
        # Real Stripe charge
        try:
            # Create payment intent and charge immediately
            payment_intent = self.stripe.PaymentIntent.create(
                amount=int(lead_fee * 100),  # Convert to pence
                currency='gbp',
                customer=stripe_customer_id,
                payment_method=payment_method_id,
                off_session=True,  # Charge without customer present
                confirm=True,  # Charge immediately
                description=f"Lead fee - {job_title}",
                metadata={
                    'plumber_id': plumber_id,
                    'job_id': job_id,
                    'lead_fee': str(lead_fee)
                }
            )
            
            if payment_intent.status == 'succeeded':
                # Record transaction in database
                # INSERT INTO transactions (plumber_id, job_id, amount, type, stripe_charge_id)
                # VALUES (?, ?, ?, 'lead_fee', ?)
                
                return {
                    'success': True,
                    'charge_id': payment_intent.id,
                    'amount': float(lead_fee),
                    'status': 'succeeded',
                    'charged_at': datetime.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': f'Payment status: {payment_intent.status}',
                    'status': payment_intent.status
                }
        
        except self.stripe.error.CardError as e:
            # Card declined
            return {
                'success': False,
                'error': f'Card declined: {e.user_message}',
                'status': 'card_declined'
            }
        
        except Exception as e:
            # Other error
            return {
                'success': False,
                'error': str(e),
                'status': 'failed'
            }
    
    def handle_payment_failure(self, plumber_id: int, job_id: int, reason: str):
        """
        Handle when plumber's card is declined
        
        Actions:
        1. Send email: "Your card was declined, update payment method"
        2. Offer lead to next plumber
        3. Suspend plumber after 3 failed payments
        """
        print(f"\n⚠️ PAYMENT FAILED")
        print(f"   Plumber: {plumber_id}")
        print(f"   Job: {job_id}")
        print(f"   Reason: {reason}")
        
        # Get plumber's failed payment count
        # failed_count = db.get_failed_payment_count(plumber_id)
        
        # If 3+ failures, suspend account
        # if failed_count >= 3:
        #     db.suspend_plumber(plumber_id, reason='Multiple payment failures')
        #     send_email(plumber, "Account suspended - update payment method")
        
        # Offer lead to next plumber
        return {
            'action': 'offer_to_next_plumber',
            'plumber_suspended': False  # Would be True if 3+ failures
        }
    
    def calculate_dynamic_fee(self, job_value_estimate: float) -> Decimal:
        """
        Calculate finder's fee based on job value
        
        Your pricing:
        - Under £75: £10
        - £75-£150: £15
        - £150-£300: £25
        - Over £300: 10% (capped at £50)
        """
        if job_value_estimate < 75:
            return Decimal('10.00')
        elif job_value_estimate < 150:
            return Decimal('15.00')
        elif job_value_estimate < 300:
            return Decimal('25.00')
        else:
            fee = job_value_estimate * 0.10
            return Decimal(str(min(fee, 50.0)))


class PlumberOnboardingFlow:
    """
    Onboarding flow for new plumbers
    Collects payment method ONCE during signup
    """
    
    def __init__(self):
        self.payment_system = PayPerLeadSystem()
    
    def signup_plumber(
        self,
        name: str,
        email: str,
        phone: str,
        postcode: str,
        card_token: str  # From Stripe.js on frontend
    ) -> Dict:
        """
        Complete plumber signup including payment setup
        
        Frontend flow:
        1. Plumber fills form (name, email, phone, postcode)
        2. Enters card details (via Stripe.js - secure, PCI compliant)
        3. Submit form
        4. This function processes signup
        
        Args:
            card_token: Stripe token from frontend (e.g., 'tok_visa')
        
        Returns:
            Success/failure status
        """
        
        print(f"\n📝 NEW PLUMBER SIGNUP")
        print(f"   Name: {name}")
        print(f"   Email: {email}")
        print(f"   Phone: {phone}")
        print(f"   Postcode: {postcode}")
        
        # 1. Create Stripe customer
        if self.payment_system.stripe_enabled:
            try:
                customer = self.payment_system.stripe.Customer.create(
                    email=email,
                    name=name,
                    phone=phone,
                    metadata={'postcode': postcode}
                )
                
                # Attach payment method
                payment_method = self.payment_system.stripe.PaymentMethod.attach(
                    card_token,
                    customer=customer.id
                )
                
                # Set as default
                self.payment_system.stripe.Customer.modify(
                    customer.id,
                    invoice_settings={
                        'default_payment_method': payment_method.id
                    }
                )
                
                stripe_customer_id = customer.id
                payment_method_id = payment_method.id
                
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Payment setup failed: {str(e)}'
                }
        else:
            # Simulation
            stripe_customer_id = f'cus_sim_{int(datetime.now().timestamp())}'
            payment_method_id = f'pm_sim_{int(datetime.now().timestamp())}'
        
        # 2. Create plumber in database
        # plumber_id = db.insert_plumber(name, email, phone, postcode, stripe_customer_id, payment_method_id)
        plumber_id = 999  # Simulated
        
        # 3. Save payment method
        self.payment_system.save_plumber_payment_method(
            plumber_id,
            stripe_customer_id,
            payment_method_id
        )
        
        print(f"   ✓ Plumber created: ID {plumber_id}")
        print(f"   ✓ Payment method saved")
        print(f"   ✓ Ready to receive leads!")
        
        return {
            'success': True,
            'plumber_id': plumber_id,
            'stripe_customer_id': stripe_customer_id,
            'message': 'Signup complete! You\'ll receive leads via SMS/Email/App'
        }


# ============================================================================
# UPDATED WORKFLOW EXAMPLE
# ============================================================================

def example_workflow():
    """
    Example of complete workflow with pay-per-lead
    """
    
    print("\n" + "="*70)
    print("PAY-PER-LEAD WORKFLOW EXAMPLE")
    print("="*70)
    
    payment_system = PayPerLeadSystem()
    onboarding = PlumberOnboardingFlow()
    
    # STEP 1: Plumber signs up
    print("\n" + "="*70)
    print("STEP 1: PLUMBER SIGNUP")
    print("="*70)
    
    signup_result = onboarding.signup_plumber(
        name="John Smith Plumbing",
        email="john@plumbing.co.uk",
        phone="07700900123",
        postcode="SW19",
        card_token="tok_visa"  # From Stripe.js
    )
    
    if signup_result['success']:
        plumber_id = signup_result['plumber_id']
        stripe_customer_id = signup_result['stripe_customer_id']
    
    # STEP 2: Job comes in
    print("\n" + "="*70)
    print("STEP 2: NEW JOB ARRIVES")
    print("="*70)
    
    job = {
        'id': 12345,
        'title': 'Leaking kitchen tap - SW19',
        'estimated_value': 120.0
    }
    
    print(f"   Job: {job['title']}")
    print(f"   Estimated value: £{job['estimated_value']:.2f}")
    
    # Calculate fee
    fee = payment_system.calculate_dynamic_fee(job['estimated_value'])
    print(f"   Your fee: £{fee}")
    
    # STEP 3: Notify plumber
    print("\n" + "="*70)
    print("STEP 3: NOTIFY PLUMBER")
    print("="*70)
    
    print(f"   📱 SMS sent to 07700900123")
    print(f"   📧 Email sent to john@plumbing.co.uk")
    print(f"   Message: New lead in SW19 - £{job['estimated_value']:.2f} job")
    print(f"            Fee: £{fee} (charged on acceptance)")
    
    # STEP 4: Plumber accepts
    print("\n" + "="*70)
    print("STEP 4: PLUMBER ACCEPTS LEAD")
    print("="*70)
    
    print(f"   ⏰ 2 minutes later...")
    print(f"   ✓ John Smith clicked 'Accept' in app")
    
    # STEP 5: Charge immediately
    print("\n" + "="*70)
    print("STEP 5: CHARGE PAYMENT")
    print("="*70)
    
    charge_result = payment_system.charge_on_lead_acceptance(
        plumber_id=plumber_id,
        job_id=job['id'],
        lead_fee=fee,
        job_title=job['title'],
        stripe_customer_id=stripe_customer_id,
        payment_method_id='pm_123456'  # Saved from signup
    )
    
    if charge_result['success']:
        print(f"\n   ✅ SUCCESS!")
        print(f"   Charge ID: {charge_result['charge_id']}")
        print(f"   Amount: £{charge_result['amount']:.2f}")
        print(f"   You earned: £{fee}")
    
    # STEP 6: Notify customer
    print("\n" + "="*70)
    print("STEP 6: NOTIFY CUSTOMER")
    print("="*70)
    
    print(f"   📨 SMS to customer:")
    print(f"   'Plumber found! John Smith will call you shortly.'")
    print(f"   'Phone: 07700900123'")
    
    # DONE
    print("\n" + "="*70)
    print("✅ COMPLETE!")
    print("="*70)
    print(f"   Customer: Happy (plumber calling them)")
    print(f"   Plumber: Happy (got a lead)")
    print(f"   You: Happy (earned £{fee})")
    print("="*70)
    
    print("\n💡 KEY POINTS:")
    print("   • Plumber only pays when they ACCEPT a lead")
    print("   • Payment is instant (charged immediately)")
    print("   • No prepaid credits needed")
    print("   • You don't care if job completes or takes multiple visits")
    print("   • Plumber earned the lead, they handle the job")


# ============================================================================
# COMPARISON: OLD VS NEW
# ============================================================================

def compare_models():
    """Show difference between prepaid vs pay-per-lead"""
    
    print("\n" + "="*70)
    print("PAYMENT MODEL COMPARISON")
    print("="*70)
    
    print("\n❌ OLD MODEL (Prepaid Credits):")
    print("   1. Plumber pays £250 upfront")
    print("   2. Credits deducted when lead accepted")
    print("   3. Must top up when balance low")
    print("   Problems:")
    print("   • High barrier to entry (£250 upfront)")
    print("   • Plumber needs to trust you before trying")
    print("   • You manage credit balances")
    print("   • More complexity")
    
    print("\n✅ NEW MODEL (Pay-Per-Lead):")
    print("   1. Plumber enters card details ONCE at signup")
    print("   2. Accepts lead in app")
    print("   3. Card charged instantly (£10-25)")
    print("   Benefits:")
    print("   • No upfront payment (easy signup)")
    print("   • Plumber only pays for leads they want")
    print("   • Simple, transparent")
    print("   • Standard for lead gen industry")
    
    print("\n💰 YOUR REVENUE (Same Either Way):")
    print("   • 100 leads accepted = 100 × £20 avg = £2,000")
    print("   • Doesn't matter if prepaid or pay-per-lead")
    print("   • But pay-per-lead = MORE plumbers sign up")
    
    print("\n" + "="*70)


# ============================================================================
# RUN DEMO
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  UPDATED PAYMENT SYSTEM - PAY-PER-LEAD")
    print("="*70)
    print()
    print("  KEY CHANGE: No prepaid credits!")
    print()
    print("  Plumber signs up → Enters card → Accepts leads → Charged instantly")
    print()
    print("="*70)
    
    input("\nPress ENTER to see workflow...")
    
    example_workflow()
    
    input("\nPress ENTER to see model comparison...")
    
    compare_models()
    
    print("\n✅ This is the standard model used by:")
    print("   • Bark.com")
    print("   • Rated People")
    print("   • MyBuilder")
    print("   • All major lead gen platforms")
    print()
    print("✅ Much better for you:")
    print("   • Lower barrier = more signups")
    print("   • No credit management")
    print("   • Instant revenue on every acceptance")
    print()
