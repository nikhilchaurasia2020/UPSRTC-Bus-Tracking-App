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

# --- 1. BROWSER LOCALSTORAGE INTEGRATION ---
# Persists recent bus numbers in browser localStorage without requiring a backend database.
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

    function saveBusToLocalStorage(busNo) {
        if (busNo) {
            localStorage.setItem("upsrtc_last_bus", busNo);
        }
    }
    </script>
    """
    st.components.v1.html(storage_component, height=0)

render_local_storage_manager()

# Grab pre-filled value from URL query params (populated by browser storage)
url_params = st.query_params
default_bus = url_params.get("bus", "")

# --- 2. HEADER & SEARCH UI ---
st.title("🚌 UPSRTC Real-Time Bus Tracker")
st.caption("Live tracking, vehicle telemetry, and location monitor via Margdarshi")

with st.container():
    col1, col2 = st.columns([3, 1])
    with col1:
        bus_input = st.text_input(
            "Enter Bus Registration Number",
            value=default_bus,
            placeholder="e.g. UP32MN9123, UP78KT4613",
            help="Registration number will be saved in your browser for quick access next time."
        ).strip().upper()
    with col2:
        st.write("")
        st.write("")
        track_btn = st.button("🔍 Track Bus", use_container_width=True, type="primary")

# Save to local storage when user searches
if bus_input:
    st.query_params["bus"] = bus_input
    save_script = f"""
    <script>
        localStorage.setItem("upsrtc_last_bus", "{bus_input}");
    </script>
    """
    st.components.v1.html(save_script, height=0)

# --- 3. TELEMETRY FETCHER ---
API_URL = "https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://margdarshi.upsrtcvlt.com/",
    "Origin": "https://margdarshi.upsrtcvlt.com",
    "Accept": "application/json, text/plain, */*"
}

@st.cache_data(ttl=10, show_spinner=False)
def fetch_telemetry(target_bus):
    try:
        response = requests.post(
            API_URL,
            headers=HEADERS,
            data={"regNo": target_bus},
            timeout=10
        )
        response.raise_for_status()
        raw_data = json.loads(response.text.strip())
        
        if isinstance(raw_data, list):
            for item in raw_data:
                reg = str(item.get("regNum") or item.get("RegNo") or item.get("bus_id", "")).upper()
                if reg == target_bus:
                    return item
            # If the backend filters on its own and returns a single-item array
            if len(raw_data) > 0 and ("regNum" in raw_data[0] or "latitude" in raw_data[0]):
                return raw_data[0]
            return None
        elif isinstance(raw_data, dict):
            return raw_data
    except Exception as e:
        return {"error": str(e)}

# --- 4. RENDER DASHBOARD ---
if bus_input:
    with st.spinner(f"Querying GPS telemetry for {bus_input}..."):
        bus_data = fetch_telemetry(bus_input)

    if not bus_data:
        st.warning(f"No active telemetry received for **{bus_input}**. The bus might be offline, out of network coverage, or the registration number is incorrect.")
    elif "error" in bus_data:
        st.error(f"Failed to communicate with Margdarshi servers: {bus_data['error']}")
    else:
        # Extract telemetry parameters
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
        timestamp = bus_data.get("timestamp", "N/A")
        received_time = bus_data.get("receivedTime", "N/A")
        firmware = bus_data.get("firmwareVersion", "N/A")
        vendor = bus_data.get("vendorId", "N/A")

        # Top Highlight: Nearest Location & Primary Status
        st.success(f"📍 **Current Location:** {zone}")

        # Metrics Row 1: Core Driving Telemetry
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        kpi1.metric("Current Speed", f"{speed} km/h")
        kpi2.metric("Vehicle Status", status)
        kpi3.metric("Ignition", ignition)
        kpi4.metric("Heading / Angle", f"{heading}°")
        kpi5.metric("Depot", depot)

        # Main View: Map + Shareable Card
        map_col, info_col = st.columns([2, 1])

        with map_col:
            st.subheader("🗺️ Live Map Tracking")
            if lat != 0.0 and lon != 0.0:
                view_state = pdk.ViewState(
                    latitude=lat,
                    longitude=lon,
                    zoom=13,
                    pitch=30
                )
                df_loc = pd.DataFrame([{"lat": lat, "lon": lon, "speed": speed, "zone": zone}])
                
                scatter_layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=df_loc,
                    get_position="[lon, lat]",
                    get_color="[235, 64, 52, 220]" if speed == 0 else "[46, 204, 113, 220]",
                    get_radius=120,
                    pickable=True
                )

                st.pydeck_chart(pdk.Deck(
                    map_style="mapbox://styles/mapbox/streets-v11",
                    initial_view_state=view_state,
                    layers=[scatter_layer],
                    tooltip={"text": f"{bus_input}\nSpeed: {speed} km/h\n{zone}"}
                ))
            else:
                st.info("Coordinates not available in this frame.")

        with info_col:
            st.subheader("📋 Shareable Update")
            maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            share_text = (
                f"🚌 *UPSRTC Bus Update ({bus_input})*\n"
                f"📍 *Location:* {zone}\n"
                f"⚡ *Speed:* {speed} km/h | Status: {status}\n"
                f"🔑 *Ignition:* {ignition}\n"
                f"🏢 *Depot:* {depot}\n"
                f"🕒 *Packet Time:* {received_time}\n"
                f"🗺️ *Google Maps:* {maps_url}"
            )
            st.text_area("Click below to copy text:", value=share_text, height=200)
            st.link_button("🌐 Open in Google Maps", maps_url, use_container_width=True)

        # Full Technical & Diagnostic Details (Collapsible)
        with st.expander("⚙️ View Complete Telemetry & Device Diagnostics", expanded=False):
            d1, d2, d3 = st.columns(3)
            with d1:
                st.write("**GPS & Sensor Diagnostics**")
                st.write(f"- **Satellites Locked:** `{satellites}`")
                st.write(f"- **Altitude:** `{altitude} m`")
                st.write(f"- **GPS Fix:** `{bus_data.get('gpsFix', 'N/A')}`")
                st.write(f"- **Distance Traveled:** `{distance} m`")
            with d2:
                st.write("**Power & Hardware**")
                st.write(f"- **Main Input Voltage:** `{main_v} V`")
                st.write(f"- **Internal Battery:** `{int_v} V`")
                st.write(f"- **Main Power Status:** `{'Connected' if bus_data.get('mainPowerStatus') == 1 else 'Disconnected'}`")
                st.write(f"- **Tamper Alert:** `{bus_data.get('tamperAlert', 'N/A')}`")
            with d3:
                st.write("**Device & Network Metadata**")
                st.write(f"- **Vendor ID:** `{vendor}`")
                st.write(f"- **Firmware Version:** `{firmware}`")
                st.write(f"- **System Code Number:** `{bus_data.get('systemCodeNumber', 'N/A')}`")
                st.write(f"- **Home Depot Code:** `{home_depot_id}`")
                st.write(f"- **Server Timestamp:** `{received_time}`")

else:
    st.info("Enter any UPSRTC bus registration number above (e.g., `UP32MN9123`) to view live telemetry and location.")
