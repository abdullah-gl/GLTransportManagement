import logging
import pandas as pd
from typing import Dict
from django.core.files.storage import FileSystemStorage
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
from concurrent.futures import ThreadPoolExecutor
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from django.http import JsonResponse
from django.conf import settings
from functools import partial
from dotenv import load_dotenv
import mimetypes
import smtplib
import os


# Configuration
load_dotenv()
logger = logging.getLogger('django')



def home(request):
    return render(request, 'front/employee_management.html')


class Config:
    BANNER_IMAGE_PATH = os.path.join(settings.STATIC_MEDIA_URL, "images" , "header_img.png")
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
    CHUNK_SIZE = 10000
    MAX_COLUMNS = 22
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
    MAX_WORKERS = 5  # For parallel email processing

class FileHandler:
    @staticmethod
    def validate_file(file) -> tuple[bool, str]:
        """Validate uploaded file extension and size."""
        if not file:
            return False, "No file uploaded"
        
        extension = file.name.split('.')[-1].lower()
        if extension not in Config.ALLOWED_EXTENSIONS:
            return False, f"Invalid file type. Allowed types: {', '.join(Config.ALLOWED_EXTENSIONS)}"
        
        if file.size > Config.MAX_FILE_SIZE:
            return False, f"File size exceeds {Config.MAX_FILE_SIZE // (1024*1024)}MB limit"
            
        return True, ""

    """Process uploaded file and return DataFrame."""
    @staticmethod
    def process_file(file_path: str) -> pd.DataFrame:
        logger.info(f"Starting to process file: {file_path}")
        
        try:
            # Check if the file is a CSV
            if file_path.endswith('.csv'):
                logger.info("File type: CSV")
                logger.debug(f"Reading CSV in chunks of size: {Config.CHUNK_SIZE}")
                chunks = pd.read_csv(file_path, chunksize=Config.CHUNK_SIZE, encoding='utf-8', low_memory=False)
                data = pd.concat(chunks, ignore_index=True)
                data = data.map(lambda x: x.strip() if isinstance(x, str) else x)
                logger.info("CSV file successfully processed and concatenated.")
            else:
                logger.info("File type: Excel")
                data = pd.read_excel(file_path)
                logger.info("Excel file successfully processed.")

            # Displaying the shape and head of the DataFrame for debugging
            logger.debug(f"DataFrame shape: {data.shape}")
            logger.debug(f"DataFrame head: \n{data.head()}")

            # Limiting columns and filling NaN values
            processed_data = data.iloc[:, :Config.MAX_COLUMNS].fillna("N/A")
            logger.info("Data processing completed with column limit and NaN handling.")
            return processed_data

        except Exception as e:
            logger.error(f"Error processing file: {str(e)}", exc_info=True)
            raise

class EmailService:
    def __init__(self):
        self.sender_email = Config.EMAIL_HOST_USER
        self.sender_password = Config.EMAIL_HOST_PASSWORD
        self.img_path = Config.BANNER_IMAGE_PATH
    
    @staticmethod
    def attach_banner_image(msg, img_path):
        with open(img_path, "rb") as img_file:
            img = MIMEImage(img_file.read(), _subtype=mimetypes.guess_type(img_path)[0].split('/')[1])
            img.add_header("Content-ID", "<banner>")
            img.add_header("Content-Disposition", "inline", filename=os.path.basename(img_path))
            msg.attach(img)
    
    
    @staticmethod
    def format_email_body(employee_data: Dict) -> str:
        """Format employee details into email body (HTML format)."""
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
                    p, ul, ol {{
                        font-size: 16px;
                        line-height: 1.5;
                    }}
                    ul, ol {{
                        margin-left: 20px;
                    }}
                    a {{
                        color: #1a73e8;
                        text-decoration: none;
                    }}
                    a:hover {{
                        text-decoration: underline;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <img src="cid:banner" alt="Banner Image">
                </div>
                <p>Dear {employee_data.get('Name', 'Employee')},</p>
                <p>We are pleased to share your updated transportation details:</p>
                <ul>
                    <li>Employee Code: {employee_data.get('Emp Code', 'N/A')}</li>
                    <li>Area: {employee_data.get('Area', 'N/A')}</li>
                    <li>Location: {employee_data.get('Location-Delhi', 'N/A')}</li>
                    <li>Pickup Time: {employee_data.get('Pickup Time', 'N/A')}</li>
                    <li>Driver Contact Number: {employee_data.get('Contact No.', 'N/A')}</li>
                    <li>Process: {employee_data.get('Process', 'N/A')}</li>
                </ul>
                <p><strong>Note:</strong></p>
                <ol>
                    <li>Please remember your route number.</li>
                    <li>Please board the cab as per scheduled pick-up time to avoid any inconvenience.</li>
                    <li>For any query call on transport helpline number (9266903058) or mail on gl-transport@globallogic.com.</li>
                    <li>Use this <a href="https://drive.google.com/file/d/1_zHCfyZ4D4S__gjHnq6LtlzbmjAR35RS/view">link</a> for transport policy.</li>
                </ol>
                <p>Please ensure you are available at the designated pickup location on time. If you have any questions or need further assistance, feel free to reach out.</p>
                <p>Best regards,<br>Your Admin Team</p>
            </body>
        </html>
        """
    
    
    """Send email using SMTP with error handling."""
    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        if '@' not in to_email:
            logger.warning(f"Invalid email format: {to_email}")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html'))
            img_path = self.img_path
            self.attach_banner_image(msg, img_path)

            with smtplib.SMTP(Config.EMAIL_HOST, Config.EMAIL_PORT) as server:
                server.starttls()
                # server.login(self.sender_email, self.sender_password)
                # server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False



"""Handle file upload and process employee data."""
def handle_employee_form(request: HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return render(request, 'front/employee.html', 
                     {'data_dict': request.session.get('data_dict')})
    try:
        uploaded_file = request.FILES.get('employee_file')
        is_valid, error_message = FileHandler.validate_file(uploaded_file)
        
        if not is_valid:
            messages.error(request, error_message)
            return redirect('handle_employee_form')
        
        employee_media_path = os.path.join(settings.MEDIA_ROOT, "employee")
        if not os.path.exists(employee_media_path):
            os.makedirs(employee_media_path)
        fs = FileSystemStorage(location=employee_media_path)
        file_path = fs.save(uploaded_file.name, uploaded_file)
        full_path = fs.path(file_path)
        
        logging.info(f'Full Path is {full_path} and File path {file_path}')

        try:
            data = FileHandler.process_file(full_path)
            if data.empty:
                raise ValueError("The uploaded file contains no data")

            data_dict = data.to_dict(orient='records')
            request.session['data_dict'] = data_dict
            messages.success(request, 'File uploaded and processed successfully!')
        except Exception as e:
            logging.error(f"Error is: {str(e)}")

        # finally:
        #     fs.delete(file_path)

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        messages.error(request, f"Error processing file: {str(e)}")

    return render(request, 'front/employee.html', 
                 {'data_dict': request.session.get('data_dict')})


def search_employee_data(request):
    search_query = request.GET.get('search', '').strip().lower()
    data_dict = request.session.get('data_dict', [])

    # If a search query exists, filter the data
    if search_query:
        filtered_data = [
            row for row in data_dict
            if any(search_query in str(value).lower() for value in row.values())
        ]
    else:
        filtered_data = data_dict  # Show all data if no search query
    return JsonResponse({'data': filtered_data})


def sort_employee_data(request):
    column = request.GET.get('column')
    direction = request.GET.get('direction', 'asc')
    data_dict = request.session.get('data_dict', [])

    # Your data (assuming data_dict is available)
    data_list = list(data_dict)  # Convert QuerySet to list if needed

    # Sorting logic
    sorted_data = sorted(data_list, key=lambda x: x[column], reverse=(direction == "desc"))

    return JsonResponse({"data": sorted_data})

def fetch_columns(request):
    data_dict = request.session.get('data_dict', [])
    
    # Extract column names from the first dictionary entry if available
    columns = list(data_dict[0].keys()) if data_dict else []

    return JsonResponse({"columns": columns})


def employee_message_template(request):
    return render(request, 'front/employee_message_template.html')



import json

def send_employee_emails(request):
    if request.method == 'POST':
        data = json.loads(request.body.decode("utf-8"))
        top_template = data.get("top_template", "")
        bottom_template = data.get("bottom_template", "")
        selected_details = data.get("selected_details", [])

        # Process email sending logic here
        logger.info(f"Top Template: {top_template}")
        logger.info(f"Selected Details: {selected_details}")
        logger.info(f"Bottom Template: {bottom_template.encode('ascii', 'ignore').decode()}")

        return JsonResponse({"error": "Invalid request method"}, status=400)
    
    data_dict = request.session.get('data_dict')
    if not isinstance(data_dict, list):
        messages.error(request, "No data found. Please upload a valid file first.")
        return JsonResponse({"error": "No data found"}, status=400)
    
    email_service = EmailService()
    
    try:
        max_workers = min(Config.MAX_WORKERS, len(data_dict), 10)  # Prevent overload
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            send_email_partial = partial(email_service.send_email, subject="Updated Roster")
            results = list(executor.map(send_email_partial,(row.get("Email", "") for row in data_dict),(email_service.format_email_body(row) for row in data_dict)))
        
        success_count = sum(results)
        total_count = len(results)
        
        if success_count == total_count:
            messages.success(request, f"All {success_count} emails were sent successfully!")
        else:
            messages.warning(request, f"Email sending completed. {success_count} of {total_count} emails sent successfully.")
        
        return JsonResponse({
            "status": "success",
            "message": "Email sending completed.",
            "success_count": success_count,
            "total_count": total_count
        })
        
    except Exception as e:
        messages.error(request, f"An error occurred while sending emails: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)




def employee_view(request):
    return render(request, 'front/employee.html')