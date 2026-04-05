"""Data models for UniFi Network API responses.

Each model is a dataclass with sensible defaults so it can be constructed
from partial API responses.  Every model exposes a ``from_dict`` classmethod
that safely extracts fields from raw JSON dicts without ever raising on
missing keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _safe_float(value: object, default: float = 0.0) -> float:
    """Coerce *value* to float, returning *default* on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    """Coerce *value* to int, returning *default* on failure."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: object, default: bool = False) -> bool:
    """Coerce *value* to bool, returning *default* on failure."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    try:
        return bool(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# WAN
# ---------------------------------------------------------------------------

@dataclass
class WanInterface:
    """A single WAN interface (wan1, wan2, etc.)."""

    name: str = ""
    up: bool = False
    ip: str = ""
    ip6: str = ""
    netmask: str = ""
    gateway: str = ""
    dns: list[str] = field(default_factory=list)
    type: str = ""
    speed: int = 0
    full_duplex: bool = False
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_bytes_r: float = 0.0
    tx_bytes_r: float = 0.0
    rx_packets: int = 0
    tx_packets: int = 0
    rx_errors: int = 0
    tx_errors: int = 0
    rx_dropped: int = 0
    tx_dropped: int = 0
    latency: float = 0.0
    availability: float = 0.0
    internet: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Create a ``WanInterface`` from a raw API dict."""
        dns_raw = data.get("dns", [])
        if isinstance(dns_raw, str):
            dns_raw = [s.strip() for s in dns_raw.split(",") if s.strip()]
        elif not isinstance(dns_raw, list):
            dns_raw = []

        return cls(
            name=str(data.get("name", data.get("ifname", ""))),
            up=_safe_bool(data.get("up", data.get("is_up"))),
            ip=str(data.get("ip", "")),
            ip6=str(data.get("ip6", data.get("ipv6", ""))),
            netmask=str(data.get("netmask", "")),
            gateway=str(data.get("gateway", data.get("gw", ""))),
            dns=dns_raw,
            type=str(data.get("type", "")),
            speed=_safe_int(data.get("speed", 0)),
            full_duplex=_safe_bool(data.get("full_duplex")),
            rx_bytes=_safe_int(data.get("rx_bytes", 0)),
            tx_bytes=_safe_int(data.get("tx_bytes", 0)),
            rx_bytes_r=_safe_float(data.get("rx_bytes-r", data.get("rx_bytes_r", 0.0))),
            tx_bytes_r=_safe_float(data.get("tx_bytes-r", data.get("tx_bytes_r", 0.0))),
            rx_packets=_safe_int(data.get("rx_packets", 0)),
            tx_packets=_safe_int(data.get("tx_packets", 0)),
            rx_errors=_safe_int(data.get("rx_errors", 0)),
            tx_errors=_safe_int(data.get("tx_errors", 0)),
            rx_dropped=_safe_int(data.get("rx_dropped", 0)),
            tx_dropped=_safe_int(data.get("tx_dropped", 0)),
            latency=_safe_float(data.get("latency", 0.0)),
            availability=_safe_float(data.get("availability", 0.0)),
            internet=_safe_bool(data.get("internet")),
        )


# ---------------------------------------------------------------------------
# Speed test
# ---------------------------------------------------------------------------

@dataclass
class SpeedTestResult:
    """Speed test results from the gateway."""

    latency: float = 0.0
    download: float = 0.0
    upload: float = 0.0
    run_date: float = 0.0
    status_summary: str = ""
    server_city: str = ""
    server_country: str = ""
    interface: str = ""
    in_progress: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Create a ``SpeedTestResult`` from a raw API dict."""
        # The controller nests results under "status_summary" or at the top
        # level depending on firmware.  Handle both.
        server = data.get("server", {}) or {}
        return cls(
            latency=_safe_float(data.get("latency", data.get("ping", 0.0))),
            download=_safe_float(data.get("xput_download", data.get("download", 0.0))),
            upload=_safe_float(data.get("xput_upload", data.get("upload", 0.0))),
            run_date=_safe_float(data.get("rundate", data.get("run_date", 0.0))),
            status_summary=str(data.get("status_summary", "")),
            server_city=str(server.get("city", data.get("server_city", ""))),
            server_country=str(server.get("country", data.get("server_country", ""))),
            interface=str(data.get("interface", data.get("source_interface", ""))),
            in_progress=_safe_bool(data.get("in_progress", data.get("status_summary") == "running")),
        )


# ---------------------------------------------------------------------------
# Hardware helpers
# ---------------------------------------------------------------------------

@dataclass
class DeviceTemperature:
    """A temperature reading from a device."""

    name: str = ""
    value: float = 0.0
    type: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            name=str(data.get("name", "")),
            value=_safe_float(data.get("value", data.get("temperature", 0.0))),
            type=str(data.get("type", "")),
        )


@dataclass
class DevicePort:
    """A physical port on a device (switch port, etc.)."""

    idx: int = 0
    name: str = ""
    up: bool = False
    speed: int = 0
    full_duplex: bool = False
    rx_bytes_r: float = 0.0
    tx_bytes_r: float = 0.0
    rx_bytes: int = 0
    tx_bytes: int = 0
    poe_enable: bool = False
    poe_power: float = 0.0
    poe_voltage: float = 0.0
    poe_current: float = 0.0
    poe_mode: str = ""
    stp_state: str = ""
    is_uplink: bool = False
    media: str = ""
    sfp_found: bool = False
    sfp_temperature: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            idx=_safe_int(data.get("port_idx", data.get("idx", 0))),
            name=str(data.get("name", "")),
            up=_safe_bool(data.get("up")),
            speed=_safe_int(data.get("speed", 0)),
            full_duplex=_safe_bool(data.get("full_duplex")),
            rx_bytes_r=_safe_float(data.get("rx_bytes-r", data.get("rx_bytes_r", 0.0))),
            tx_bytes_r=_safe_float(data.get("tx_bytes-r", data.get("tx_bytes_r", 0.0))),
            rx_bytes=_safe_int(data.get("rx_bytes", 0)),
            tx_bytes=_safe_int(data.get("tx_bytes", 0)),
            poe_enable=_safe_bool(data.get("poe_enable")),
            poe_power=_safe_float(data.get("poe_power", data.get("port_poe", 0.0))),
            poe_voltage=_safe_float(data.get("poe_voltage", 0.0)),
            poe_current=_safe_float(data.get("poe_current", 0.0)),
            poe_mode=str(data.get("poe_mode", "")),
            stp_state=str(data.get("stp_state", "")),
            is_uplink=_safe_bool(data.get("is_uplink")),
            media=str(data.get("media", "")),
            sfp_found=_safe_bool(data.get("sfp_found")),
            sfp_temperature=_safe_float(data.get("sfp_temperature", 0.0)),
        )


@dataclass
class DeviceRadio:
    """A radio on an AP."""

    name: str = ""
    radio: str = ""
    channel: int = 0
    tx_power: int = 0
    ht: str = ""
    num_sta: int = 0
    cu_total: int = 0
    cu_self_rx: int = 0
    cu_self_tx: int = 0
    satisfaction: int = 0
    tx_retries: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            name=str(data.get("name", "")),
            radio=str(data.get("radio", "")),
            channel=_safe_int(data.get("channel", 0)),
            tx_power=_safe_int(data.get("tx_power", 0)),
            ht=str(data.get("ht", "")),
            num_sta=_safe_int(data.get("num_sta", 0)),
            cu_total=_safe_int(data.get("cu_total", 0)),
            cu_self_rx=_safe_int(data.get("cu_self_rx", 0)),
            cu_self_tx=_safe_int(data.get("cu_self_tx", 0)),
            satisfaction=_safe_int(data.get("satisfaction", 0)),
            tx_retries=_safe_int(data.get("tx_retries", 0)),
        )


@dataclass
class DeviceStorage:
    """Storage info on a device (e.g., NVR microSD)."""

    name: str = ""
    mount_point: str = ""
    size: int = 0
    used: int = 0
    type: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            name=str(data.get("name", "")),
            mount_point=str(data.get("mount_point", "")),
            size=_safe_int(data.get("size", 0)),
            used=_safe_int(data.get("used", 0)),
            type=str(data.get("type", "")),
        )


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------

@dataclass
class Device:
    """A UniFi network device (gateway, AP, switch)."""

    mac: str = ""
    ip: str = ""
    name: str = ""
    model: str = ""
    model_name: str = ""
    type: str = ""
    version: str = ""
    upgradable: bool = False
    upgrade_to_firmware: str = ""
    adopted: bool = False
    state: int = 0
    uptime: int = 0
    last_seen: int = 0
    serial: str = ""

    # System stats
    cpu_usage: float = 0.0
    mem_usage: float = 0.0
    mem_total: int = 0
    mem_used: int = 0
    loadavg_1: float = 0.0
    loadavg_5: float = 0.0
    loadavg_15: float = 0.0

    # Clients
    num_sta: int = 0
    user_num_sta: int = 0
    guest_num_sta: int = 0

    # WAN (gateway only)
    wan_interfaces: list[WanInterface] = field(default_factory=list)
    internet: bool = False
    active_wan: str = ""

    # Speed test
    speedtest: SpeedTestResult | None = None

    # Hardware
    temperatures: list[DeviceTemperature] = field(default_factory=list)
    fan_level: int = 0

    # Ports (switches and gateways)
    ports: list[DevicePort] = field(default_factory=list)

    # Radios (APs)
    radios: list[DeviceRadio] = field(default_factory=list)

    # Storage
    storage: list[DeviceStorage] = field(default_factory=list)

    # LED
    led_enabled: bool = True
    led_color: str = ""
    led_brightness: int = 0

    # VRRP / Shadow Mode
    vrrp_enabled: bool = False
    vrrp_state: str = ""

    # Uplink info
    uplink_mac: str = ""
    uplink_type: str = ""

    # Raw data
    raw: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict) -> Self:  # noqa: C901 (complex but intentional)
        """Create a ``Device`` from a raw API dict.

        Handles the many nested / oddly-named keys that the UniFi controller
        returns.
        """
        # --- system-stats (note the hyphen) --------------------------
        sys_stats_hyphen: dict = data.get("system-stats", {}) or {}
        sys_stats: dict = data.get("sys_stats", {}) or {}

        cpu_usage = _safe_float(sys_stats_hyphen.get("cpu", sys_stats.get("cpu")))
        mem_usage = _safe_float(sys_stats_hyphen.get("mem", sys_stats.get("mem")))
        mem_total = _safe_int(sys_stats.get("mem_total", 0))
        mem_used = _safe_int(sys_stats.get("mem_used", 0))
        loadavg_1 = _safe_float(sys_stats.get("loadavg_1", 0.0))
        loadavg_5 = _safe_float(sys_stats.get("loadavg_5", 0.0))
        loadavg_15 = _safe_float(sys_stats.get("loadavg_15", 0.0))

        # --- WAN interfaces -----------------------------------------
        wan_interfaces: list[WanInterface] = []
        for wan_key in ("wan1", "wan2", "wan3", "wan4"):
            wan_raw = data.get(wan_key)
            if isinstance(wan_raw, dict):
                # Inject a name if the dict does not carry one already.
                if "name" not in wan_raw and "ifname" not in wan_raw:
                    wan_raw = {**wan_raw, "name": wan_key}
                wan_interfaces.append(WanInterface.from_dict(wan_raw))

        # Some firmware versions place WAN info under "network_table".
        if not wan_interfaces:
            for net in data.get("network_table", []) or []:
                if isinstance(net, dict) and str(net.get("name", "")).startswith("wan"):
                    wan_interfaces.append(WanInterface.from_dict(net))

        # --- active WAN & internet ----------------------------------
        active_wan = ""
        # Prefer the uplink dict for active WAN detection.
        uplink = data.get("uplink", {}) or {}
        uplink_name = str(uplink.get("name", uplink.get("ifname", "")))
        if uplink_name.startswith("wan"):
            active_wan = uplink_name

        # Fall back to the first interface that is up.
        if not active_wan:
            for wi in wan_interfaces:
                if wi.up:
                    active_wan = wi.name
                    break

        # Internet reachability: explicit field, or infer from WAN state.
        internet_raw = data.get("internet")
        if internet_raw is not None:
            internet = _safe_bool(internet_raw)
        else:
            internet = any(wi.internet for wi in wan_interfaces)

        # --- speed test ---------------------------------------------
        speedtest_raw = data.get("speedtest-status", data.get("speedtest_status"))
        speedtest: SpeedTestResult | None = None
        if isinstance(speedtest_raw, dict):
            speedtest = SpeedTestResult.from_dict(speedtest_raw)

        # --- temperatures -------------------------------------------
        temps_raw = data.get("temperatures", []) or []
        temperatures = [
            DeviceTemperature.from_dict(t)
            for t in temps_raw
            if isinstance(t, dict)
        ]

        # --- ports --------------------------------------------------
        ports_raw = data.get("port_table", []) or []
        ports = [
            DevicePort.from_dict(p)
            for p in ports_raw
            if isinstance(p, dict)
        ]

        # --- radios -------------------------------------------------
        # Prefer radio_table_stats (runtime stats) over radio_table (config).
        radios_raw = data.get("radio_table_stats", data.get("radio_table", [])) or []
        radios = [
            DeviceRadio.from_dict(r)
            for r in radios_raw
            if isinstance(r, dict)
        ]

        # --- storage ------------------------------------------------
        storage_raw = data.get("storage", []) or []
        storage = [
            DeviceStorage.from_dict(s)
            for s in storage_raw
            if isinstance(s, dict)
        ]

        # --- LED ----------------------------------------------------
        led_override = data.get("led_override", "")
        led_enabled = True
        if isinstance(led_override, str):
            led_enabled = led_override != "off"
        elif isinstance(led_override, bool):
            led_enabled = led_override

        # --- VRRP ---------------------------------------------------
        config_network = data.get("config_network", {}) or {}
        vrrp_enabled = _safe_bool(config_network.get("vrrp_enabled", data.get("vrrp_enabled")))
        vrrp_state = str(config_network.get("vrrp_state", data.get("vrrp_state", "")))

        # --- uplink -------------------------------------------------
        uplink_mac = str(uplink.get("uplink_mac", uplink.get("mac", "")))
        uplink_type = str(uplink.get("type", uplink.get("media", "")))

        return cls(
            mac=str(data.get("mac", "")),
            ip=str(data.get("ip", "")),
            name=str(data.get("name", data.get("hostname", ""))),
            model=str(data.get("model", "")),
            model_name=str(data.get("model_name", data.get("model_in_lts", ""))),
            type=str(data.get("type", "")),
            version=str(data.get("version", data.get("firmware_version", ""))),
            upgradable=_safe_bool(data.get("upgradable", data.get("upgrade_available"))),
            upgrade_to_firmware=str(data.get("upgrade_to_firmware", "")),
            adopted=_safe_bool(data.get("adopted")),
            state=_safe_int(data.get("state", 0)),
            uptime=_safe_int(data.get("uptime", 0)),
            last_seen=_safe_int(data.get("last_seen", 0)),
            serial=str(data.get("serial", "")),
            cpu_usage=cpu_usage,
            mem_usage=mem_usage,
            mem_total=mem_total,
            mem_used=mem_used,
            loadavg_1=loadavg_1,
            loadavg_5=loadavg_5,
            loadavg_15=loadavg_15,
            num_sta=_safe_int(data.get("num_sta", 0)),
            user_num_sta=_safe_int(data.get("user-num_sta", data.get("user_num_sta", 0))),
            guest_num_sta=_safe_int(data.get("guest-num_sta", data.get("guest_num_sta", 0))),
            wan_interfaces=wan_interfaces,
            internet=internet,
            active_wan=active_wan,
            speedtest=speedtest,
            temperatures=temperatures,
            fan_level=_safe_int(data.get("fan_level", 0)),
            ports=ports,
            radios=radios,
            storage=storage,
            led_enabled=led_enabled,
            led_color=str(data.get("led_override_color", "")),
            led_brightness=_safe_int(data.get("led_override_color_brightness", 0)),
            vrrp_enabled=vrrp_enabled,
            vrrp_state=vrrp_state,
            uplink_mac=uplink_mac,
            uplink_type=uplink_type,
            raw=data,
        )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

@dataclass
class Client:
    """A connected network client."""

    mac: str = ""
    ip: str = ""
    hostname: str = ""
    name: str = ""
    oui: str = ""
    is_wired: bool = False
    is_guest: bool = False

    # Connection
    essid: str = ""
    bssid: str = ""
    ap_mac: str = ""
    sw_mac: str = ""
    sw_port: int = 0
    network: str = ""
    vlan: int = 0

    # Wireless stats
    signal: int = 0
    rssi: int = 0
    noise: int = 0
    channel: int = 0
    radio: str = ""
    radio_proto: str = ""
    satisfaction: int = 0

    # Bandwidth
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_bytes_r: float = 0.0
    tx_bytes_r: float = 0.0
    rx_rate: int = 0
    tx_rate: int = 0

    # State
    uptime: int = 0
    last_seen: int = 0
    first_seen: int = 0
    blocked: bool = False

    # Fingerprint
    dev_cat: int = 0
    dev_family: int = 0
    dev_vendor: int = 0
    os_name: str = ""
    dev_id_override: int = 0
    fingerprint_source: int = 0

    # Raw
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Create a ``Client`` from a raw API dict.

        Handles the many alternative / underscore-prefixed field names the
        controller may return (``_is_guest_by_uap``, ``_last_seen_by_uap``,
        etc.).
        """
        # Guest detection — several flags, any True means guest.
        is_guest = _safe_bool(
            data.get(
                "is_guest",
                data.get(
                    "_is_guest_by_uap",
                    data.get(
                        "_is_guest_by_ugw",
                        data.get("_is_guest_by_usw", False),
                    ),
                ),
            )
        )

        # last_seen — controller may report per-device type.
        last_seen = _safe_int(
            data.get(
                "last_seen",
                data.get(
                    "_last_seen_by_uap",
                    data.get(
                        "_last_seen_by_ugw",
                        data.get("_last_seen_by_usw", 0),
                    ),
                ),
            )
        )

        # uptime — controller sometimes uses _uptime_by_*.
        uptime = _safe_int(
            data.get(
                "uptime",
                data.get(
                    "_uptime_by_uap",
                    data.get(
                        "_uptime_by_ugw",
                        data.get("_uptime_by_usw", 0),
                    ),
                ),
            )
        )

        return cls(
            mac=str(data.get("mac", "")),
            ip=str(data.get("ip", data.get("fixed_ip", ""))),
            hostname=str(data.get("hostname", "")),
            name=str(data.get("name", data.get("display_name", ""))),
            oui=str(data.get("oui", "")),
            is_wired=_safe_bool(data.get("is_wired")),
            is_guest=is_guest,
            essid=str(data.get("essid", "")),
            bssid=str(data.get("bssid", "")),
            ap_mac=str(data.get("ap_mac", "")),
            sw_mac=str(data.get("sw_mac", "")),
            sw_port=_safe_int(data.get("sw_port", 0)),
            network=str(data.get("network", data.get("network_name", ""))),
            vlan=_safe_int(data.get("vlan", data.get("use_fixedip", 0))),
            signal=_safe_int(data.get("signal", 0)),
            rssi=_safe_int(data.get("rssi", 0)),
            noise=_safe_int(data.get("noise", 0)),
            channel=_safe_int(data.get("channel", 0)),
            radio=str(data.get("radio", "")),
            radio_proto=str(data.get("radio_proto", "")),
            satisfaction=_safe_int(data.get("satisfaction", data.get("wifi_experience_score", 0))),
            rx_bytes=_safe_int(data.get("rx_bytes", 0)),
            tx_bytes=_safe_int(data.get("tx_bytes", 0)),
            rx_bytes_r=_safe_float(data.get("rx_bytes-r", data.get("rx_bytes_r", 0.0))),
            tx_bytes_r=_safe_float(data.get("tx_bytes-r", data.get("tx_bytes_r", 0.0))),
            rx_rate=_safe_int(data.get("rx_rate", 0)),
            tx_rate=_safe_int(data.get("tx_rate", 0)),
            uptime=uptime,
            last_seen=last_seen,
            first_seen=_safe_int(data.get("first_seen", 0)),
            blocked=_safe_bool(data.get("blocked")),
            dev_cat=_safe_int(data.get("dev_cat", 0)),
            dev_family=_safe_int(data.get("dev_family", 0)),
            dev_vendor=_safe_int(data.get("dev_vendor", 0)),
            os_name=str(data.get("os_name", "")),
            dev_id_override=_safe_int(data.get("dev_id_override", 0)),
            fingerprint_source=_safe_int(data.get("fingerprint_source", 0)),
            raw=data,
        )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@dataclass
class HealthSubsystem:
    """A subsystem from stat/health (wan, www, wlan, lan, vpn)."""

    subsystem: str = ""
    status: str = ""

    # WAN-specific
    wan_ip: str = ""
    isp_name: str = ""
    isp_organization: str = ""
    latency: float = 0.0
    uptime: float = 0.0
    drops: int = 0
    xput_down: float = 0.0
    xput_up: float = 0.0
    speedtest_lastrun: int = 0
    speedtest_ping: float = 0.0

    # Counts
    num_user: int = 0
    num_guest: int = 0
    num_iot: int = 0
    num_adopted: int = 0
    num_pending: int = 0
    num_disconnected: int = 0
    num_ap: int = 0
    num_sw: int = 0

    # Throughput
    rx_bytes_r: float = 0.0
    tx_bytes_r: float = 0.0

    # VPN-specific
    remote_user_num_active: int = 0
    remote_user_num_inactive: int = 0
    remote_user_rx_bytes: int = 0
    remote_user_tx_bytes: int = 0
    site_to_site_num_active: int = 0
    site_to_site_num_inactive: int = 0

    # Gateway system stats (embedded in wan subsystem)
    gw_cpu: float = 0.0
    gw_mem: float = 0.0
    gw_uptime: int = 0
    gw_version: str = ""
    gw_name: str = ""

    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Create a ``HealthSubsystem`` from a raw API dict.

        Handles ``gw_system-stats`` (note the hyphen).
        """
        # gw_system-stats is a nested dict with "cpu" and "mem".
        gw_sys: dict = data.get("gw_system-stats", data.get("gw_system_stats", {})) or {}

        return cls(
            subsystem=str(data.get("subsystem", "")),
            status=str(data.get("status", "")),
            wan_ip=str(data.get("wan_ip", "")),
            isp_name=str(data.get("isp_name", "")),
            isp_organization=str(data.get("isp_organization", "")),
            latency=_safe_float(data.get("latency", 0.0)),
            uptime=_safe_float(data.get("uptime", 0.0)),
            drops=_safe_int(data.get("drops", 0)),
            xput_down=_safe_float(data.get("xput_down", 0.0)),
            xput_up=_safe_float(data.get("xput_up", 0.0)),
            speedtest_lastrun=_safe_int(data.get("speedtest_lastrun", 0)),
            speedtest_ping=_safe_float(data.get("speedtest_ping", 0.0)),
            num_user=_safe_int(data.get("num_user", 0)),
            num_guest=_safe_int(data.get("num_guest", 0)),
            num_iot=_safe_int(data.get("num_iot", 0)),
            num_adopted=_safe_int(data.get("num_adopted", 0)),
            num_pending=_safe_int(data.get("num_pending", 0)),
            num_disconnected=_safe_int(data.get("num_disconnected", 0)),
            num_ap=_safe_int(data.get("num_ap", 0)),
            num_sw=_safe_int(data.get("num_sw", 0)),
            rx_bytes_r=_safe_float(data.get("rx_bytes-r", data.get("rx_bytes_r", 0.0))),
            tx_bytes_r=_safe_float(data.get("tx_bytes-r", data.get("tx_bytes_r", 0.0))),
            remote_user_num_active=_safe_int(data.get("remote_user_num_active", 0)),
            remote_user_num_inactive=_safe_int(data.get("remote_user_num_inactive", 0)),
            remote_user_rx_bytes=_safe_int(data.get("remote_user_rx_bytes", 0)),
            remote_user_tx_bytes=_safe_int(data.get("remote_user_tx_bytes", 0)),
            site_to_site_num_active=_safe_int(data.get("site_to_site_num_active", 0)),
            site_to_site_num_inactive=_safe_int(data.get("site_to_site_num_inactive", 0)),
            gw_cpu=_safe_float(gw_sys.get("cpu", 0.0)),
            gw_mem=_safe_float(gw_sys.get("mem", 0.0)),
            gw_uptime=_safe_int(data.get("gw_uptime", 0)),
            gw_version=str(data.get("gw_version", "")),
            gw_name=str(data.get("gw_name", data.get("gw_mac", ""))),
            raw=data,
        )


# ---------------------------------------------------------------------------
# Alarm
# ---------------------------------------------------------------------------

@dataclass
class Alarm:
    """An alarm/event from stat/alarm."""

    id: str = ""
    key: str = ""
    msg: str = ""
    datetime: str = ""
    timestamp: int = 0
    archived: bool = False

    # IPS-specific
    catname: str = ""
    src_ip: str = ""
    src_port: int = 0
    dest_ip: str = ""
    dest_port: int = 0
    proto: str = ""
    inner_alert_action: str = ""
    inner_alert_severity: int = 0
    inner_alert_signature: str = ""

    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        # IPS alerts nest extra info under "inner_alert_*" keys.
        return cls(
            id=str(data.get("_id", data.get("id", ""))),
            key=str(data.get("key", "")),
            msg=str(data.get("msg", "")),
            datetime=str(data.get("datetime", "")),
            timestamp=_safe_int(data.get("time", data.get("timestamp", 0))),
            archived=_safe_bool(data.get("archived")),
            catname=str(data.get("catname", "")),
            src_ip=str(data.get("src_ip", "")),
            src_port=_safe_int(data.get("src_port", 0)),
            dest_ip=str(data.get("dest_ip", "")),
            dest_port=_safe_int(data.get("dest_port", 0)),
            proto=str(data.get("proto", "")),
            inner_alert_action=str(data.get("inner_alert_action", "")),
            inner_alert_severity=_safe_int(data.get("inner_alert_severity", 0)),
            inner_alert_signature=str(data.get("inner_alert_signature", "")),
            raw=data,
        )


# ---------------------------------------------------------------------------
# DPI
# ---------------------------------------------------------------------------

@dataclass
class DpiCategory:
    """DPI traffic category."""

    cat: int = 0
    app: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            cat=_safe_int(data.get("cat", 0)),
            app=_safe_int(data.get("app", 0)),
            rx_bytes=_safe_int(data.get("rx_bytes", 0)),
            tx_bytes=_safe_int(data.get("tx_bytes", 0)),
            rx_packets=_safe_int(data.get("rx_packets", 0)),
            tx_packets=_safe_int(data.get("tx_packets", 0)),
        )


@dataclass
class DpiData:
    """DPI data from stat/sitedpi."""

    by_cat: list[DpiCategory] = field(default_factory=list)
    by_app: list[DpiCategory] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        by_cat_raw = data.get("by_cat", []) or []
        by_app_raw = data.get("by_app", []) or []
        return cls(
            by_cat=[
                DpiCategory.from_dict(c) for c in by_cat_raw if isinstance(c, dict)
            ],
            by_app=[
                DpiCategory.from_dict(a) for a in by_app_raw if isinstance(a, dict)
            ],
        )


# ---------------------------------------------------------------------------
# WLAN
# ---------------------------------------------------------------------------

@dataclass
class Wlan:
    """WLAN configuration."""

    id: str = ""
    name: str = ""
    enabled: bool = True
    security: str = ""
    wpa_mode: str = ""
    x_passphrase: str = ""
    is_guest: bool = False

    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            id=str(data.get("_id", data.get("id", ""))),
            name=str(data.get("name", "")),
            enabled=_safe_bool(data.get("enabled", True)),
            security=str(data.get("security", "")),
            wpa_mode=str(data.get("wpa_mode", "")),
            x_passphrase=str(data.get("x_passphrase", "")),
            is_guest=_safe_bool(data.get("is_guest")),
            raw=data,
        )


# ---------------------------------------------------------------------------
# Port forward
# ---------------------------------------------------------------------------

@dataclass
class PortForward:
    """Port forward rule."""

    id: str = ""
    name: str = ""
    enabled: bool = True
    dst_port: str = ""
    fwd_ip: str = ""
    fwd_port: str = ""
    proto: str = ""
    src: str = ""

    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            id=str(data.get("_id", data.get("id", ""))),
            name=str(data.get("name", "")),
            enabled=_safe_bool(data.get("enabled", True)),
            dst_port=str(data.get("dst_port", "")),
            fwd_ip=str(data.get("fwd", data.get("fwd_ip", ""))),
            fwd_port=str(data.get("fwd_port", "")),
            proto=str(data.get("proto", "")),
            src=str(data.get("src", "")),
            raw=data,
        )


# ---------------------------------------------------------------------------
# Traffic rule (v2 API)
# ---------------------------------------------------------------------------

@dataclass
class TrafficRule:
    """Traffic rule (v2 API)."""

    id: str = ""
    description: str = ""
    enabled: bool = True
    action: str = ""
    matching_target: str = ""
    target_devices: list[dict] = field(default_factory=list)

    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        target_devices = data.get("target_devices", [])
        if not isinstance(target_devices, list):
            target_devices = []
        return cls(
            id=str(data.get("_id", data.get("id", ""))),
            description=str(data.get("description", "")),
            enabled=_safe_bool(data.get("enabled", True)),
            action=str(data.get("action", "")),
            matching_target=str(data.get("matching_target", "")),
            target_devices=target_devices,
            raw=data,
        )


# ---------------------------------------------------------------------------
# Firewall policy (v2 API)
# ---------------------------------------------------------------------------

@dataclass
class FirewallPolicy:
    """Firewall policy (v2 API)."""

    id: str = ""
    name: str = ""
    enabled: bool = True
    action: str = ""
    source_zone: str = ""
    dest_zone: str = ""
    source_network: str = ""
    dest_network: str = ""
    protocol: str = ""
    index: int = 0

    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        # Extract source/destination context for better naming
        src_zone = str(data.get("source_zone", data.get("src_zone", "")))
        dst_zone = str(data.get("destination_zone", data.get("dst_zone", "")))
        src_net = str(data.get("source_network_id", data.get("source_network", "")))
        dst_net = str(data.get("destination_network_id", data.get("destination_network", "")))
        # Some policies use source/destination firewall groups
        if not src_zone:
            src_zone = str(data.get("source_firewall_group_ids", [""])[0]) if data.get("source_firewall_group_ids") else ""
        if not dst_zone:
            dst_zone = str(data.get("destination_firewall_group_ids", [""])[0]) if data.get("destination_firewall_group_ids") else ""
        protocol = str(data.get("protocol", data.get("protocol_match_type", "")))
        index = _safe_int(data.get("index", data.get("rule_index", 0)))
        return cls(
            id=str(data.get("_id", data.get("id", ""))),
            name=str(data.get("name", data.get("description", ""))),
            enabled=_safe_bool(data.get("enabled", True)),
            action=str(data.get("action", "")),
            source_zone=src_zone,
            dest_zone=dst_zone,
            source_network=src_net,
            dest_network=dst_net,
            protocol=protocol,
            index=index,
            raw=data,
        )

    @property
    def display_name(self) -> str:
        """Build a descriptive name for this policy."""
        parts = []
        if self.name:
            parts.append(self.name)
        # Add zone context if available
        zones = []
        if self.source_zone:
            zones.append(self.source_zone)
        if self.dest_zone:
            zones.append(self.dest_zone)
        if zones:
            parts.append(f"({' → '.join(zones)})")
        elif self.index:
            parts.append(f"(#{self.index})")
        return " ".join(parts) if parts else f"Policy {self.id[:8]}"


# ---------------------------------------------------------------------------
# Cloud / Site Manager
# ---------------------------------------------------------------------------

@dataclass
class CloudHost:
    """A host from the cloud Site Manager API."""

    id: str = ""
    hardware_id: str = ""
    name: str = ""
    type: str = ""
    ip: str = ""
    firmware: str = ""
    is_online: bool = False

    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            id=str(data.get("_id", data.get("id", ""))),
            hardware_id=str(data.get("hardware_id", data.get("hardwareId", ""))),
            name=str(data.get("name", data.get("hostname", ""))),
            type=str(data.get("type", "")),
            ip=str(data.get("ip", data.get("ipAddress", ""))),
            firmware=str(data.get("firmware", data.get("firmwareVersion", ""))),
            is_online=_safe_bool(data.get("is_online", data.get("isOnline"))),
            raw=data,
        )


@dataclass
class CloudIspMetrics:
    """ISP metrics from cloud API."""

    period_start: str = ""
    period_end: str = ""
    wan_name: str = ""
    isp_name: str = ""
    isp_asn: int = 0
    avg_latency: float = 0.0
    max_latency: float = 0.0
    packet_loss: float = 0.0
    download_kbps: float = 0.0
    upload_kbps: float = 0.0
    uptime: float = 0.0
    downtime: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            period_start=str(data.get("period_start", data.get("periodStart", ""))),
            period_end=str(data.get("period_end", data.get("periodEnd", ""))),
            wan_name=str(data.get("wan_name", data.get("wanName", ""))),
            isp_name=str(data.get("isp_name", data.get("ispName", ""))),
            isp_asn=_safe_int(data.get("isp_asn", data.get("ispAsn", 0))),
            avg_latency=_safe_float(data.get("avg_latency", data.get("avgLatency", 0.0))),
            max_latency=_safe_float(data.get("max_latency", data.get("maxLatency", 0.0))),
            packet_loss=_safe_float(data.get("packet_loss", data.get("packetLoss", 0.0))),
            download_kbps=_safe_float(data.get("download_kbps", data.get("downloadKbps", 0.0))),
            upload_kbps=_safe_float(data.get("upload_kbps", data.get("uploadKbps", 0.0))),
            uptime=_safe_float(data.get("uptime", 0.0)),
            downtime=_safe_float(data.get("downtime", 0.0)),
        )


@dataclass
class SdWanConfig:
    """SD-WAN config from cloud API."""

    id: str = ""
    description: str = ""
    status: str = ""

    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            id=str(data.get("_id", data.get("id", ""))),
            description=str(data.get("description", "")),
            status=str(data.get("status", "")),
            raw=data,
        )
