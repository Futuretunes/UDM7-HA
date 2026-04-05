# TODO

## High Priority

- [ ] **Firewall policy naming** — Check `raw_keys` attribute on firewall policy switches to find proper source/destination zone field names from the v2 API, then use them for descriptive names like "Allow All Traffic (LAN In → WAN Out)" instead of numbered duplicates
- [ ] **Custom integration icon** — Design and replace the placeholder UniFi controller icon with a custom gear-styled icon

## Medium Priority

- [ ] **Device product images** — Verify images display correctly after cache clear; add more verified CDN UUIDs for additional device models
- [ ] **Custom Lovelace card** — Build a JavaScript-based custom card for network topology visualization (devices, clients, uplinks, signal quality)
- [ ] **UniFi Talk / Access** — Expose door lock, intercom status for UniFi Access/Talk devices on the network

## Low Priority

- [ ] **Dashboard template auto-generation** — Generate dashboard YAML with actual entity IDs from the user's setup instead of generic placeholders
- [ ] **Historical traffic graphs** — Integrate with HA long-term statistics for bandwidth trend visualization
- [ ] **DHCP pool usage** — Expose DHCP pool utilization per network/VLAN
