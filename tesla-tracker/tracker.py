import asyncio
import time
import teslapy
import gspread
import requests
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from math import radians, cos, sin, asin, sqrt
from dotenv import load_dotenv
load_dotenv()

# --- Config ---
TESLA_EMAIL = os.getenv("TESLA_EMAIL")
TESLA_TOKEN_CACHE = os.getenv("TESLA_TOKEN_CACHE", "/home/jacob/tesla-tracker/tesla_token.json")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")
SHEET_NAME = os.getenv("SHEET_NAME", "Tesla Tracker")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 60))

# Track trips
vehicle_states = {}

# --- Helper Functions ---

def init_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS_JSON, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    return sheet

def reverse_geocode(lat, lon):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        results = response.json().get('results')
        if results:
            return results[0]['formatted_address']
    return ""

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    requests.post(url, data=payload)

def haversine(lat1, lon1, lat2, lon2):
    # Calculate great circle distance between two points (miles)
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    miles = 3956 * c
    return miles

async def track_vehicle():
    with teslapy.Tesla(TESLA_EMAIL, cache_file=TESLA_TOKEN_CACHE) as tesla:
        if not tesla.authorized:
            print("Authorize via browser...")
            print(tesla.authorization_url(locale='en-US'))
            auth_code = input('Enter authorization code: ')
            tesla.fetch_token(authorization_response=auth_code)

        vehicles = tesla.vehicle_list()
        sheet = init_sheet()

        car_labels = [os.getenv("CAR_LABEL_1"), os.getenv("CAR_LABEL_2")]  # Updated names for vehicles

        last_label = {}
        last_lat = {}
        last_lon = {}
        last_battery = {}
        last_address = {}

        while True:
            for i, vehicle in enumerate(vehicles):
                label = None
                try:
                    # Set label as early as possible for error handling
                    vin = vehicle['vin'] if isinstance(vehicle, dict) and 'vin' in vehicle else getattr(vehicle, 'vin', '(unknown)')
                    label = car_labels[i] if i < len(car_labels) else f'Car {i+1}'
                    vehicle.sync_wake_up()
                    data = vehicle.get_vehicle_data()

                    drive_state = data['drive_state']
                    charge_state = data['charge_state']

                    lat = drive_state.get('latitude')
                    lon = drive_state.get('longitude')
                    speed = drive_state.get('speed')  # None if parked
                    battery = charge_state.get('battery_level')
                    timestamp = datetime.utcnow().isoformat()
                    vin = vehicle['vin']
                    address = reverse_geocode(lat, lon) if lat and lon else ""

                    # Only write to sheet if data is meaningfully different
                    should_log = True
                    distance_moved = None
                    battery_delta = None
                    if vin in last_lat and vin in last_lon and vin in last_battery:
                        distance_moved = haversine(last_lat[vin], last_lon[vin], lat, lon)
                        battery_delta = abs(battery - last_battery[vin])
                        if (distance_moved < 0.02 and battery_delta < 10):  # 0.02 miles ≈ 32 meters
                            should_log = False
                    if should_log:
                        sheet.append_row([timestamp, label, lat, lon, speed, battery, address])
                        print(f"Logged {label} at {timestamp} → {lat}, {lon}, {speed} mph, {battery}%, {address}")
                        last_label[vin] = label
                        last_lat[vin] = lat
                        last_lon[vin] = lon
                        last_battery[vin] = battery
                        last_address[vin] = address
                    else:
                        print(f"No significant change for {label}: distance_moved={distance_moved:.2f} mi, battery_delta={battery_delta}%, skipping log.")

                    # --- Save latest status to file ---
                    latest_status_path = os.getenv("LATEST_STATUS_PATH", '/opt/tesla-tracker/latest_status.json')
                    if 'latest_status' not in globals():
                        global latest_status
                        latest_status = {}
                    odometer = data['vehicle_state'].get('odometer')
                    charging_state = data['charge_state'].get('charging_state')
                    charger_power = data['charge_state'].get('charger_power')
                    inside_temp = data['climate_state'].get('inside_temp')
                    outside_temp = data['climate_state'].get('outside_temp')
                    locked = data['vehicle_state'].get('locked')
                    sentry_mode = data['vehicle_state'].get('sentry_mode')
                    software_version = data['vehicle_state'].get('software_version')
                    # Tire pressure (front left, front right, rear left, rear right)
                    tire_pressure = {
                        'fl': data['vehicle_state'].get('tpms_pressure_fl'),
                        'fr': data['vehicle_state'].get('tpms_pressure_fr'),
                        'rl': data['vehicle_state'].get('tpms_pressure_rl'),
                        'rr': data['vehicle_state'].get('tpms_pressure_rr'),
                    }
                    # Doors/windows open/closed
                    doors = {
                        'df': data['vehicle_state'].get('df'),
                        'dr': data['vehicle_state'].get('dr'),
                        'pf': data['vehicle_state'].get('pf'),
                        'pr': data['vehicle_state'].get('pr'),
                    }
                    windows = {
                        'fd_window': data['vehicle_state'].get('fd_window'),
                        'fp_window': data['vehicle_state'].get('fp_window'),
                        'rd_window': data['vehicle_state'].get('rd_window'),
                        'rp_window': data['vehicle_state'].get('rp_window'),
                    }
                    heading = data['drive_state'].get('heading')
                    notifications = data.get('notifications', [])

                    latest_status[vin] = {
                        'label': label,
                        'battery': battery,
                        'address': address,
                        'timestamp': timestamp,
                        'latitude': lat,
                        'longitude': lon,
                        'odometer': odometer,
                        'charging_state': charging_state,
                        'charger_power': charger_power,
                        'inside_temp': inside_temp,
                        'outside_temp': outside_temp,
                        'locked': locked,
                        'sentry_mode': sentry_mode,
                        'software_version': software_version,
                        'tire_pressure': tire_pressure,
                        'doors': doors,
                        'windows': windows,
                        'heading': heading,
                        'notifications': notifications
                    }
                    try:
                        with open(latest_status_path, 'w') as f:
                            json.dump(latest_status, f)
                    except Exception as e:
                        print(f"Error writing latest_status.json: {e}")

                    # --- Trip tracking logic ---
                    if vin not in vehicle_states:
                        vehicle_states[vin] = {'moving': False, 'trip_start_time': None, 'trip_start_latlon': None}

                    state = vehicle_states[vin]

                    if speed and speed > 5:
                        # Car is moving
                        if not state['moving']:
                            # New trip started
                            state['trip_start_time'] = datetime.utcnow()
                            state['trip_start_latlon'] = (lat, lon)
                            state['moving'] = True
                    else:
                        # Car is stopped
                        if state['moving']:
                            # Trip ended
                            trip_end_time = datetime.utcnow()
                            trip_duration = (trip_end_time - state['trip_start_time']).total_seconds() / 60.0  # minutes
                            start_lat, start_lon = state['trip_start_latlon']
                            start_address = reverse_geocode(start_lat, start_lon)
                            end_address = address
                            trip_miles = haversine(start_lat, start_lon, lat, lon)

                            message = f" {label} Trip ended\nDuration: {trip_duration:.1f} min\nDistance: {trip_miles:.1f} miles\nFrom: {start_address}\nTo: {end_address}"
                            send_telegram_message(message)
                            print(f"Trip summary sent for {label}")
                            state['moving'] = False

                except Exception as e:
                    print(f"Error tracking {label or '(unknown)'}: {e}")

            await asyncio.sleep(POLL_INTERVAL)

# --- Entrypoint ---
if __name__ == "__main__":
    asyncio.run(track_vehicle())
