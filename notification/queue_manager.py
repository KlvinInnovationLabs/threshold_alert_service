"""Queue management for breach notifications."""
import threading
import queue
import traceback
import os
from config.settings import QUEUE_SIZE, WARNING_BREACH_CHECK_INTERVAL, CRITICAL_BREACH_CHECK_INTERVAL
from utils.logging import get_logger

logger = get_logger(__name__)

class QueueManager:
    """
    Manages queues for breach notifications.
    
    Provides methods to add breaches to queues and start processing threads.
    """
    
    def __init__(self):
        # Create queues for breach notifications
        self.red_queue = queue.Queue(QUEUE_SIZE)
        self.warning_queue = queue.Queue(QUEUE_SIZE)
        
        # Track queue statistics
        self.red_queue_high_water_mark = 0
        self.warning_queue_high_water_mark = 0
    
    def add_red_breach(self, breach):
        """Add a red breach to the queue."""
        try:
            self.red_queue.put(breach, block=False)
            
            # Update statistics
            qsize = self.red_queue.qsize()
            if qsize > self.red_queue_high_water_mark:
                self.red_queue_high_water_mark = qsize
                if qsize > QUEUE_SIZE * 0.8:
                    logger.warning(f"Red queue at {qsize}/{QUEUE_SIZE} ({qsize/QUEUE_SIZE:.0%})")
        except queue.Full:
            logger.error("Red breach queue is full! Breach discarded.")
    
    def add_warning_breach(self, breach):
        """Add a yellow or orange breach to the queue."""
        try:
            self.warning_queue.put(breach, block=False)
            
            # Update statistics
            qsize = self.warning_queue.qsize()
            if qsize > self.warning_queue_high_water_mark:
                self.warning_queue_high_water_mark = qsize
                if qsize > QUEUE_SIZE * 0.8:
                    logger.warning(f"Warning queue at {qsize}/{QUEUE_SIZE} ({qsize/QUEUE_SIZE:.0%})")
        except queue.Full:
            logger.error("Warning breach queue is full! Breach discarded.")
    
    def start_processing_threads(self, process_func):
        """
        Start threads to process queues at specified intervals.
        
        Args:
            process_func: Function to process breaches
        """
        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)
        
        # Start thread for red breaches
        def process_red_breaches():
            while True:
                try:
                    # Signal end of batch with None
                    self.red_queue.put(None)
                    
                    # Collect all available breaches
                    breaches = []
                    while True:
                        breach = self.red_queue.get()
                        self.red_queue.task_done()
                        
                        if breach is None:
                            break
                        
                        breaches.append(breach)
                    
                    # Process breaches if any
                    if breaches:
                        logger.info(f"Processing {len(breaches)} red breaches")
                        # Ensure log path is valid
                        process_func(breaches, "red")
                    
                    # Wait before next processing
                    threading.Event().wait(CRITICAL_BREACH_CHECK_INTERVAL)
                except Exception as e:
                    logger.error(f"Error in red breach processing: {e}")
                    logger.error(traceback.format_exc())
        
        # Start thread for warning breaches
        def process_warning_breaches():
            while True:
                try:
                    # Signal end of batch with None
                    self.warning_queue.put(None)
                    
                    # Collect all available breaches
                    breaches = []
                    while True:
                        breach = self.warning_queue.get()
                        self.warning_queue.task_done()
                        
                        if breach is None:
                            break
                        
                        breaches.append(breach)
                    
                    # Process breaches if any
                    if breaches:
                        logger.info(f"Processing {len(breaches)} warning breaches")
                        # Ensure log path is valid
                        process_func(breaches, "warning")
                    
                    # Wait before next processing
                    threading.Event().wait(WARNING_BREACH_CHECK_INTERVAL)
                except Exception as e:
                    logger.error(f"Error in warning breach processing: {e}")
                    logger.error(traceback.format_exc())
        
        # Start the threads with names for better debugging
        red_thread = threading.Thread(
            target=process_red_breaches, 
            daemon=True,
            name="RedBreachProcessor"
        )
        warning_thread = threading.Thread(
            target=process_warning_breaches, 
            daemon=True,
            name="WarningBreachProcessor"
        )
        
        red_thread.start()
        warning_thread.start()
        
        logger.info("Queue processing threads started")
    
    def get_queue_status(self):
        """Get current status of queues."""
        return {
            "red_queue_size": self.red_queue.qsize(),
            "warning_queue_size": self.warning_queue.qsize(),
            "red_queue_high_water_mark": self.red_queue_high_water_mark,
            "warning_queue_high_water_mark": self.warning_queue_high_water_mark
        }