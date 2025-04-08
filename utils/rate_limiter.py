"""Rate limiting for email notifications."""
import time
import threading
from config.settings import BREACH_TIMEOUT_IN_SECONDS
from utils.logging import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """
    Rate limiter for email notifications.
    
    Tracks when notifications were last sent for each device/sensor/threshold
    combination and determines whether new notifications should be sent.
    """
    
    def __init__(self):
        self.history = {}  # {(device_id, sensor_id, threshold_type): timestamp}
        self.lock = threading.Lock()
        
        # Start cleanup thread
        self._start_cleanup_thread()
    
    def should_send(self, device_id, sensor_id, threshold_type):
        """
        Check if notification should be sent based on rate limits.
        
        Args:
            device_id: Device identifier
            sensor_id: Sensor identifier
            threshold_type: Type of threshold (red, orange, yellow)
            
        Returns:
            bool: True if notification should be sent, False otherwise
        """
        threshold_type = threshold_type.lower()
        key = (device_id, sensor_id, threshold_type)
        current_time = time.time()
        
        with self.lock:
            if key not in self.history:
                self.history[key] = current_time
                return True
            
            last_sent = self.history[key]
            timeout = BREACH_TIMEOUT_IN_SECONDS.get(threshold_type, 3600)
            
            if current_time - last_sent >= timeout:
                self.history[key] = current_time
                return True
        
        return False
    
    def _cleanup_old_entries(self):
        """Remove entries that are older than their timeout period."""
        current_time = time.time()
        with self.lock:
            for key in list(self.history.keys()):
                _, _, threshold_type = key
                timeout = BREACH_TIMEOUT_IN_SECONDS.get(threshold_type, 3600)
                
                if current_time - self.history[key] > timeout * 2:
                    del self.history[key]
    
    def _start_cleanup_thread(self):
        """Start a background thread to periodically clean up old entries."""
        def cleanup_job():
            while True:
                try:
                    time.sleep(3600)  # Run hourly
                    self._cleanup_old_entries()
                except Exception as e:
                    logger.error(f"Error in rate limiter cleanup: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_job, daemon=True)
        cleanup_thread.start()