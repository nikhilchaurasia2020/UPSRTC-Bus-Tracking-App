# UPSRTC Real-Time Bus Tracker 🚌

A lightweight, real-time vehicle tracking dashboard built with **Streamlit**, **PyDeck**, and **Python**. It tracks Uttar Pradesh State Road Transport Corporation (UPSRTC) buses across Uttar Pradesh using live telemetry feeds, presenting real-time coordinates, driving indicators, nearest landmarks/zones, and hardware diagnostics.

---

## Key Features

- **Live Telemetry & Driving Metrics:** Real-time tracking of speed (km/h), heading/bearing, ignition state, GPS satellite count, altitude, and current status (`live`, `stationary`, `no_signal`).
- **Browser Persistence:** Remembers previously queried bus registration numbers in the client's browser using HTML5 `localStorage` and query parameters.
- **Geographic Zone Identification:** Displays human-readable location descriptions, road segments, and districts directly from Margdarshi telemetry frames without external geocoding API rate limits.
- **Interactive Geospatial Visualization:** Renders 2.5D/3D interactive maps via PyDeck with color-coded vehicle markers based on motion status.
- **Hardware & Packet Diagnostics:** Collapsible inspector for low-level device data: main/internal battery voltage, GPS fix status, frame counters, tamper flags, firmware version, and depot metadata.
- **One-Click Share:** Generates copy-ready status updates for WhatsApp and SMS along with a direct Google Maps pin link.

---

## Project Structure

```text
UPSRTC-Bus-Tracking-App/
├── app.py              # Main Streamlit dashboard application
├── requirements.txt    # Python package dependencies
└── README.md           # Documentation
```

---

## Local Setup & Installation

### 1. Prerequisites
Ensure you have **Python 3.9+** and `git` installed.

### 2. Clone the Repository
```bash
git clone https://github.com/nikhilchaurasia2020/UPSRTC-Bus-Tracking-App.git
cd UPSRTC-Bus-Tracking-App
```

### 3. Create a Virtual Environment
```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows (Command Prompt / PowerShell)
python -m venv venv
venv\Scripts\activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the Application
```bash
streamlit run app.py
```
Open your browser and navigate to `http://localhost:8501`.

---

## Free Cloud Deployment (Streamlit Community Cloud)

You can host this project 24/7 for free directly from GitHub:

1. Push your code to [nikhilchaurasia2020/UPSRTC-Bus-Tracking-App](https://github.com/nikhilchaurasia2020/UPSRTC-Bus-Tracking-App).
2. Visit [share.streamlit.io](https://share.streamlit.io) and authenticate with GitHub.
3. Click **New app**.
4. Configure the deployment settings:
   - **Repository:** `nikhilchaurasia2020/UPSRTC-Bus-Tracking-App`
   - **Branch:** `main`
   - **Main file path:** `app.py`
5. Click **Deploy!**

---

## Architecture & Data Flow

```text
User Browser (localStorage)
       │ (Auto-fills registration number)
       ▼
Streamlit Frontend (app.py)
       │ (POST request to Margdarshi endpoint)
       ▼
UPSRTC VLT Server (/php/getGpsLiveData.php)
       │ (Returns JSON telemetry packet)
       ▼
Parser & Filter Layer
       ├── Telemetry Extraction (Speed, Coordinates, Voltage, Heading)
       ├── Location Resolution (zone_name)
       └── PyDeck Visualizer + WhatsApp Template Generator
```

---

## Telemetry Fields Reference

| Field | Description |
| :--- | :--- |
| `regNum` / `RegNo` | Vehicle registration plate number |
| `latitude`, `longitude` | Current WGS-84 GPS coordinates |
| `speed` | Vehicle speed in km/h |
| `heading` | Orientation angle in degrees ($0^{\circ}$–$360^{\circ}$) |
| `ignition` | Engine status (`1` for ON, `0` for OFF) |
| `vehicle_status` | Status string: `live`, `stationary`, or `no_signal` |
| `zone_name` | Resolved location string (town, district, state) |
| `mainInputVoltage` | Alternator/vehicle battery voltage |
| `internalBatteryVoltage` | Tracker device internal backup battery |
| `depot_name` | Bus operational home depot |

---

## License

This project is licensed under the [MIT License](LICENSE).
