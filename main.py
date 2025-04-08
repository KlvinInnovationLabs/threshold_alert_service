"""Main entry point for the threshold alert service."""

import threading
import socketio
import time
from queue import Queue

from config.settings import (
    SERVER_HOST,
    QUEUE_SIZE,
    WARNING_BREACH_CHECK_INTERVAL,
    CRITICAL_BREACH_CHECK_INTERVAL,
)
from utils.db_interface import get_all_company_ids
from utils.logging import get_logger, log_to_file
from utils.rate_limiter import RateLimiter
from monitoring.threshold_checker import run_threshold_check
from notification.queue_manager import QueueManager
from notification.email_sender import EmailSender

logger = get_logger(__name__)


def main():
    """Main function to start the threshold alert service."""
    logger.info("Starting threshold alert service")

    # Initialize components
    rate_limiter = RateLimiter()
    email_sender = EmailSender(rate_limiter)

    # Define breach processing function for the queue manager
    def process_breaches(breaches, breach_type):
        if breach_type == "red":
            log_path = "red.log"
        else:
            log_path = "non_red.log"

        logger.info(f"Processing {len(breaches)} {breach_type} breaches")
        log_to_file(f"\nProcessing {len(breaches)} {breach_type} breaches", log_path)

        # Log each breach for debugging
        for i, breach in enumerate(breaches):
            log_to_file(
                f"\nBreach {i+1}: Device={breach['device_id']}, "
                f"Sensor={breach['sensor_id']}, Type={breach['threshold_type']}",
                log_path,
            )

        email_sender.process_breaches(breaches, log_path)

    # Initialize queue manager and start processing threads
    queue_manager = QueueManager()
    queue_manager.start_processing_threads(process_breaches)
    logger.info("Queue processing threads started")

    # Wrapper for threshold checker to use queue_manager's queues
    def threshold_check_wrapper(data):
        try:
            logger.debug(f"Processing data for device {data.get('device_id')}")
            run_threshold_check(
                data, queue_manager.red_queue, queue_manager.warning_queue
            )
        except Exception as e:
            logger.error(f"Error in threshold check: {e}")

    # Monitor active threads periodically
    def log_active_threads():
        while True:
            try:
                active_threads = [t.name for t in threading.enumerate()]
                logger.info(f"Active threads: {active_threads}")
                logger.info(
                    f"Red queue size: {queue_manager.red_queue.qsize()}, "
                    f"Warning queue size: {queue_manager.warning_queue.qsize()}"
                )
                time.sleep(60)  # Log every minute
            except Exception as e:
                logger.error(f"Error in thread monitor: {e}")

    # Start thread monitor
    monitor_thread = threading.Thread(
        target=log_active_threads, daemon=True, name="ThreadMonitor"
    )
    monitor_thread.start()

    # Set up Socket.IO client
    sio = socketio.Client()

    @sio.event
    def connect():
        logger.info("Connected to Socket.IO server")

    @sio.event
    def connect_error(error=None):
        error_msg = str(error) if error else "Unknown error"
        logger.error(f"Socket.IO connection failed: {error_msg}")
        # We don't reconnect here as the socketio client will auto-reconnect

    @sio.event
    def disconnect():
        logger.info("Disconnected from Socket.IO server")

    # Get company namespaces
    try:
        company_namespaces = list(map(lambda y: "/" + y, get_all_company_ids()))
        logger.info(
            f"Listening on {len(company_namespaces)} company namespaces: {company_namespaces}"
        )
    except Exception as e:
        logger.error(f"Error getting company namespaces: {e}")
        company_namespaces = []

    # Set up event handlers for each namespace
    for company_namespace in company_namespaces:
        # Use a function factory to capture the namespace value
        def create_handler(namespace):
            @sio.on("NewReadingsEvent", namespace=namespace)
            def on_new_readings(data):
                logger.debug(f"Received new readings from {namespace}")
                threshold_check_wrapper(data)

            return on_new_readings

        # Create the handler for this namespace
        handler = create_handler(company_namespace)

    # Connect to Socket.IO server
    try:
        logger.info(f"Connecting to Socket.IO server at {SERVER_HOST}")
        sio.connect(SERVER_HOST, namespaces=company_namespaces, wait=True)

        # Keep the main thread running
        logger.info("Service running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error in main thread: {e}")
    finally:
        if sio.connected:
            sio.disconnect()


if __name__ == "__main__":
    main()
