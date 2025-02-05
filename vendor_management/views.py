import logging
import pandas as pd
from typing import Dict, List, Tuple, Optional
from django.core.files.storage import FileSystemStorage
from django.contrib import messages
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

load_dotenv()

class Config:
    MAX_FILE_SIZE = 25 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
    CHUNK_SIZE = 10000
    MAX_COLUMNS = 29
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
    MAX_WORKERS = 5

class FileHandlerError(Exception):
    """Custom exception for file handling errors"""
    pass

class EmailServiceError(Exception):
    """Custom exception for email service errors"""
    pass

class FileHandler:
    @staticmethod
    def validate_file(file) -> Tuple[bool, str]:
        logger.info(f"Validating file: {getattr(file, 'name', 'No file')}")
        try:
            if not file:
                raise FileHandlerError("No file uploaded")
            
            extension = file.name.split('.')[-1].lower()
            if extension not in Config.ALLOWED_EXTENSIONS:
                raise FileHandlerError(f"Invalid file type. Allowed types: {', '.join(Config.ALLOWED_EXTENSIONS)}")
            
            if file.size > Config.MAX_FILE_SIZE:
                raise FileHandlerError(f"File size exceeds {Config.MAX_FILE_SIZE // (1024*1024)}MB limit")
                
            return True, ""

        except FileHandlerError as e:
            logger.error(f"File validation error: {str(e)}")
            return False, str(e)
        except Exception as e:
            logger.error(f"Unexpected error during file validation: {str(e)}", exc_info=True)
            return False, "An unexpected error occurred during file validation"

    @staticmethod
    def process_file(file_path: str) -> Optional[pd.DataFrame]:
        logger.info(f"Processing file: {file_path}")
        try:
            if file_path.endswith('.csv'):
                chunks = pd.read_csv(file_path, chunksize=Config.CHUNK_SIZE, encoding='utf-8')
                data = pd.concat(chunks, ignore_index=True)
            else:
                data = pd.read_excel(file_path)
            
            if data.empty:
                raise FileHandlerError("File contains no data")
                
            return data.iloc[:, :Config.MAX_COLUMNS].fillna("N/A")

        except Exception as e:
            logger.error(f"File processing error: {str(e)}", exc_info=True)
            raise FileHandlerError(f"Error processing file: {str(e)}")

class EmailService:
    def __init__(self):
        self.sender_email = Config.EMAIL_HOST_USER
        self.sender_password = Config.EMAIL_HOST_PASSWORD
        if not self.sender_email or not self.sender_password:
            raise EmailServiceError("Email credentials not properly configured")

    @staticmethod
    def format_route_email_body(route_data: List[Dict]) -> str:
        try:
            route_no = route_data[0].get('Route No', 'N/A')
            body = f"<h2>Route Number: {route_no}</h2><h3>Vehicle Details:</h3>"
            
            for vehicle in route_data:
                body += (
                    "<div style='margin-bottom: 20px; padding: 10px; border: 1px solid #ccc;'>"
                    f"<p>🔹 Vendor Name: {vehicle.get('Vendor Name', 'N/A')}</p>"
                    f"<p>🔹 Contact: {vehicle.get('Contact No.', 'N/A')}</p>"
                    f"<p>🔹 Email: {vehicle.get('Vendor Email', 'N/A')}</p>"
                    f"<p>🔹 Address: {vehicle.get('Address (Office Reporting Time 07:20 Hrs & Departure Time 16:45 Hrs)', 'N/A')}</p>"
                    "</div>"
                )
            
            return body + "<p>Best regards,<br>Admin Team</p>"
        except Exception as e:
            logger.error(f"Error formatting email body: {str(e)}", exc_info=True)
            raise EmailServiceError(f"Error formatting email body: {str(e)}")

    def send_email(self, to_email: str, subject: str, body: str, attachment_path: str = None) -> bool:
        """Send email with improved error handling and logging"""
        logger.info(f"Attempting to send email to: {to_email}")
        
        # Basic email validation
        if not isinstance(to_email, str) or '@' not in to_email or to_email.lower() == 'vendor email':
            logger.warning(f"Invalid email address: {to_email}")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')  # Changed to 'alternative' for better HTML support
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Attach HTML body
            html_part = MIMEText(body, 'html', 'utf-8')
            msg.attach(html_part)

            # Handle attachment
            if attachment_path:
                if not os.path.exists(attachment_path):
                    logger.error(f"Attachment file not found: {attachment_path}")
                    raise EmailServiceError("Attachment file not found")
                
                try:
                    with open(attachment_path, 'rb') as f:
                        attachment = MIMEApplication(f.read())
                        attachment.add_header(
                            'Content-Disposition', 
                            'attachment', 
                            filename=os.path.basename(attachment_path)
                        )
                        msg.attach(attachment)
                        logger.info(f"Attached file: {attachment_path}")
                except Exception as e:
                    logger.error(f"Error attaching file: {str(e)}")
                    raise EmailServiceError(f"Error attaching file: {str(e)}")

            # Connect to SMTP server with explicit SSL/TLS
            logger.info("Connecting to SMTP server...")
            with smtplib.SMTP(Config.EMAIL_HOST, Config.EMAIL_PORT, timeout=30) as server:
                server.set_debuglevel(1)  # Enable SMTP debug output
                server.ehlo()  # Identify ourselves to the server
                server.starttls()  # Enable TLS encryption
                server.ehlo()  # Re-identify ourselves over TLS connection
                
                # Login
                logger.info("Attempting SMTP login...")
                server.login(self.sender_email, self.sender_password)
                
                # Send email
                logger.info("Sending email...")
                server.send_message(msg)

            logger.info(f"Email successfully sent to {to_email}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication failed: {str(e)}")
            raise EmailServiceError("Email authentication failed. Check your credentials.")
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error occurred: {str(e)}")
            raise EmailServiceError(f"SMTP error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error sending email to {to_email}: {str(e)}", exc_info=True)
            raise EmailServiceError(f"Error sending email: {str(e)}")





def handle_vendor_form(request: HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return render(request, 'front/index.html', 
                     {'vendor_data_dict': request.session.get('vendor_data_dict')})

    try:
        uploaded_file = request.FILES.get('vendor_file')
        is_valid, error_message = FileHandler.validate_file(uploaded_file)
        
        if not is_valid:
            messages.error(request, error_message)
            return redirect('handle_vendor_form')

        fs = FileSystemStorage(location=settings.MEDIA_ROOT)
        file_path = fs.save(uploaded_file.name, uploaded_file)
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)

        try:
            data = FileHandler.process_file(full_path)
            vendor_data_dict = data.to_dict(orient='records')
            request.session['vendor_data_dict'] = vendor_data_dict
            request.session['uploaded_file_path'] = full_path
            messages.success(request, 'File processed successfully!')

        except FileHandlerError as e:
            logger.error(f"File processing error: {str(e)}")
            messages.error(request, str(e))
            if os.path.exists(full_path):
                os.remove(full_path)

    except Exception as e:
        logger.error(f"Unexpected error in handle_vendor_form: {str(e)}", exc_info=True)
        messages.error(request, "An unexpected error occurred while processing the file")

    return render(request, 'front/index.html', 
                 {'vendor_data_dict': request.session.get('vendor_data_dict')})




def send_vendor_emails(request: HttpRequest) -> HttpResponse:
    """Updated send_vendor_emails function with better error handling"""
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid method"}, status=400)

    try:
        vendor_data = request.session.get('vendor_data_dict')
        file_path = request.session.get('uploaded_file_path')

        if not vendor_data or not file_path:
            logger.error("Missing vendor data or file path in session")
            return JsonResponse({"error": "No data or file found"}, status=400)

        if not os.path.exists(file_path):
            logger.error(f"Attachment file not found: {file_path}")
            return JsonResponse({"error": "Attachment file not found"}, status=400)

        route_groups = {}
        # Group vendors by route number
        for row in vendor_data:
            route_no = row.get('Route No')
            if route_no:
                if route_no not in route_groups:
                    route_groups[route_no] = []
                route_groups[route_no].append(row)

        email_service = EmailService()
        success_count = 0
        failed_emails = []
        processed_emails = set()  # Track processed emails to avoid duplicates

        for route_no, route_data in route_groups.items():
            logger.info(f"Processing route: {route_no}")
            
            # Get unique valid emails for this route
            emails = {
                row.get('Vendor Email') for row in route_data 
                if isinstance(row.get('Vendor Email'), str) 
                and '@' in row.get('Vendor Email')
                and row.get('Vendor Email').lower() != 'vendor email'
            }
            
            if not emails:
                logger.warning(f"No valid emails found for route {route_no}")
                continue

            subject = f'Route {route_no} - Vehicle Details'
            try:
                body = email_service.format_route_email_body(route_data)
                
                for email in emails:
                    if email in processed_emails:
                        logger.info(f"Skipping duplicate email: {email}")
                        continue
                        
                    processed_emails.add(email)
                    try:
                        if email_service.send_email(email, subject, body, file_path):
                            success_count += 1
                        else:
                            failed_emails.append(email)
                    except EmailServiceError as e:
                        logger.error(f"Failed to send email to {email}: {str(e)}")
                        failed_emails.append(email)
                        
            except Exception as e:
                logger.error(f"Error processing route {route_no}: {str(e)}")
                continue

        response_data = {
            "message": "Email processing completed",
            "success_count": success_count,
            "failed_count": len(failed_emails),
            "total_routes": len(route_groups),
            "total_unique_emails": len(processed_emails)
        }

        if failed_emails:
            response_data["failed_emails"] = failed_emails
            
        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Unexpected error in send_vendor_emails: {str(e)}", exc_info=True)
        return JsonResponse({
            "error": "An unexpected error occurred while sending emails",
            "details": str(e)
        }, status=500)