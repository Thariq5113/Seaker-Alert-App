# Seaker-Alert-App

A system monitoring and alerting app built for the Seaker Jr. IoT Engineer assignment. It tracks CPU, RAM, Disk, uptime and temperature on a Windows/Linux machine, shows them live on a web dashboard, stores history in a database, and sends alerts (Telegram/email/on-screen) when a metric crosses a threshold you set.

![Architecture](docs/architecture.svg)

## Features

- Live dashboard with CPU/RAM/Disk gauges and a historical chart (1h/24h/7d)
- Alerts via Telegram, email, and on-screen banner, with customizable thresholds
- Data stored in SQLite for history
- CSV/JSON export of historical data
- MQTT support for pushing metrics to other devices
- Basic role-based access: anyone can view, only an admin login can change thresholds
- Dockerized

## Tech stack

Python, FastAPI, psutil, SQLite, WebSockets, Chart.js, Docker, Telegram Bot API, SMTP, MQTT

## Running it locally (Windows)

```powershell
git clone https://github.com/Thariq5113/Seaker-Alert-App 
cd Seaker-Alert-App

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000

## Running it with Docker

```bash
git clone https://github.com/Thariq5113/Seaker-Alert-App
cd Seaker-Alert-App

cp .env.example .env
docker compose up --build
```

Same URL, http://localhost:8000. Note: inside the container, the app reports the container's own resource usage, not the host machine's — this is expected Docker behaviour, not a bug.

## Setting up alerts

**Telegram** (easiest to demo):
1. Message `@BotFather` on Telegram → `/newbot` → copy the token it gives you
2. Message your new bot once (so it's allowed to reply to you)
3. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the `chat id` you see
4. In `.env`:
   ```
   TELEGRAM_ENABLED=true
   TELEGRAM_BOT_TOKEN=<token>
   TELEGRAM_CHAT_ID=<chat id>
   ```

**Email** (Gmail):
1. Turn on 2-Step Verification on your Google account
2. Generate an App Password at https://myaccount.google.com/apppasswords
3. In `.env`:
   ```
   EMAIL_ENABLED=true
   SMTP_USER=your_gmail@gmail.com
   SMTP_PASSWORD=<app password, no spaces>
   ALERT_EMAIL_TO=where_alerts_should_go@gmail.com
   ```

**MQTT** (optional, needs a broker like Mosquitto running):
```
MQTT_ENABLED=true
MQTT_BROKER_HOST=localhost
MQTT_TOPIC=seaker/metrics
```

Restart the app after changing `.env` for any of these to take effect.

## Changing thresholds

Edit them directly from the dashboard under "Alert Thresholds." Saving requires an admin login — your browser will prompt for it. Set the admin username/password in `.env`:
```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<pick a real password>
```

Default thresholds used to trigger alerts:

| Metric | Default |
|---|---|
| CPU % | 85 |
| RAM % | 85 |
| Disk % | 90 |
| Temperature °C | NA |

To simulate an alert for a demo: just lower a threshold below the current value on the dashboard and save — the alert fires within a few seconds.

## Live demo

Dashboard: `<add your ngrok / deployed URL here before submitting>`

## Notes

I used a custom FastAPI + SQLite setup instead of the TICK stack, so I could build the full pipeline myself (collection, storage, alerting, real-time dashboard) rather than just wiring together existing tools. Happy to walk through how it'd map onto TICK stack if useful.

Temperature shows N/A on Windows since Windows doesn't expose it through a standard API the way Linux does — this is why the brief marks it optional.
