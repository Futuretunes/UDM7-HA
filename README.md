# Advanced UniFi Network HA

A comprehensive [Home Assistant](https://www.home-assistant.io/) custom integration for **all UniFi gateways and network devices**. Combines the features of four existing UniFi integrations into one, and adds WAN failover detection, IDS/IPS alerts, VPN monitoring, DPI traffic analysis, and cloud ISP metrics.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/Futuretunes/advanced-unifi-network-ha)](https://github.com/Futuretunes/advanced-unifi-network-ha/releases)

## Why this integration?

| Feature | Official UniFi | Unifi-WAN | ha-unifi-network | Site Manager | **This** |
|---------|:-:|:-:|:-:|:-:|:-:|
| Device tracking | x | | | | x |
| PoE / port control | x | | | | x |
| WAN status & throughput | | x | | | x |
| WAN failover events | | | | | x |
| Speedtest trigger & results | | x | | | x |
| Per-AP radio health | | | x | | x |
| Cloud ISP metrics | | | | x | x |
| IDS/IPS alert events | | | | | x |
| VPN monitoring | | | | | x |
| DPI traffic analysis | | | | | x |
| Firewall / traffic rules | x | | | | x |
| LED control | x | | | | x |
| Firmware updates | x | | x | | x |
| WebSocket real-time | x | | | | x |
| Zero pip dependencies | | | | | x |

## Supported devices

Any UniFi OS gateway running Network Application 7.x+:

- Cloud Gateway Ultra (UCG-Ultra)
- Dream Machine (UDM)
- Dream Machine Pro / SE / Pro Max
- Dream Router (UDR)
- Dream Router 7 (UDR7)
- Enterprise Fortress Gateway (EFG)
- Next-Gen Gateway (UXG-Pro, UXG-Enterprise, UXG-Lite)
- Security Gateway (USG, USG-Pro-4)

All adopted APs and switches are also monitored.

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right and select **Custom repositories**
3. Add `https://github.com/Futuretunes/advanced-unifi-network-ha` with category **Integration**
4. Search for "Advanced UniFi Network HA" and install
5. Restart Home Assistant

### Manual

1. Copy `custom_components/unifi_network_ha/` to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

Add the integration via **Settings > Devices & Services > Add Integration > Advanced UniFi Network HA**.

### Setup steps

1. **Connection** — Enter your UniFi controller's host, port (default: 443), and site name (default: `default`)
2. **Authentication** — Choose one:
   - **API Key** (recommended) — Generate at UniFi Network > Settings > Control Plane > Integrations. Polling only.
   - **Username/Password** — Enables WebSocket for real-time updates in addition to polling.
3. **Cloud API** (optional) — Enter a cloud API key from [unifi.ui.com](https://unifi.ui.com) for ISP metrics and multi-site overview
4. **Site selection** — Pick the site to monitor (auto-discovered)
5. **Features** — Toggle which capabilities to enable

### Authentication methods compared

| | API Key | Username/Password |
|---|---|---|
| Setup | Generate in UniFi UI | Use local admin account |
| WebSocket (real-time) | No (polling only) | Yes |
| Security | Scoped token | Full credentials |
| Recommended for | Most users | Power users wanting real-time |

## Entities

### Sensors (~80+)

<details>
<summary>Gateway system</summary>

| Entity | Unit | Update |
|--------|------|--------|
| CPU Usage | % | 30s |
| Memory Usage | % | 30s |
| Uptime | seconds | 30s |
| Load Average (1/5/15 min) | — | 30s |
| Connected Clients | count | 30s |
| Temperature (per sensor) | C | 30s |
| Storage Usage (per volume) | % | 30s |
| Firmware Version | — | 30s |
| Device State | — | 30s |

</details>

<details>
<summary>WAN (per interface, up to 4)</summary>

| Entity | Unit | Update |
|--------|------|--------|
| IP Address | — | 30s |
| IPv6 Address | — | 30s |
| Download Rate | B/s | **5s** |
| Upload Rate | B/s | **5s** |
| Link Speed | Mbps | 30s |
| Latency | ms | 30s |
| Type (DHCP/PPPoE/Static) | — | 30s |
| Gateway IP | — | 30s |
| Active WAN | — | 30s |
| ISP Name | — | 60s |
| WAN Latency (via health) | ms | 60s |

</details>

<details>
<summary>Speed test</summary>

| Entity | Unit | Update |
|--------|------|--------|
| Download Speed | Mbps | on-demand |
| Upload Speed | Mbps | on-demand |
| Ping | ms | on-demand |
| Last Run | timestamp | on-demand |
| Server | — | on-demand |

</details>

<details>
<summary>Network health</summary>

| Entity | Unit | Source |
|--------|------|--------|
| WLAN Clients / Guests / IoT | count | health |
| WLAN Throughput RX/TX | B/s | health |
| AP Count | count | health |
| LAN Clients / Guests | count | health |
| Switch Count | count | health |
| LAN Throughput RX/TX | B/s | health |

</details>

<details>
<summary>VPN</summary>

| Entity | Unit |
|--------|------|
| Remote Users Active / Inactive | count |
| Site-to-Site Tunnels Active / Inactive | count |

</details>

<details>
<summary>Per-AP radio</summary>

| Entity | Unit |
|--------|------|
| Channel | — |
| Client Count | count |
| Channel Utilization | % |
| TX Retries | count |
| Satisfaction | 0-100 |
| TX Power | dBm |

</details>

<details>
<summary>Per-switch port</summary>

| Entity | Unit |
|--------|------|
| RX Rate | B/s |
| TX Rate | B/s |
| Link Speed | Mbps |
| PoE Power | W |

</details>

<details>
<summary>DPI & Alarms</summary>

| Entity | Unit |
|--------|------|
| Top DPI Category / App | — |
| DPI Total RX / TX | bytes |
| Alarm Count | count |
| Latest Alarm | text |

</details>

<details>
<summary>Cloud ISP metrics (optional)</summary>

| Entity | Unit |
|--------|------|
| ISP Avg / Max Latency | ms |
| ISP Packet Loss | % |
| ISP Download / Upload | kbps |
| ISP Uptime / Downtime | seconds |

</details>

### Binary sensors

| Entity | Device class |
|--------|-------------|
| Internet Connected | connectivity |
| WAN Health | problem |
| Speedtest In Progress | running |
| WAN{N} Link Up | connectivity |
| WAN{N} Internet | connectivity |
| VPN Active | connectivity |

### Device tracker

Every connected client gets a `device_tracker` entity with heartbeat-based presence detection (default 5-minute timeout). Rich attributes include:

- SSID, AP MAC, signal strength, channel, WiFi standard
- Switch MAC, switch port (wired clients)
- IP address, network name, OS

Filter options: track wired/wireless, SSID allowlist.

### Switches

| Switch | Category |
|--------|----------|
| Block/Unblock Client | per-client |
| WLAN Enable/Disable | per-WLAN |
| PoE Port Toggle | per-port |
| Port Enable/Disable | per-port |
| Port Forward Toggle | per-rule |
| Traffic Rule Toggle | per-rule |
| Firewall Policy Toggle | per-policy |
| DPI Restriction Toggle | per-group |

### Buttons

| Button | Scope |
|--------|-------|
| Run Speed Test | gateway / per-WAN |
| Restart Device | per-device |
| Force Provision | gateway |
| Locate Device (LED flash) | per-device |
| Power Cycle PoE Port | per-port |
| Archive All Alarms | gateway |

### Events

| Event entity | Event types | Data |
|-------------|-------------|------|
| WAN Failover | `failover`, `recovery`, `wan_change` | previous_wan, new_wan, timestamp |
| IPS Alert | `ips_alert`, `threat_detected`, `intrusion_attempt` | message, source/dest IP & port, protocol, severity, signature |

Use these in automations:

```yaml
automation:
  - alias: "Notify on WAN failover"
    trigger:
      - platform: state
        entity_id: event.gateway_wan_failover
    action:
      - service: notify.mobile_app
        data:
          title: "WAN Failover"
          message: >
            Switched from {{ trigger.to_state.attributes.previous_wan }}
            to {{ trigger.to_state.attributes.new_wan }}
```

### Other

| Platform | Entities |
|----------|----------|
| **Update** | Firmware install per device |
| **Light** | LED on/off per device |
| **Image** | WiFi QR code per WLAN |

### Services

| Service | Description |
|---------|-------------|
| `unifi_network_ha.reconnect_client` | Force a client to reconnect |
| `unifi_network_ha.remove_clients` | Remove all offline clients |
| `unifi_network_ha.block_client` | Block a client by MAC |
| `unifi_network_ha.unblock_client` | Unblock a client by MAC |

## Architecture

```
UniFi Device --> API Client --> Coordinators --> Entities
                    |               ^
                    +-> WebSocket --+  (real-time merge)
```

### Data update intervals

| Coordinator | Default | Configurable |
|-------------|---------|:---:|
| Devices | 30s | Yes |
| Clients | 30s | Yes |
| Health | 60s | Yes |
| **WAN Rates** | **5s** | Yes |
| Alarms | 120s | Yes |
| DPI | 300s | Yes |
| Cloud | 900s | Yes |

All intervals are adjustable in the integration's options flow.

### API surfaces used

| API | Auth | Use |
|-----|------|-----|
| Legacy v1 (`/api/s/{site}/...`) | API key or cookie | Devices, clients, health, commands, config |
| V2 (`/v2/api/site/{site}/...`) | API key or cookie | Traffic rules, firewall policies |
| Integration v1 (`/integration/v1/...`) | API key | Device statistics, site discovery |
| Cloud (`api.ui.com`) | Cloud API key | ISP metrics, SD-WAN |
| WebSocket (`wss://`) | Cookie (credentials auth only) | Real-time device/client/event updates |

### Zero dependencies

This integration uses only `aiohttp`, which is bundled with Home Assistant. No additional Python packages are installed. This avoids version conflicts and keeps the installation lightweight.

## Coexistence

This integration uses a separate domain (`unifi_network_ha`) and unique ID namespace. It can run **side-by-side** with the official Home Assistant UniFi integration without conflicts.

## Options

After setup, configure via **Settings > Devices & Services > Advanced UniFi Network HA > Configure**:

- **Features** — Enable/disable device tracking, WAN monitoring, DPI, alarms, VPN
- **Update intervals** — Adjust polling frequency for each coordinator (5s to 3600s)
- **Client tracking** — Filter by wired/wireless, SSID allowlist, heartbeat timeout

## Troubleshooting

### Common issues

**"Cannot connect" during setup**
- Verify the host IP and port (default 443) are correct
- Ensure the UniFi controller is reachable from Home Assistant
- Check that SSL verification matches your setup (usually off for self-signed certs)

**"Invalid auth" during setup**
- For API key: regenerate at UniFi Network > Settings > Control Plane > Integrations
- For credentials: use a local admin account (not a UI.com SSO account)

**No gateway found**
- The integration auto-detects the gateway device. Ensure at least one gateway is adopted in the selected site.

**WebSocket not connecting**
- WebSocket requires username/password auth. API key auth uses polling only.
- Check HA logs for WebSocket-related warnings.

### Diagnostics

Go to **Settings > Devices & Services > Advanced UniFi Network HA > three dots > Download diagnostics** for a redacted snapshot of your integration state.

### Logs

Enable debug logging:

```yaml
logger:
  logs:
    custom_components.unifi_network_ha: debug
```

## Contributing

Contributions are welcome! Please open an issue or pull request on [GitHub](https://github.com/Futuretunes/advanced-unifi-network-ha).

## License

MIT
