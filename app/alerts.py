"""
Alert dispatch: Telegram + email, with a per-metric cooldown so a metric
stuck above threshold doesn't spam the channel every collection cycle.
"""
import time
import smtplib
from email.mime.text import MIMEText
import requests
from . import config, database

_last_alert_time = {}  # metric -> unix ts


def _cooldown_ok(metric: str) -> bool:
    last = _last_alert_time.get(metric, 0)
    return (time.time() - last) >= config.ALERT_COOLDOWN_SECONDS


def _mark_alerted(metric: str):
    _last_alert_time[metric] = time.time()


def send_telegram(message: str):
    if not (config.TELEGRAM_ENABLED and config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": config.TELEGRAM_CHAT_ID, "text": message}, timeout=5)
    except requests.RequestException as e:
        print(f"[alerts] Telegram send failed: {e}")


def send_email(subject: str, body: str):
    if not (config.EMAIL_ENABLED and config.SMTP_USER and config.SMTP_PASSWORD and config.ALERT_EMAIL_TO):
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = config.SMTP_USER
        msg["To"] = config.ALERT_EMAIL_TO
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"[alerts] Email send failed: {e}")


METRIC_LABELS = {
    "cpu_percent": ("CPU usage", "%"),
    "ram_percent": ("RAM usage", "%"),
    "disk_percent": ("Disk usage", "%"),
    "temp_celsius": ("Temperature", "°C"),
}


def evaluate_and_dispatch(sample: dict, thresholds: dict, broadcast_fn=None):
    """
    Compares the latest sample against current thresholds. Fires
    Telegram/email/on-screen alerts (via broadcast_fn, which pushes
    to connected WebSocket dashboard clients) for anything breached,
    respecting the per-metric cooldown.
    """
    triggered = []
    for metric, (label, unit) in METRIC_LABELS.items():
        value = sample.get(metric)
        threshold = thresholds.get(metric)
        if value is None or threshold is None:
            continue
        if value >= threshold and _cooldown_ok(metric):
            message = (
                f"⚠️ {config.DEVICE_NAME}: {label} is {value}{unit}, "
                f"above threshold of {threshold}{unit}"
            )
            send_telegram(message)
            send_email(f"[Seaker Alert] {label} threshold exceeded", message)
            database.log_alert(metric, value, threshold, message)
            _mark_alerted(metric)
            triggered.append({"metric": metric, "label": label, "value": value,
                               "threshold": threshold, "message": message})

    if triggered and broadcast_fn:
        broadcast_fn({"type": "alert", "alerts": triggered})

    return triggered
