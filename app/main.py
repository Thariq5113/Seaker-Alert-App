import asyncio
import csv
import io
import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, database, collector, alerts, mqtt_client, auth, telegram_poller

connected_clients: set[WebSocket] = set()
latest_sample: dict = {}


async def broadcast(payload: dict):
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_clients.discard(ws)


def sync_broadcast(payload: dict):
    """Bridge for the alerts module, which is synchronous."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(broadcast(payload))
    except RuntimeError:
        pass


async def collection_loop():
    last_persist = 0
    while True:
        try:
            sample = collector.collect()
            global latest_sample
            latest_sample = sample

            thresholds = database.get_thresholds()
            alerts.evaluate_and_dispatch(sample, thresholds, broadcast_fn=sync_broadcast)
            mqtt_client.publish(sample)

            await broadcast({"type": "metrics", "data": sample})

            now = time.time()
            if now - last_persist >= config.COLLECT_INTERVAL_SECONDS:
                database.insert_metric(sample)
                last_persist = now
        except Exception as e:
            print(f"[collection_loop] error: {e}")

        await asyncio.sleep(config.BROADCAST_INTERVAL_SECONDS)


async def telegram_poll_loop():
    while True:
        try:
            telegram_poller.poll_once()
        except Exception as e:
            print(f"[telegram_poll_loop] error: {e}")
        await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    task = asyncio.create_task(collection_loop())
    poll_task = asyncio.create_task(telegram_poll_loop())
    yield
    task.cancel()
    poll_task.cancel()


app = FastAPI(title="Seaker Alert App", lifespan=lifespan)


@app.get("/api/metrics/latest")
def api_latest():
    return latest_sample or database.get_latest() or {}


@app.get("/api/metrics/history")
def api_history(hours: float = 24):
    return database.get_history(hours=hours)


@app.get("/api/thresholds")
def api_get_thresholds():
    return database.get_thresholds()


class ThresholdsUpdate(BaseModel):
    cpu_percent: float | None = None
    ram_percent: float | None = None
    disk_percent: float | None = None
    temp_celsius: float | None = None


@app.post("/api/thresholds")
async def api_set_thresholds(update: ThresholdsUpdate, admin_user: str = Depends(auth.require_admin)):
    values = {k: v for k, v in update.model_dump().items() if v is not None}
    database.set_thresholds(values)
    new_thresholds = database.get_thresholds()

    # Check the current live sample against the freshly-saved thresholds
    # right now, rather than waiting for the next collection cycle — and
    # bypass the cooldown for the metrics that were just changed, so a
    # threshold that's already breached alerts immediately (useful for
    # demos: lower a threshold, save, see/get the alert right away).
    if latest_sample:
        alerts.reset_cooldown(values.keys())
        alerts.evaluate_and_dispatch(latest_sample, new_thresholds, broadcast_fn=sync_broadcast)

    return new_thresholds


@app.get("/api/alerts")
def api_alerts(limit: int = 20):
    return database.get_recent_alerts(limit=limit)


@app.get("/api/telegram/subscribers")
def api_telegram_subscribers():
    return {"subscribers": database.get_telegram_subscribers()}


@app.get("/api/export/csv")
def export_csv(hours: float = 24):
    rows = database.get_history(hours=hours)
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=metrics_export.csv"},
    )


@app.get("/api/export/json")
def export_json(hours: float = 24):
    rows = database.get_history(hours=hours)
    return JSONResponse(content=rows)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        if latest_sample:
            await websocket.send_json({"type": "metrics", "data": latest_sample})
        while True:
            await websocket.receive_text()  # keep-alive / ignore incoming
    except WebSocketDisconnect:
        connected_clients.discard(websocket)


app.mount("/", StaticFiles(directory="static", html=True), name="static")