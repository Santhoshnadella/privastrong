"""
Logging Configuration
Sets up structured JSON logging for production observability
"""

import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logging(level=logging.INFO):
    """Configure root logger for JSON output"""
    handler = logging.StreamHandler(sys.stdout)
    
    # Define JSON log format
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%SZ'
    )
    
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid double logging
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
        
    root_logger.addHandler(handler)
    
    # Suppress verbose third-party logs
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    
    return root_logger
