import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="UPSRTC Live Navigation Tracker",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom minimal styling
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 0rem; max-width: 100%; }
    header { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# 1. Read pre-filled query param
url_params = st.query_params
default_bus = url_params.get("bus", "")

# 2. Search Bar
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

# 3. Client-Side Live Navigation Engine (Zero-Flicker Leaflet.js)
leaflet_navigation_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body, html {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            overflow: hidden;
            background: #111;
        }}
        #map {{
            width: 100%;
            height: 100vh;
            z-index: 1;
        }}
        /* Floating Navigation HUD */
        .nav-hud {{
            position: absolute;
            top: 15px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            background: rgba(18, 20, 24, 0.92);
            backdrop-filter: blur(8px);
            color: #fff;
            padding: 12px 24px;
            border-radius: 35px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            display: flex;
            align-items: center;
            gap: 25px;
            border: 1px solid rgba(255,255,255,0.15);
            font-size: 14px;
        }}
        .hud-metric {{
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .hud-val {{
            font-size: 20px;
            font-weight: 700;
            color: #2ecc71;
        }}
        .hud-lbl {{
            font-size: 10px;
            text-transform: uppercase;
            color: #aaa;
            letter-spacing: 0.5px;
        }}
        .pulse-dot {{
            width: 10px;
            height: 10px;
            background: #2ecc71;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 10px #2ecc71;
            animation: pulse 1.5s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(46, 204, 113, 0.7); }}
            70% {{ transform: scale(1.1); box-shadow: 0 0 0 8px rgba(46, 204, 113, 0); }}
            100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(46, 204, 113, 0); }}
        }}
        /* Custom Smooth Bus Marker */
        .bus-marker-icon {{
            transition: transform 0.8s linear, top 0.8s linear, left 0.8s linear;
        }}
        .floating-info {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            right: 20px;
            z-index: 1000;
            background: rgba(18, 20, 24, 0.92);
            backdrop-filter: blur(8px);
            color: #fff;
            padding: 12px 20px;
            border-radius: 12px;
            font-size: 13px;
            border: 1px solid rgba(255,255,255,0.15);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
    </style>
</head>
<body>

    <div class="nav-hud">
        <div style="display:flex; align-items:center; gap:8px;">
            <span class="pulse-dot"></span>
            <span id="busTag" style="font-weight:600;">{bus_input if bus_input else "NO BUS SELECTED"}</span>
        </div>
        <div class="hud-metric">
            <span class="hud-val" id="speedVal">--</span>
            <span class="hud-lbl">Speed (km/h)</span>
        </div>
        <div class="hud-metric">
            <span class="hud-val" id="statusVal" style="color:#3498db; font-size:16px;">--</span>
            <span class="hud-lbl">Status</span>
        </div>
    </div>

    <div id="map"></div>

    <div class="floating-info">
        <div>
            <strong>📍 Location:</strong> <span id="zoneVal">Searching telemetry...</span>
        </div>
        <div style="color:#aaa;">
            <strong>Depot:</strong> <span id="depotVal">--</span> | <strong>Last Packet:</strong> <span id="timeVal">--</span>
        </div>
    </div>

    <script>
        const BUS_NO = "{bus_input}".trim().toUpperCase();

        // Save bus to local storage
        if (BUS_NO) {{
            localStorage.setItem("upsrtc_last_bus", BUS_NO);
        }} else {{
            const saved = localStorage.getItem("upsrtc_last_bus");
            if (saved) {{
                const url = new URL(window.parent.location);
                url.searchParams.set("bus", saved);
                window.parent.location.replace(url.toString());
            }}
        }}

        // Initialize Map
        const map = L.map('map', {{
            zoomControl: false,
            attributionControl: false
        }}).setView([26.8467, 80.9462], 14); // Default near UP

        L.control.zoom({{ position: 'bottomright' }}).addTo(map);

        // Vector/Raster Tiles (CartoDB Voyager - Clean Google Maps aesthetic)
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            maxZoom: 19
        }}).addTo(map);

        // Custom Bus SVG Marker with Heading Arrow
        function createBusIcon(heading) {{
            return L.divIcon({{
                className: 'bus-marker-icon',
                html: `
                    <div style="
                        transform: rotate(${{heading}}deg);
                        width: 44px;
                        height: 44px;
                        background: #007AFF;
                        border: 3px solid #ffffff;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        box-shadow: 0 4px 15px rgba(0,122,255,0.6);
                    ">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polygon points="12 2 19 21 12 17 5 21 12 2"></polygon>
                        </svg>
                    </div>
                `,
                iconSize: [44, 44],
                iconAnchor: [22, 22]
            }});
        }}

        let busMarker = null;
        let polyline = L.polyline([], {{ color: '#007AFF', weight: 4, opacity: 0.7 }}).addTo(map);
        let isFirstFix = true;

        // Smooth telemetry loop directly from Margdarshi API
        async function fetchLiveTelemetry() {{
            if (!BUS_NO) return;

            try {{
                const formData = new URLSearchParams();
                formData.append('regNo', BUS_NO);

                const res = await fetch('https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }},
                    body: formData
                }});

                const data = await res.json();
                let bus = null;

                if (Array.isArray(data)) {{
                    bus = data.find(item => 
                        (item.regNum && item.regNum.toUpperCase() === BUS_NO) ||
                        (item.RegNo && item.RegNo.toUpperCase() === BUS_NO) ||
                        (item.bus_id && item.bus_id.toUpperCase() === BUS_NO)
                    );
                    if (!bus && data.length > 0) bus = data[0];
                }} else if (typeof data === 'object') {{
                    bus = data;
                }}

                if (bus && bus.latitude && bus.longitude) {{
                    const lat = parseFloat(bus.latitude);
                    const lng = parseFloat(bus.longitude);
                    const speed = parseFloat(bus.speed || 0).toFixed(1);
                    const heading = parseFloat(bus.heading || 0);
                    const status = (bus.vehicle_status || 'LIVE').toUpperCase();
                    const zone = bus.zone_name || 'En route';
                    const depot = bus.depot_name || '--';
                    const time = bus.receivedTime || bus.timestamp || '--';

                    // Update HUD text without touching DOM map
                    document.getElementById('speedVal').innerText = speed;
                    document.getElementById('statusVal').innerText = status;
                    document.getElementById('zoneVal').innerText = zone;
                    document.getElementById('depotVal').innerText = depot;
                    document.getElementById('timeVal').innerText = time;

                    const newLatLng = [lat, lng];

                    if (!busMarker) {{
                        busMarker = L.marker(newLatLng, {{ icon: createBusIcon(heading) }}).addTo(map);
                    }} else {{
                        // Smoothly animate marker to new position
                        busMarker.setLatLng(newLatLng);
                        busMarker.setIcon(createBusIcon(heading));
                    }}

                    // Append to route trail
                    polyline.addLatLng(newLatLng);

                    // Smooth pan map along with bus (navigation mode)
                    if (isFirstFix) {{
                        map.setView(newLatLng, 15);
                        isFirstFix = false;
                    }} else {{
                        map.panTo(newLatLng, {{ animate: true, duration: 0.8 }});
                    }}
                }}
            }} catch (err) {{
                console.error("Telemetry fetch error:", err);
            }}
        }}

        // Poll every 1.5 seconds for true smooth navigation
        fetchLiveTelemetry();
        setInterval(fetchLiveTelemetry, 1500);
    </script>
</body>
</html>
"""

if bus_input:
    components.html(leaflet_navigation_html, height=720, scrolling=False)
else:
    st.info("Enter a bus number above (e.g. `UP32MN9123`) to launch real-time turn-by-turn tracking.")
