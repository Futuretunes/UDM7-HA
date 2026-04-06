# TODO

## Completed
- [x] ~~Firewall policy naming~~ — resolved via zone API lookup (v0.3.7)
- [x] ~~Device product images~~ — 21 verified CDN UUIDs (v0.4.0)
- [x] ~~Custom Lovelace card~~ — network topology card (v0.4.0)
- [x] ~~UniFi Talk / Access~~ — door locks, device connectivity (v0.4.0)
- [x] ~~Dashboard auto-generation~~ — generate_dashboard service (v0.4.0)
- [x] ~~DHCP pool usage~~ — per-network utilization sensors (v0.4.0)
- [x] ~~Historical traffic graphs~~ — monthly traffic with HA long-term stats (v0.4.0)
- [x] ~~Device hierarchy~~ — via_device for parent-child tree (v0.4.4)

## Open

### High Priority
- [ ] **Custom integration icon** — Design and replace the placeholder UniFi controller icon
- [ ] **HACS search icon** — PR submitted to home-assistant/brands (#10081), awaiting merge

### Medium Priority
- [ ] **More device image UUIDs** — add verified CDN URLs for additional models (USW-Pro-48-PoE, USW-Pro-Max, U7-Pro-Max, U7-Outdoor, UXG-Pro, etc.)
- [ ] **UniFi Talk entities** — currently only device discovery; add intercom call events, phone status sensors
- [ ] **Access event entities** — fire HA events on door unlock/lock/access denied with user info

### Low Priority
- [ ] **Lovelace card enhancements** — add AP/switch topology tier, connection lines, click-to-navigate
- [ ] **Per-client bandwidth history** — track bandwidth over time per client for trend analysis
- [ ] **Guest portal integration** — show captive portal status, active guest sessions as sensors
