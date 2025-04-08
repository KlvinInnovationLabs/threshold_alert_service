import time
import threading
import smtplib
from queue import Queue
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

from config.settings import (SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD, LOGGER_EMAILS, MAX_EMAIL_RETRY_ATTEMPTS)
from utils.db_interface import get_emails
from utils.logging import get_logger, log_to_file
from notification.email_formatter import create_email_subject, create_html_content

logger = get_logger(__name__)

# Get test email recipient from environment variable
TEST_EMAIL = os.environ.get("TEST_EMAIL_RECIPIENT", "test@example.com")
USE_TEST_EMAIL = os.environ.get("USE_TEST_EMAIL", "false").lower() == "true"

class EmailSender:
    """
    Handles email sending with retry logic.
    
    Provides methods to send emails and manage failed email retries.
    """
    
    def __init__(self, rate_limiter):
        self.rate_limiter = rate_limiter
        self.retry_queue = Queue()
        self.log_path = "logs/email_sender.log"
        
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Start retry thread
        self._start_retry_thread()
    
    def send_email(self, recipients, subject, content, log_path=None):
        """
        Send email to recipients.
        
        Args:
            recipients: List of email recipients
            subject: Email subject
            content: Email HTML content
            log_path: Path to log file
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not log_path:
            log_path = self.log_path
            
        log_to_file("\n\n Inside send_email\n", log_path)
        logger.info(f"Sending email to: {recipients}")
        # Use test email if configured
        if USE_TEST_EMAIL:
            logger.info(f"Using test email address: {TEST_EMAIL}")
            all_recipients = [TEST_EMAIL]
        else:
            # Add logger emails to recipients
            all_recipients = recipients + LOGGER_EMAILS
        
        # Join recipients into comma-separated string
        recipient_str = ",".join(all_recipients)
        
        try:
            # Set up the email server
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            
            # Log in to the server
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            
            # Set up the MIME
            message = MIMEMultipart("alternative")
            message["From"] = SENDER_EMAIL
            message["To"] = recipient_str
            message["Subject"] = subject
            
            # Attach HTML content
            message.attach(MIMEText(content, "html"))
            
            # Send the email
            response = server.send_message(message)
            
            # Close the connection
            server.quit()
            
            if not response:
                log_to_file("\nEmail sent successfully", log_path)
                logger.info("Email sent successfully")
                return True
            else:
                # If there were any failed recipients
                log_to_file(f"\nPartial email delivery failure: {response}", log_path)
                logger.warning(f"Partial email delivery failure: {response}")
                return False
                
        except Exception as e:
            log_to_file(f"Error while sending email: {e}", log_path)
            logger.error(f"Failed to send email: {e}")
            return False
    
    def queue_for_retry(self, email_data, attempt=1):
        """
        Queue a failed email for retry.
        
        Args:
            email_data: Dictionary with email data
            attempt: Current attempt number
        """
        if attempt <= MAX_EMAIL_RETRY_ATTEMPTS:
            email_data["attempt"] = attempt
            email_data["next_try"] = time.time() + 30  # Retry after 30 seconds
            self.retry_queue.put(email_data)
            logger.info(f"Email queued for retry (attempt {attempt}/{MAX_EMAIL_RETRY_ATTEMPTS})")
        else:
            logger.error(f"Email failed after {MAX_EMAIL_RETRY_ATTEMPTS} attempts: {email_data}")
            log_to_file(f"Email permanently failed after {MAX_EMAIL_RETRY_ATTEMPTS} attempts: {email_data}", self.log_path)
    
    def _start_retry_thread(self):
        """Start a background thread to process the retry queue."""
        def retry_job():
            while True:
                try:
                    # If queue is empty, wait and try again
                    if self.retry_queue.empty():
                        time.sleep(5)
                        continue
                    
                    # Get the next email to retry
                    email_data = self.retry_queue.get()
                    
                    # If it's not time to retry yet, put it back and wait
                    if email_data["next_try"] > time.time():
                        self.retry_queue.put(email_data)
                        time.sleep(5)
                        continue
                    
                    # Try to send the email
                    success = self.send_email(
                        email_data["recipients"],
                        email_data["subject"],
                        email_data["content"]
                    )
                    
                    if not success:
                        # Queue for another retry with incremented attempt
                        self.queue_for_retry(email_data, email_data["attempt"] + 1)
                    
                except Exception as e:
                    logger.error(f"Error in email retry thread: {e}")
                
                # Short sleep to avoid busy waiting
                time.sleep(1)
        
        retry_thread = threading.Thread(target=retry_job, daemon=True, name="EmailRetryThread")
        retry_thread.start()
        logger.info("Email retry thread started")
    
    def process_breaches(self, breaches, log_path):
        """
        Process breach notifications and send emails.
        
        Args:
            breaches: List of breach objects
            log_path: Path to log file
        """
        log_to_file("\nInside process_breaches", log_path)
        logger.info(f"Processing {len(breaches)} breaches for email notifications")
        
        # Group breaches by device for efficient email retrieval
        device_breaches = {}
        for breach in breaches:
            device_id = breach["device_id"]
            if device_id not in device_breaches:
                device_breaches[device_id] = []
            device_breaches[device_id].append(breach)
        
        # Get email recipients for each device and check rate limits
        emails_to_send = {}  # {email: [breaches]}
        
        for device_id, device_breach_list in device_breaches.items():
            # Check rate limits for each breach
            filtered_breaches = []
            for breach in device_breach_list:
                if self.rate_limiter.should_send(
                    breach["device_id"], 
                    breach["sensor_id"], 
                    breach["threshold_type"]
                ):
                    filtered_breaches.append(breach)
            
            if not filtered_breaches:
                logger.info(f"No breaches passed rate limiting for device {device_id}")
                continue
                
            # Get email recipients for this device
            try:
                # For each breach, get the recipients
                for breach in filtered_breaches:
                    threshold_type = breach["threshold_type"]
                    
                    try:
                        # Get recipients
                        recipients = get_emails(device_id, threshold_type)
                        
                        # Ensure recipients is a list or tuple
                        if isinstance(recipients, str):
                            recipients = [recipients]
                        
                        # Add each recipient as a key in the dictionary
                        for email in recipients:
                            # Convert email to string to ensure it's hashable
                            email_str = str(email).strip()
                            if email_str:
                                if email_str not in emails_to_send:
                                    emails_to_send[email_str] = []
                                emails_to_send[email_str].append(breach)
                                
                    except Exception as e:
                        logger.error(f"Error processing recipient for breach {breach['device_id']}/{breach['sensor_id']}: {e}")
                        
            except Exception as e:
                logger.error(f"Error getting email recipients for {device_id}: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        # Send emails to each recipient
        if not emails_to_send:
            logger.warning("No emails to send after processing breaches")
            return
            
        logger.info(f"Sending emails to {len(emails_to_send)} recipients")
        
        for recipient_email, recipient_breaches in emails_to_send.items():
            # Create email content
            subject = create_email_subject(recipient_breaches)
            html_content = create_html_content(recipient_breaches)
            
            log_to_file(f"\nSending email to {recipient_email} with {len(recipient_breaches)} breaches", log_path)
            
            # Try to send the email
            success = self.send_email([recipient_email], subject, html_content, log_path)
            
            if not success:
                # Queue for retry
                self.queue_for_retry({
                    "recipients": [recipient_email],
                    "subject": subject,
                    "content": html_content
                })