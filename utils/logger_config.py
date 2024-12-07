import logging
import os
import hashlib
from datetime import datetime

def generate_unique_hash():
    """Generates a unique 4-digit hash based on timestamp"""
    timestamp = str(datetime.now().timestamp())
    hash_object = hashlib.md5(timestamp.encode())
    return hash_object.hexdigest()[:4]

def setup_logger(name, level=logging.INFO):
    """Configure and return a logger with specified name and level"""
    # Get today's date and unique hash for log files
    today_date = datetime.now().strftime('%Y%m%d')
    unique_hash = generate_unique_hash()

    # Configure logging directory
    log_directory = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    # Setup log file paths
    log_files = {
        'general_logger': os.path.join(log_directory, f'LOGS_{today_date}_{unique_hash}.txt'),
        'crash_logger': os.path.join(log_directory, f'CRASH_LOGS_{today_date}_{unique_hash}.txt'),
        'update_logger': os.path.join(log_directory, f'UPDATED_PRODUCTS_LOGS_{today_date}_{unique_hash}.txt')
    }

    # Create logger
    logger = logging.getLogger(name)
    
    # Avoid adding handlers if they already exist
    if not logger.handlers:
        logger.setLevel(level)
        
        # Create file handler
        handler = logging.FileHandler(log_files.get(name, log_files['general_logger']))
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        logger.addHandler(handler)

    return logger
