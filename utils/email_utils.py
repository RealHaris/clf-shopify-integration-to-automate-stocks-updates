import os
import json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import base64
from datetime import datetime
from typing import List, Dict
import glob

class EmailSender:
    def __init__(self):
        # Load credentials
        credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'credentials.json')
        with open(credentials_path, 'r') as f:
            self.credentials = json.load(f)
        
        # Initialize SendGrid client
        self.sg = SendGridAPIClient(api_key=self.credentials.get('sendgrid', {}).get('api_key'))
        self.from_email = self.credentials.get('sendgrid', {}).get('from_email')
        self.to_email = self.credentials.get('sendgrid', {}).get('to_email')

    def _get_current_log_files(self, start_date: str) -> List[str]:
        """Get all log files generated from the start_date"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        formatted_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y%m%d')
        
        # Get all files in the logs directory
        all_files = glob.glob(os.path.join(log_dir, '*.txt'))
        
        # Filter files that contain the formatted date
        current_log_files = [f for f in all_files if formatted_date in os.path.basename(f)]
        print(f"Found log files for date {formatted_date}: {current_log_files}")
        
        return current_log_files

    def _create_attachment(self, file_path: str) -> Attachment:
        """Create an email attachment from a file"""
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        encoded_content = base64.b64encode(file_content).decode()
        file_name = os.path.basename(file_path)
        file_type = 'text/plain'
        
        attachment = Attachment()
        attachment.file_content = FileContent(encoded_content)
        attachment.file_name = FileName(file_name)
        attachment.file_type = FileType(file_type)
        attachment.disposition = Disposition('attachment')
        
        return attachment

    def send_completion_email(self, stats: Dict, start_date: str):
        """Send email when script completes successfully"""
        subject = 'Stock Update Script - Completed Successfully'
        content = f"""
        Stock Update Script has completed successfully.
        
        Summary:
        - Start Time: {stats.get('start_time', 'N/A')}
        - End Time: {stats.get('end_time', 'N/A')}
        - Total Runtime: {stats.get('runtime', 'N/A')}
        - Total SKUs Processed: {stats.get('total_skus', 0)}
        - Products Updated Successfully: {stats.get('products_updated', 0)}
        - Errors: {stats.get('error_count', 0)}
        - Warnings: {stats.get('warning_count', 0)}
        - Total Issues: {stats.get('total_issues', 0)}
        
        Please find the detailed logs attached.
        """
        
        self._send_email(subject, content, start_date)

    def send_token_limit_email(self, stats: Dict, start_date: str):
        """Send email when token generation limit is exceeded"""
        subject = 'Stock Update Script - Stopped (Token Limit Exceeded)'
        content = f"""
        Stock Update Script has been stopped due to token generation limit exceeded.
        
        Summary:
        - Start Time: {stats.get('start_time', 'N/A')}
        - Stop Time: {stats.get('end_time', 'N/A')}
        - Runtime Before Stop: {stats.get('runtime', 'N/A')}
        - Products Updated Before Stop: {stats.get('products_updated', 0)}
        - Errors: {stats.get('error_count', 0)}
        - Warnings: {stats.get('warning_count', 0)}
        - Total Issues: {stats.get('total_issues', 0)}
        - Reason: Token generation limit (20) exceeded
        
        Please find the detailed logs attached.
        """
        
        self._send_email(subject, content, start_date)

    def _send_email(self, subject: str, content: str, start_date: str):
        """Common method to send email with attachments"""
        message = Mail(
            from_email=self.from_email,
            to_emails=self.to_email,
            subject=subject,
            plain_text_content=content
        )

        # Attach all current log files based on start_date
        log_files = self._get_current_log_files(start_date)
        print(f"Found {len(log_files)} log files to attach")
        
        for log_file in log_files:
            try:
                print(f"Attaching log file: {log_file}")
                attachment = self._create_attachment(log_file)
                message.add_attachment(attachment)
                print(f"Successfully attached: {log_file}")
            except Exception as e:
                print(f"Failed to attach {log_file}: {str(e)}")
        
        try:
            response = self.sg.send(message)
            print(f"Email sent successfully with status code: {response.status_code}")
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
