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

# Custom minimal UI styling
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; max-width: 100%; }
    header { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# 1. Read / save query params
url_params = st.query_params
default_bus = url_params.get("bus", "")

col_search, col_action = st.columns([4, 1])
with col_search:
    bus_input = st.text_input(
        "Enter UPSRTC Bus Registration Number",
        value=default_bus,
        placeholder="e.g. UP32MN9123, UP78KT4613",
        label_visibility="collapsed"
    ).strip().upper()

with col_action:
    track_btn = st.button("🧭 Start Navigation", use_container_width=True, type="primary")

if bus_input:
    st.query_params["bus"] = bus_input

# 2. Server-side Telemetry Fetcher (Bypasses CORS)
API_URL = "https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://margdarshi.upsrtcvlt.com/",
    "Origin": "https://margdarshi.upsrtcvlt.com",
    "Accept": "application/json, text/plain, */*"
}

def fetch_telemetry(bus_no):
    try:
        res = requests.post(
            API_URL,
            headers=HEADERS,
            data={"regNo": bus_no},
            timeout=5
        )
        res.raise_for_status()
        data = json.loads(res.text.strip())

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

# 3. Live Updating Map Fragment
@st.fragment(run_every="2s")
def render_live_map(bus_no):
    data = fetch_telemetry(bus_no)
    
    if not data or "error" in data:
        st.warning(f"Waiting for telemetry data for **{bus_no}**... Make sure the bus is active and registration is correct.")
        return

    lat = float(data.get("latitude", 0.0))
    lon = float(data.get("longitude", 0.0))
    speed = float(data.get("speed", 0.0))
    heading = float(data.get("heading", 0.0))
    status = str(data.get("vehicle_status", "LIVE")).upper()
    zone = data.get("zone_name", "Location Unknown")
    depot = data.get("depot_name", "N/A")
    pkt_time = data.get("receivedTime", data.get("timestamp", "N/A"))

    if lat == 0.0 and lon == 0.0:
        st.warning("No GPS coordinates in the latest packet.")
        return

    # Leaflet HTML with OpenStreetMap Tiles (No API key needed)
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
            #map {{ width: 100%; height: 100vh; }}
            .nav-hud {{
                position: absolute; top: 15px; left: 50%; transform: translateX(-50%);
                z-index: 1000; background: rgba(18, 20, 24, 0.94); backdrop-filter: blur(8px);
                color: #fff; padding: 10px 22px; border-radius: 35px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.4); display: flex; align-items: center;
                gap: 20px; border: 1px solid rgba(255,255,255,0.15); font-size: 13px;
            }}
            .hud-metric {{ display: flex; flex-direction: column; align-items: center; }}
            .hud-val {{ font-size: 18px; font-weight: 700; color: #2ecc71; }}
            .hud-lbl {{ font-size: 9px; text-transform: uppercase; color: #aaa; }}
            .pulse-dot {{
                width: 9px; height: 9px; background: #2ecc71; border-radius: 50%;
                display: inline-block; box-shadow: 0 0 10px #2ecc71;
            }}
            .floating-info {{
                position: absolute; bottom: 18px; left: 18px; right: 18px; z-index: 1000;
                background: rgba(18, 20, 24, 0.94); backdrop-filter: blur(8px);
                color: #fff; padding: 10px 16px; border-radius: 10px; font-size: 12px;
                border: 1px solid rgba(255,255,255,0.15); display: flex;
                justify-content: space-between; align-items: center;
            }}
        </style>
    </head>
    <body>
        <div class="nav-hud">
            <div style="display:flex; align-items:center; gap:8px;">
                <span class="pulse-dot"></span>
                <span style="font-weight:600;">{bus_no}</span>
            </div>
            <div class="hud-metric">
                <span class="hud-val">{speed:.1f}</span>
                <span class="hud-lbl">Speed (km/h)</span>
            </div>
            <div class="hud-metric">
                <span class="hud-val" style="color:#3498db;">{status}</span>
                <span class="hud-lbl">Status</span>
            </div>
        </div>

        <div id="map"></div>

        <div class="floating-info">
            <div><strong>📍 Location:</strong> {zone}</div>
            <div style="color:#aaa;"><strong>Depot:</strong> {depot} | <strong>Packet:</strong> {pkt_time}</div>
        </div>

        <script>
            // OpenStreetMap Standard Tiles (completely free, no API key required)
            const map = L.map('map', {{ zoomControl: false }}).setView([{lat}, {lon}], 15);
            L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19
            }}).addTo(map);

            const busIcon = L.divIcon({{
                className: 'bus-icon',
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
    components.html(leaflet_html, height=650, scrolling=False)

if bus_input:
    render_live_map(bus_input)
else:
    st.info("Enter a bus registration number to begin tracking.")
