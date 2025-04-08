"""Logging utilities for the threshold alert service."""
import logging
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_logger(name):
    """Get a logger for the specified module."""
    return logging.getLogger(name)

def log_to_file(message, log_path):
    """Write a message to the specified log file."""
    # Handle empty or None log_path
    if not log_path:
        log_path = "default.log"  # Provide a default log file
    
    # Create directory if it doesn't exist
    log_dir = os.path.dirname(log_path)
    if log_dir:  # Only create directory if there's a directory path
        os.makedirs(log_dir, exist_ok=True)
    
    with open(log_path, "a", encoding="UTF-8") as file:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file.write(f"[{timestamp}] {message}\n")