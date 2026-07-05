"""
Optional MQTT publisher (bonus: IoT protocol support). When enabled,
every collected sample is also published to an MQTT broker as JSON,
so other IoT tooling (Node-RED, another dashboard, a microcontroller)
can subscribe to live metrics.
"""
import json
import threading
from . import config

_client = None
_lock = threading.Lock()


def _get_client():
    global _client
    if not config.MQTT_ENABLED:
        return None
    with _lock:
        if _client is None:
            import paho.mqtt.client as mqtt
            _client = mqtt.Client()
            try:
                _client.connect(config.MQTT_BROKER_HOST, config.MQTT_BROKER_PORT, keepalive=30)
                _client.loop_start()
            except Exception as e:
                print(f"[mqtt] connection failed: {e}")
                _client = None
    return _client


def publish(sample: dict):
    if not config.MQTT_ENABLED:
        return
    client = _get_client()
    if client is None:
        return
    try:
        client.publish(config.MQTT_TOPIC, json.dumps(sample))
    except Exception as e:
        print(f"[mqtt] publish failed: {e}")
