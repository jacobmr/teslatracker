import time
import json
import requests

# --- Config ---
TELEGRAM_BOT_TOKEN = "7748644682:AAHYHAtgu8Xf5kRve_p5JdZRX-qQZM5pN7E"
TELEGRAM_CHAT_ID = "6269997804"
LATEST_STATUS_FILE = '/home/jacob/tesla-tracker/latest_status.json'

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
    # Convert from bar to psi (1 bar ≈ 14.5 psi)
    psi = {k: (round(v * 14.5) if v else None) for k, v in tp.items()}
    # Only show if any value is present
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

                if message == "/status":
                    try:
                        with open(LATEST_STATUS_FILE, 'r') as f:
                            status_data = json.load(f)
                    except Exception:
                        status_data = {}

                    if status_data:
                        status_message = "\U0001F697 Tesla Status:\n"
                        for vin, data in status_data.items():
                            lat = data.get('latitude')
                            lon = data.get('longitude')
                            map_link = ""
                            if lat is not None and lon is not None:
                                map_link = f"[Google Maps](https://maps.google.com/?q={lat},{lon})"
                                send_telegram_location(lat, lon)
                            # Compose improved, normalized status
                            status_message += f"🚗 *{data['label']}*\n"
                            status_message += f"🔋 Battery: {data.get('battery', 'N/A')}%   |   Odometer: {fmt_odometer(data.get('odometer'))} mi\n"
                            status_message += f"⚡ Charging: {data.get('charging_state', 'N/A')} ({data.get('charger_power', 'N/A')} kW)\n"
                            status_message += f"🌡️ Inside: {fmt_temp(data.get('inside_temp'))}   |   Outside: {fmt_temp(data.get('outside_temp'))}\n"
                            status_message += f"🔒 Locked: {fmt_bool(data.get('locked'))}   |   Sentry: {fmt_bool(data.get('sentry_mode'))}\n"
                            status_message += f"🧑‍💻 Software: {data.get('software_version', 'N/A')}\n"
                            # Tire pressure (convert bar to psi)
                            tp = data.get('tire_pressure', {})
                            status_message += f"🛞 Tire Pressure (psi): {fmt_tire_pressure(tp)}\n"
                            # Doors/windows
                            doors = data.get('doors', {})
                            windows = data.get('windows', {})
                            status_message += f"🚪 Doors: {summarize_doors(doors)}\n"
                            status_message += f"🪟 Windows: {summarize_windows(windows)}\n"
                            status_message += f"🧭 Heading: {data.get('heading', 'N/A')}°\n"
                            # Notifications/alerts
                            notes = data.get('notifications', [])
                            if notes:
                                status_message += "⚠️ Alerts: " + ", ".join([str(n) for n in notes]) + "\n"
                            status_message += f"📍 {data.get('address', 'N/A')}\n"
                            status_message += f"🕒 {data.get('timestamp', 'N/A')}\n"
                            if map_link:
                                status_message += f"{map_link}\n"
                            status_message += "\n"
                    else:
                        status_message = "No status available yet."

                    send_telegram_message(status_message)
        except Exception as e:
            print(f"Error polling Telegram: {e}")

        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    poll_telegram_commands()
