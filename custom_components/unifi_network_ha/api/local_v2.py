"""Wrapper for the UniFi V2 API endpoints.

These endpoints live under ``/v2/api/site/{site}/...`` and expose newer
features such as traffic rules, traffic routes, firewall policies, and
firewall zones.  The V2 API may return data directly (not wrapped in the
standard ``{"meta": …, "data": …}`` envelope), but the base client's
:meth:`~.client.UniFiApiClient.request` handles both formats transparently.
"""

from __future__ import annotations

import logging
from typing import Any

from .client import UniFiApiClient

_LOGGER = logging.getLogger(__name__)


class LocalV2Api:
    """UniFi V2 API wrapper."""

    def __init__(self, client: UniFiApiClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Path helper
    # ------------------------------------------------------------------

    def _v2_path(self, path: str) -> str:
        """Build ``/v2/api/site/{site}/{path}``."""
        return f"/v2/api/site/{self._client.site}/{path}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _as_list(data: Any) -> list[dict]:
        """Normalise a response to a list of dicts.

        V2 endpoints may return a bare list or a wrapper object with a data
        key.  This helper handles both cases.
        """
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data:
            inner = data["data"]
            if isinstance(inner, list):
                return inner
        return []

    # ==================================================================
    # Traffic rules
    # ==================================================================

    async def get_traffic_rules(self) -> list[dict]:
        """Return all traffic rules for the site.

        ``GET /v2/api/site/{site}/trafficrules``
        """
        data = await self._client.get(self._v2_path("trafficrules"))
        return self._as_list(data)

    async def set_traffic_rule(self, rule_id: str, data: dict) -> dict:
        """Update a traffic rule.

        ``PUT /v2/api/site/{site}/trafficrules/{id}``

        Args:
            rule_id: The identifier of the rule to update.
            data: Dictionary of fields to change.
        """
        result = await self._client.put(
            self._v2_path(f"trafficrules/{rule_id}"),
            json=data,
        )
        return result if isinstance(result, dict) else {}

    # ==================================================================
    # Traffic routes
    # ==================================================================

    async def get_traffic_routes(self) -> list[dict]:
        """Return all traffic routes for the site.

        ``GET /v2/api/site/{site}/trafficroutes``
        """
        data = await self._client.get(self._v2_path("trafficroutes"))
        return self._as_list(data)

    async def set_traffic_route(self, route_id: str, data: dict) -> dict:
        """Update a traffic route.

        ``PUT /v2/api/site/{site}/trafficroutes/{id}``

        Args:
            route_id: The identifier of the route to update.
            data: Dictionary of fields to change.
        """
        result = await self._client.put(
            self._v2_path(f"trafficroutes/{route_id}"),
            json=data,
        )
        return result if isinstance(result, dict) else {}

    # ==================================================================
    # Firewall policies
    # ==================================================================

    async def get_firewall_policies(self) -> list[dict]:
        """Return all firewall policies for the site.

        ``GET /v2/api/site/{site}/firewall-policies``
        """
        data = await self._client.get(self._v2_path("firewall-policies"))
        return self._as_list(data)

    async def set_firewall_policy(self, policy_id: str, data: dict) -> dict:
        """Update a firewall policy.

        ``PUT /v2/api/site/{site}/firewall-policies/{id}``

        Args:
            policy_id: The identifier of the policy to update.
            data: Dictionary of fields to change.
        """
        result = await self._client.put(
            self._v2_path(f"firewall-policies/{policy_id}"),
            json=data,
        )
        return result if isinstance(result, dict) else {}

    # ==================================================================
    # Firewall zones
    # ==================================================================

    async def get_firewall_zones(self) -> list[dict]:
        """Return all firewall zones for the site.

        ``GET /v2/api/site/{site}/firewall-zones``
        """
        data = await self._client.get(self._v2_path("firewall-zones"))
        return self._as_list(data)
