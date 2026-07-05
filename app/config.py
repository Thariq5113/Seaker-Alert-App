"""
Central configuration. All values can be overridden via environment
variables (see .env.example). Nothing sensitive is hard-coded.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Collection ---
COLLECT_INTERVAL_SECONDS = int(os.getenv("COLLECT_INTERVAL_SECONDS", 5))     # how often we persist to DB
BROADCAST_INTERVAL_SECONDS = float(os.getenv("BROADCAST_INTERVAL_SECONDS", 2))  # how often we push to the live dashboard

# --- Database ---
DB_PATH = os.getenv("DB_PATH", "data/metrics.db")

# --- Alerting ---
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", 300))  # don't re-alert on the same metric within this window

TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

# --- MQTT (bonus: IoT protocol support) ---
MQTT_ENABLED = os.getenv("MQTT_ENABLED", "false").lower() == "true"
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "seaker/metrics")

# --- Default thresholds (seeded into DB on first run, then user-editable) ---
DEFAULT_THRESHOLDS = {
    "cpu_percent": 85.0,
    "ram_percent": 85.0,
    "disk_percent": 90.0,
    "temp_celsius": 75.0,
}

DEVICE_NAME = os.getenv("DEVICE_NAME", "Windows-Laptop")

# --- Role-based access control ---
# Viewing the dashboard/metrics is open to anyone with the URL (viewer role).
# Changing thresholds requires these admin credentials (HTTP Basic Auth).
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")