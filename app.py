import streamlit as st
import requests
import json
import pandas as pd
import pydeck as pdk
from datetime import datetime

st.set_page_config(
    page_title="UPSRTC Bus Tracker",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 1. LOCAL STORAGE JS INTEGRATION ---
def render_local_storage_manager():
    storage_component = """
    <script>
    (function() {
        const savedBus = localStorage.getItem("upsrtc_last_bus");
        if (savedBus) {
            const currentQuery = new URLSearchParams(window.location.search).get("bus");
            if (!currentQuery) {
                const url = new URL(window.location);
                url.searchParams.set("bus", savedBus);
                window.location.replace(url.toString());
            }
        }
    })();
    </script>
    """
    st.components.v1.html(storage_component, height=0)

render_local_storage_manager()

# Read pre-filled query param
url_params = st.query_params
default_bus = url_params.get("bus", "")

# --- 2. SEARCH & HEADER ---
st.title("🚌 UPSRTC Real-Time Bus Tracker")

col_search, col_rate = st.columns([3, 1])
with col_search:
    bus_input = st.text_input(
        "Enter Bus Registration Number",
        value=default_bus,
        placeholder="e.g. UP32MN9123, UP78KT4613",
        help="Saves automatically in browser storage."
    ).strip().upper()

with col_rate:
    refresh_rate = st.selectbox(
        "Refresh Interval",
        options=["1s", "2s", "5s", "10s"],
        index=0,
        help="Polling interval for fetching updated telemetry"
    )

# Save bus to local storage when changed
if bus_input:
    st.query_params["bus"] = bus_input
    st.components.v1.html(
        f"<script>localStorage.setItem('upsrtc_last_bus', '{bus_input}');</script>",
        height=0
    )

# --- 3. TELEMETRY NETWORK FETCHER ---
API_URL = "https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://margdarshi.upsrtcvlt.com/",
    "Origin": "https://margdarshi.upsrtcvlt.com",
    "Accept": "application/json, text/plain, */*"
}

def fetch_telemetry_live(target_bus):
    try:
        response = requests.post(
            API_URL,
            headers=HEADERS,
            data={"regNo": target_bus},
            timeout=3
        )
        response.raise_for_status()
        raw = response.text.strip()
        data = json.loads(raw)

        if isinstance(data, list):
            for item in data:
                reg = str(item.get("regNum") or item.get("RegNo") or item.get("bus_id", "")).upper()
                if reg == target_bus:
                    return item
            if len(data) > 0 and ("latitude" in data[0] or "regNum" in data[0]):
                return data[0]
            return None
        elif isinstance(data, dict):
            return data
    except Exception as e:
        return {"error": str(e)}

# --- 4. REAL-TIME AUTO-REFRESH FRAGMENT ---
# This runs strictly inside this fragment every second without reloading the search bar or entire DOM
@st.fragment(run_every=refresh_rate)
def render_live_dashboard(target_bus):
    bus_data = fetch_telemetry_live(target_bus)

    if not bus_data:
        st.warning(f"No active telemetry received for **{target_bus}**. The bus might be offline or currently out of signal.")
        return
    if "error" in bus_data:
        st.error(f"Network error: {bus_data['error']}")
        return

    # Extract coordinates & attributes
    lat = float(bus_data.get("latitude", 0.0))
    lon = float(bus_data.get("longitude", 0.0))
    speed = float(bus_data.get("speed", 0.0))
    heading = float(bus_data.get("heading", 0.0))
    altitude = bus_data.get("altitude", "N/A")
    satellites = bus_data.get("numSatellites", "N/A")
    ignition = "ON" if bus_data.get("ignition") == 1 else "OFF"
    status = str(bus_data.get("vehicle_status", "unknown")).upper()
    zone = bus_data.get("zone_name", "Location Unknown")
    depot = bus_data.get("depot_name", "N/A")
    home_depot_id = bus_data.get("home_depot", "N/A")
    main_v = bus_data.get("mainInputVoltage", "N/A")
    int_v = bus_data.get("internalBatteryVoltage", "N/A")
    distance = bus_data.get("distance", "N/A")
    received_time = bus_data.get("receivedTime", bus_data.get("timestamp", "N/A"))
    vendor = bus_data.get("vendorId", "N/A")
    firmware = bus_data.get("firmwareVersion", "N/A")

    # Live connection header
    now_str = datetime.now().strftime("%H:%M:%S")
    st.markdown(
        f"🟢 **LIVE PING** `{now_str}` | **Bus Status:** `{status}` | **Packet Time:** `{received_time}`"
    )

    st.success(f"📍 **Current Location:** {zone}")

    # Driving Metrics KPIs
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Live Speed", f"{speed:.1f} km/h")
    k2.metric("Ignition", ignition)
    k3.metric("Depot", depot)
    k4.metric("Heading", f"{heading:.1f}°")
    k5.metric("GPS Satellites", satellites)

    # Live Map + Info Block
    map_col, info_col = st.columns([2, 1])

    with map_col:
        st.subheader("🗺️ Live GPS Position")
        if lat != 0.0 and lon != 0.0:
            df_coords = pd.DataFrame([{
                "lat": lat,
                "lon": lon,
                "speed": speed,
                "label": f"{target_bus} ({speed} km/h)"
            }])

            # PyDeck configured with free OpenStreetMap Carto raster tiles (no API keys required)
            osm_tile_layer = pdk.Layer(
                "BitmapLayer",
                data=None,
                image="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            )

            marker_layer = pdk.Layer(
                "ScatterplotLayer",
                data=df_coords,
                get_position="[lon, lat]",
                get_fill_color="[46, 204, 113, 220]" if speed > 0 else "[235, 64, 52, 220]",
                get_radius=120,
                pickable=True
            )

            text_layer = pdk.Layer(
                "TextLayer",
                data=df_coords,
                get_position="[lon, lat]",
                get_text="label",
                get_size=16,
                get_color=[0, 0, 0, 255],
                get_alignment_baseline="'bottom'",
                get_pixel_offset=[0, -15]
            )

            view_state = pdk.ViewState(
                latitude=lat,
                longitude=lon,
                zoom=14,
                pitch=0
            )

            st.pydeck_chart(
                pdk.Deck(
                    layers=[marker_layer, text_layer],
                    initial_view_state=view_state,
                    tooltip={"text": "{label}\nLat: {lat}, Lon: {lon}"}
                )
            )
        else:
            st.warning("Coordinates unavailable in this frame.")

    with info_col:
        st.subheader("📋 Shareable Update")
        maps_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        share_payload = (
            f"🚌 *UPSRTC Bus Update ({target_bus})*\n"
            f"📍 *Location:* {zone}\n"
            f"⚡ *Speed:* {speed} km/h | Status: {status}\n"
            f"🔑 *Ignition:* {ignition}\n"
            f"🏢 *Depot:* {depot}\n"
            f"🕒 *Updated:* {received_time}\n"
            f"🗺️ *Live Map:* {maps_link}"
        )
        st.text_area("Live update text (copy & paste):", value=share_payload, height=180)
        st.link_button("🌐 Open in Google Maps", maps_link, use_container_width=True)

    # Diagnostic metadata
    with st.expander("⚙️ Hardware Diagnostics & Packet Details"):
        d1, d2, d3 = st.columns(3)
        with d1:
            st.write(f"- **Satellites:** `{satellites}`")
            st.write(f"- **Altitude:** `{altitude} m`")
            st.write(f"- **Distance Traveled:** `{distance} m`")
        with d2:
            st.write(f"- **Main Voltage:** `{main_v} V`")
            st.write(f"- **Battery Voltage:** `{int_v} V`")
            st.write(f"- **Main Power:** `{'Connected' if bus_data.get('mainPowerStatus') == 1 else 'Disconnected'}`")
        with d3:
            st.write(f"- **Vendor ID:** `{vendor}`")
            st.write(f"- **Firmware:** `{firmware}`")
            st.write(f"- **Depot Code:** `{home_depot_id}`")


# --- 5. RUN DASHBOARD ---
if bus_input:
    render_live_dashboard(bus_input)
else:
    st.info("Enter any UPSRTC bus registration number above to begin real-time 1-second tracking.")
