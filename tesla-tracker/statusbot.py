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
                            # Try to extract latitude and longitude from address if available
                            lat = data.get('latitude')
                            lon = data.get('longitude')
                            map_link = ""
                            if lat is not None and lon is not None:
                                map_link = f"[Google Maps](https://maps.google.com/?q={lat},{lon})"
                                # Send a map location first
                                send_telegram_location(lat, lon)
                            status_message += f"{data['label']}: {data['battery']}% @ {data['address']} (as of {data['timestamp']})\n{map_link}\n"
                    else:
                        status_message = "No status available yet."

                    send_telegram_message(status_message)
        except Exception as e:
            print(f"Error polling Telegram: {e}")

        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    poll_telegram_commands()
