/**
 * UniFi Network Topology Card
 *
 * A custom Lovelace card for the unifi_network_ha integration.
 * Visualises the network topology: gateway -> switches/APs -> clients,
 * with connection lines, signal quality indicators, and live stats.
 *
 * @version 0.1.0
 */

const CARD_VERSION = '0.1.0';

/* ───────────────────────── helpers ──────────────────────── */

function formatBytes(bytesPerSec) {
  if (bytesPerSec == null || bytesPerSec === 'unknown' || bytesPerSec === 'unavailable') return '\u2014';
  const b = parseFloat(bytesPerSec);
  if (isNaN(b)) return '\u2014';
  if (b >= 1e9) return `${(b / 1e9).toFixed(1)} GB/s`;
  if (b >= 1e6) return `${(b / 1e6).toFixed(1)} MB/s`;
  if (b >= 1e3) return `${(b / 1e3).toFixed(0)} KB/s`;
  return `${b.toFixed(0)} B/s`;
}

function formatRate(mbps) {
  if (mbps == null || mbps === 'unknown' || mbps === 'unavailable') return '\u2014';
  const v = parseFloat(mbps);
  if (isNaN(v)) return '\u2014';
  if (v >= 1000) return `${(v / 1000).toFixed(1)} Gbps`;
  return `${v.toFixed(0)} Mbps`;
}

function signalColor(dbm) {
  if (dbm == null) return 'var(--secondary-text-color)';
  const s = parseInt(dbm, 10);
  if (isNaN(s)) return 'var(--secondary-text-color)';
  if (s > -50) return '#4CAF50';
  if (s > -60) return '#8BC34A';
  if (s > -70) return '#FFC107';
  if (s > -80) return '#FF9800';
  return '#F44336';
}

function signalLabel(dbm) {
  if (dbm == null) return '';
  const s = parseInt(dbm, 10);
  if (isNaN(s)) return '';
  if (s > -50) return 'Excellent';
  if (s > -60) return 'Good';
  if (s > -70) return 'Fair';
  if (s > -80) return 'Weak';
  return 'Poor';
}

function stateVal(hass, entityId) {
  const e = hass.states[entityId];
  if (!e) return null;
  const v = e.state;
  if (v === 'unknown' || v === 'unavailable') return null;
  return v;
}

function entityAttr(hass, entityId, attr) {
  const e = hass.states[entityId];
  if (!e || !e.attributes) return null;
  return e.attributes[attr] ?? null;
}

function deviceIcon(client) {
  const name = (client.name || '').toLowerCase();
  const os = (client.os || '').toLowerCase();
  if (os.includes('ios') || name.includes('iphone') || name.includes('ipad')) return 'mdi:cellphone';
  if (os.includes('android') || name.includes('android') || name.includes('pixel')) return 'mdi:cellphone';
  if (os.includes('mac') || name.includes('macbook') || name.includes('imac')) return 'mdi:laptop';
  if (os.includes('windows') || name.includes('desktop') || name.includes('pc')) return 'mdi:desktop-tower-monitor';
  if (name.includes('tv') || name.includes('apple tv') || name.includes('chromecast') || name.includes('roku') || name.includes('shield')) return 'mdi:television';
  if (name.includes('printer') || name.includes('print')) return 'mdi:printer';
  if (name.includes('camera') || name.includes('doorbell') || name.includes('protect')) return 'mdi:cctv';
  if (name.includes('switch') || name.includes('hub') || name.includes('plug') || name.includes('sonoff')) return 'mdi:power-socket-us';
  if (name.includes('speaker') || name.includes('homepod') || name.includes('echo') || name.includes('sonos')) return 'mdi:speaker';
  if (name.includes('thermostat') || name.includes('nest') || name.includes('ecobee')) return 'mdi:thermostat';
  if (name.includes('light') || name.includes('hue') || name.includes('bulb')) return 'mdi:lightbulb';
  if (name.includes('game') || name.includes('playstation') || name.includes('xbox') || name.includes('nintendo')) return 'mdi:gamepad-variant';
  if (name.includes('watch')) return 'mdi:watch-variant';
  if (name.includes('tablet') || name.includes('ipad')) return 'mdi:tablet';
  if (client.wired) return 'mdi:desktop-classic';
  return 'mdi:devices';
}


/* ───────────────────── card definition ──────────────────── */

class UniFiNetworkCard extends HTMLElement {

  static getConfigElement() {
    return document.createElement('hui-generic-entity-row');
  }

  static getStubConfig() {
    return {
      show_clients: true,
      show_signal: true,
      show_infrastructure: true,
      max_clients: 30,
      client_sort: 'name',
    };
  }

  setConfig(config) {
    this._config = {
      show_clients: true,
      show_signal: true,
      show_infrastructure: true,
      max_clients: 30,
      client_sort: 'name',        // name | signal | traffic
      show_offline: false,
      ...config,
    };
  }

  set hass(hass) {
    const prev = this._hass;
    this._hass = hass;

    // Throttle re-renders to once per second
    const now = Date.now();
    if (this._lastRender && now - this._lastRender < 1000) {
      if (!this._pendingRender) {
        this._pendingRender = setTimeout(() => {
          this._pendingRender = null;
          this._render();
        }, 1000 - (now - this._lastRender));
      }
      return;
    }
    this._render();
  }

  connectedCallback() {
    if (this._hass) this._render();
  }

  /* ─────────────── entity discovery ─────────────── */

  /**
   * Discover all entities belonging to this integration by matching the HA
   * device registry. We rely on entity_id naming patterns that the integration
   * creates:
   *   sensor.<device_slug>_cpu_usage          -> gateway marker
   *   sensor.<device_slug>_connected_clients   -> gateway marker
   *   binary_sensor.<device_slug>_internet_connected
   *   sensor.<device_slug>_wan1_download_rate
   *   device_tracker.<client_slug>_tracker
   *
   * Users can also specify a `gateway` entity in config to pin discovery.
   */
  _discoverGateway() {
    const h = this._hass;
    if (!h) return null;

    // If user configured an explicit gateway entity, extract the device prefix
    if (this._config.gateway) {
      const parts = this._config.gateway.split('.');
      if (parts.length === 2) {
        const id = parts[1];
        // Strip common suffixes to get device slug
        const slug = id
          .replace(/_cpu_usage$/, '')
          .replace(/_connected_clients$/, '')
          .replace(/_memory_usage$/, '')
          .replace(/_uptime$/, '');
        return this._buildGatewayInfo(slug);
      }
    }

    // Auto-discover: find sensor.*_cpu_usage where a matching *_connected_clients exists
    for (const entityId of Object.keys(h.states)) {
      if (!entityId.startsWith('sensor.')) continue;
      if (!entityId.endsWith('_cpu_usage')) continue;

      const slug = entityId.replace('sensor.', '').replace('_cpu_usage', '');

      // Confirm this is a gateway (not just any device with CPU) by checking
      // for connected_clients or internet_connected
      const clientsEntity = `sensor.${slug}_connected_clients`;
      const internetEntity = `binary_sensor.${slug}_internet_connected`;
      if (h.states[clientsEntity] || h.states[internetEntity]) {
        return this._buildGatewayInfo(slug);
      }
    }
    return null;
  }

  _buildGatewayInfo(slug) {
    const h = this._hass;
    const val = (suffix) => stateVal(h, `sensor.${slug}_${suffix}`);
    const attr = (suffix, a) => entityAttr(h, `sensor.${slug}_${suffix}`, a);

    // Get friendly name from entity
    const cpuEntity = h.states[`sensor.${slug}_cpu_usage`];
    const clientsEntity = h.states[`sensor.${slug}_connected_clients`];
    let name = slug.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    if (cpuEntity && cpuEntity.attributes.friendly_name) {
      name = cpuEntity.attributes.friendly_name.replace(/ CPU usage$/, '');
    }

    return {
      slug,
      name,
      cpu: val('cpu_usage'),
      memory: val('memory_usage'),
      uptime: val('uptime'),
      clients: val('connected_clients'),
      firmware: val('firmware_version'),
      wanDownload: val('wan1_download_rate'),
      wanUpload: val('wan1_upload_rate'),
      activeWan: val('active_wan'),
      wifiExperience: val('wifi_experience'),
      wlanClients: val('wlan_clients'),
      lanClients: val('lan_clients'),
      apCount: val('ap_count'),
      switchCount: val('switch_count'),
      wan1Ip: val('wan1_ip'),
      wan1Latency: val('wan1_latency'),
      internet: stateVal(h, `binary_sensor.${slug}_internet_connected`),
      speedtestDown: val('speedtest_download'),
      speedtestUp: val('speedtest_upload'),
      speedtestPing: val('speedtest_ping'),
      ispName: val('isp_name'),
    };
  }

  _discoverInfraDevices() {
    const h = this._hass;
    if (!h) return { aps: [], switches: [] };

    const aps = [];
    const switches = [];
    const seen = new Set();

    // Find APs by looking for radio sensor patterns:
    // sensor.<slug>_radio_ng_channel (2.4 GHz) or sensor.<slug>_radio_na_channel (5 GHz)
    for (const entityId of Object.keys(h.states)) {
      if (!entityId.startsWith('sensor.')) continue;

      // AP detection: radio channel sensors
      const radioMatch = entityId.match(/^sensor\.(.+)_radio_(ng|na|6e)_channel$/);
      if (radioMatch) {
        const slug = radioMatch[1];
        if (seen.has(`ap_${slug}`)) continue;
        seen.add(`ap_${slug}`);

        const friendlyEntity = h.states[entityId];
        let apName = slug.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        if (friendlyEntity && friendlyEntity.attributes.friendly_name) {
          apName = friendlyEntity.attributes.friendly_name.replace(/ (2\.4 GHz|5 GHz|6 GHz) channel$/, '');
        }

        const ap = { slug, name: apName, radios: [] };

        // Gather radio info
        for (const band of ['ng', 'na', '6e']) {
          const chEntity = `sensor.${slug}_radio_${band}_channel`;
          const clEntity = `sensor.${slug}_radio_${band}_clients`;
          const satEntity = `sensor.${slug}_radio_${band}_satisfaction`;
          const cuEntity = `sensor.${slug}_radio_${band}_channel_utilization`;

          const ch = stateVal(h, chEntity);
          if (ch != null) {
            const bandLabel = band === 'ng' ? '2.4 GHz' : band === 'na' ? '5 GHz' : '6 GHz';
            ap.radios.push({
              band: bandLabel,
              channel: ch,
              clients: stateVal(h, clEntity),
              satisfaction: stateVal(h, satEntity),
              utilization: stateVal(h, cuEntity),
            });
          }
        }

        aps.push(ap);
        continue;
      }

      // Switch detection: port sensors
      const portMatch = entityId.match(/^sensor\.(.+)_port_1_rx_rate$/);
      if (portMatch) {
        const slug = portMatch[1];
        if (seen.has(`sw_${slug}`)) continue;
        seen.add(`sw_${slug}`);

        const friendlyEntity = h.states[entityId];
        let swName = slug.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        if (friendlyEntity && friendlyEntity.attributes.friendly_name) {
          swName = friendlyEntity.attributes.friendly_name.replace(/ Port 1 RX rate$/, '');
        }

        // Count ports by scanning for port_N_rx_rate
        let portCount = 0;
        let poeTotal = null;
        for (let i = 1; i <= 52; i++) {
          if (h.states[`sensor.${slug}_port_${i}_rx_rate`]) {
            portCount = i;
          }
        }

        // Look for PoE power used sensor
        const poeEntity = Object.keys(h.states).find(
          eid => eid.startsWith(`sensor.${slug}`) && eid.endsWith('_poe_power_used')
        );
        if (poeEntity) {
          poeTotal = stateVal(h, poeEntity);
        }

        switches.push({
          slug,
          name: swName,
          portCount,
          poePower: poeTotal,
        });
        continue;
      }
    }

    return { aps, switches };
  }

  _discoverClients() {
    const h = this._hass;
    if (!h) return [];

    const clients = [];
    for (const [entityId, state] of Object.entries(h.states)) {
      if (!entityId.startsWith('device_tracker.')) continue;
      if (!entityId.endsWith('_tracker')) continue;

      const attrs = state.attributes || {};
      // Filter: must have source_type router (our integration sets this)
      // and must have either wired or ssid attribute
      if (attrs.source_type !== 'router') continue;
      if (attrs.wired === undefined && !attrs.ssid) continue;

      const isHome = state.state === 'home';
      if (!isHome && !this._config.show_offline) continue;

      clients.push({
        entityId,
        name: attrs.friendly_name || entityId,
        state: state.state,
        connected: isHome,
        ip: attrs.ip || '',
        wired: attrs.wired || false,
        ssid: attrs.ssid || '',
        signal: attrs.signal || null,
        rssi: attrs.rssi || null,
        ap_mac: attrs.ap_mac || '',
        switch_mac: attrs.switch_mac || '',
        channel: attrs.channel || null,
        radio: attrs.radio || '',
        os: attrs.os || '',
        network: attrs.network || '',
        vlan: attrs.vlan || null,
        satisfaction: attrs.satisfaction || null,
        rx_bytes_r: attrs.rx_bytes_r || 0,
        tx_bytes_r: attrs.tx_bytes_r || 0,
        device_category: attrs.device_category || null,
        device_vendor: attrs.device_vendor || '',
        guest: attrs.guest || false,
        blocked: attrs.blocked || false,
      });
    }

    // Sort
    const sort = this._config.client_sort || 'name';
    clients.sort((a, b) => {
      // Connected first
      if (a.connected !== b.connected) return a.connected ? -1 : 1;

      if (sort === 'signal') {
        // Better signal (less negative) first; wired at top
        const sa = a.wired ? 0 : (a.signal || -999);
        const sb = b.wired ? 0 : (b.signal || -999);
        return sb - sa;
      }
      if (sort === 'traffic') {
        return (b.rx_bytes_r + b.tx_bytes_r) - (a.rx_bytes_r + a.tx_bytes_r);
      }
      // Default: name
      return (a.name || '').localeCompare(b.name || '');
    });

    return clients;
  }

  /* ─────────────── rendering ─────────────── */

  _render() {
    if (!this._hass) return;
    this._lastRender = Date.now();

    if (!this.shadowRoot) {
      this.attachShadow({ mode: 'open' });
    }

    const gateway = this._discoverGateway();
    const infra = this._config.show_infrastructure ? this._discoverInfraDevices() : { aps: [], switches: [] };
    const clients = this._config.show_clients !== false ? this._discoverClients() : [];
    const connectedClients = clients.filter(c => c.connected);
    const wiredClients = connectedClients.filter(c => c.wired);
    const wirelessClients = connectedClients.filter(c => !c.wired);
    const maxClients = this._config.max_clients || 30;
    const shownClients = connectedClients.slice(0, maxClients);

    this.shadowRoot.innerHTML = `
      <ha-card>
        ${this._renderStyles()}
        <div class="card-content">
          ${gateway ? this._renderGateway(gateway) : this._renderNoGateway()}
          ${infra.aps.length || infra.switches.length ? this._renderInfrastructure(infra) : ''}
          ${this._config.show_clients !== false ? this._renderClients(shownClients, connectedClients, wiredClients, wirelessClients, maxClients) : ''}
        </div>
      </ha-card>
    `;
  }

  _renderStyles() {
    return `<style>
      :host { display: block; }
      .card-content { padding: 16px; }

      /* ── Gateway ── */
      .gateway {
        background: var(--primary-color);
        color: var(--text-primary-color, #fff);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        position: relative;
        overflow: hidden;
      }
      .gateway::before {
        content: '';
        position: absolute;
        top: 0; right: 0; bottom: 0; left: 0;
        background: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, transparent 60%);
        pointer-events: none;
      }
      .gw-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
        position: relative;
      }
      .gw-header ha-icon {
        --mdc-icon-size: 28px;
        opacity: 0.9;
      }
      .gw-name {
        font-size: 1.15em;
        font-weight: 600;
        flex: 1;
      }
      .gw-internet {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        flex-shrink: 0;
      }
      .gw-internet.up { background: #4CAF50; box-shadow: 0 0 6px rgba(76,175,80,0.6); }
      .gw-internet.down { background: #F44336; box-shadow: 0 0 6px rgba(244,67,54,0.6); }
      .gw-internet.unknown { background: rgba(255,255,255,0.3); }
      .gw-stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(72px, 1fr));
        gap: 8px;
        position: relative;
      }
      .stat {
        text-align: center;
        background: rgba(255,255,255,0.1);
        border-radius: 8px;
        padding: 8px 4px;
      }
      .stat-value {
        font-size: 1.15em;
        font-weight: 600;
        line-height: 1.2;
      }
      .stat-label {
        font-size: 0.7em;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        opacity: 0.75;
        margin-top: 2px;
      }
      .wan-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(255,255,255,0.1);
        border-radius: 8px;
        padding: 8px 12px;
        margin-top: 10px;
        font-size: 0.85em;
        position: relative;
      }
      .wan-bar .speed {
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 4px;
      }
      .wan-bar .wan-label {
        font-size: 0.8em;
        opacity: 0.8;
        text-align: center;
      }
      .wan-bar .wan-isp {
        font-size: 0.75em;
        opacity: 0.6;
      }

      /* ── Infrastructure ── */
      .infra-section {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 8px;
        margin-bottom: 12px;
      }
      .infra-device {
        border: 1px solid var(--divider-color);
        border-radius: 10px;
        padding: 12px;
        background: var(--card-background-color, var(--ha-card-background, #fff));
        position: relative;
      }
      .infra-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
      }
      .infra-header ha-icon {
        --mdc-icon-size: 22px;
        color: var(--primary-color);
      }
      .infra-name {
        font-weight: 500;
        font-size: 0.9em;
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .infra-detail {
        font-size: 0.8em;
        color: var(--secondary-text-color);
        display: flex;
        flex-wrap: wrap;
        gap: 4px 10px;
      }
      .infra-detail .detail-item {
        display: flex;
        align-items: center;
        gap: 3px;
      }
      .infra-detail ha-icon {
        --mdc-icon-size: 14px;
      }
      .radio-band {
        display: inline-block;
        font-size: 0.7em;
        font-weight: 600;
        padding: 1px 5px;
        border-radius: 4px;
        background: var(--primary-color);
        color: var(--text-primary-color, #fff);
        opacity: 0.85;
      }

      /* ── Clients ── */
      .clients-section {
        border: 1px solid var(--divider-color);
        border-radius: 12px;
        overflow: hidden;
      }
      .clients-header {
        padding: 10px 16px;
        font-weight: 500;
        font-size: 0.9em;
        background: var(--secondary-background-color, rgba(0,0,0,0.03));
        border-bottom: 1px solid var(--divider-color);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .clients-header .client-counts {
        display: flex;
        gap: 12px;
        font-size: 0.85em;
        color: var(--secondary-text-color);
      }
      .clients-header .client-counts span {
        display: flex;
        align-items: center;
        gap: 3px;
      }
      .clients-header .client-counts ha-icon {
        --mdc-icon-size: 14px;
      }
      .client-row {
        display: flex;
        align-items: center;
        padding: 7px 16px;
        border-bottom: 1px solid var(--divider-color);
        font-size: 0.88em;
        gap: 8px;
        transition: background 0.15s;
        cursor: pointer;
      }
      .client-row:last-child { border-bottom: none; }
      .client-row:hover {
        background: var(--secondary-background-color, rgba(0,0,0,0.03));
      }
      .client-row.offline {
        opacity: 0.45;
      }
      .client-icon {
        flex-shrink: 0;
        color: var(--secondary-text-color);
      }
      .client-icon ha-icon {
        --mdc-icon-size: 20px;
      }
      .client-info {
        flex: 1;
        min-width: 0;
      }
      .client-name {
        font-weight: 450;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .client-sub {
        font-size: 0.8em;
        color: var(--secondary-text-color);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .client-signal {
        flex-shrink: 0;
        font-size: 0.78em;
        font-weight: 600;
        padding: 2px 7px;
        border-radius: 10px;
        white-space: nowrap;
      }
      .client-type {
        flex-shrink: 0;
        font-size: 0.78em;
        color: var(--secondary-text-color);
        display: flex;
        align-items: center;
        gap: 3px;
        min-width: 36px;
        justify-content: flex-end;
      }
      .client-type ha-icon {
        --mdc-icon-size: 14px;
      }
      .client-traffic {
        flex-shrink: 0;
        font-size: 0.72em;
        color: var(--secondary-text-color);
        text-align: right;
        min-width: 60px;
      }
      .more-clients {
        text-align: center;
        padding: 8px;
        color: var(--secondary-text-color);
        font-size: 0.85em;
        background: var(--secondary-background-color, rgba(0,0,0,0.02));
      }

      /* ── Connection topology line ── */
      .topology-connector {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 20px;
        margin-bottom: 4px;
      }
      .topology-line {
        width: 2px;
        height: 100%;
        background: var(--divider-color);
      }

      /* ── No gateway ── */
      .no-gateway {
        text-align: center;
        padding: 32px 16px;
        color: var(--secondary-text-color);
      }
      .no-gateway ha-icon {
        --mdc-icon-size: 48px;
        opacity: 0.4;
        display: block;
        margin: 0 auto 12px;
      }
      .no-gateway .title {
        font-size: 1.1em;
        font-weight: 500;
        margin-bottom: 4px;
        color: var(--primary-text-color);
      }

      /* ── Badge ── */
      .badge {
        display: inline-block;
        font-size: 0.7em;
        font-weight: 600;
        padding: 1px 6px;
        border-radius: 8px;
        margin-left: 4px;
      }
      .badge-guest {
        background: rgba(255,152,0,0.15);
        color: #FF9800;
      }
      .badge-blocked {
        background: rgba(244,67,54,0.15);
        color: #F44336;
      }
    </style>`;
  }

  _renderNoGateway() {
    return `
      <div class="no-gateway">
        <ha-icon icon="mdi:router-wireless-off"></ha-icon>
        <div class="title">UniFi Network</div>
        <div>No gateway found. Make sure the UniFi Network Advanced integration is configured.</div>
      </div>
    `;
  }

  _renderGateway(gw) {
    const internetClass = gw.internet === 'on' ? 'up' : gw.internet === 'off' ? 'down' : 'unknown';
    const internetTooltip = gw.internet === 'on' ? 'Internet connected' : gw.internet === 'off' ? 'Internet disconnected' : 'Unknown';

    return `
      <div class="gateway">
        <div class="gw-header">
          <ha-icon icon="mdi:router-network"></ha-icon>
          <span class="gw-name">${gw.name}</span>
          <span class="gw-internet ${internetClass}" title="${internetTooltip}"></span>
        </div>
        <div class="gw-stats">
          <div class="stat">
            <div class="stat-value">${gw.cpu != null ? `${parseFloat(gw.cpu).toFixed(0)}%` : '\u2014'}</div>
            <div class="stat-label">CPU</div>
          </div>
          <div class="stat">
            <div class="stat-value">${gw.memory != null ? `${parseFloat(gw.memory).toFixed(0)}%` : '\u2014'}</div>
            <div class="stat-label">Memory</div>
          </div>
          <div class="stat">
            <div class="stat-value">${gw.clients ?? '\u2014'}</div>
            <div class="stat-label">Clients</div>
          </div>
          <div class="stat">
            <div class="stat-value">${gw.wifiExperience != null ? `${parseFloat(gw.wifiExperience).toFixed(0)}%` : '\u2014'}</div>
            <div class="stat-label">WiFi</div>
          </div>
          ${gw.wan1Latency != null ? `
          <div class="stat">
            <div class="stat-value">${parseFloat(gw.wan1Latency).toFixed(0)}ms</div>
            <div class="stat-label">Latency</div>
          </div>` : ''}
        </div>
        <div class="wan-bar">
          <span class="speed">
            <ha-icon icon="mdi:arrow-down-bold" style="--mdc-icon-size:16px"></ha-icon>
            ${formatBytes(gw.wanDownload)}
          </span>
          <span class="wan-label">
            ${gw.activeWan || 'WAN'}
            ${gw.ispName ? `<br><span class="wan-isp">${gw.ispName}</span>` : ''}
          </span>
          <span class="speed">
            ${formatBytes(gw.wanUpload)}
            <ha-icon icon="mdi:arrow-up-bold" style="--mdc-icon-size:16px"></ha-icon>
          </span>
        </div>
      </div>
    `;
  }

  _renderInfrastructure(infra) {
    if (!infra.aps.length && !infra.switches.length) return '';

    let html = '<div class="topology-connector"><div class="topology-line"></div></div>';
    html += '<div class="infra-section">';

    for (const ap of infra.aps) {
      const totalClients = ap.radios.reduce((s, r) => s + (parseInt(r.clients, 10) || 0), 0);
      const avgSatisfaction = ap.radios.length
        ? Math.round(ap.radios.reduce((s, r) => s + (parseInt(r.satisfaction, 10) || 0), 0) / ap.radios.length)
        : null;

      html += `
        <div class="infra-device">
          <div class="infra-header">
            <ha-icon icon="mdi:access-point"></ha-icon>
            <span class="infra-name" title="${ap.name}">${ap.name}</span>
          </div>
          <div class="infra-detail">
            <span class="detail-item">
              <ha-icon icon="mdi:account-multiple"></ha-icon>
              ${totalClients} clients
            </span>
            ${avgSatisfaction != null ? `
            <span class="detail-item">
              <ha-icon icon="mdi:emoticon-happy-outline"></ha-icon>
              ${avgSatisfaction}%
            </span>` : ''}
          </div>
          <div class="infra-detail" style="margin-top:4px">
            ${ap.radios.map(r => `
              <span class="detail-item">
                <span class="radio-band">${r.band}</span>
                Ch ${r.channel}
                ${r.utilization != null ? `(${r.utilization}%)` : ''}
              </span>
            `).join('')}
          </div>
        </div>
      `;
    }

    for (const sw of infra.switches) {
      html += `
        <div class="infra-device">
          <div class="infra-header">
            <ha-icon icon="mdi:switch"></ha-icon>
            <span class="infra-name" title="${sw.name}">${sw.name}</span>
          </div>
          <div class="infra-detail">
            <span class="detail-item">
              <ha-icon icon="mdi:ethernet"></ha-icon>
              ${sw.portCount} ports
            </span>
            ${sw.poePower != null ? `
            <span class="detail-item">
              <ha-icon icon="mdi:flash"></ha-icon>
              ${parseFloat(sw.poePower).toFixed(1)}W PoE
            </span>` : ''}
          </div>
        </div>
      `;
    }

    html += '</div>';
    return html;
  }

  _renderClients(shownClients, allConnected, wired, wireless, maxClients) {
    let html = '';

    if (this._config.show_infrastructure) {
      html += '<div class="topology-connector"><div class="topology-line"></div></div>';
    }

    html += `
      <div class="clients-section">
        <div class="clients-header">
          <span>Clients</span>
          <span class="client-counts">
            <span>
              <ha-icon icon="mdi:wifi"></ha-icon>
              ${wireless.length}
            </span>
            <span>
              <ha-icon icon="mdi:ethernet"></ha-icon>
              ${wired.length}
            </span>
          </span>
        </div>
    `;

    for (const c of shownClients) {
      const icon = deviceIcon(c);
      const sub = [c.ip, c.network].filter(Boolean).join(' \u00b7 ');
      const hasTraffic = c.rx_bytes_r > 0 || c.tx_bytes_r > 0;
      const rowClass = c.connected ? '' : ' offline';

      html += `
        <div class="client-row${rowClass}">
          <span class="client-icon"><ha-icon icon="${icon}"></ha-icon></span>
          <span class="client-info">
            <span class="client-name">
              ${c.name}
              ${c.guest ? '<span class="badge badge-guest">Guest</span>' : ''}
              ${c.blocked ? '<span class="badge badge-blocked">Blocked</span>' : ''}
            </span>
            ${sub ? `<span class="client-sub">${sub}</span>` : ''}
          </span>
      `;

      // Signal indicator for wireless clients
      if (!c.wired && c.signal && this._config.show_signal !== false) {
        const color = signalColor(c.signal);
        html += `
          <span class="client-signal" style="color:${color};background:${color}18">
            ${c.signal} dBm
          </span>
        `;
      }

      // Traffic
      if (hasTraffic) {
        html += `
          <span class="client-traffic">
            <ha-icon icon="mdi:arrow-down" style="--mdc-icon-size:10px"></ha-icon>${formatBytes(c.rx_bytes_r)}<br>
            <ha-icon icon="mdi:arrow-up" style="--mdc-icon-size:10px"></ha-icon>${formatBytes(c.tx_bytes_r)}
          </span>
        `;
      }

      // Connection type
      html += `
          <span class="client-type">
            <ha-icon icon="${c.wired ? 'mdi:ethernet' : 'mdi:wifi'}"></ha-icon>
            ${c.wired ? '' : (c.ssid || '')}
          </span>
        </div>
      `;
    }

    if (allConnected.length > maxClients) {
      html += `<div class="more-clients">+ ${allConnected.length - maxClients} more clients</div>`;
    }

    if (shownClients.length === 0) {
      html += '<div class="more-clients">No connected clients</div>';
    }

    html += '</div>';
    return html;
  }

  getCardSize() {
    return 6;
  }
}

/* ───────────────── registration ──────────────────── */

customElements.define('unifi-network-card', UniFiNetworkCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'unifi-network-card',
  name: 'UniFi Network Topology',
  description: 'Network topology overview for UniFi Network Advanced',
  preview: true,
  documentationURL: 'https://github.com/Futuretunes/advanced-unifi-network-ha',
});

console.info(
  `%c UniFi Network Card %c v${CARD_VERSION} `,
  'background:#0559C9;color:#fff;font-weight:700;padding:2px 6px;border-radius:4px 0 0 4px',
  'background:#333;color:#fff;font-weight:400;padding:2px 6px;border-radius:0 4px 4px 0',
);
