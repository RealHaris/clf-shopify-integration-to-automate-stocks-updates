# logs_deletion.py
import os
import glob
from datetime import datetime, timedelta
import re
from utils.logger_config import setup_logger

general_logger = setup_logger('general_logger')

class LogsCleaner:
    def __init__(self, retention_days=60):
        self.retention_days = retention_days
        self.base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        
    def extract_date_from_filename(self, filename):
        """Extract date from filename using regex"""
        try:
            # Match pattern YYYYMMDD in the filename
            date_match = re.search(r'\d{8}', filename)
            if date_match:
                date_str = date_match.group()
                return datetime.strptime(date_str, '%Y%m%d')
            return None
        except Exception as e:
            general_logger.error(f"Error extracting date from filename {filename}: {str(e)}")
            return None

    def is_file_expired(self, file_date):
        """Check if file is older than retention period"""
        if not file_date:
            return False
        current_date = datetime.now()
        age = current_date - file_date
        return age.days > self.retention_days

    def clean_old_logs(self):
        """Delete log files older than retention period"""
        general_logger.info(f"Starting logs cleanup process. Retention period: {self.retention_days} days")
        
        # Get all log files
        log_files = glob.glob(os.path.join(self.base_path, '*.txt'))
        files_deleted = 0
        total_size_freed = 0

        for file_path in log_files:
            try:
                filename = os.path.basename(file_path)
                file_date = self.extract_date_from_filename(filename)
                
                if not file_date:
                    general_logger.warning(f"Could not extract date from filename: {filename}")
                    continue

                if self.is_file_expired(file_date):
                    # Get file size before deletion
                    file_size = os.path.getsize(file_path)
                    
                    # Calculate file age
                    age_days = (datetime.now() - file_date).days
                    
                    # Delete file
                    os.remove(file_path)
                    
                    files_deleted += 1
                    total_size_freed += file_size
                    
                    general_logger.info(f"""
                    Deleted log file:
                    - Filename: {filename}
                    - Creation Date: {file_date.strftime('%Y-%m-%d')}
                    - Age: {age_days} days
                    - Size: {file_size/1024:.2f} KB
                    """)

            except Exception as e:
                general_logger.error(f"Error processing file {filename}: {str(e)}")

        if files_deleted > 0:
            general_logger.info(f"""
            Logs cleanup completed:
            - Files deleted: {files_deleted}
            - Total space freed: {total_size_freed/1024:.2f} KB
            - Cleanup date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """)
        else:
            general_logger.info("No files were old enough to be deleted")
