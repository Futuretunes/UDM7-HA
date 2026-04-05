"""Base entity for UniFi Network HA."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinators.base import UniFiDataUpdateCoordinator
from .device_images import get_device_image_url

if TYPE_CHECKING:
    from .hub import UniFiHub

_LOGGER = logging.getLogger(__name__)


class UniFiEntity(CoordinatorEntity[UniFiDataUpdateCoordinator]):
    """Base entity for all UniFi Network HA platforms.

    Every entity is tied to:
    * a coordinator (for automatic polling / update callbacks),
    * a physical device identified by its MAC address,
    * an ``EntityDescription`` whose *key* is combined with the MAC to form
      the unique ID.

    The ``hub`` reference is stored so that ``value_fn`` callbacks in
    platform-specific descriptions can reach into any coordinator data they
    need without coupling the base class to a particular data shape.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UniFiDataUpdateCoordinator,
        description: EntityDescription,
        hub: UniFiHub,
        mac: str,
        device_name: str,
        device_model: str,
    ) -> None:
        """Initialise the entity.

        Parameters
        ----------
        coordinator:
            The coordinator this entity subscribes to for updates.
        description:
            Platform-specific entity description (carries ``key``, ``name``,
            ``value_fn``, etc.).
        hub:
            The central ``UniFiHub`` — passed through so ``value_fn``
            callbacks can access any coordinator's data.
        mac:
            MAC address of the physical UniFi device this entity belongs to.
        device_name:
            Friendly name shown in the device registry.
        device_model:
            Model string shown in the device registry.
        """
        super().__init__(coordinator)
        self.entity_description = description
        self._hub = hub
        self._device_mac = mac
        self._device_name = device_name
        self._device_model = device_model
        self._attr_unique_id = f"{mac}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self._device_mac)},
            name=self._device_name,
            manufacturer=MANUFACTURER,
            model=self._device_model,
        )
        # Add a configuration_url linking to the product image when available.
        # Home Assistant does not natively support custom device images via
        # DeviceInfo, but configuration_url gives users quick access to the
        # product page / image.
        image_url = get_device_image_url(self._device_model)
        if image_url:
            info["configuration_url"] = image_url
        return info
