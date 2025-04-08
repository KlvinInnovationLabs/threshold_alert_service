"""Caching utilities for the threshold alert service."""
import time
from functools import wraps
from config.settings import THRESHOLD_CACHE_TTL, EMAIL_CACHE_TTL
from utils.logging import get_logger

logger = get_logger(__name__)

# Cache dictionaries
threshold_cache = {}  # {(device_id, sensor_id): (value, timestamp)}
email_cache = {}      # {(device_id, threshold_type): (emails, timestamp)}

def get_cached_thresholds(get_thresholds_func):
    """
    Decorator to cache threshold values.
    
    Args:
        get_thresholds_func: The original function to get thresholds from DB
    
    Returns:
        Decorated function that uses cache when possible
    """
    @wraps(get_thresholds_func)
    def wrapper(device_id, sensor_id):
        cache_key = (device_id, sensor_id)
        
        # Check if we have a cached value that's still valid
        if cache_key in threshold_cache:
            value, timestamp = threshold_cache[cache_key]
            if time.time() - timestamp < THRESHOLD_CACHE_TTL:
                return value
        
        # Get fresh value from the database
        logger.debug(f"Cache miss for thresholds: {device_id}, {sensor_id}")
        thresholds = get_thresholds_func(device_id, sensor_id)
        
        # Cache the new value
        threshold_cache[cache_key] = (thresholds, time.time())
        return thresholds
    
    return wrapper

def get_cached_emails(get_emails_func):
    """
    Decorator to cache email recipients.
    
    Args:
        get_emails_func: The original function to get emails from DB
    
    Returns:
        Decorated function that uses cache when possible
    """
    @wraps(get_emails_func)
    def wrapper(device_id, threshold_type):
        cache_key = (device_id, threshold_type)
        
        # Check if we have a cached value that's still valid
        if cache_key in email_cache:
            value, timestamp = email_cache[cache_key]
            if time.time() - timestamp < EMAIL_CACHE_TTL:
                return value
        
        # Get fresh value from the database
        logger.debug(f"Cache miss for emails: {device_id}, {threshold_type}")
        emails = get_emails_func(device_id, threshold_type)
        
        # Cache the new value
        email_cache[cache_key] = (emails, time.time())
        return emails
    
    return wrapper

def clear_cache():
    """Clear all cached data."""
    threshold_cache.clear()
    email_cache.clear()
    logger.info("Cache cleared")

def cleanup_expired_cache():
    """Remove expired entries from cache."""
    current_time = time.time()
    
    # Clean threshold cache
    expired_threshold_keys = [
        key for key, (_, timestamp) in threshold_cache.items()
        if current_time - timestamp > THRESHOLD_CACHE_TTL
    ]
    for key in expired_threshold_keys:
        del threshold_cache[key]
    
    # Clean email cache
    expired_email_keys = [
        key for key, (_, timestamp) in email_cache.items()
        if current_time - timestamp > EMAIL_CACHE_TTL
    ]
    for key in expired_email_keys:
        del email_cache[key]
    
    logger.debug(f"Cleaned {len(expired_threshold_keys)} threshold and {len(expired_email_keys)} email cache entries")