"""
PAYMENT & CREDIT MANAGEMENT SYSTEM
Handles plumber credits, finder's fees, and payment processing via Stripe
"""

import os
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from decimal import Decimal


class TransactionType(Enum):
    CREDIT_PURCHASE = "credit_purchase"
    LEAD_FEE = "lead_fee"
    REFUND = "refund"
    PAYOUT = "payout"
    AUTO_RELOAD = "auto_reload"


@dataclass
class Transaction:
    """Single financial transaction"""
    plumber_id: int
    transaction_type: TransactionType
    amount: Decimal
    balance_before: Decimal
    balance_after: Decimal
    description: str
    job_id: Optional[int] = None
    stripe_payment_id: Optional[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class StripePaymentService:
    """
    Payment processing via Stripe
    
    Setup:
        pip install stripe
        export STRIPE_SECRET_KEY=sk_test_...
        export STRIPE_PUBLISHABLE_KEY=pk_test_...
    """
    
    def __init__(self):
        self.secret_key = os.getenv('STRIPE_SECRET_KEY')
        
        if self.secret_key:
            try:
                import stripe
                stripe.api_key = self.secret_key
                self.stripe = stripe
                self.enabled = True
            except ImportError:
                print("Stripe not installed. Run: pip install stripe")
                self.enabled = False
        else:
            print("Stripe API key not set. Payments disabled.")
            self.enabled = False
    
    def create_payment_intent(self, amount: float, plumber_id: int, description: str) -> Dict:
        """
        Create Stripe Payment Intent for credit purchase
        
        Args:
            amount: Amount in GBP
            plumber_id: ID of plumber making purchase
            description: Description for payment
        
        Returns:
            Dict with payment_intent_id and client_secret
        """
        if not self.enabled:
            print(f"[PAYMENT SIMULATION] £{amount:.2f} for plumber {plumber_id}")
            return {
                'status': 'simulated',
                'payment_intent_id': f'pi_sim_{int(datetime.now().timestamp())}',
                'client_secret': 'sim_secret_123',
                'amount': amount
            }
        
        try:
            # Create payment intent
            intent = self.stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Stripe uses pence
                currency='gbp',
                metadata={
                    'plumber_id': plumber_id,
                    'description': description
                },
                description=description
            )
            
            return {
                'status': 'created',
                'payment_intent_id': intent.id,
                'client_secret': intent.client_secret,
                'amount': amount
            }
        except Exception as e:
            print(f"Stripe payment error: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def confirm_payment(self, payment_intent_id: str) -> Dict:
        """Confirm payment was successful"""
        if not self.enabled:
            return {'status': 'confirmed', 'payment_intent_id': payment_intent_id}
        
        try:
            intent = self.stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if intent.status == 'succeeded':
                return {
                    'status': 'confirmed',
                    'payment_intent_id': intent.id,
                    'amount': intent.amount / 100  # Convert pence to pounds
                }
            else:
                return {
                    'status': intent.status,
                    'payment_intent_id': intent.id
                }
        except Exception as e:
            print(f"Error confirming payment: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def create_refund(self, payment_intent_id: str, amount: Optional[float] = None) -> Dict:
        """Issue refund for a payment"""
        if not self.enabled:
            return {
                'status': 'simulated',
                'refund_id': f'ref_sim_{int(datetime.now().timestamp())}'
            }
        
        try:
            refund_params = {'payment_intent': payment_intent_id}
            if amount:
                refund_params['amount'] = int(amount * 100)
            
            refund = self.stripe.Refund.create(**refund_params)
            
            return {
                'status': 'refunded',
                'refund_id': refund.id,
                'amount': refund.amount / 100
            }
        except Exception as e:
            print(f"Refund error: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def create_payout(self, plumber_id: int, amount: float, stripe_account_id: str) -> Dict:
        """
        Create payout to plumber's bank account via Stripe Connect
        
        Note: Requires Stripe Connect setup for plumber
        """
        if not self.enabled:
            return {
                'status': 'simulated',
                'transfer_id': f'tr_sim_{int(datetime.now().timestamp())}',
                'amount': amount
            }
        
        try:
            transfer = self.stripe.Transfer.create(
                amount=int(amount * 100),
                currency='gbp',
                destination=stripe_account_id,
                metadata={'plumber_id': plumber_id}
            )
            
            return {
                'status': 'sent',
                'transfer_id': transfer.id,
                'amount': amount
            }
        except Exception as e:
            print(f"Payout error: {e}")
            return {'status': 'error', 'error': str(e)}


class CreditManager:
    """
    Manages plumber credit balances and transactions
    """
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self.payment_service = StripePaymentService()
    
    def get_balance(self, plumber_id: int) -> Decimal:
        """Get current credit balance for plumber"""
        if self.db:
            # In production, query database
            # SELECT credit_balance FROM plumbers WHERE id = plumber_id
            pass
        
        # Simulation
        return Decimal('250.00')
    
    def purchase_credits(
        self,
        plumber_id: int,
        amount: float,
        payment_method_id: str
    ) -> Dict:
        """
        Purchase credits for plumber account
        
        Args:
            plumber_id: Plumber purchasing credits
            amount: Amount to purchase (£100, £250, £500, etc.)
            payment_method_id: Stripe payment method ID
        
        Returns:
            Dict with transaction details
        """
        # Create Stripe payment
        payment_result = self.payment_service.create_payment_intent(
            amount=amount,
            plumber_id=plumber_id,
            description=f"Credit purchase - £{amount:.2f}"
        )
        
        if payment_result['status'] in ['created', 'simulated']:
            # Update plumber balance
            current_balance = self.get_balance(plumber_id)
            new_balance = current_balance + Decimal(str(amount))
            
            # Record transaction
            transaction = Transaction(
                plumber_id=plumber_id,
                transaction_type=TransactionType.CREDIT_PURCHASE,
                amount=Decimal(str(amount)),
                balance_before=current_balance,
                balance_after=new_balance,
                description=f"Purchased £{amount:.2f} credits",
                stripe_payment_id=payment_result.get('payment_intent_id')
            )
            
            # Save to database
            if self.db:
                self._save_transaction(transaction)
                self._update_balance(plumber_id, new_balance)
            
            return {
                'success': True,
                'transaction': transaction,
                'new_balance': new_balance
            }
        else:
            return {
                'success': False,
                'error': payment_result.get('error', 'Payment failed')
            }
    
    def charge_lead_fee(
        self,
        plumber_id: int,
        job_id: int,
        fee_amount: Decimal,
        job_title: str
    ) -> Dict:
        """
        Charge plumber for accepting a lead
        
        Args:
            plumber_id: Plumber accepting the lead
            job_id: ID of job
            fee_amount: Fee to charge (usually £10-25)
            job_title: Title of job for description
        
        Returns:
            Dict with success status and new balance
        """
        current_balance = self.get_balance(plumber_id)
        
        # Check sufficient balance
        if current_balance < fee_amount:
            return {
                'success': False,
                'error': 'Insufficient credits',
                'current_balance': current_balance,
                'required': fee_amount
            }
        
        # Deduct fee
        new_balance = current_balance - fee_amount
        
        # Record transaction
        transaction = Transaction(
            plumber_id=plumber_id,
            transaction_type=TransactionType.LEAD_FEE,
            amount=-fee_amount,  # Negative for deduction
            balance_before=current_balance,
            balance_after=new_balance,
            description=f"Lead fee - {job_title}",
            job_id=job_id
        )
        
        # Save to database
        if self.db:
            self._save_transaction(transaction)
            self._update_balance(plumber_id, new_balance)
        
        # Check if auto-reload needed
        self._check_auto_reload(plumber_id, new_balance)
        
        return {
            'success': True,
            'transaction': transaction,
            'new_balance': new_balance,
            'fee_charged': fee_amount
        }
    
    def refund_lead_fee(
        self,
        plumber_id: int,
        job_id: int,
        refund_amount: Decimal,
        reason: str
    ) -> Dict:
        """
        Refund lead fee (e.g., bad lead, customer never responded)
        
        Args:
            plumber_id: Plumber to refund
            job_id: Original job ID
            refund_amount: Amount to refund
            reason: Reason for refund
        
        Returns:
            Dict with refund details
        """
        current_balance = self.get_balance(plumber_id)
        new_balance = current_balance + refund_amount
        
        # Record transaction
        transaction = Transaction(
            plumber_id=plumber_id,
            transaction_type=TransactionType.REFUND,
            amount=refund_amount,  # Positive for credit
            balance_before=current_balance,
            balance_after=new_balance,
            description=f"Refund - {reason}",
            job_id=job_id
        )
        
        # Save to database
        if self.db:
            self._save_transaction(transaction)
            self._update_balance(plumber_id, new_balance)
        
        return {
            'success': True,
            'transaction': transaction,
            'new_balance': new_balance,
            'refund_amount': refund_amount
        }
    
    def process_job_payout(
        self,
        plumber_id: int,
        job_id: int,
        payout_amount: Decimal,
        job_title: str,
        stripe_account_id: str
    ) -> Dict:
        """
        Pay plumber for completed job
        
        Args:
            plumber_id: Plumber to pay
            job_id: Completed job ID
            payout_amount: Amount to pay plumber
            job_title: Job description
            stripe_account_id: Plumber's Stripe Connect account
        
        Returns:
            Dict with payout details
        """
        # Create Stripe payout
        payout_result = self.payment_service.create_payout(
            plumber_id=plumber_id,
            amount=float(payout_amount),
            stripe_account_id=stripe_account_id
        )
        
        if payout_result['status'] in ['sent', 'simulated']:
            # Record transaction
            transaction = Transaction(
                plumber_id=plumber_id,
                transaction_type=TransactionType.PAYOUT,
                amount=payout_amount,
                balance_before=Decimal('0'),  # Payouts don't affect credit balance
                balance_after=Decimal('0'),
                description=f"Job payout - {job_title}",
                job_id=job_id,
                stripe_payment_id=payout_result.get('transfer_id')
            )
            
            # Save to database
            if self.db:
                self._save_transaction(transaction)
            
            return {
                'success': True,
                'transaction': transaction,
                'payout_amount': payout_amount,
                'transfer_id': payout_result.get('transfer_id')
            }
        else:
            return {
                'success': False,
                'error': payout_result.get('error', 'Payout failed')
            }
    
    def _check_auto_reload(self, plumber_id: int, current_balance: Decimal):
        """
        Check if auto-reload should trigger
        
        If plumber has auto-reload enabled and balance falls below threshold,
        automatically purchase more credits
        """
        if self.db:
            # Query plumber settings
            # auto_reload_enabled, auto_reload_threshold, auto_reload_amount
            pass
        
        # Simulation
        auto_reload_enabled = True
        auto_reload_threshold = Decimal('50.00')
        auto_reload_amount = Decimal('250.00')
        
        if auto_reload_enabled and current_balance <= auto_reload_threshold:
            print(f"Auto-reload triggered for plumber {plumber_id}")
            # In production, charge saved payment method
            # self.purchase_credits(plumber_id, float(auto_reload_amount), saved_payment_method)
    
    def _save_transaction(self, transaction: Transaction):
        """Save transaction to database"""
        # In production: INSERT INTO transactions ...
        print(f"Transaction saved: {transaction.transaction_type.value} £{transaction.amount}")
    
    def _update_balance(self, plumber_id: int, new_balance: Decimal):
        """Update plumber's credit balance"""
        # In production: UPDATE plumbers SET credit_balance = new_balance WHERE id = plumber_id
        print(f"Updated plumber {plumber_id} balance to £{new_balance}")
    
    def get_transaction_history(
        self,
        plumber_id: int,
        limit: int = 50
    ) -> list:
        """Get recent transactions for plumber"""
        if self.db:
            # SELECT * FROM transactions WHERE plumber_id = ? ORDER BY created_at DESC LIMIT ?
            pass
        
        # Simulation
        return []


class PricingTiers:
    """
    Credit purchase pricing tiers
    """
    
    TIERS = [
        {
            'amount': 100,
            'bonus': 0,
            'total_credits': 100,
            'estimated_leads': '4-10 leads',
            'popular': False
        },
        {
            'amount': 250,
            'bonus': 12.50,  # 5% bonus
            'total_credits': 262.50,
            'estimated_leads': '10-25 leads',
            'popular': True
        },
        {
            'amount': 500,
            'bonus': 37.50,  # 7.5% bonus
            'total_credits': 537.50,
            'estimated_leads': '20-50 leads',
            'popular': False
        },
        {
            'amount': 1000,
            'bonus': 100,  # 10% bonus
            'total_credits': 1100,
            'estimated_leads': '40-100 leads',
            'popular': False
        }
    ]
    
    @classmethod
    def get_tier(cls, amount: float) -> Optional[Dict]:
        """Get pricing tier for amount"""
        for tier in cls.TIERS:
            if tier['amount'] == amount:
                return tier
        return None
    
    @classmethod
    def format_pricing_table(cls) -> str:
        """Format pricing tiers as display table"""
        lines = [
            "CREDIT PRICING TIERS",
            "=" * 60,
            ""
        ]
        
        for tier in cls.TIERS:
            popular = " ⭐ POPULAR" if tier['popular'] else ""
            lines.append(f"£{tier['amount']:.0f}{popular}")
            lines.append(f"  • Get: £{tier['total_credits']:.2f} credits")
            if tier['bonus'] > 0:
                lines.append(f"  • Bonus: £{tier['bonus']:.2f} ({tier['bonus']/tier['amount']*100:.1f}%)")
            lines.append(f"  • Estimated: {tier['estimated_leads']}")
            lines.append("")
        
        return "\n".join(lines)


# ================================================================
# USAGE EXAMPLE
# ================================================================

if __name__ == "__main__":
    print("PAYMENT & CREDIT MANAGEMENT - DEMO")
    print("="*60)
    
    # Initialize credit manager
    credit_manager = CreditManager()
    
    # Show pricing tiers
    print("\n" + PricingTiers.format_pricing_table())
    
    # Example 1: Plumber purchases credits
    print("\n1. CREDIT PURCHASE")
    print("-"*60)
    
    result = credit_manager.purchase_credits(
        plumber_id=1,
        amount=250.00,
        payment_method_id='pm_123456'
    )
    
    if result['success']:
        print(f"✓ Purchase successful")
        print(f"  Amount: £{result['transaction'].amount}")
        print(f"  New balance: £{result['new_balance']}")
    else:
        print(f"✗ Purchase failed: {result['error']}")
    
    # Example 2: Charge lead fee when plumber accepts job
    print("\n\n2. CHARGE LEAD FEE")
    print("-"*60)
    
    result = credit_manager.charge_lead_fee(
        plumber_id=1,
        job_id=12345,
        fee_amount=Decimal('25.00'),
        job_title="Leaking kitchen tap - SW19"
    )
    
    if result['success']:
        print(f"✓ Lead fee charged")
        print(f"  Fee: £{result['fee_charged']}")
        print(f"  New balance: £{result['new_balance']}")
    else:
        print(f"✗ Charge failed: {result['error']}")
    
    # Example 3: Refund lead fee (bad lead)
    print("\n\n3. REFUND LEAD FEE")
    print("-"*60)
    
    result = credit_manager.refund_lead_fee(
        plumber_id=1,
        job_id=12345,
        refund_amount=Decimal('12.50'),  # 50% refund
        reason="Customer never responded"
    )
    
    if result['success']:
        print(f"✓ Refund processed")
        print(f"  Refund: £{result['refund_amount']}")
        print(f"  New balance: £{result['new_balance']}")
    
    # Example 4: Job payout
    print("\n\n4. JOB PAYOUT TO PLUMBER")
    print("-"*60)
    
    result = credit_manager.process_job_payout(
        plumber_id=1,
        job_id=12345,
        payout_amount=Decimal('111.37'),
        job_title="Leaking kitchen tap - SW19",
        stripe_account_id='acct_123456'
    )
    
    if result['success']:
        print(f"✓ Payout sent")
        print(f"  Amount: £{result['payout_amount']}")
        print(f"  Transfer ID: {result.get('transfer_id')}")
    else:
        print(f"✗ Payout failed: {result['error']}")
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("\nTo enable real payments:")
    print("Set STRIPE_SECRET_KEY environment variable")
    print("pip install stripe")
