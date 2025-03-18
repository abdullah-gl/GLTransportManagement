import logging
import pandas as pd
from django.core.files.storage import FileSystemStorage
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
from concurrent.futures import ThreadPoolExecutor
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.http import JsonResponse
from django.conf import settings
from dotenv import load_dotenv
import smtplib
import os
import json

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
        self.smtp_host = Config.EMAIL_HOST
        self.smtp_port = Config.EMAIL_PORT
        self.img_path = Config.BANNER_IMAGE_PATH
    
    def send_email(self, subject, body, recipient):
        if not isinstance(recipient, str) or '@' not in recipient:
            logger.warning(f"Invalid email format: {recipient}")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {recipient}")
            return True

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error while sending email to {recipient}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while sending email to {recipient}: {str(e)}")
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


def send_employee_emails(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body.decode("utf-8"))
        logger.info(f"Received Data: {data}")
        
        top_template = data.get("top_template", "").strip()
        bottom_template = data.get("bottom_template", "").strip()
        selected_details = data.get("selected_details", [])

        logger.info(f"Top Template: {top_template}")
        logger.info(f"Selected Details: {selected_details}")
        logger.info(f"Bottom Template: {bottom_template.encode('ascii', 'ignore').decode()}")

        data_dict = request.session.get('data_dict', [])
        if not isinstance(data_dict, list) or not data_dict:
            messages.error(request, "No data found. Please upload a valid file first.")
            return JsonResponse({"error": "No data found"}, status=400)

        email_service = EmailService()
        email_sent_count = 0

        for row in data_dict:
            email = row.get("Email", "").strip()
            if not email or '@' not in email:
                logger.warning(f"Skipping row due to missing or invalid email: {row}")
                continue
            
            # Convert employee data to HTML format
            each_employee_data = """
            <div style="padding: 12px; font-size: 16px; background-color: #eef3ff; 
                        border-left: 5px solid #4a90e2; margin: 12px 0;">
                <p style="margin: 0; line-height: 1.6;">""" + "<br>".join(
                    [f"• <strong>{col}</strong>: {row.get(col, '')}" for col in selected_details]
                ) + """</p>
            </div>
            """

            # Construct full email body in HTML format
            email_body = f"""
            <p>{top_template}</p<br>
            <div style="
                padding: 16px; 
                font-size: 15px; 
                background: linear-gradient(135deg, #f0f7ff, #dbe9ff); 
                border-radius: 10px;
                box-shadow: 0 4px 10px rgba(53, 114, 239, 0.15);
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #2c3e50;
                font-weight: 500;
                line-height: 1.6;
                text-align: left;
            ">
                {each_employee_data}
            </div>  
            <p>{bottom_template}</p>
            """

            logger.info(f"Sending email to {email} with body:\n{email_body}")

            try:
                email_service.send_email(
                    subject="Roster Updated",
                    body=email_body,
                    recipient=email,
                )
                email_sent_count += 1
                logger.info(f"Successfully sent email to {email}")
                
                
            except Exception as e:
                logger.error(f"Failed to send email to {email}: {str(e)}")

        return JsonResponse({"status": "success", "emails_sent": email_sent_count})

    except json.JSONDecodeError:
        logger.error("Invalid JSON format in request body")
        return JsonResponse({"error": "Invalid JSON format"}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JsonResponse({"error": "Something went wrong"}, status=500)



def employee_view(request):
    return render(request, 'front/employee.html')