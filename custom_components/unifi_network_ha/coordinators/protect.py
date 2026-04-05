"""UniFi Protect coordinator."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from .base import UniFiDataUpdateCoordinator

if TYPE_CHECKING:
    from ..hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


@dataclass
class ProtectCamera:
    """Simplified camera data."""

    id: str = ""
    name: str = ""
    mac: str = ""
    type: str = ""  # "UVC-G4-PRO", etc.
    state: str = ""  # "CONNECTED", "DISCONNECTED"
    is_connected: bool = False
    is_recording: bool = False
    last_motion: int = 0  # unix timestamp
    up_since: int = 0
    firmware: str = ""
    model: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> ProtectCamera:
        """Create a ProtectCamera from a Protect API camera dict."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            mac=data.get("mac", ""),
            type=data.get("type", ""),
            state=data.get("state", ""),
            is_connected=data.get("state") == "CONNECTED",
            is_recording=data.get("isRecording", False),
            last_motion=data.get("lastMotion", 0),
            up_since=data.get("upSince", 0),
            firmware=data.get("firmwareVersion", ""),
            model=data.get("type", ""),
        )


@dataclass
class ProtectNvr:
    """Simplified NVR data."""

    name: str = ""
    version: str = ""
    uptime: int = 0
    storage_used: int = 0  # bytes
    storage_total: int = 0  # bytes
    recording_retention: int = 0  # hours
    cpu_usage: float = 0.0
    mem_usage: float = 0.0
    camera_count: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> ProtectNvr:
        """Create a ProtectNvr from a Protect API NVR dict."""
        storage_info = data.get("storageInfo", {}) or {}
        system_info = data.get("systemInfo", {}) or {}
        cpu = system_info.get("cpu", {}) or {}
        memory = system_info.get("memory", {}) or {}

        total_size = storage_info.get("totalSize", 0) or 0
        available = storage_info.get("totalSpaceAvailable", 0) or 0

        mem_total = memory.get("total", 0) or 0
        mem_available = memory.get("available", 0) or 0
        mem_pct = (
            round((1 - mem_available / mem_total) * 100, 1)
            if mem_total > 0
            else 0
        )

        retention_ms = data.get("recordingRetentionDurationMs", 0) or 0

        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            uptime=data.get("uptime", 0),
            storage_used=max(total_size - available, 0),
            storage_total=total_size,
            recording_retention=retention_ms // 3600000,
            cpu_usage=cpu.get("averageLoad", 0.0),
            mem_usage=mem_pct,
            camera_count=len(data.get("cameras", [])) if "cameras" in data else 0,
        )


class ProtectCoordinator(UniFiDataUpdateCoordinator):
    """Coordinator for UniFi Protect data."""

    def __init__(self, hub: UniFiHub, update_interval: int = 60) -> None:
        super().__init__(
            hub.hass,
            _LOGGER,
            name="UniFi Protect",
            update_interval=timedelta(seconds=update_interval),
        )
        self.hub = hub
        self.cameras: dict[str, ProtectCamera] = {}
        self.nvr: ProtectNvr | None = None
        self.available: bool = False

    async def _async_fetch_data(self) -> dict[str, Any]:
        """Fetch data from the Protect API."""
        if not self.hub.protect:
            return {"cameras": {}, "nvr": None}

        bootstrap = await self.hub.protect.get_bootstrap()
        if bootstrap is None:
            self.available = False
            return {"cameras": self.cameras, "nvr": self.nvr}

        self.available = True

        # Parse NVR
        nvr_data = bootstrap.get("nvr")
        if isinstance(nvr_data, dict):
            self.nvr = ProtectNvr.from_dict(nvr_data)

        # Parse cameras
        cameras_data = bootstrap.get("cameras", [])
        self.cameras = {}
        for cam in cameras_data:
            camera = ProtectCamera.from_dict(cam)
            if camera.id:
                self.cameras[camera.id] = camera

        return {"cameras": self.cameras, "nvr": self.nvr}
