"""
NOTIFICATION SYSTEM
Sends notifications via SMS, Email, and Push to plumbers and customers
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class NotificationChannel(Enum):
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    VOICE = "voice"


class NotificationType(Enum):
    NEW_LEAD = "new_lead"
    JOB_ACCEPTED = "job_accepted"
    JOB_DECLINED = "job_declined"
    QUOTE_REVISED = "quote_revised"
    JOB_COMPLETED = "job_completed"
    PAYMENT_DUE = "payment_due"
    PAYMENT_RECEIVED = "payment_received"
    LOW_CREDIT = "low_credit"
    PERFORMANCE_WARNING = "performance_warning"


@dataclass
class Notification:
    """Single notification to send"""
    recipient_type: str  # 'plumber' or 'customer'
    recipient_id: int
    channel: NotificationChannel
    notification_type: NotificationType
    title: str
    message: str
    data: Dict  # Additional data (job_id, etc.)
    priority: str = "normal"  # low, normal, high, urgent


class TwilioSMSService:
    """
    SMS notifications via Twilio
    
    Setup:
        pip install twilio
        export TWILIO_ACCOUNT_SID=your_sid
        export TWILIO_AUTH_TOKEN=your_token
        export TWILIO_PHONE_NUMBER=+44XXXXXXXXXX
    """
    
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        if self.account_sid and self.auth_token:
            try:
                from twilio.rest import Client
                self.client = Client(self.account_sid, self.auth_token)
                self.enabled = True
            except ImportError:
                print("Twilio not installed. Run: pip install twilio")
                self.enabled = False
        else:
            print("Twilio credentials not set. SMS disabled.")
            self.enabled = False
    
    def send_sms(self, to_number: str, message: str) -> Dict:
        """Send SMS via Twilio"""
        if not self.enabled:
            print(f"[SMS SIMULATION] To: {to_number}")
            print(f"Message: {message}")
            return {'status': 'simulated', 'sid': 'sim_123'}
        
        try:
            msg = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            return {
                'status': 'sent',
                'sid': msg.sid,
                'sent_at': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"SMS Error: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def make_voice_call(self, to_number: str, message: str) -> Dict:
        """Make emergency voice call via Twilio"""
        if not self.enabled:
            print(f"[VOICE SIMULATION] To: {to_number}")
            print(f"Message: {message}")
            return {'status': 'simulated'}
        
        try:
            # TwiML for text-to-speech
            twiml = f'<Response><Say>{message}</Say></Response>'
            
            call = self.client.calls.create(
                twiml=twiml,
                to=to_number,
                from_=self.from_number
            )
            return {'status': 'initiated', 'sid': call.sid}
        except Exception as e:
            print(f"Voice call error: {e}")
            return {'status': 'failed', 'error': str(e)}


class SendGridEmailService:
    """
    Email notifications via SendGrid
    
    Setup:
        pip install sendgrid
        export SENDGRID_API_KEY=your_key
        export FROM_EMAIL=noreply@yourplatform.com
    """
    
    def __init__(self):
        self.api_key = os.getenv('SENDGRID_API_KEY')
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@plumberplatform.com')
        
        if self.api_key:
            try:
                from sendgrid import SendGridAPIClient
                from sendgrid.helpers.mail import Mail
                self.client = SendGridAPIClient(self.api_key)
                self.Mail = Mail
                self.enabled = True
            except ImportError:
                print("SendGrid not installed. Run: pip install sendgrid")
                self.enabled = False
        else:
            print("SendGrid API key not set. Email disabled.")
            self.enabled = False
    
    def send_email(self, to_email: str, subject: str, html_content: str) -> Dict:
        """Send email via SendGrid"""
        if not self.enabled:
            print(f"[EMAIL SIMULATION] To: {to_email}")
            print(f"Subject: {subject}")
            print(f"Body: {html_content[:100]}...")
            return {'status': 'simulated'}
        
        try:
            message = self.Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_content
            )
            
            response = self.client.send(message)
            return {
                'status': 'sent',
                'status_code': response.status_code,
                'sent_at': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Email error: {e}")
            return {'status': 'failed', 'error': str(e)}


class FirebasePushService:
    """
    Push notifications via Firebase Cloud Messaging
    
    Setup:
        pip install firebase-admin
        Place firebase-credentials.json in project root
    """
    
    def __init__(self):
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
            
            cred_path = 'firebase-credentials.json'
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                self.messaging = messaging
                self.enabled = True
            else:
                print("Firebase credentials not found. Push notifications disabled.")
                self.enabled = False
        except ImportError:
            print("Firebase not installed. Run: pip install firebase-admin")
            self.enabled = False
    
    def send_push(self, device_token: str, title: str, body: str, data: Dict) -> Dict:
        """Send push notification to device"""
        if not self.enabled:
            print(f"[PUSH SIMULATION]")
            print(f"Title: {title}")
            print(f"Body: {body}")
            return {'status': 'simulated'}
        
        try:
            message = self.messaging.Message(
                notification=self.messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data,
                token=device_token
            )
            
            response = self.messaging.send(message)
            return {'status': 'sent', 'message_id': response}
        except Exception as e:
            print(f"Push notification error: {e}")
            return {'status': 'failed', 'error': str(e)}


class NotificationService:
    """
    Main notification service that orchestrates all channels
    """
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self.sms_service = TwilioSMSService()
        self.email_service = SendGridEmailService()
        self.push_service = FirebasePushService()
    
    def send_to_plumber(
        self,
        plumber_id: int,
        plumber_phone: str,
        plumber_email: str,
        notification: Notification,
        device_token: Optional[str] = None
    ) -> Dict:
        """
        Send notification to plumber via their preferred channels
        """
        results = {}
        
        # Determine which channels to use based on notification type and plumber prefs
        # For now, send via all enabled channels
        
        # 1. Push notification (instant)
        if device_token and notification.channel in [NotificationChannel.PUSH, None]:
            push_result = self.push_service.send_push(
                device_token=device_token,
                title=notification.title,
                body=notification.message,
                data=notification.data
            )
            results['push'] = push_result
        
        # 2. SMS (instant)
        if notification.channel in [NotificationChannel.SMS, None]:
            sms_result = self.sms_service.send_sms(
                to_number=plumber_phone,
                message=f"{notification.title}\n\n{notification.message}"
            )
            results['sms'] = sms_result
        
        # 3. Email (backup)
        if notification.channel in [NotificationChannel.EMAIL, None]:
            email_html = self._format_email_html(notification)
            email_result = self.email_service.send_email(
                to_email=plumber_email,
                subject=notification.title,
                html_content=email_html
            )
            results['email'] = email_result
        
        # 4. Voice call (emergency only)
        if notification.priority == 'urgent' and notification.channel == NotificationChannel.VOICE:
            voice_result = self.sms_service.make_voice_call(
                to_number=plumber_phone,
                message=notification.message
            )
            results['voice'] = voice_result
        
        # Log to database
        if self.db:
            self._log_notification(plumber_id, None, notification, results)
        
        return results
    
    def send_to_customer(
        self,
        customer_id: int,
        customer_phone: str,
        customer_email: Optional[str],
        notification: Notification
    ) -> Dict:
        """
        Send notification to customer
        """
        results = {}
        
        # Customers typically only get SMS and email (no app)
        
        # 1. SMS
        if notification.channel in [NotificationChannel.SMS, None]:
            sms_result = self.sms_service.send_sms(
                to_number=customer_phone,
                message=f"{notification.title}\n\n{notification.message}"
            )
            results['sms'] = sms_result
        
        # 2. Email (if available)
        if customer_email and notification.channel in [NotificationChannel.EMAIL, None]:
            email_html = self._format_email_html(notification)
            email_result = self.email_service.send_email(
                to_email=customer_email,
                subject=notification.title,
                html_content=email_html
            )
            results['email'] = email_result
        
        # Log to database
        if self.db:
            self._log_notification(None, customer_id, notification, results)
        
        return results
    
    def _format_email_html(self, notification: Notification) -> str:
        """Format notification as HTML email"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2563eb; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
                .button {{ 
                    display: inline-block; 
                    background: #2563eb; 
                    color: white; 
                    padding: 12px 24px; 
                    text-decoration: none; 
                    border-radius: 6px;
                    margin: 20px 0;
                }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>{notification.title}</h2>
                </div>
                <div class="content">
                    <p>{notification.message.replace(chr(10), '<br>')}</p>
                </div>
                <div class="footer">
                    <p>Plumber Matching Platform</p>
                    <p>Reply STOP to unsubscribe</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _log_notification(self, plumber_id, customer_id, notification, results):
        """Log notification to database"""
        # Placeholder - in production, save to notifications table
        print(f"Logged notification: {notification.notification_type.value}")


class NotificationTemplates:
    """
    Pre-built notification templates for common scenarios
    """
    
    @staticmethod
    def new_lead_for_plumber(
        job_title: str,
        postcode: str,
        urgency: str,
        earnings: float,
        work_hours: float,
        lead_fee: float,
        job_id: int
    ) -> Notification:
        """Notification when new lead is available"""
        
        urgency_emoji = {
            'emergency': '🚨',
            'today': '⚡',
            'this_week': '📅',
            'flexible': '🔧'
        }
        
        title = f"{urgency_emoji.get(urgency, '🔧')} New Lead: {job_title}"
        
        message = f"""
New plumbing job available!

📍 Location: {postcode}
⏱️ Urgency: {urgency.replace('_', ' ').title()}
💷 Your earnings: £{earnings:.2f}
⏰ Work time: ~{work_hours:.1f} hours
💳 Lead fee: £{lead_fee:.2f}

Reply ACCEPT to claim this lead
Reply DECLINE to pass

Job ID: #{job_id}
        """.strip()
        
        return Notification(
            recipient_type='plumber',
            recipient_id=0,  # Set by caller
            channel=NotificationChannel.SMS,
            notification_type=NotificationType.NEW_LEAD,
            title=title,
            message=message,
            data={'job_id': job_id, 'action_required': True},
            priority='high' if urgency == 'emergency' else 'normal'
        )
    
    @staticmethod
    def job_accepted_customer(
        plumber_name: str,
        plumber_phone: str,
        rating: float,
        estimated_price: float,
        job_id: int
    ) -> Notification:
        """Notification to customer when plumber accepts"""
        
        title = "Plumber Found!"
        
        message = f"""
Great news! We've found a plumber for your job.

👷 {plumber_name}
⭐ {rating}/5.0 rating
📞 {plumber_phone}
💷 Estimated: £{estimated_price:.2f}

They will contact you shortly to confirm details and arrange a time.

Job reference: #{job_id}
        """.strip()
        
        return Notification(
            recipient_type='customer',
            recipient_id=0,
            channel=NotificationChannel.SMS,
            notification_type=NotificationType.JOB_ACCEPTED,
            title=title,
            message=message,
            data={'job_id': job_id},
            priority='normal'
        )
    
    @staticmethod
    def quote_revised(
        job_title: str,
        original_price: float,
        new_price: float,
        reason: str,
        job_id: int
    ) -> Notification:
        """Notification when plumber revises quote on-site"""
        
        title = "Quote Updated"
        
        message = f"""
The plumber has updated the quote for your job.

Job: {job_title}

Original estimate: £{original_price:.2f}
New quote: £{new_price:.2f}

Reason: {reason}

Reply YES to accept the new quote
Reply NO to cancel

Job #{job_id}
        """.strip()
        
        return Notification(
            recipient_type='customer',
            recipient_id=0,
            channel=NotificationChannel.SMS,
            notification_type=NotificationType.QUOTE_REVISED,
            title=title,
            message=message,
            data={'job_id': job_id, 'action_required': True},
            priority='high'
        )
    
    @staticmethod
    def low_credit_warning(
        current_balance: float,
        plumber_id: int
    ) -> Notification:
        """Warning when plumber credit balance is low"""
        
        title = "⚠️ Low Credit Balance"
        
        message = f"""
Your credit balance is running low.

Current balance: £{current_balance:.2f}

You won't receive new leads once your balance reaches £0.

Top up now to keep receiving jobs:
• £100 = 4-10 leads
• £250 = 10-25 leads
• £500 = 20-50 leads

Login to top up: [link]
        """.strip()
        
        return Notification(
            recipient_type='plumber',
            recipient_id=plumber_id,
            channel=NotificationChannel.EMAIL,
            notification_type=NotificationType.LOW_CREDIT,
            title=title,
            message=message,
            data={'current_balance': current_balance},
            priority='normal'
        )
    
    @staticmethod
    def invoice_to_customer(
        job_title: str,
        plumber_name: str,
        labour_cost: float,
        travel_cost: float,
        materials_cost: float,
        total: float,
        invoice_id: int
    ) -> Notification:
        """Send invoice to customer after job completion"""
        
        title = f"Invoice for {job_title}"
        
        message = f"""
Job completed by {plumber_name}

INVOICE BREAKDOWN:
Labour: £{labour_cost:.2f}
Travel: £{travel_cost:.2f}
Materials: £{materials_cost:.2f}
─────────────────
TOTAL: £{total:.2f}

Payment due within 7 days.

Invoice #{invoice_id}
View full invoice: [link]
        """.strip()
        
        return Notification(
            recipient_type='customer',
            recipient_id=0,
            channel=NotificationChannel.EMAIL,
            notification_type=NotificationType.PAYMENT_DUE,
            title=title,
            message=message,
            data={'invoice_id': invoice_id},
            priority='normal'
        )


# ================================================================
# USAGE EXAMPLE
# ================================================================

if __name__ == "__main__":
    print("NOTIFICATION SYSTEM - DEMO")
    print("="*60)
    
    # Initialize service
    notification_service = NotificationService()
    
    # Example 1: Send new lead notification to plumber
    print("\n1. NEW LEAD NOTIFICATION TO PLUMBER")
    print("-"*60)
    
    new_lead_notification = NotificationTemplates.new_lead_for_plumber(
        job_title="Leaking kitchen tap",
        postcode="SW19 2AB",
        urgency="today",
        earnings=111.37,
        work_hours=1.0,
        lead_fee=15.00,
        job_id=12345
    )
    
    results = notification_service.send_to_plumber(
        plumber_id=1,
        plumber_phone="+447700900001",
        plumber_email="plumber@example.com",
        notification=new_lead_notification
    )
    
    print(f"\nNotification sent via: {list(results.keys())}")
    
    # Example 2: Notify customer that plumber accepted
    print("\n\n2. JOB ACCEPTED NOTIFICATION TO CUSTOMER")
    print("-"*60)
    
    job_accepted_notification = NotificationTemplates.job_accepted_customer(
        plumber_name="John Smith",
        plumber_phone="07700 900 001",
        rating=4.8,
        estimated_price=136.00,
        job_id=12345
    )
    
    results = notification_service.send_to_customer(
        customer_id=1,
        customer_phone="+447700900123",
        customer_email="customer@example.com",
        notification=job_accepted_notification
    )
    
    print(f"\nNotification sent via: {list(results.keys())}")
    
    # Example 3: Low credit warning
    print("\n\n3. LOW CREDIT WARNING")
    print("-"*60)
    
    low_credit_notification = NotificationTemplates.low_credit_warning(
        current_balance=35.00,
        plumber_id=1
    )
    
    results = notification_service.send_to_plumber(
        plumber_id=1,
        plumber_phone="+447700900001",
        plumber_email="plumber@example.com",
        notification=low_credit_notification
    )
    
    print(f"\nNotification sent via: {list(results.keys())}")
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("\nTo enable real notifications:")
    print("1. SMS: Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER")
    print("2. Email: Set SENDGRID_API_KEY, FROM_EMAIL")
    print("3. Push: Add firebase-credentials.json")
