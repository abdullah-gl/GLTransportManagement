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
from email import encoders
from email.mime.base import MIMEBase
import os
from dotenv import load_dotenv

from .transport_image import TransportDataProcessor

# Initialize logging and environment variables
logger = logging.getLogger(__name__)
load_dotenv()

class Config:
    """Configuration settings for the application"""
    # File handling configurations
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
    CHUNK_SIZE = 10000
    MAX_COLUMNS = 29
    
    # Email configurations
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
    
    # Processing configurations
    MAX_WORKERS = 5
    
    # Required columns for vendor data
    REQUIRED_COLUMNS = [
        'S No', 'Route No', 'Emp Code', 'Name', 'SUV', 'Shift',
        'Vendor Name', 'Area', 'Location-Delhi', 'Pickup Time',
        'Address (Office Reporting Time 07:20 Hrs & Departure Time 16:45 Hrs)',
        'Vendor Email', 'Gender'
    ]

class FileHandlerError(Exception):
    """Custom exception for file handling related errors"""
    pass

class EmailServiceError(Exception):
    """Custom exception for email service related errors"""
    pass

class FileHandler:
    """Handles all file-related operations including validation and processing"""
    
    @staticmethod
    def validate_file(file) -> Tuple[bool, str]:
        """
        Validates uploaded file against size and type constraints
        
        Args:
            file: The uploaded file object
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        logger.info(f"Validating file: {getattr(file, 'name', 'No file')}")
        
        try:
            if not file:
                raise FileHandlerError("No file uploaded")
            
            extension = file.name.split('.')[-1].lower()
            if extension not in Config.ALLOWED_EXTENSIONS:
                raise FileHandlerError(
                    f"Invalid file type. Allowed types: {', '.join(Config.ALLOWED_EXTENSIONS)}"
                )
            
            if file.size > Config.MAX_FILE_SIZE:
                max_size_mb = Config.MAX_FILE_SIZE // (1024 * 1024)
                raise FileHandlerError(f"File size exceeds {max_size_mb}MB limit")
                
            return True, ""

        except FileHandlerError as e:
            logger.error(f"File validation error: {str(e)}")
            return False, str(e)
        except Exception as e:
            logger.error(f"Unexpected error during file validation: {str(e)}", exc_info=True)
            return False, "An unexpected error occurred during file validation"

    @staticmethod
    def process_file(file_path: str) -> Optional[pd.DataFrame]:
        """
        Processes the uploaded file and returns a DataFrame
        
        Args:
            file_path: Path to the uploaded file
            
        Returns:
            Optional[pd.DataFrame]: Processed DataFrame or None if processing fails
        """
        logger.info(f"Processing file: {file_path}")
        
        try:
            # Read file based on extension
            if file_path.endswith('.csv'):
                chunks = pd.read_csv(file_path, chunksize=Config.CHUNK_SIZE, encoding='utf-8')
                data = pd.concat(chunks, ignore_index=True)
            else:
                data = pd.read_excel(file_path)
            
            if data.empty:
                raise FileHandlerError("File contains no data")
            
            # Validate required columns
            missing_columns = set(Config.REQUIRED_COLUMNS) - set(data.columns)
            if missing_columns:
                raise FileHandlerError(f"Missing required columns: {', '.join(missing_columns)}")
                
            return data.iloc[:, :Config.MAX_COLUMNS].fillna("N/A")

        except Exception as e:
            logger.error(f"File processing error: {str(e)}", exc_info=True)
            raise FileHandlerError(f"Error processing file: {str(e)}")

class EmailService:
    """Handles email composition and sending operations"""
    
    def __init__(self):
        """Initialize email service with credentials"""
        self.sender_email = Config.EMAIL_HOST_USER
        self.sender_password = Config.EMAIL_HOST_PASSWORD
        
        if not self.sender_email or not self.sender_password:
            raise EmailServiceError("Email credentials not properly configured")

    @staticmethod
    def format_route_email_body(route_data: str) -> str:
        """
        Formats the email body with route information
        
        Args:
            route_data: Route information to include in email
            
        Returns:
            str: Formatted email body
        """
        return f"""
        Dear {route_data},
        
        Please find attached the All Route Excel File and Individual Route Image.
        
        Best regards,
        Admin Team
        """

    def send_email(self, vendor_email: str, subject: str, body: str, 
                  vendor_file_name: str, vendor_data: dict, vendor_name: str) -> bool:
        """
        Sends email with attachments to vendors
        
        Args:
            vendor_email: Recipient email address
            subject: Email subject
            body: Email body
            vendor_file_name: Path to vendor file attachment
            vendor_data: Vendor data dictionary
            vendor_name: Name of the vendor
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if '@' not in vendor_email:
            logger.warning(f"Invalid email address: {vendor_email}")
            return False

        try:
            # Create email message
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = vendor_email
            
            # Attach Excel file
            self._attach_file(msg, vendor_file_name)
            
            # Attach related images
            self._attach_vendor_images(msg, vendor_file_name, vendor_name)
            
            # Add email body
            msg.attach(MIMEText(body))
            
            # Send email
            with smtplib.SMTP(Config.EMAIL_HOST, Config.EMAIL_PORT) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {vendor_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {vendor_email}: {str(e)}")
            return False

    def _attach_file(self, msg: MIMEMultipart, file_path: str) -> None:
        """Helper method to attach files to email"""
        with open(file_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(file_path)}",
            )
            msg.attach(part)

    def _attach_vendor_images(self, msg: MIMEMultipart, vendor_file_name: str, 
                            vendor_name: str) -> None:
        """Helper method to attach vendor-specific images to email"""
        vendor_directory_path = os.path.dirname(vendor_file_name)
        image_pattern = vendor_name.lower().replace(" ", "_")
        
        for filename in os.listdir(vendor_directory_path):
            if (filename.lower().endswith((".png", ".jpg", ".jpeg")) and 
                image_pattern in filename.lower()):
                self._attach_file(msg, os.path.join(vendor_directory_path, filename))

def handle_vendor_form(request: HttpRequest) -> HttpResponse:
    """
    Handles the vendor form submission and file processing
    
    Args:
        request: HTTP request object
        
    Returns:
        HttpResponse: Rendered template with processing results
    """
    if request.method != 'POST':
        return render(request, 'front/index.html', 
                     {'vendor_data_dict': request.session.get('vendor_data_dict')})

    try:
        uploaded_file = request.FILES.get('vendor_file')
        is_valid, error_message = FileHandler.validate_file(uploaded_file)
        
        if not is_valid:
            messages.error(request, error_message)
            return redirect('handle_vendor_form')
        
        # Create vendor media directory if it doesn't exist
        vendor_media_path = os.path.join(settings.MEDIA_ROOT, "vendor")
        os.makedirs(vendor_media_path, exist_ok=True)
        
        # Save and process file
        fs = FileSystemStorage(location=vendor_media_path)
        file_path = fs.save(uploaded_file.name, uploaded_file)
        full_path = fs.path(file_path)

        try:
            data = FileHandler.process_file(full_path)
            vendor_data_dict = data.to_dict(orient='records')
            
            # Store processed data in session
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
    """
    Processes vendor data and sends emails to vendors
    
    Args:
        request: HTTP request object
        
    Returns:
        JsonResponse: Processing results and status
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid method"}, status=400)

    try:
        # Get vendor data and file path from session
        vendor_data = request.session.get('vendor_data_dict')
        file_path = request.session.get('uploaded_file_path')
        
        if not vendor_data or not file_path:
            logger.error("Missing vendor data or file path in session")
            return JsonResponse({"error": "No data or file found"}, status=400)

        if not os.path.exists(file_path):
            logger.error(f"Attachment file not found: {file_path}")
            return JsonResponse({"error": "Attachment file not found"}, status=400)

        # Process vendor data
        processor = TransportDataProcessor(file_path)
        vendor_json_data = processor.process()
        
        # Initialize email service
        email_service = EmailService()
        success_count = 0
        failed_emails = []
        processed_emails = set()

        vendor_media_path = os.path.join(settings.MEDIA_ROOT, "vendor")

        for vendor_name, vendor_data in vendor_json_data.items():
            logger.info(f"Processing vendor: {vendor_name}")
            
            # Get vendor email from first route
            for route_no, route_data in vendor_data.items():
                vendor_email = route_data[0].get('Vendor Email', '')
                break

            if vendor_email in processed_emails:
                continue

            processed_emails.add(vendor_email)
            
            try:
                # Prepare email content
                subject = f'Route {vendor_name} - Vehicle Details'
                body = email_service.format_route_email_body(vendor_name)
                
                # Create vendor-specific Excel file
                df_dict = {
                    key: pd.DataFrame(value) for key, value in vendor_data.items()
                }
                final_df = pd.concat(df_dict.values(), ignore_index=True)
                final_df = final_df[Config.REQUIRED_COLUMNS]

                vendor_file_name = os.path.join(vendor_media_path, 
                                                f'{vendor_name}_vendor_route.xlsx')
                final_df.to_excel(vendor_file_name, index=False)
                
                # Send email
                if email_service.send_email(vendor_email, subject, body, 
                                          vendor_file_name, vendor_data, vendor_name):
                    success_count += 1
                else:
                    failed_emails.append(vendor_email)

                # Cleanup temporary files
                cleanup_vendor_files(vendor_media_path, vendor_name, vendor_file_name)

            except Exception as e:
                logger.error(f"Error processing vendor {vendor_name}: {str(e)}")
                failed_emails.append(vendor_email)
                continue

        return JsonResponse({
            "message": "Email processing completed",
            "success_count": success_count,
            "failed_count": len(failed_emails),
            "total_unique_emails": len(processed_emails),
            "failed_emails": failed_emails if failed_emails else None
        })

    except Exception as e:
        logger.error(f"Unexpected error in send_vendor_emails: {str(e)}", exc_info=True)
        return JsonResponse({
            "error": "An unexpected error occurred while sending emails",
            "details": str(e)
        }, status=500)

def cleanup_vendor_files(vendor_media_path: str, vendor_name: str, vendor_file_name: str)-> None:
    """
    Cleans up temporary vendor files after email processing
    
    Args:
        vendor_media_path: Path to vendor media directory
        vendor_name: Name of the vendor
        vendor_file_name: Path to vendor Excel file
    """
    # Remove generated images
    for filename in os.listdir(vendor_media_path):
        if (filename.lower().endswith((".png", ".jpg", ".jpeg")) and 
            vendor_name.lower().replace(" ", "_") in filename.lower()):
            file_path = os.path.join(vendor_media_path, filename)
            os.remove(file_path)
            logger.debug(f"Removed temporary image: {file_path}")
    
    # Remove generated Excel file
    os.remove(vendor_file_name)
    logger.debug(f"Removed temporary Excel file: {vendor_file_name}")