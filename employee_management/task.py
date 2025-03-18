# tasks.py
from celery import shared_task
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_email_task(subject, body, recipient, sender_email, sender_password, smtp_host, smtp_port):
    """Celery task to send email asynchronously"""
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        logger.info(f"Email sent successfully to {recipient}")
        return True

    except smtplib.SMTPException as e:
        logger.error(f"SMTP error while sending email to {recipient}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error while sending email to {recipient}: {str(e)}")
    
    return False
