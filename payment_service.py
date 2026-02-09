"""
PlumberFlow Payment Service
Handles all Stripe payment operations
"""

import stripe
import os
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class PaymentService:
    """
    Service for handling all payment operations via Stripe
    """
    
    @staticmethod
    def create_customer(email: str, name: str, phone: str, metadata: Dict = None) -> Dict:
        """
        Create a Stripe customer
        
        Args:
            email: Customer email
            name: Customer name
            phone: Customer phone
            metadata: Additional data to store
            
        Returns:
            Dict with customer ID and details
        """
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                phone=phone,
                description=f"Plumber: {name}",
                metadata=metadata or {}
            )
            
            logger.info(f"Created Stripe customer: {customer.id} for {email}")
            
            return {
                'customer_id': customer.id,
                'email': customer.email,
                'name': customer.name
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer: {e}")
            raise Exception(f"Payment setup failed: {str(e)}")
    
    @staticmethod
    def attach_payment_method(customer_id: str, payment_method_id: str) -> Dict:
        """
        Attach a payment method to a customer and set as default
        
        Args:
            customer_id: Stripe customer ID
            payment_method_id: Payment method ID from frontend
            
        Returns:
            Dict with payment method details
        """
        try:
            # Attach payment method to customer
            payment_method = stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            # Set as default payment method
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )
            
            logger.info(f"Attached payment method {payment_method_id} to customer {customer_id}")
            
            return {
                'payment_method_id': payment_method.id,
                'card_last4': payment_method.card.last4,
                'card_brand': payment_method.card.brand,
                'exp_month': payment_method.card.exp_month,
                'exp_year': payment_method.card.exp_year
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error attaching payment method: {e}")
            raise Exception(f"Payment method setup failed: {str(e)}")
    
    @staticmethod
    def charge_lead_fee(customer_id: str, amount: int, description: str, metadata: Dict = None) -> Dict:
        """
        Charge a plumber for accepting a lead
        
        Args:
            customer_id: Stripe customer ID
            amount: Amount in pence (e.g., 1800 = £18.00)
            description: Charge description
            metadata: Additional data
            
        Returns:
            Dict with charge details
        """
        try:
            # Create payment intent
            payment_intent = stripe.PaymentIntent.create(
                amount=amount,
                currency='gbp',
                customer=customer_id,
                off_session=True,  # Charge without customer present
                confirm=True,
                description=description,
                metadata=metadata or {},
                automatic_payment_methods={
                    'enabled': True,
                    'allow_redirects': 'never'
                }
            )
            
            logger.info(f"Charged £{amount/100:.2f} to customer {customer_id}")
            
            return {
                'payment_intent_id': payment_intent.id,
                'amount': amount,
                'currency': 'gbp',
                'status': payment_intent.status,
                'charge_id': payment_intent.latest_charge if payment_intent.latest_charge else None
            }
            
        except stripe.error.CardError as e:
            # Card was declined
            logger.error(f"Card declined for customer {customer_id}: {e.user_message}")
            raise Exception(f"Card declined: {e.user_message}")
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error charging customer: {e}")
            raise Exception(f"Payment failed: {str(e)}")
    
    @staticmethod
    def calculate_lead_fee(job_type: str, urgency: str, postcode: str = None) -> int:
        """
        Calculate lead fee based on job characteristics
        
        Args:
            job_type: Type of job
            urgency: Urgency level
            postcode: Customer postcode (for location-based pricing)
            
        Returns:
            Fee amount in pence
        """
        # Base fee
        base_fee = 1500  # £15.00
        
        # Urgency pricing
        urgency_fees = {
            'emergency': 2500,    # £25.00
            'today': 2000,        # £20.00
            'this_week': 1500,    # £15.00
            'flexible': 1200      # £12.00
        }
        
        fee = urgency_fees.get(urgency, base_fee)
        
        # Job type premium
        premium_jobs = ['boiler_repair', 'bathroom_fitting', 'kitchen_fitting', 'burst_pipe']
        if job_type in premium_jobs:
            fee += 500  # Add £5
        
        # Location premium (Central London)
        if postcode:
            central_postcodes = ['W1', 'WC', 'EC', 'SW1', 'SE1', 'E1', 'N1', 'NW1']
            postcode_prefix = postcode[:2].upper()
            if postcode_prefix in central_postcodes:
                fee += 300  # Add £3
        
        # Cap at £25
        return min(fee, 2500)
    
    @staticmethod
    def refund_charge(payment_intent_id: str, amount: Optional[int] = None, reason: str = None) -> Dict:
        """
        Refund a charge
        
        Args:
            payment_intent_id: Payment intent ID to refund
            amount: Amount to refund in pence (None = full refund)
            reason: Refund reason
            
        Returns:
            Dict with refund details
        """
        try:
            refund_params = {
                'payment_intent': payment_intent_id
            }
            
            if amount:
                refund_params['amount'] = amount
            
            if reason:
                refund_params['reason'] = reason
            
            refund = stripe.Refund.create(**refund_params)
            
            logger.info(f"Refunded payment intent {payment_intent_id}")
            
            return {
                'refund_id': refund.id,
                'amount': refund.amount,
                'status': refund.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating refund: {e}")
            raise Exception(f"Refund failed: {str(e)}")
    
    @staticmethod
    def get_customer_payment_methods(customer_id: str) -> list:
        """
        Get all payment methods for a customer
        
        Args:
            customer_id: Stripe customer ID
            
        Returns:
            List of payment methods
        """
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type='card'
            )
            
            return [{
                'id': pm.id,
                'card_last4': pm.card.last4,
                'card_brand': pm.card.brand,
                'exp_month': pm.card.exp_month,
                'exp_year': pm.card.exp_year
            } for pm in payment_methods.data]
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error listing payment methods: {e}")
            return []

# Example usage:
if __name__ == "__main__":
    # Test the service
    ps = PaymentService()
    
    # Create customer
    customer = ps.create_customer(
        email="test@example.com",
        name="Test Plumber",
        phone="07700900123",
        metadata={'postcode': 'SW19'}
    )
    print(f"Created customer: {customer}")
    
    # Calculate fee
    fee = ps.calculate_lead_fee('leaking_tap', 'emergency', 'SW19')
    print(f"Lead fee: £{fee/100:.2f}")
