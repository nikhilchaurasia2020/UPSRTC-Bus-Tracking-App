import streamlit as st
import streamlit.components.v1 as components
import requests
import json

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
    div[data-testid="stExpander"] { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 1. LOCAL STORAGE & SEARCH HISTORY (LAST 5 SEARCHES) ---
if "recent_buses" not in st.session_state:
    st.session_state["recent_buses"] = []

url_params = st.query_params
url_bus = url_params.get("bus", "").strip().upper()

# Search Bar, Recent Searches, Refresh Rate, & Action Button
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
    refresh_rate = st.selectbox(
        "Auto Refresh",
        options=["1s", "2s", "5s", "10s", "30s", "1m"],
        index=1,
        label_visibility="collapsed",
        help="Telemetry polling frequency (max 1 minute)"
    )

with col_btn:
    track_btn = st.button("🧭 Track Bus", use_container_width=True, type="primary")

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


# --- 2. SERVER-SIDE DATA FETCHER (BYPASSES CORS) ---
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
@st.fragment(run_every=refresh_rate)
def render_dashboard(bus_no):
    packet = fetch_telemetry_packet(bus_no)

    if not packet or "error" in packet:
        st.warning(f"No active telemetry received for **{bus_no}**. The bus might be offline or currently out of network coverage.")
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
    share_msg = (
        f"🚌 *UPSRTC Bus Update ({bus_no})*\n"
        f"📍 *Location:* {zone}\n"
        f"⚡ *Speed:* {speed:.1f} km/h | Status: {status}\n"
        f"🔑 *Ignition:* {ignition}\n"
        f"🏢 *Depot:* {depot}\n"
        f"🕒 *Packet Time:* {pkt_time}\n"
        f"🗺️ *Live Google Maps:* {google_maps_url}"
    )

    # --- POSITIONED AT TOP: SHAREABLE UPDATE & CORE METRICS ---
    st.write("")
    with st.container():
        st.success(f"📍 **Nearest Location:** {zone}")
        
        info_col1, info_col2 = st.columns([3, 1])
        with info_col1:
            st.text_area("📋 Shareable Update (WhatsApp / SMS):", value=share_msg, height=135)
        with info_col2:
            st.write("")
            st.write("")
            st.link_button("🌐 Open in Google Maps", google_maps_url, use_container_width=True)
            st.caption(f"⏱️ **Last Packet:** `{pkt_time}`")

        # Top highlight metrics row
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Live Speed", f"{speed:.1f} km/h")
        m2.metric("Status", status)
        m3.metric("Ignition", ignition)
        m4.metric("Depot", depot)
        m5.metric("Satellites", satellites)

    # --- MAP COMPONENT (PERSISTENT OPENSTREETMAP LEAFLET) ---
    st.write("")
    st.subheader("🗺️ Live Navigation View")

    leaflet_html = f"""
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
            #map {{ width: 100%; height: 560px; }}
            .nav-hud {{
                position: absolute; top: 12px; left: 50%; transform: translateX(-50%);
                z-index: 1000; background: rgba(18, 20, 24, 0.94); backdrop-filter: blur(8px);
                color: #fff; padding: 10px 24px; border-radius: 40px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.45); display: flex; align-items: center;
                gap: 20px; border: 1px solid rgba(255,255,255,0.18); font-size: 13px;
            }}
            .hud-metric {{ display: flex; flex-direction: column; align-items: center; }}
            .hud-val {{ font-size: 19px; font-weight: 700; color: #2ecc71; }}
            .hud-lbl {{ font-size: 9px; text-transform: uppercase; color: #aaa; }}
            .pulse-dot {{
                width: 10px; height: 10px; background: #2ecc71; border-radius: 50%;
                display: inline-block; box-shadow: 0 0 10px #2ecc71;
            }}
        </style>
    </head>
    <body>
        <div class="nav-hud">
            <div style="display:flex; align-items:center; gap:8px;">
                <span class="pulse-dot"></span>
                <span style="font-weight:700;">{bus_no}</span>
            </div>
            <div class="hud-metric">
                <span class="hud-val">{speed:.1f}</span>
                <span class="hud-lbl">Speed (km/h)</span>
            </div>
            <div class="hud-metric">
                <span class="hud-val" style="color:#3498db; font-size:15px;">{status}</span>
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

            const busIcon = L.divIcon({{
                className: 'bus-pointer',
                html: `
                    <div style="
                        transform: rotate({heading}deg);
                        width: 42px; height: 42px; background: #007AFF;
                        border: 3px solid #ffffff; border-radius: 50%;
                        display: flex; align-items: center; justify-content: center;
                        box-shadow: 0 4px 15px rgba(0,122,255,0.7);
                    ">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polygon points="12 2 19 21 12 17 5 21 12 2"></polygon>
                        </svg>
                    </div>
                `,
                iconSize: [42, 42],
                iconAnchor: [21, 21]
            }});

            L.marker([{lat}, {lon}], {{ icon: busIcon }}).addTo(map);
        </script>
    </body>
    </html>
    """
    components.html(leaflet_html, height=570, scrolling=False)

    # --- HARDWARE DIAGNOSTICS SECTION ---
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
            st.write(f"- **Packet Type:** `{packet.get('packetType')}`")


if active_bus:
    render_dashboard(active_bus)
else:
    st.info("Enter any UPSRTC bus registration number above (or pick from your recent searches) to start navigation.")
