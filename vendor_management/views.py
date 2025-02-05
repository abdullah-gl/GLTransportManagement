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
    def format_route_email_body(route_data: str) -> str:        
        body = f"""
        Dear {route_data},
        
        Please find the attached All route Excel File and with Indidual Route Image.
        
        Best regards,
        Admin Team
        """       
        return body

    def send_email(self, vendor_email: str, subject, body, vendor_file_name, vendor_data, vendor_name) -> bool:
        if '@' not in vendor_email:
            logger.warning(f"Invalid email: {vendor_email}")
            return False

        try:
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = vendor_email
            
            # Attach the XLSX file
            media_directory = settings.MEDIA_ROOT
            # xlsx_filename = os.path.join(media_directory, [filename for filename in os.listdir(media_directory) if filename.lower().endswith((".csv", ".xlsx"))][0])

            with open(vendor_file_name, "rb") as xlsx_file:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(xlsx_file.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={vendor_file_name}",
                )
                msg.attach(part)

            # Attach the image files
            vendor_directory_path = os.path.dirname(vendor_file_name)
            image_filenames = [os.path.join(vendor_directory_path, filename) for filename in os.listdir(vendor_directory_path) if filename.lower().endswith((".png", ".jpg", ".jpeg")) and vendor_name.lower().replace(" ", "_") in filename.lower()]
            for image_filename in image_filenames:
                with open(image_filename, "rb") as image_file:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(image_file.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={image_filename}",
                    )
                    msg.attach(part)

            
            html_part = MIMEText(body)
            msg.attach(html_part)
            msg.attach(part)

            with smtplib.SMTP(Config.EMAIL_HOST, Config.EMAIL_PORT) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent to {vendor_email}")
            return True

        except Exception as e:
            logger.error(f"Email failed to {vendor_email}: {str(e)}")
            return False




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
        
        vendor_media_path = os.path.join(settings.MEDIA_ROOT, "vendor")
        if not os.path.exists(vendor_media_path):
            os.makedirs(vendor_media_path)
        fs = FileSystemStorage(location=vendor_media_path)
        file_path = fs.save(uploaded_file.name, uploaded_file)
        full_path = fs.path(file_path)
        

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
        processor = TransportDataProcessor(file_path)
        vendor_json_data = processor.process()

        if not vendor_data or not file_path:
            logger.error("Missing vendor data or file path in session")
            return JsonResponse({"error": "No data or file found"}, status=400)

        if not os.path.exists(file_path):
            logger.error(f"Attachment file not found: {file_path}")
            return JsonResponse({"error": "Attachment file not found"}, status=400)

        # route_groups = {}
        # Group vendors by route number
        # for row in vendor_data:
        #     route_no = row.get('Route No')
        #     if route_no:
        #         if route_no not in route_groups:
        #             route_groups[route_no] = []
        #         route_groups[route_no].append(row)

        email_service = EmailService()
        success_count = 0
        failed_emails = []
        processed_emails = set()  # Track processed emails to avoid duplicates

        for vendor_name, vendor_data in vendor_json_data.items():
            logger.info(f"Processing route: {vendor_name}")
            
            for route_no, route_data in vendor_data.items():
                vendor_email = route_data[0].get('Vendor Email', '')
                break


            subject = f'Route {vendor_name} - Vehicle Details'
            try:
                body = email_service.format_route_email_body(vendor_name)
                df = pd.DataFrame()
                
                
                df_dict = {
                    key: pd.DataFrame(value) for key, value in vendor_data.items()
                        
                }
                final_df = pd.concat(df_dict.values(), ignore_index=True)
                
                final_df = final_df[['S No',   'Route No',   'Emp Code','Name','SUV','Shift','Vendor Name',   'Area','Location-Delhi'    ,'Pickup Time','Address (Office Reporting Time 07:20 Hrs & Departure Time 16:45 Hrs)','Vendor Email','Gender']]


                vendor_media_path = os.path.join(settings.MEDIA_ROOT, "vendor")
                vendor_file_name = os.path.join(vendor_media_path, f'{vendor_name}_vendor_route.xlsx')
                final_df.to_excel(vendor_file_name, index=False)
                                
                email_service.send_email(vendor_email, subject, body, vendor_file_name, vendor_data, vendor_name)
                
                for filename in os.listdir(vendor_media_path):
                    if filename.lower().endswith((".png", ".jpg", ".jpeg")) and vendor_name.lower().replace(" ", "_") in filename.lower():
                        file_path = os.path.join(vendor_media_path, filename)
                        os.remove(file_path)
                        print(f"Removed: {file_path}")
                
                os.remove(vendor_file_name)

                            
                
                
                
                # for email in emails:
                #     if email in processed_emails:
                #         logger.info(f"Skipping duplicate email: {email}")
                #         continue
                        
                    # processed_emails.add(email)
                    # try:
                    #     if email_service.send_email(email, subject, body, file_path):
                    #         success_count += 1
                    #     else:
                    #         failed_emails.append(email)
                    # except EmailServiceError as e:
                    #     logger.error(f"Failed to send email to {email}: {str(e)}")
                    #     failed_emails.append(email)
                        
            except Exception as e:
                logger.error(f"Error processing route {route_no}: {str(e)}")
                continue

        response_data = {
            "message": "Email processing completed",
            "success_count": success_count,
            "failed_count": len(failed_emails),
            # "total_routes": len(route_groups),
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