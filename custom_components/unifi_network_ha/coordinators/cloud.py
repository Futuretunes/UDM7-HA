"""Cloud API coordinator for UniFi Network HA."""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from ..api.models import CloudHost, CloudIspMetrics, SdWanConfig
from .base import UniFiDataUpdateCoordinator

if TYPE_CHECKING:
    from ..hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


class CloudCoordinator(UniFiDataUpdateCoordinator):
    """Coordinator for cloud Site Manager API data.

    Fetches ISP metrics, hosts, and SD-WAN configurations from the
    Ubiquiti cloud API (api.ui.com).
    """

    def __init__(self, hub: UniFiHub, update_interval: int = 900) -> None:
        super().__init__(
            hub.hass,
            _LOGGER,
            name="UniFi Cloud",
            update_interval=timedelta(seconds=update_interval),
        )
        self.hub = hub
        self.isp_metrics: list[CloudIspMetrics] = []
        self.hosts: list[CloudHost] = []
        self.sdwan_configs: list[SdWanConfig] = []

    async def _async_fetch_data(self) -> dict[str, Any]:
        """Fetch cloud data: ISP metrics, hosts, and SD-WAN configs."""
        if self.hub.cloud is None:
            return {}

        # Fetch ISP metrics for the last 24 hours
        now = int(time.time())
        begin = now - 86400  # 24 hours ago

        raw_metrics = await self.hub.cloud.get_isp_metrics(
            "5m", begin_ts=begin, end_ts=now
        )
        self.isp_metrics = [CloudIspMetrics.from_dict(m) for m in raw_metrics]

        raw_hosts = await self.hub.cloud.get_hosts()
        self.hosts = [CloudHost.from_dict(h) for h in raw_hosts]

        raw_sdwan = await self.hub.cloud.get_sdwan_configs()
        self.sdwan_configs = [SdWanConfig.from_dict(s) for s in raw_sdwan]

        return {
            "isp_metrics": self.isp_metrics,
            "hosts": self.hosts,
            "sdwan_configs": self.sdwan_configs,
        }

    @property
    def latest_isp_metrics(self) -> CloudIspMetrics | None:
        """Return the most recent ISP metrics entry, or None."""
        if not self.isp_metrics:
            return None
        # Return the entry with the highest period_end
        return max(self.isp_metrics, key=lambda m: m.period_end)
