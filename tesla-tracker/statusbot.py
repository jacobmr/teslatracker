import sys
sys.stdout = open("statusbot_debug.log", "a")
sys.stderr = sys.stdout
print("StatusBot started")
import time
import json
import requests
import os
from dotenv import load_dotenv
load_dotenv()

import teslapy

# --- Config ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LATEST_STATUS_FILE = os.getenv("LATEST_STATUS_FILE")
TESLA_EMAIL = os.getenv("TESLA_EMAIL")
TESLA_TOKEN_CACHE = os.getenv("TESLA_TOKEN_CACHE")
CAR_LABELS = [s.strip() for s in os.getenv("CAR_LABELS", "Alicia,Jacob").split(",")]

pending_actions = {}

# --- Telegram send helpers ---
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def send_telegram_location(lat, lon):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendLocation"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "latitude": lat,
        "longitude": lon
    }
    requests.post(url, data=payload)

# --- Helper Formatting Functions ---
def fmt_bool(val):
    return "Yes" if val else "No"
def fmt_temp(val):
    return f"{round(val)}°" if val is not None else "N/A"
def fmt_odometer(val):
    return f"{int(round(val)):,}" if val is not None else "N/A"
def fmt_tire_pressure(tp):
    psi = {k: (round(v * 14.5) if v else None) for k, v in tp.items()}
    if any(v for v in psi.values()):
        return " | ".join([f"{k.upper()} {v if v else 'N/A'}" for k, v in psi.items()])
    return "N/A"
def summarize_doors(doors):
    if not doors or all(v == 0 or v is None for v in doors.values()):
        return "All Closed"
    open_doors = [k.upper() for k,v in doors.items() if v]
    return ", ".join(open_doors) + " Open"
def summarize_windows(windows):
    if not windows or all(v == 0 or v is None for v in windows.values()):
        return "All Closed"
    open_windows = [k.upper() for k,v in windows.items() if v]
    return ", ".join(open_windows) + " Open"

# --- Tesla API action helpers ---
def perform_tesla_action(car_index, action):
    try:
        with teslapy.Tesla(TESLA_EMAIL, cache_file=TESLA_TOKEN_CACHE) as tesla:
            vehicles = tesla.vehicle_list()
            if car_index < 0 or car_index >= len(vehicles):
                return False, "Invalid car selection."
            vehicle = vehicles[car_index]
            vehicle.sync_wake_up()
            if action == "lock":
                resp = vehicle.command('door_lock')
                return resp['response']['result'], "Lock command sent." if resp['response']['result'] else "Failed to lock."
            elif action == "close":
                resp = vehicle.command('window_control', command='close')
                return resp['response']['result'], "Close windows command sent." if resp['response']['result'] else "Failed to close windows."
            elif action == "sentry":
                resp = vehicle.command('set_sentry_mode', on=True)
                return resp['response']['result'], "Sentry mode enabled." if resp['response']['result'] else "Failed to enable sentry mode."
            else:
                return False, "Unknown action."
    except Exception as e:
        return False, f"Tesla API error: {e}"

# --- Main polling loop ---
def poll_telegram_commands():
    last_update_id = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            if last_update_id:
                url += f"?offset={last_update_id + 1}"
            response = requests.get(url)
            updates = response.json().get('result', [])
            for update in updates:
                last_update_id = update['update_id']
                message = update.get('message', {}).get('text', '')
                user_id = update.get('message', {}).get('from', {}).get('id')
                # Handle pending action
                if user_id in pending_actions:
                    action = pending_actions[user_id]
                    if message.strip() in ["1", "2"]:
                        car_index = int(message.strip()) - 1
                        success, result_msg = perform_tesla_action(car_index, action)
                        send_telegram_message(result_msg)
                        # After action, send status
                        try:
                            with open(LATEST_STATUS_FILE, 'r') as f:
                                status_data = json.load(f)
                            data = list(status_data.values())[car_index]
                            status_message = f"Status for {CAR_LABELS[car_index]}:\n"
                            status_message += f"🔋 Battery: {data.get('battery', 'N/A')}%   |   Odometer: {fmt_odometer(data.get('odometer'))} mi\n"
                            status_message += f"⚡ Charging: {data.get('charging_state', 'N/A')} ({data.get('charger_power', 'N/A')} kW)\n"
                            status_message += f"🌡️ Inside: {fmt_temp(data.get('inside_temp'))}   |   Outside: {fmt_temp(data.get('outside_temp'))}\n"
                            status_message += f"🔒 Locked: {fmt_bool(data.get('locked'))}   |   Sentry: {fmt_bool(data.get('sentry_mode'))}\n"
                            send_telegram_message(status_message)
                        except Exception as e:
                            send_telegram_message(f"Could not load status: {e}")
                        del pending_actions[user_id]
                        continue
                    else:
                        send_telegram_message("Please reply with 1 for Alicia or 2 for Jacob.")
                        continue
                # Handle new commands
                if message == "/status":
                    try:
                        with open(LATEST_STATUS_FILE, 'r') as f:
                            status_data = json.load(f)
                        status_message = ""
                        for vin, data in status_data.items():
                            lat = data.get('latitude')
                            lon = data.get('longitude')
                            map_link = ""
                            if lat is not None and lon is not None:
                                map_link = f"[Google Maps](https://maps.google.com/?q={lat},{lon})"
                                send_telegram_location(lat, lon)
                            status_message += f"🚗 *{data['label']}*\n"
                            status_message += f"🔋 Battery: {data.get('battery', 'N/A')}%   |   Odometer: {fmt_odometer(data.get('odometer'))} mi\n"
                            status_message += f"⚡ Charging: {data.get('charging_state', 'N/A')} ({data.get('charger_power', 'N/A')} kW)\n"
                            status_message += f"🌡️ Inside: {fmt_temp(data.get('inside_temp'))}   |   Outside: {fmt_temp(data.get('outside_temp'))}\n"
                            status_message += f"🔒 Locked: {fmt_bool(data.get('locked'))}   |   Sentry: {fmt_bool(data.get('sentry_mode'))}\n"
                            status_message += f"🧑‍💻 Software: {data.get('software_version', 'N/A')}\n"
                            tp = data.get('tire_pressure', {})
                            status_message += f"🛞 Tire Pressure (psi): {fmt_tire_pressure(tp)}\n"
                            doors = data.get('doors', {})
                            windows = data.get('windows', {})
                            status_message += f"🚪 Doors: {summarize_doors(doors)}\n"
                            status_message += f"🪟 Windows: {summarize_windows(windows)}\n"
                            status_message += f"🧭 Heading: {data.get('heading', 'N/A')}°\n"
                            notes = data.get('notifications', [])
                            if notes:
                                status_message += "⚠️ Alerts: " + ", ".join([str(n) for n in notes]) + "\n"
                            status_message += f"📍 {data.get('address', 'N/A')}\n"
                            status_message += f"🕒 {data.get('timestamp', 'N/A')}\n"
                            if map_link:
                                status_message += f"{map_link}\n"
                            status_message += "\n"
                    except Exception as e:
                        status_message = f"Error reading status: {e}"
                    send_telegram_message(status_message)
                elif message == "/lock":
                    pending_actions[user_id] = "lock"
                    send_telegram_message("Which car? (1 for Alicia, 2 for Jacob)")
                elif message == "/close":
                    pending_actions[user_id] = "close"
                    send_telegram_message("Which car? (1 for Alicia, 2 for Jacob)")
                elif message == "/sentry":
                    pending_actions[user_id] = "sentry"
                    send_telegram_message("Which car? (1 for Alicia, 2 for Jacob)")
        except Exception as e:
            print(f"Error polling Telegram: {e}")
        time.sleep(30)

if __name__ == "__main__":
    poll_telegram_commands()
