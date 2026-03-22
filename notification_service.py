"""
Best Trade - Notification Service
Handles Email (SendGrid) and SMS (Twilio) notifications
"""

import os
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

class EmailService:
    def __init__(self):
        self.sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
        self.from_email = os.getenv('SENDGRID_FROM_EMAIL', 'hello@besttrade.uk')
        
        if not self.sendgrid_api_key:
            print("WARNING: SENDGRID_API_KEY not set")
    
    def send_email(self, to_email: str, subject: str, html_content: str):
        """Send email via SendGrid"""
        try:
            if not self.sendgrid_api_key:
                print(f"Email would be sent to {to_email}: {subject}")
                return
            
            message = Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_content
            )
            
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            
            print(f"Email sent to {to_email}: {subject}")
            return response
            
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            raise


class SMSService:
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            print("WARNING: Twilio credentials not set")
    
    def send_sms(self, to_phone: str, message: str):
        """Send SMS via Twilio"""
        try:
            if not self.client:
                print(f"SMS would be sent to {to_phone}: {message}")
                return
            
            message = self.client.messages.create(
                body=message,
                from_=self.phone_number,
                to=to_phone
            )
            
            print(f"SMS sent to {to_phone}")
            return message
            
        except Exception as e:
            print(f"Error sending SMS: {str(e)}")
            raise


class NotificationService:
    def __init__(self):
        self.email_service = EmailService()
        self.sms_service = SMSService()


# Global notification service instance
notification_service = NotificationService()
