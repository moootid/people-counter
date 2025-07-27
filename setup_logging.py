#!/usr/bin/env python3
"""
Production logging setup script
This script helps configure logging for production debugging
"""

import logging
import logging.handlers
import os
from datetime import datetime


def setup_production_logging(log_level="INFO", log_file=None):
    """
    Set up comprehensive logging for production environment
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path. If None, uses default location
    """
    
    # Create logs directory if it doesn't exist
    log_dir = "/app/logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Default log file
    if log_file is None:
        log_file = f"{log_dir}/people_counter_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler (for Docker logs)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler (only errors and critical)
    error_file = f"{log_dir}/errors_{datetime.now().strftime('%Y%m%d')}.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Reduce noise from some third-party libraries
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('boto3').setLevel(logging.WARNING)
    
    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("PRODUCTION LOGGING CONFIGURED")
    logger.info(f"Log level: {log_level}")
    logger.info(f"Main log file: {log_file}")
    logger.info(f"Error log file: {error_file}")
    logger.info("=" * 60)
    
    return log_file, error_file


if __name__ == "__main__":
    # Test the logging setup
    setup_production_logging("DEBUG")
    
    logger = logging.getLogger("test")
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    print("Logging test completed. Check the log files in /app/logs/")
