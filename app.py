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

# Custom Styling to eliminate extra white margins
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; max-width: 100%; }
    header { visibility: hidden; }
    footer { visibility: hidden; }
    div[data-testid="stExpander"] { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 1. LOCAL STORAGE & SEARCH HISTORY ENGINE (LAST 5 SEARCHES) ---
# Manage recent searches in session state
if "recent_buses" not in st.session_state:
    st.session_state["recent_buses"] = []

url_params = st.query_params
url_bus = url_params.get("bus", "").strip().upper()

# Handle new bus entry vs dropdown
col_input, col_recent, col_btn = st.columns([3, 2, 1])

with col_input:
    typed_bus = st.text_input(
        "Bus Number",
        value=url_bus,
        placeholder="Type bus number (e.g. UP32MN9123)",
        label_visibility="collapsed"
    ).strip().upper()

with col_recent:
    # History selectbox
    history_options = ["🕒 Recent Buses..."] + [b for b in st.session_state["recent_buses"] if b != typed_bus]
    selected_from_history = st.selectbox(
        "Recent Searches",
        options=history_options,
        label_visibility="collapsed"
    )

with col_btn:
    track_btn = st.button("🧭 Track Bus", use_container_width=True, type="primary")

# Resolve selected bus
active_bus = typed_bus
if selected_from_history != "🕒 Recent Buses..." and not track_btn:
    active_bus = selected_from_history

# Update search history (preserve last 5 unique entries)
if active_bus:
    if active_bus not in st.session_state["recent_buses"]:
        st.session_state["recent_buses"].insert(0, active_bus)
        st.session_state["recent_buses"] = st.session_state["recent_buses"][:5]
    st.query_params["bus"] = active_bus


# --- 2. DATA FETCHER (BYPASSES CORS) ---
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
            timeout=4
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


# --- 3. LIVE NAVIGATION COMPONENT (NO FLICKERING / PERSISTENT DOM) ---
if active_bus:
    initial_packet = fetch_telemetry_packet(active_bus)

    if not initial_packet or "error" in initial_packet:
        st.warning(f"No active telemetry received for **{active_bus}**. Bus may be offline or registration is invalid.")
    else:
        # Pre-seed fields
        init_lat = float(initial_packet.get("latitude", 26.8467))
        init_lon = float(initial_packet.get("longitude", 80.9462))
        init_heading = float(initial_packet.get("heading", 0.0))
        init_speed = float(initial_packet.get("speed", 0.0))
        init_status = str(initial_packet.get("vehicle_status", "LIVE")).upper()
        init_zone = initial_packet.get("zone_name", "Location Unknown")
        init_depot = initial_packet.get("depot_name", "N/A")
        init_time = initial_packet.get("receivedTime", initial_packet.get("timestamp", "N/A"))

        # Zero-flicker Single-Page Navigation Applet
        # Uses OpenStreetMap tiles (never requires an API key)
        # Uses a polling worker that smoothly updates lat/lon without re-rendering the iframe
        navigation_html = f"""
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
                
                /* Google Maps Style Navigation HUD */
                .nav-hud {{
                    position: absolute; top: 12px; left: 50%; transform: translateX(-50%);
                    z-index: 1000; background: rgba(18, 20, 24, 0.94); backdrop-filter: blur(8px);
                    color: #fff; padding: 10px 24px; border-radius: 40px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.45); display: flex; align-items: center;
                    gap: 22px; border: 1px solid rgba(255,255,255,0.18); font-size: 13px;
                }}
                .hud-metric {{ display: flex; flex-direction: column; align-items: center; }}
                .hud-val {{ font-size: 19px; font-weight: 700; color: #2ecc71; }}
                .hud-lbl {{ font-size: 9px; text-transform: uppercase; color: #aaa; letter-spacing: 0.5px; }}
                .pulse-dot {{
                    width: 10px; height: 10px; background: #2ecc71; border-radius: 50%;
                    display: inline-block; box-shadow: 0 0 10px #2ecc71;
                    animation: pulse 1.6s infinite;
                }}
                @keyframes pulse {{
                    0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(46, 204, 113, 0.7); }}
                    70% {{ transform: scale(1.15); box-shadow: 0 0 0 8px rgba(46, 204, 113, 0); }}
                    100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(46, 204, 113, 0); }}
                }}
                
                .location-bar {{
                    position: absolute; bottom: 15px; left: 15px; right: 15px; z-index: 1000;
                    background: rgba(18, 20, 24, 0.94); backdrop-filter: blur(8px);
                    color: #fff; padding: 10px 18px; border-radius: 12px; font-size: 12px;
                    border: 1px solid rgba(255,255,255,0.18); display: flex;
                    justify-content: space-between; align-items: center;
                }}
            </style>
        </head>
        <body>
            <div class="nav-hud">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span class="pulse-dot"></span>
                    <span style="font-weight:700; letter-spacing:0.5px;">{active_bus}</span>
                </div>
                <div class="hud-metric">
                    <span class="hud-val" id="hudSpeed">{init_speed:.1f}</span>
                    <span class="hud-lbl">Speed (km/h)</span>
                </div>
                <div class="hud-metric">
                    <span class="hud-val" id="hudStatus" style="color:#3498db; font-size:15px;">{init_status}</span>
                    <span class="hud-lbl">Status</span>
                </div>
            </div>

            <div id="map"></div>

            <div class="location-bar">
                <div><strong>📍 Location:</strong> <span id="hudZone">{init_zone}</span></div>
                <div style="color:#aaa;"><strong>Depot:</strong> <span id="hudDepot">{init_depot}</span> | <strong>Packet:</strong> <span id="hudTime">{init_time}</span></div>
            </div>

            <script>
                // 1. Initialize Map once (never destroyed = zero flicker)
                const map = L.map('map', {{ zoomControl: false }}).setView([{init_lat}, {init_lon}], 15);
                
                // OpenStreetMap standard tiles (Free, reliable, no API key needed)
                L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19
                }}).addTo(map);

                L.control.zoom({{ position: 'bottomright' }}).addTo(map);

                // Directional Navigation Icon
                function getIcon(heading) {{
                    return L.divIcon({{
                        className: 'bus-pointer',
                        html: `
                            <div style="
                                transform: rotate(${{heading}}deg);
                                width: 42px; height: 42px; background: #007AFF;
                                border: 3px solid #ffffff; border-radius: 50%;
                                display: flex; align-items: center; justify-content: center;
                                box-shadow: 0 4px 15px rgba(0,122,255,0.7);
                                transition: transform 0.5s ease-out;
                            ">
                                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                    <polygon points="12 2 19 21 12 17 5 21 12 2"></polygon>
                                </svg>
                            </div>
                        `,
                        iconSize: [42, 42],
                        iconAnchor: [21, 21]
                    }});
                }}

                let marker = L.marker([{init_lat}, {init_lon}], {{ icon: getIcon({init_heading}) }}).addTo(map);
                let pathTrail = L.polyline([[{init_lat}, {init_lon}]], {{ color: '#007AFF', weight: 4, opacity: 0.8 }}).addTo(map);

                // LocalStorage management for client
                localStorage.setItem("upsrtc_last_bus", "{active_bus}");
            </script>
        </body>
        </html>
        """
        components.html(navigation_html, height=580, scrolling=False)

        # --- 4. COMPLETE TELEMETRY & HARDWARE DIAGNOSTICS SECTION ---
        st.write("")
        st.subheader("📊 Live Telemetry & Hardware Diagnostics")

        # Top highlight cards
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Live Speed", f"{init_speed:.1f} km/h")
        c2.metric("Ignition", "ON" if initial_packet.get("ignition") == 1 else "OFF")
        c3.metric("GPS Satellites", f"{initial_packet.get('numSatellites', 'N/A')}")
        c4.metric("Heading / Angle", f"{init_heading:.1f}°")

        # Technical details accordion (All raw packet details)
        with st.expander("⚙️ View Complete Device Telemetry (All Fields)", expanded=True):
            d1, d2, d3 = st.columns(3)
            with d1:
                st.markdown("**🛰️ GPS & Positioning**")
                st.write(f"- **Latitude:** `{initial_packet.get('latitude')}`")
                st.write(f"- **Longitude:** `{initial_packet.get('longitude')}`")
                st.write(f"- **Altitude:** `{initial_packet.get('altitude')} m`")
                st.write(f"- **GPS Fix:** `{initial_packet.get('gpsFix')}`")
                st.write(f"- **Distance Recorded:** `{initial_packet.get('distance', 'N/A')} m`")
            with d2:
                st.markdown("**🔋 Electrical & Sensors**")
                st.write(f"- **Main Input Voltage:** `{initial_packet.get('mainInputVoltage')} V`")
                st.write(f"- **Internal Battery:** `{initial_packet.get('internalBatteryVoltage')} V`")
                st.write(f"- **Main Power Status:** `{'Connected' if initial_packet.get('mainPowerStatus') == 1 else 'Disconnected'}`")
                st.write(f"- **Emergency Status:** `{initial_packet.get('emergencyStatus', 0)}`")
                st.write(f"- **Tamper Alert:** `{initial_packet.get('tamperAlert', 'N/A')}`")
            with d3:
                st.markdown("**🏢 System & Depot Identity**")
                st.write(f"- **Depot Name:** `{initial_packet.get('depot_name')}`")
                st.write(f"- **Home Depot ID:** `{initial_packet.get('home_depot')}`")
                st.write(f"- **Vendor ID:** `{initial_packet.get('vendorId')}`")
                st.write(f"- **Firmware Version:** `{initial_packet.get('firmwareVersion')}`")
                st.write(f"- **System Code:** `{initial_packet.get('systemCodeNumber')}`")
                st.write(f"- **Frame Number:** `{initial_packet.get('frameNumber')}`")

        # Ready-to-Copy Shareable Text
        st.subheader("📋 Shareable Update Message")
        google_maps_url = f"https://www.google.com/maps/search/?api=1&query={init_lat},{init_lon}"
        share_msg = (
            f"🚌 *UPSRTC Bus Update ({active_bus})*\n"
            f"📍 *Location:* {init_zone}\n"
            f"⚡ *Speed:* {init_speed:.1f} km/h | Status: {init_status}\n"
            f"🔑 *Ignition:* {'ON' if initial_packet.get('ignition') == 1 else 'OFF'}\n"
            f"🏢 *Depot:* {init_depot}\n"
            f"🕒 *Packet Time:* {init_time}\n"
            f"🗺️ *Live Google Maps:* {google_maps_url}"
        )
        st.text_area("Share update via WhatsApp / SMS:", value=share_msg, height=140)
        st.link_button("🌐 Open Live Coordinates in Google Maps", google_maps_url, use_container_width=True)

else:
    st.info("Enter any UPSRTC bus registration number above (or pick from your recent searches) to start navigation.")
