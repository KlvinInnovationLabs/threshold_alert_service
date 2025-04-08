"""Configuration settings for the threshold alert service."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/home/suri/VSCode/klvinai/SentinelSuite/config/.env')


# Service configuration
SERVER_HOST = f"{os.environ.get("SERVER_URL")}:{os.environ.get("SERVER_PORT")}"

# Breach thresholds
BREACH_ORDER = {
    "red": 3,
    "orange": 2,
    "yellow": 1
}

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "klvintechlabs@gmail.com")
SENDER_PASSWORD = os.environ.get("EMAIL_PASSWORD")
LOGGER_EMAILS = os.environ.get("LOGGER_EMAILS", "connect@klvin.ai").split(",")

# Breach timeouts in seconds (for rate limiting)
BREACH_TIMEOUT_IN_SECONDS = {
    "red": int(os.environ.get("RED_EMAIL_TIMEOUT_IN_SECONDS", 300)),
    "orange": int(os.environ.get("ORANGE_EMAIL_TIMEOUT_IN_SECONDS", 1800)),
    "yellow": int(os.environ.get("YELLOW_EMAIL_TIMEOUT_IN_SECONDS", 3600))
}

# Sustenance periods (how long a threshold must be exceeded)
YELLOW_SUSTENANCE_PERIOD = int(os.environ.get("YELLOW_SUSTENANCE_PERIOD", 10))
ORANGE_SUSTENANCE_PERIOD = int(os.environ.get("ORANGE_SUSTENANCE_PERIOD", 5))

# Queue sizes
QUEUE_SIZE = 100

# Processing intervals in seconds
WARNING_BREACH_CHECK_INTERVAL = int(os.environ.get("WARNING_BREACH_CHECK_INTERVAL", 60))
CRITICAL_BREACH_CHECK_INTERVAL = int(os.environ.get("CRITICAL_BREACH_CHECK_INTERVAL", 30))

# Cache TTLs in seconds
THRESHOLD_CACHE_TTL = 3600  # 1 hour
EMAIL_CACHE_TTL = 86400     # 24 hours

# Email retry settings
MAX_EMAIL_RETRY_ATTEMPTS = 3