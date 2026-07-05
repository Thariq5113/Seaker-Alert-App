"""
Cross-platform system metrics collection using psutil.
Works on Windows, Linux, and Raspberry Pi with no code changes.
"""
import os
import time
import psutil
from . import config


def _get_disk_root():
    return "C:\\" if os.name == "nt" else "/"


def _get_temperature():
    """
    Temperature is optional per the spec. psutil.sensors_temperatures()
    only works on Linux (and Raspberry Pi exposes it cleanly via the
    thermal zone). On Windows it's unavailable through psutil, so we
    return None there rather than faking a value.
    """
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        for _, entries in temps.items():
            for entry in entries:
                if entry.current:
                    return round(entry.current, 1)
    except (AttributeError, NotImplementedError):
        return None
    return None


def collect() -> dict:
    cpu_percent = psutil.cpu_percent(interval=0.5)

    vm = psutil.virtual_memory()
    ram_total_gb = round(vm.total / (1024 ** 3), 2)
    ram_used_gb = round((vm.total - vm.available) / (1024 ** 3), 2)
    ram_percent = round(vm.percent, 1)

    disk = psutil.disk_usage(_get_disk_root())
    disk_total_gb = round(disk.total / (1024 ** 3), 2)
    disk_used_gb = round(disk.used / (1024 ** 3), 2)
    disk_percent = round(disk.percent, 1)

    uptime_hours = round((time.time() - psutil.boot_time()) / 3600, 2)

    temp_celsius = _get_temperature()

    return {
        "ts": time.time(),
        "device_name": config.DEVICE_NAME,
        "cpu_percent": round(cpu_percent, 1),
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "ram_percent": ram_percent,
        "disk_used_gb": disk_used_gb,
        "disk_total_gb": disk_total_gb,
        "disk_percent": disk_percent,
        "uptime_hours": uptime_hours,
        "temp_celsius": temp_celsius,
    }
