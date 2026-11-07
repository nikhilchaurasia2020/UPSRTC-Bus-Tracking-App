import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import urllib.parse

st.set_page_config(
    page_title="UPSRTC Live Navigation Tracker",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; max-width: 100%; }
    header { visibility: hidden; }
    footer { visibility: hidden; }
    div[data-testid="stExpander"] { border-radius: 10px; margin-top: 0.75rem; }
</style>
""", unsafe_allow_html=True)

# --- 1. LOCAL STORAGE & SEARCH HISTORY ---
if "recent_buses" not in st.session_state:
    st.session_state["recent_buses"] = []

url_params = st.query_params
url_bus = url_params.get("bus", "").strip().upper()

# Search Bar, Recent Searches, Refresh Rate & Action Button
col_input, col_recent, col_rate, col_btn = st.columns([3, 2, 1.5, 1.2])

with col_input:
    typed_bus = st.text_input(
        "Bus Number",
        value=url_bus,
        placeholder="Type bus number (e.g. UP32MN9123)",
        label_visibility="collapsed"
    ).strip().upper()

with col_recent:
    history_options = ["🕒 Recent Searches..."] + [b for b in st.session_state["recent_buses"] if b != typed_bus]
    selected_from_history = st.selectbox(
        "Recent Searches",
        options=history_options,
        label_visibility="collapsed"
    )

with col_rate:
    refresh_rate_label = st.selectbox(
        "Auto Refresh",
        options=["1s", "2s", "5s", "10s", "30s", "1m"],
        index=4,  # Default set to 30s
        label_visibility="collapsed",
        help="Telemetry polling frequency (Default: 30 seconds)"
    )

with col_btn:
    track_btn = st.button("🧭 Track Bus", use_container_width=True, type="primary")

# Convert interval label to milliseconds
rate_map = {"1s": 1000, "2s": 2000, "5s": 5000, "10s": 10000, "30s": 30000, "1m": 60000}
poll_interval_ms = rate_map.get(refresh_rate_label, 30000)

# Resolve selected bus
active_bus = typed_bus
if selected_from_history != "🕒 Recent Searches..." and not track_btn:
    active_bus = selected_from_history

# Update search history (preserve last 5 unique entries)
if active_bus:
    if active_bus not in st.session_state["recent_buses"]:
        st.session_state["recent_buses"].insert(0, active_bus)
        st.session_state["recent_buses"] = st.session_state["recent_buses"][:5]
    st.query_params["bus"] = active_bus


# --- 2. SERVER FETCH (BYPASSES CORS) ---
API_URL = "https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://margdarshi.upsrtcvlt.com/",
    "Origin": "https://margdarshi.upsrtcvlt.com",
    "Accept": "application/json, text/plain, */*"
}

def fetch_telemetry_packet(bus_no):
    if not bus_no:
        return None
    try:
        res = requests.post(
            API_URL,
            headers=HEADERS,
            data={"regNo": bus_no},
            timeout=5
        )
        res.raise_for_status()
        raw = res.text.strip()
        data = json.loads(raw)

        if isinstance(data, list):
            for item in data:
                reg = str(item.get("regNum") or item.get("RegNo") or item.get("bus_id", "")).upper()
                if reg == bus_no:
                    return item
            if len(data) > 0 and ("latitude" in data[0] or "regNum" in data[0]):
                return data[0]
            return None
        elif isinstance(data, dict):
            return data
    except Exception as e:
        return {"error": str(e)}


# --- 3. DASHBOARD RENDERER ---
if active_bus:
    initial_packet = fetch_telemetry_packet(active_bus)

    if not initial_packet or "error" in initial_packet:
        st.warning(f"No active telemetry received for **{active_bus}**. The bus might be offline or currently out of network coverage.")
    else:
        lat = float(initial_packet.get("latitude", 26.8467))
        lon = float(initial_packet.get("longitude", 80.9462))
        speed = float(initial_packet.get("speed", 0.0))
        heading = float(initial_packet.get("heading", 0.0))
        status = str(initial_packet.get("vehicle_status", "LIVE")).upper()
        zone = initial_packet.get("zone_name", "Location Unknown")
        depot = initial_packet.get("depot_name", "N/A")
        home_depot_id = initial_packet.get("home_depot", "N/A")
        pkt_time = initial_packet.get("receivedTime", initial_packet.get("timestamp", "N/A"))
        ignition = "ON" if initial_packet.get("ignition") == 1 else "OFF"
        satellites = initial_packet.get("numSatellites", "N/A")

        google_maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        
        formatted_share_text = (
            f"🚌 *UPSRTC BUS UPDATE ({active_bus})*\n"
            f"📍 *Location:* {zone}\n"
            f"⚡ *Speed:* {speed:.1f} km/h  |  *Status:* {status}\n"
            f"🔑 *Ignition:* {ignition}  |  *Depot:* {depot}\n"
            f"🕒 *Packet Time:* {pkt_time}\n"
            f"🗺️ *Live Google Maps:* {google_maps_url}"
        )
        whatsapp_url = f"https://api.whatsapp.com/send?text={urllib.parse.quote(formatted_share_text)}"

        # --- SECTION 1: CLEAN HEADER CARD ---
        with st.container(border=True):
            top_col1, top_col2 = st.columns([3, 1])
            with top_col1:
                st.caption("🟢 ACTIVE VEHICLE")
                st.subheader(f"🚌 {active_bus}")
                st.markdown(f"📍 **Location:** `{zone}`")
            with top_col2:
                st.caption(f"🏢 **Depot:** {depot}")
                st.caption(f"🕒 **Last Packet:** `{pkt_time}`")

            # Metrics Row
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Live Speed", f"{speed:.1f} km/h")
            m2.metric("Status", status)
            m3.metric("Ignition", ignition)
            m4.metric("Heading", f"{heading:.1f}°")
            m5.metric("Satellites", satellites)

        # Quick action buttons row
        btn_c1, btn_c2, btn_c3 = st.columns([1.5, 1.5, 3])
        with btn_c1:
            st.link_button("📲 Share on WhatsApp", whatsapp_url, use_container_width=True, type="primary")
        with btn_c2:
            st.link_button("🗺️ Open Google Maps", google_maps_url, use_container_width=True)
        with btn_c3:
            st.text_input("Copy Share Text", value=formatted_share_text.replace('\n', ' | '), label_visibility="collapsed")

        # --- SECTION 2: COMPACT LIVE NAVIGATION VIEW ---
        st.write("")
        st.subheader("🗺️ Live Navigation View")

        live_map_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <style>
                body, html {{
                    margin: 0; padding: 0; width: 100%; height: 100%;
                    overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                }}
                #map {{
                    width: 100%;
                    height: 420px;
                    border-radius: 8px;
                }}
                @media (max-width: 768px) {{
                    #map {{
                        height: 300px;
                    }}
                    .nav-hud {{
                        padding: 6px 14px !important;
                        gap: 12px !important;
                        font-size: 11px !important;
                    }}
                    .hud-val {{
                        font-size: 15px !important;
                    }}
                }}
                
                .nav-hud {{
                    position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
                    z-index: 1000; background: rgba(15, 23, 42, 0.94); backdrop-filter: blur(8px);
                    color: #fff; padding: 8px 18px; border-radius: 30px;
                    box-shadow: 0 4px 16px rgba(0,0,0,0.4); display: flex; align-items: center;
                    gap: 16px; border: 1px solid rgba(255,255,255,0.18); font-size: 12px;
                }}
                .hud-metric {{ display: flex; flex-direction: column; align-items: center; }}
                .hud-val {{ font-size: 17px; font-weight: 700; color: #4ade80; }}
                .hud-lbl {{ font-size: 9px; text-transform: uppercase; color: #94a3b8; }}
                .pulse-dot {{
                    width: 8px; height: 8px; background: #4ade80; border-radius: 50%;
                    display: inline-block; box-shadow: 0 0 8px #4ade80;
                    animation: pulse 1.6s infinite;
                }}
                @keyframes pulse {{
                    0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.7); }}
                    70% {{ transform: scale(1.15); box-shadow: 0 0 0 6px rgba(74, 222, 128, 0); }}
                    100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(74, 222, 128, 0); }}
                }}
            </style>
        </head>
        <body>
            <div class="nav-hud">
                <div style="display:flex; align-items:center; gap:6px;">
                    <span class="pulse-dot"></span>
                    <span style="font-weight:700;">{active_bus}</span>
                </div>
                <div class="hud-metric">
                    <span class="hud-val" id="hudSpeed">{speed:.1f}</span>
                    <span class="hud-lbl">Speed (km/h)</span>
                </div>
                <div class="hud-metric">
                    <span class="hud-val" id="hudStatus" style="color:#38bdf8; font-size:14px;">{status}</span>
                    <span class="hud-lbl">Status</span>
                </div>
            </div>

            <div id="map"></div>

            <script>
                const BUS_REG = "{active_bus}";
                const POLL_INTERVAL = {poll_interval_ms};

                const map = L.map('map', {{ zoomControl: false }}).setView([{lat}, {lon}], 15);
                
                L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19
                }}).addTo(map);

                L.control.zoom({{ position: 'bottomright' }}).addTo(map);

                function createPointer(heading) {{
                    return L.divIcon({{
                        className: 'bus-pointer',
                        html: `
                            <div style="
                                transform: rotate(${{heading}}deg);
                                width: 36px; height: 36px; background: #2563eb;
                                border: 2.5px solid #ffffff; border-radius: 50%;
                                display: flex; align-items: center; justify-content: center;
                                box-shadow: 0 3px 12px rgba(37,99,235,0.7);
                                transition: transform 0.5s ease-out;
                            ">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                    <polygon points="12 2 19 21 12 17 5 21 12 2"></polygon>
                                </svg>
                            </div>
                        `,
                        iconSize: [36, 36],
                        iconAnchor: [18, 18]
                    }});
                }}

                let marker = L.marker([{lat}, {lon}], {{ icon: createPointer({heading}) }}).addTo(map);
                let trail = L.polyline([[{lat}, {lon}]], {{ color: '#2563eb', weight: 4, opacity: 0.85 }}).addTo(map);

                async function syncTelemetry() {{
                    try {{
                        const body = new URLSearchParams();
                        body.append('regNo', BUS_REG);

                        const res = await fetch('https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                            body: body
                        }});

                        if (!res.ok) return;
                        const data = await res.json();
                        let bus = null;

                        if (Array.isArray(data)) {{
                            bus = data.find(i => (i.regNum || i.RegNo || i.bus_id || '').toUpperCase() === BUS_REG);
                            if (!bus && data.length > 0) bus = data[0];
                        }} else if (typeof data === 'object') {{
                            bus = data;
                        }}

                        if (bus && bus.latitude && bus.longitude) {{
                            const newLat = parseFloat(bus.latitude);
                            const newLng = parseFloat(bus.longitude);
                            const newSpeed = parseFloat(bus.speed || 0).toFixed(1);
                            const newHeading = parseFloat(bus.heading || 0);
                            const newStatus = (bus.vehicle_status || 'LIVE').toUpperCase();

                            document.getElementById('hudSpeed').innerText = newSpeed;
                            document.getElementById('hudStatus').innerText = newStatus;

                            const nextPos = [newLat, newLng];
                            marker.setLatLng(nextPos);
                            marker.setIcon(createPointer(newHeading));
                            trail.addLatLng(nextPos);
                            map.panTo(nextPos, {{ animate: true, duration: 0.8 }});
                        }}
                    }} catch (e) {{
                        console.log("Telemetry ping handled silently:", e);
                    }}
                }}

                setInterval(syncTelemetry, POLL_INTERVAL);
            </script>
        </body>
        </html>
        """
        components.html(live_map_html, height=430, scrolling=False)

        # --- SECTION 3: SENSOR & HARDWARE DIAGNOSTICS ---
        with st.expander("⚙️ View Complete Device Telemetry & Sensor Details", expanded=False):
            d1, d2, d3 = st.columns(3)
            with d1:
                st.markdown("**🛰️ GPS & Coordinates**")
                st.write(f"- **Latitude:** `{initial_packet.get('latitude')}`")
                st.write(f"- **Longitude:** `{initial_packet.get('longitude')}`")
                st.write(f"- **Altitude:** `{initial_packet.get('altitude')} m`")
                st.write(f"- **Heading / Bearing:** `{heading:.1f}°`")
                st.write(f"- **GPS Fix:** `{initial_packet.get('gpsFix')}`")
                st.write(f"- **Distance Recorded:** `{initial_packet.get('distance', 'N/A')} m`")
            with d2:
                st.markdown("**🔋 Electrical & Power Systems**")
                st.write(f"- **Main Input Voltage:** `{initial_packet.get('mainInputVoltage')} V`")
                st.write(f"- **Internal Battery:** `{initial_packet.get('internalBatteryVoltage')} V`")
                st.write(f"- **Main Power Status:** `{'Connected' if initial_packet.get('mainPowerStatus') == 1 else 'Disconnected'}`")
                st.write(f"- **Emergency Status:** `{initial_packet.get('emergencyStatus', 0)}`")
                st.write(f"- **Tamper Alert:** `{initial_packet.get('tamperAlert', 'N/A')}`")
            with d3:
                st.markdown("**🏢 Vehicle & System Metadata**")
                st.write(f"- **Home Depot ID:** `{home_depot_id}`")
                st.write(f"- **Vendor ID:** `{initial_packet.get('vendorId')}`")
                st.write(f"- **Firmware Version:** `{initial_packet.get('firmwareVersion')}`")
                st.write(f"- **System Code:** `{initial_packet.get('systemCodeNumber')}`")
                st.write(f"- **Frame Number:** `{initial_packet.get('frameNumber')}`")
                st.write(f"- **Packet Type:** `{packetType}`" if (packetType := initial_packet.get('packetType')) else "- **Packet Type:** `N/A`")

else:
    st.info("Enter any UPSRTC bus registration number above (or pick from your recent searches) to start navigation.")
