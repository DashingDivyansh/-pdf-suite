import logging
import os
from logging.handlers import RotatingFileHandler
from platformdirs import user_log_dir

def get_logger(name: str) -> logging.Logger:
    # Use a user-writable directory for logs to avoid PermissionError in compiled .exe
    log_dir = user_log_dir("PDFTool", "Divyansh")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "pdf_tool.log")

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # File handler (Rotating, max 5MB, 1 backup)
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=1)
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
