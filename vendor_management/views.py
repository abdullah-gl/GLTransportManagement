import logging
import pandas as pd
from typing import Dict, List, Tuple, Optional
from django.core.files.storage import FileSystemStorage
from django.contrib import messages
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
import mimetypes
import smtplib
import os
from pathlib import Path
import json
from dotenv import load_dotenv
from .transport_image import TransportDataProcessor
import pandas as pd
from xlsxwriter import Workbook
from io import BytesIO


load_dotenv()
logger = logging.getLogger('django')

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
        'S No', 'Route No', 'Name', 'Vendor Names','Vendor Emails'
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
                data = data.map(lambda x: x.strip() if isinstance(x, str) else x)
            else:
                data = pd.read_excel(file_path)
                data = data.map(lambda x: x.strip() if isinstance(x, str) else x)
                
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
        self.smtp_host = Config.EMAIL_HOST
        self.smtp_port = Config.EMAIL_PORT
        
        if not self.sender_email or not self.sender_password:
            raise EmailServiceError("Email credentials not properly configured")
    
    
    def send_emaill(self, subject, body, recipient, folder, vendor_entries,vendor_name):
        
        df = pd.DataFrame(vendor_entries)      # Convert to DataFrame
        
        # Save DataFrame to an in-memory Excel file
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name=vendor_name)
        excel_buffer.seek(0)  # Move cursor to the start of the buffer
        
        
        if not isinstance(recipient, str) or '@' not in recipient:
            logger.warning(f"Invalid email format: {recipient}")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html'))
            
            # 🔹 Attach Excel File (Vendor Data)
            part = MIMEBase("application", "octet-stream")
            part.set_payload(excel_buffer.getvalue())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={vendor_name}_Data.xlsx")
            msg.attach(part)

            # Attach all .png files from the given folder
            for filename in os.listdir(folder):
                if filename.endswith(".png"):
                    file_path = os.path.join(folder, filename)
                    logger.info(f"IMAGE PATH .png: {file_path}")
                    
                    with open(file_path, "rb") as attachment:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(attachment.read())

                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={filename}")
                    msg.attach(part)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"Email with attachments sent successfully to {recipient}")
            return True

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error while sending email to {recipient}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while sending email to {recipient}: {str(e)}")

        return False
    
    


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
        <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        color: #333;
                    }}
                    .container {{
                        text-align: left; /* Centers the image */
                        margin: 20px 0;
                    }}
                    img {{
                        width: 100%;
                        max-width: 600px;
                        display: block;
                        margin: 0; /* Ensures the image stays centered */
                    }}
                    p {{
                        font-size: 16px;
                        line-height: 1.5;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <img src="cid:banner" alt="Banner Image">
                </div>
                <p>Dear {route_data},</p>
                    <p>Please find attached the All Route Excel File and Individual Route Image.</p>
                    <p>If you have any questions or need further assistance, feel free to reach out.</p>
                    <p>Best regards,<br><strong>Admin Team</strong></p>
            </body>
        </html>
        """



def handle_vendor_form(request: HttpRequest) -> HttpResponse:
    """
    Handles vendor form submission and file processing.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Rendered template with processing results.
    """
    # Handle GET request
    if request.method != 'POST':
        return render(request, 'front/vendor.html', {'data_dict': request.session.get('vendor_data_dict')})

    uploaded_file = request.FILES.get('vendor_file')

    # Validate file
    is_valid, error_message = FileHandler.validate_file(uploaded_file)
    if not is_valid:
        messages.error(request, error_message)
        return redirect('handle_vendor_form')

    # Define vendor media path
    vendor_media_path = Path(settings.MEDIA_ROOT) / "vendor"
    vendor_media_path.mkdir(parents=True, exist_ok=True)

    # Save file
    fs = FileSystemStorage(location=str(vendor_media_path))
    file_path = Path(fs.save(uploaded_file.name, uploaded_file))
    full_path = vendor_media_path / file_path

    try:
        # Process file
        data = FileHandler.process_file(str(full_path))
        vendor_data_dict = data.to_dict(orient='records')

        # Store data in session
        request.session.update({
            'vendor_data_dict': vendor_data_dict,
            'uploaded_file_path': str(full_path)
        })
        
        messages.success(request, 'File processed successfully!')

    except FileHandlerError as e:
        logger.error(f"File processing error: {e}")
        messages.error(request, str(e))
        full_path.unlink(missing_ok=True)  # Remove file if processing fails

    except Exception as e:
        logger.error(f"Unexpected error in handle_vendor_form: {e}", exc_info=True)
        messages.error(request, "An unexpected error occurred while processing the file.")
        full_path.unlink(missing_ok=True)

    return render(request, 'front/vendor.html', {'data_dict': request.session.get('vendor_data_dict')})


def search_vendor_data(request):
    search_query = request.GET.get('search', '').strip().lower()
    data_dict = request.session.get('vendor_data_dict', [])

    # If a search query exists, filter the data
    if search_query:
        filtered_data = [
            row for row in data_dict
            if any(search_query in str(value).lower() for value in row.values())
        ]
    else:
        filtered_data = data_dict  # Show all data if no search query
    return JsonResponse({'data': filtered_data})



def sort_vendor_data(request):
    column = request.GET.get('column')
    direction = request.GET.get('direction', 'asc')
    data_dict = request.session.get('vendor_data_dict', [])

    # Your data (assuming data_dict is available)
    data_list = list(data_dict)  # Convert QuerySet to list if needed

    # Sorting logic
    sorted_data = sorted(data_list, key=lambda x: x[column], reverse=(direction == "desc"))

    return JsonResponse({"data": sorted_data})


def send_vendor_emails(request: HttpRequest) -> HttpResponse:
    """
    Processes vendor data and sends emails with PNG attachments to vendors.

    Args:
        request: HTTP request object.

    Returns:
        JsonResponse: JSON response with email processing results.
    """
    
    # Ensure the request method is POST; otherwise, return an error response.
    if request.method != 'POST':
        logger.info("Request method is not POST")
        return JsonResponse({"error": "Invalid method"}, status=400)

    try:
        # Parse JSON data from the request body.
        data = json.loads(request.body.decode("utf-8"))

        # Extract required data from the request payload.
        top_template = data.get("top_template", "").strip()
        bottom_template = data.get("bottom_template", "").strip()
        selected_details = data.get("selected_details", [])

        # Retrieve vendor data and file path from the session.
        vendor_data = request.session.get('vendor_data_dict', [])
        file_path = request.session.get('uploaded_file_path', "")

        # Extract unique vendor names and sanitize them.
        # unique_vendor_names = {entry.get("Vendor Names", "").strip().replace(" ", "_") 
        #                        for entry in vendor_data if "Vendor Names" in entry}


        # Extract unique vendor emails mapped to vendor names.
        unique_vendor_email = {}
        for entry in vendor_data:
            vendor_name = entry.get("Vendor Names", "").strip()
            vendor_email = entry.get("Vendor Emails", "").strip()

            # Validate and store vendor emails
            if vendor_name and vendor_email and "@" in vendor_email:
                sanitized_name = vendor_name.replace(" ", "_")
                unique_vendor_email.setdefault(sanitized_name, set()).add(vendor_email)

        # Log extracted vendor emails.
        logger.info(f"Vendor EMAILS: {unique_vendor_email}")

        # Dictionary to store route-wise vendor entries.
        vendors_image_dirs = []
        route_wise_entries = {}
        vendor_data_dict = {} 
        previous_route_no = None  # Keeps track of the last seen route number.
        previous_vendor_name = None

        # Iterate through vendor data to group entries by Route No.
        for entry in vendor_data:
            # Extract only the selected details for the current vendor entry.
            selected_entry = {key: entry[key] for key in selected_details if key in entry}
            current_route_no = entry.get("Route No", "Unknown")  # Default to 'Unknown' if missing.
            current_vendor_name = entry.get("Vendor Names", "Unknown")
            current_vendor_name = current_vendor_name.replace(' ', '_')
            vendor_email = entry.get("Vendor Emails", "").strip()
            
            # Skip invalid emails.
            if '@' not in vendor_email:
                continue

            # Store all row data for each vendor name.
            if current_vendor_name not in vendor_data_dict:
                vendor_data_dict[current_vendor_name] = []
            vendor_data_dict[current_vendor_name].append(entry) 

            

            # If Route No changes, process the collected route-wise entries.
            if previous_route_no and current_route_no != previous_route_no:
                processor = TransportDataProcessor(route_wise_entries, previous_vendor_name)
                vendors_image_directory = processor.generate_table_image()
                vendors_image_dirs.append(vendors_image_directory)

                # Reset the dictionary for new route-wise entries.
                route_wise_entries = {}

                # Log separator for readability.
                logger.info(f"{'~' * 100}")

            # Ensure the route number key exists before appending new entries.
            route_wise_entries.setdefault(current_route_no, []).append(selected_entry)

            # Update the last seen Route No and Vendor Name.
            previous_route_no = current_route_no   
            previous_vendor_name = current_vendor_name   
        
        # Flatten and extract unique vendor directories.
        flat_vendor_dirs = [item for sublist in vendors_image_dirs for item in sublist]
        unique_vendor_dirs = set(flat_vendor_dirs)

        # logger.info(f"Vendors DATA: {vendor_data_dict}")
        
        # Log extracted vendor directories.
        # logger.info(f"Vendor IMAGE DIRECTORY: {unique_vendor_dirs}")
        # logger.info(f"Vendor IMAGE LEN: {len(unique_vendor_dirs)}")

        # Construct full email body in HTML format.
        subject = "Roaster"
        email_body = f"""
        <p>{top_template}</p>
        <p>{bottom_template}</p>
        """

        # Send emails to vendors with their respective PNG attachments.
        success_count = 0
        failed_emails = []
        processed_emails = set()

        for vendor_name, emails in unique_vendor_email.items():
            if vendor_name in vendor_data_dict:
                vendor_entries = vendor_data_dict[vendor_name]
                for folder in unique_vendor_dirs:
                    if vendor_name in folder:  # Check if vendor name is part of the folder path.
                        recipient_emails = ", ".join(emails)  # Convert set to comma-separated string.
                        logger.info(f"Sending Email to: {recipient_emails}")
                        logger.info(f"Vendor Folder: {folder}")
                        # logger.info(f"Vendor name: {vendor_entries}")
                        

                        email_service = EmailService()
                        email_sent = email_service.send_emaill(subject, email_body, recipient_emails, folder, vendor_entries,vendor_name)

                        # # Track success/failure.
                        # if email_sent:
                        #     success_count += 1
                        #     processed_emails.update(emails)
                        # else:
                        #     failed_emails.extend(emails)

        # Return processing results.
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
    
    
def vendor_view(request):
    return render(request, 'front/vendor.html')
    
def vendor_message_template(request):
    return render(request, 'front/vendor_message_template.html')


def fetch_columns_vendor(request):
    data_dict = request.session.get('vendor_data_dict', [])    
    
    # Extract column names from the first dictionary entry if available
    columns = list(data_dict[0].keys()) if data_dict else []
    return JsonResponse({"columns": columns})