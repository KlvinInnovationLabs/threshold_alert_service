"""Database interface functions with caching."""
from utils.cache import get_cached_thresholds, get_cached_emails
from utils.logging import get_logger

logger = get_logger(__name__)
import os
import sys

# Get the absolute path of the current file (db_interface.py)
current_file_path = os.path.dirname(os.path.abspath(__file__))

# Navigate up to the project root directory
project_root = os.path.abspath(os.path.join(current_file_path, '../../..'))

# Add the project root to sys.path
sys.path.append(project_root)

# Now you can import db from config
from utils.db import get_emails as original_get_emails, get_thresholds as original_get_thresholds, get_entity_names, get_all_company_ids, get_sensor_IDs

# Apply caching to the DB functions
get_thresholds = get_cached_thresholds(original_get_thresholds)
get_emails = get_cached_emails(original_get_emails)