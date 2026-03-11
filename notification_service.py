import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.rest import Client

class EmailService:
    """Email service using SendGrid"""
    
    def __init__(self):
        self.api_key = os.getenv('SENDGRID_API_KEY')
        self.from_email = os.getenv('SENDGRID_FROM_EMAIL', 'hello@besttrade.uk')
        
    def send_email(self, to_email, subject, html_content=None, body=None):
        """Send email via SendGrid"""
        if not self.api_key:
            print("Warning: SENDGRID_API_KEY not set. Email not sent.")
            return False
            
        try:
            # Use html_content if provided, otherwise use body
            content = html_content if html_content else body
            
            message = Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject=subject,
                html_content=content
            )
            
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            
            print(f"Email sent to {to_email}: {response.status_code}")
            return True
            
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False


class SMSService:
    """SMS service using Twilio"""
    
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            
    def send_sms(self, to_phone, message):
        """Send SMS via Twilio"""
        if not self.client:
            print("Warning: Twilio credentials not set. SMS not sent.")
            return False
            
        try:
            message = self.client.messages.create(
                body=message,
                from_=self.phone_number,
                to=to_phone
            )
            
            print(f"SMS sent to {to_phone}: {message.sid}")
            return True
            
        except Exception as e:
            print(f"Error sending SMS: {str(e)}")
            return False


class NotificationService:
    """Main notification service combining email and SMS"""
    
    def __init__(self):
        self.email_service = EmailService()
        self.sms_service = SMSService()
    
    # Backward compatibility - delegate to email_service
    def send_email(self, to_email, subject, html_content=None, body=None):
        """Delegate to email_service for backward compatibility"""
        return self.email_service.send_email(to_email, subject, html_content, body)
    
    def send_sms(self, to_phone, message):
        """Delegate to sms_service for backward compatibility"""
        return self.sms_service.send_sms(to_phone, message)
