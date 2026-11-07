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

# --- 1. NETWORK CONSTANTS & APIS ---
BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://margdarshi.upsrtcvlt.com/",
    "Origin": "https://margdarshi.upsrtcvlt.com",
    "Accept": "application/json, text/plain, */*"
}

API_LIVE_URL = "https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php"
API_SEARCH_URL = "https://margdarshi.upsrtcvlt.com/php/getRegNum.php"

@st.cache_data(ttl=60, show_spinner=False)
def search_bus_registry(query_str):
    if not query_str or len(query_str) < 3:
        return []
    try:
        res = requests.get(
            API_SEARCH_URL,
            params={"query": query_str.strip().upper()},
            headers=BASE_HEADERS,
            timeout=3
        )
        if res.ok:
            data = res.json()
            if isinstance(data, list):
                return [str(x).strip().upper() for x in data]
    except Exception:
        pass
    return []

def fetch_telemetry_packet(bus_no):
    if not bus_no:
        return None
    try:
        res = requests.post(
            API_LIVE_URL,
            headers=BASE_HEADERS,
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


# --- 2. SEARCH & CONTROLS UI ---
if "recent_buses" not in st.session_state:
    st.session_state["recent_buses"] = []

url_params = st.query_params
url_bus = url_params.get("bus", "").strip().upper()

col_input, col_recent, col_rate, col_btn = st.columns([3.5, 2, 1.3, 1.2])

with col_input:
    # Single clean text bar
    input_bus = st.text_input(
        "Bus Number Search",
        value=url_bus,
        placeholder="Search bus (e.g. UP32MN9123)...",
        label_visibility="collapsed"
    ).strip().upper()

with col_recent:
    history_options = ["🕒 Recent Searches..."] + [b for b in st.session_state["recent_buses"] if b != input_bus]
    selected_from_history = st.selectbox(
        "Recent Searches",
        options=history_options,
        label_visibility="collapsed"
    )

with col_rate:
    refresh_rate_label = st.selectbox(
        "Auto Refresh",
        options=["1s", "2s", "5s", "10s", "30s", "1m"],
        index=4,  # Default: 30s
        label_visibility="collapsed",
        help="Telemetry polling frequency (Default: 30 seconds)"
    )

with col_btn:
    track_btn = st.button("🧭 Track Bus", use_container_width=True, type="primary")

# Resolve selected bus
active_bus = input_bus
if selected_from_history != "🕒 Recent Searches..." and not track_btn:
    active_bus = selected_from_history

# Update search history & URL parameter
if active_bus:
    if active_bus not in st.session_state["recent_buses"]:
        st.session_state["recent_buses"].insert(0, active_bus)
        st.session_state["recent_buses"] = st.session_state["recent_buses"][:5]
    st.query_params["bus"] = active_bus


# --- 3. AUTO-REFRESHING DASHBOARD FRAGMENT ---
@st.fragment(run_every=refresh_rate_label)
def render_live_dashboard(bus_no):
    # Step 1: Validate bus registration against UPSRTC registry
    registered_matches = search_bus_registry(bus_no)
    
    # If a specific registration was typed, check if it's registered
    if registered_matches and bus_no not in registered_matches:
        # Check if it's a prefix with matches
        suggestion_str = ", ".join(registered_matches[:5])
        st.info(f"🔍 Did you mean one of these buses? **{suggestion_str}**")
        return
    elif len(bus_no) >= 6 and not registered_matches:
        st.error(f"❌ Bus **{bus_no}** not found in the UPSRTC registry. Please double-check the registration number.")
        return

    # Step 2: Fetch Telemetry
    packet = fetch_telemetry_packet(bus_no)

    if not packet or "error" in packet:
        st.warning(f"⚠️ No active live telemetry received for **{bus_no}**. The bus is registered, but currently offline or out of network coverage.")
        return

    lat = float(packet.get("latitude", 26.8467))
    lon = float(packet.get("longitude", 80.9462))
    speed = float(packet.get("speed", 0.0))
    heading = float(packet.get("heading", 0.0))
    status = str(packet.get("vehicle_status", "LIVE")).upper()
    zone = packet.get("zone_name", "Location Unknown")
    depot = packet.get("depot_name", "N/A")
    home_depot_id = packet.get("home_depot", "N/A")
    pkt_time = packet.get("receivedTime", packet.get("timestamp", "N/A"))
    ignition = "ON" if packet.get("ignition") == 1 else "OFF"
    satellites = packet.get("numSatellites", "N/A")

    google_maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    
    formatted_share_text = (
        f"🚌 *UPSRTC BUS UPDATE ({bus_no})*\n"
        f"📍 *Location:* {zone}\n"
        f"⚡ *Speed:* {speed:.1f} km/h  |  *Status:* {status}\n"
        f"🔑 *Ignition:* {ignition}  |  *Depot:* {depot}\n"
        f"🕒 *Packet Time:* {pkt_time}\n"
        f"🗺️ *Live Google Maps:* {google_maps_url}"
    )
    whatsapp_url = f"https://api.whatsapp.com/send?text={urllib.parse.quote(formatted_share_text)}"

    # SECTION 1: HEADER & METRICS
    with st.container(border=True):
        top_col1, top_col2 = st.columns([3, 1])
        with top_col1:
            st.caption("🟢 ACTIVE VEHICLE")
            st.subheader(f"🚌 {bus_no}")
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

    # Quick Action Buttons
    btn_c1, btn_c2, btn_c3 = st.columns([1.5, 1.5, 3])
    with btn_c1:
        st.link_button("📲 Share on WhatsApp", whatsapp_url, use_container_width=True, type="primary")
    with btn_c2:
        st.link_button("🗺️ Open Google Maps", google_maps_url, use_container_width=True)
    with btn_c3:
        st.text_input("Copy Share Text", value=formatted_share_text.replace('\n', ' | '), label_visibility="collapsed")

    # SECTION 2: RESPONSIVE LIVE NAVIGATION VIEW
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
                <span style="font-weight:700;">{bus_no}</span>
            </div>
            <div class="hud-metric">
                <span class="hud-val">{speed:.1f}</span>
                <span class="hud-lbl">Speed (km/h)</span>
            </div>
            <div class="hud-metric">
                <span class="hud-val" style="color:#38bdf8; font-size:14px;">{status}</span>
                <span class="hud-lbl">Status</span>
            </div>
        </div>

        <div id="map"></div>

        <script>
            const map = L.map('map', {{ zoomControl: false }}).setView([{lat}, {lon}], 15);
            
            L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19
            }}).addTo(map);

            L.control.zoom({{ position: 'bottomright' }}).addTo(map);

            const pointerIcon = L.divIcon({{
                className: 'bus-pointer',
                html: `
                    <div style="
                        transform: rotate({heading}deg);
                        width: 36px; height: 36px; background: #2563eb;
                        border: 2.5px solid #ffffff; border-radius: 50%;
                        display: flex; align-items: center; justify-content: center;
                        box-shadow: 0 3px 12px rgba(37,99,235,0.7);
                    ">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polygon points="12 2 19 21 12 17 5 21 12 2"></polygon>
                        </svg>
                    </div>
                `,
                iconSize: [36, 36],
                iconAnchor: [18, 18]
            }});

            L.marker([{lat}, {lon}], {{ icon: pointerIcon }}).addTo(map);
        </script>
    </body>
    </html>
    """
    components.html(live_map_html, height=430, scrolling=False)

    # SECTION 3: HARDWARE & SENSOR DIAGNOSTICS
    with st.expander("⚙️ View Complete Device Telemetry & Sensor Details", expanded=False):
        d1, d2, d3 = st.columns(3)
        with d1:
            st.markdown("**🛰️ GPS & Coordinates**")
            st.write(f"- **Latitude:** `{packet.get('latitude')}`")
            st.write(f"- **Longitude:** `{packet.get('longitude')}`")
            st.write(f"- **Altitude:** `{packet.get('altitude')} m`")
            st.write(f"- **Heading / Bearing:** `{heading:.1f}°`")
            st.write(f"- **GPS Fix:** `{packet.get('gpsFix')}`")
            st.write(f"- **Distance Recorded:** `{packet.get('distance', 'N/A')} m`")
        with d2:
            st.markdown("**🔋 Electrical & Power Systems**")
            st.write(f"- **Main Input Voltage:** `{packet.get('mainInputVoltage')} V`")
            st.write(f"- **Internal Battery:** `{packet.get('internalBatteryVoltage')} V`")
            st.write(f"- **Main Power Status:** `{'Connected' if packet.get('mainPowerStatus') == 1 else 'Disconnected'}`")
            st.write(f"- **Emergency Status:** `{packet.get('emergencyStatus', 0)}`")
            st.write(f"- **Tamper Alert:** `{packet.get('tamperAlert', 'N/A')}`")
        with d3:
            st.markdown("**🏢 Vehicle & System Metadata**")
            st.write(f"- **Home Depot ID:** `{home_depot_id}`")
            st.write(f"- **Vendor ID:** `{packet.get('vendorId')}`")
            st.write(f"- **Firmware Version:** `{packet.get('firmwareVersion')}`")
            st.write(f"- **System Code:** `{packet.get('systemCodeNumber')}`")
            st.write(f"- **Frame Number:** `{packet.get('frameNumber')}`")
            packet_type = packet.get('packetType', 'N/A')
            st.write(f"- **Packet Type:** `{packet_type}`")


# --- 4. EXECUTION ENTRY POINT ---
if active_bus:
    render_live_dashboard(active_bus)
else:
    st.info("Enter any UPSRTC bus registration number above to begin tracking.")
