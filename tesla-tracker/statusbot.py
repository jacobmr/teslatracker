print("StatusBot version 2025-04-27-1 started", flush=True)
import sys
sys.stdout = open("statusbot_debug.log", "a")
sys.stderr = sys.stdout
print("StatusBot started", flush=True)
import time
import json
import requests
import os
import re
from dotenv import load_dotenv
load_dotenv()
print(f"[DEBUG] TELEGRAM_CHAT_ID at startup: {os.getenv('TELEGRAM_CHAT_ID')}", flush=True)
print(f"[DEBUG] TESLA_EMAIL: {os.getenv('TESLA_EMAIL')}", flush=True)
print(f"[DEBUG] LATEST_STATUS_FILE: {os.getenv('LATEST_STATUS_FILE')}", flush=True)
print(f"[DEBUG] TESLA_TOKEN_CACHE: {os.getenv('TESLA_TOKEN_CACHE')}", flush=True)
print(f"[DEBUG] GOOGLE_CREDS_JSON: {os.getenv('GOOGLE_CREDS_JSON')}", flush=True)
print(f"[DEBUG] CAR_LABELS: {os.getenv('CAR_LABELS')}", flush=True)
print(f"[DEBUG] CAR_COLORS: {os.getenv('CAR_COLORS')}", flush=True)
print(f"[DEBUG] SHEET_NAME: {os.getenv('SHEET_NAME')}", flush=True)

# --- Config ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LATEST_STATUS_FILE = os.getenv("LATEST_STATUS_FILE")
TESLA_EMAIL = os.getenv("TESLA_EMAIL")
TESLA_TOKEN_CACHE = os.getenv("TESLA_TOKEN_CACHE")
CAR_LABELS = [s.strip() for s in os.getenv("CAR_LABELS", "Car 1,Car 2").split(",")]
CAR_COLORS = [s.strip() for s in os.getenv("CAR_COLORS", "🔵,⚪").split(",")]

pending_actions = {}

# --- Persistent update_id storage ---
LAST_UPDATE_ID_FILE = "last_update_id.txt"

def load_last_update_id():
    try:
        with open(LAST_UPDATE_ID_FILE, "r") as f:
            return int(f.read().strip())
    except Exception:
        return None

def save_last_update_id(update_id):
    try:
        with open(LAST_UPDATE_ID_FILE, "w") as f:
            f.write(str(update_id))
    except Exception as e:
        print(f"[ERROR] Could not save last_update_id: {e}", flush=True)

# --- Telegram send helpers ---
def send_telegram_message(message, markdown=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }
    if markdown:
        payload["parse_mode"] = "Markdown"
    print(f"[DEBUG] Telegram payload: {payload}", flush=True)
    try:
        resp = requests.post(url, data=payload)
        if resp.status_code != 200:
            print(f"[ERROR] Failed to send Telegram message: {resp.status_code} {resp.text}", flush=True)
        else:
            print(f"[DEBUG] Sent Telegram message: {message}", flush=True)
    except Exception as e:
        print(f"[ERROR] Exception sending Telegram message: {e}", flush=True)

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
        tesla_email = os.getenv("TESLA_EMAIL")
        tesla_token_cache = os.getenv("TESLA_TOKEN_CACHE")
        if not tesla_email:
            return False, "Tesla API error: email is not set"
        if not tesla_token_cache:
            return False, "Tesla API error: token cache path is not set"
        import teslapy
        with teslapy.Tesla(tesla_email, cache_file=tesla_token_cache) as tesla:
            vehicles = tesla.vehicle_list()
            if car_index < 0 or car_index >= len(vehicles):
                return False, "Invalid car selection."
            vehicle = vehicles[car_index]
            vehicle.sync_wake_up()
            if action == "lock":
                success = vehicle.command('LOCK')
                return success, "Lock command sent." if success else "Failed to lock."
            elif action == "close":
                success = vehicle.command('window_control', command='close')
                return success, "Close windows command sent." if success else "Failed to close windows."
            elif action == "sentry":
                success = vehicle.command('set_sentry_mode', on=True)
                return success, "Sentry mode enabled." if success else "Failed to enable sentry mode."
            else:
                return False, "Unknown action."
    except Exception as e:
        return False, f"Tesla API error: {e}"

# --- Allowed users management ---
ALLOWED_USERS_FILE = "allowed_users.json"
PENDING_ADDS_FILE = "pending_adds.json"

def load_allowed_users():
    try:
        with open(ALLOWED_USERS_FILE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_allowed_users(users):
    try:
        with open(ALLOWED_USERS_FILE, "w") as f:
            json.dump(list(users), f)
    except Exception as e:
        print(f"[ERROR] Could not save allowed users: {e}", flush=True)

def load_pending_adds():
    try:
        with open(PENDING_ADDS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_pending_adds(pending):
    try:
        with open(PENDING_ADDS_FILE, "w") as f:
            json.dump(pending, f)
    except Exception as e:
        print(f"[ERROR] Could not save pending adds: {e}", flush=True)

# --- Main polling loop ---
def poll_telegram_commands():
    print("[DEBUG] poll_telegram_commands loop started", flush=True)
    last_update_id = load_last_update_id()
    processed_update_ids = set()
    allowed_users = load_allowed_users()
    pending_adds = load_pending_adds()
    pending_requests = {}  # user_id -> {name, username}
    ADMIN_USER_ID = int(os.getenv("TELEGRAM_ADMIN_USER_ID", "6269997804"))  # Set your own user ID here
    while True:
        print("[DEBUG] poll_telegram_commands loop alive", flush=True)
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            if last_update_id is not None:
                url += f"?offset={last_update_id + 1}"
            response = requests.get(url)
            updates = response.json().get('result', [])
            for update in updates:
                update_id = update['update_id']
                if update_id in processed_update_ids:
                    continue
                processed_update_ids.add(update_id)
                try:
                    message = update.get('message', {}).get('text', '')
                    user_id = update.get('message', {}).get('from', {}).get('id')
                    username = update.get('message', {}).get('from', {}).get('username')
                    first_name = update.get('message', {}).get('from', {}).get('first_name', '')
                    last_name = update.get('message', {}).get('from', {}).get('last_name', '')
                    full_name = f"{first_name} {last_name}".strip()
                    print(f"[DEBUG] Received message: '{message}' from user {user_id} (update: {update})", flush=True)

                    # --- Handle admin approval for pending requests ---
                    if user_id == ADMIN_USER_ID and message.lower().startswith("yes "):
                        try:
                            approve_id = int(message.strip().split()[1])
                        except Exception:
                            send_telegram_message("Usage: yes <user_id>")
                            continue
                        if approve_id in pending_requests:
                            allowed_users.add(approve_id)
                            save_allowed_users(allowed_users)
                            user_info = pending_requests.pop(approve_id)
                            send_telegram_message(f"Access granted to {user_info['full_name']} (@{user_info['username']}) [{approve_id}].")
                            # Notify the newly approved user
                            notify_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                            notify_payload = {"chat_id": approve_id, "text": "You have been approved to use Tesla Tracker!"}
                            requests.post(notify_url, data=notify_payload)
                        else:
                            send_telegram_message(f"No pending request for user_id {approve_id}.")
                        continue

                    # --- Handle /add command (admin only) ---
                    if user_id == ADMIN_USER_ID and message.lower().startswith("/add"):
                        match = re.search(r"@([A-Za-z0-9_]+)", message)
                        if match:
                            pending_username = match.group(1)
                            pending_adds[pending_username.lower()] = True
                            save_pending_adds(pending_adds)
                            send_telegram_message(f"Ask @{pending_username} to send me any message to complete registration.")
                        else:
                            send_telegram_message("Usage: /add @username (ask the user to send me any message after)")
                        continue

                    # --- Handle new user registration via /add ---
                    if username and username.lower() in pending_adds:
                        allowed_users.add(user_id)
                        save_allowed_users(allowed_users)
                        del pending_adds[username.lower()]
                        save_pending_adds(pending_adds)
                        send_telegram_message(f"Welcome, @{username}! You now have access to Tesla Tracker.")
                        # Notify admin
                        send_telegram_message(f"@{username} ({user_id}) has been added to allowed users.", markdown=False)
                        continue

                    # --- Only allow commands from allowed users or admin ---
                    if user_id not in allowed_users and user_id != ADMIN_USER_ID:
                        # Notify the admin of the access request
                        if user_id not in pending_requests:
                            pending_requests[user_id] = {"full_name": full_name, "username": username or "(none)"}
                            send_telegram_message(f"User {full_name} (@{username or 'none'}) [{user_id}] has requested access. Reply with 'yes {user_id}' to approve.")
                        # Notify the user
                        send_telegram_message("You are not authorized to use this bot. The admin has been notified of your request.")
                        continue

                    # Handle pending action
                    if user_id in pending_actions:
                        action = pending_actions[user_id]
                        if message.strip() in ["1", "2"]:
                            car_index = int(message.strip()) - 1
                            try:
                                success, result_msg = perform_tesla_action(car_index, action)
                                print(f"[DEBUG] Tesla action result_msg: {result_msg}", flush=True)
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
                                    send_telegram_message(status_message, markdown=True)
                                except Exception as e:
                                    send_telegram_message(f"Could not load status: {e}")
                            finally:
                                if user_id in pending_actions:
                                    del pending_actions[user_id]
                            continue
                        else:
                            send_telegram_message("Please reply with 1 for Car 1 or 2 for Car 2.")
                            continue
                    # Handle new commands
                    if message == "/status":
                        print("[DEBUG] Entered /status command handler", flush=True)
                        try:
                            with open(LATEST_STATUS_FILE, 'r') as f:
                                status_data = json.load(f)
                            status_message = ""
                            for idx, (vin, data) in enumerate(status_data.items()):
                                lat = data.get('latitude')
                                lon = data.get('longitude')
                                map_link = ""
                                if lat is not None and lon is not None:
                                    map_link = f"[Google Maps](https://maps.google.com/?q={lat},{lon})"
                                    send_telegram_location(lat, lon)
                                color_emoji = CAR_COLORS[idx] if idx < len(CAR_COLORS) else ''
                                status_message += f"🚗 {color_emoji} *{data['label']}*\n"
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
                        send_telegram_message(status_message, markdown=True)
                    # --- Direct lock commands ---
                    elif message.startswith("/lock") and len(message) > 5 and message[5:].isdigit():
                        car_index = int(message[5:]) - 1
                        if car_index in [0, 1]:
                            success, result_msg = perform_tesla_action(car_index, "lock")
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
                                send_telegram_message(status_message, markdown=True)
                            except Exception as e:
                                send_telegram_message(f"Could not load status: {e}")
                            return
                    # --- Direct close commands ---
                    elif message.startswith("/close") and len(message) > 6 and message[6:].isdigit():
                        car_index = int(message[6:]) - 1
                        if car_index in [0, 1]:
                            success, result_msg = perform_tesla_action(car_index, "close")
                            send_telegram_message(result_msg)
                            try:
                                with open(LATEST_STATUS_FILE, 'r') as f:
                                    status_data = json.load(f)
                                data = list(status_data.values())[car_index]
                                status_message = f"Status for {CAR_LABELS[car_index]}:\n"
                                status_message += f"🔋 Battery: {data.get('battery', 'N/A')}%   |   Odometer: {fmt_odometer(data.get('odometer'))} mi\n"
                                status_message += f"⚡ Charging: {data.get('charging_state', 'N/A')} ({data.get('charger_power', 'N/A')} kW)\n"
                                status_message += f"🌡️ Inside: {fmt_temp(data.get('inside_temp'))}   |   Outside: {fmt_temp(data.get('outside_temp'))}\n"
                                status_message += f"🔒 Locked: {fmt_bool(data.get('locked'))}   |   Sentry: {fmt_bool(data.get('sentry_mode'))}\n"
                                send_telegram_message(status_message, markdown=True)
                            except Exception as e:
                                send_telegram_message(f"Could not load status: {e}")
                            return
                    # --- Direct sentry commands ---
                    elif message.startswith("/sentry") and len(message) > 7 and message[7:].isdigit():
                        car_index = int(message[7:]) - 1
                        if car_index in [0, 1]:
                            success, result_msg = perform_tesla_action(car_index, "sentry")
                            send_telegram_message(result_msg)
                            try:
                                with open(LATEST_STATUS_FILE, 'r') as f:
                                    status_data = json.load(f)
                                data = list(status_data.values())[car_index]
                                status_message = f"Status for {CAR_LABELS[car_index]}:\n"
                                status_message += f"🔋 Battery: {data.get('battery', 'N/A')}%   |   Odometer: {fmt_odometer(data.get('odometer'))} mi\n"
                                status_message += f"⚡ Charging: {data.get('charging_state', 'N/A')} ({data.get('charger_power', 'N/A')} kW)\n"
                                status_message += f"🌡️ Inside: {fmt_temp(data.get('inside_temp'))}   |   Outside: {fmt_temp(data.get('outside_temp'))}\n"
                                status_message += f"🔒 Locked: {fmt_bool(data.get('locked'))}   |   Sentry: {fmt_bool(data.get('sentry_mode'))}\n"
                                send_telegram_message(status_message, markdown=True)
                            except Exception as e:
                                send_telegram_message(f"Could not load status: {e}")
                            return
                    elif message == "/lock":
                        print("[DEBUG] Entered /lock command handler", flush=True)
                        pending_actions[user_id] = "lock"
                        send_telegram_message("Which car? (1 for Car 1, 2 for Car 2)")
                    elif message == "/close":
                        print("[DEBUG] Entered /close command handler", flush=True)
                        pending_actions[user_id] = "close"
                        send_telegram_message("Which car? (1 for Car 1, 2 for Car 2)")
                    elif message == "/sentry":
                        print("[DEBUG] Entered /sentry command handler", flush=True)
                        pending_actions[user_id] = "sentry"
                        send_telegram_message("Which car? (1 for Car 1, 2 for Car 2)")
                    # --- Help command ---
                    elif message == "/help":
                        help_message = (
                            "*Tesla Tracker Bot Help*\n"
                            "\n"
                            "/status or /status# — Show the status of all vehicles.\n"
                            "/lock or /lock# — Lock a car (prompt or specify 1=Car 1, 2=Car 2).\n"
                            "/lock1 — Lock Car 1 directly.\n"
                            "/lock2 — Lock Car 2 directly.\n"
                            "/close or /close# — Close all windows (prompt or specify car).\n"
                            "/sentry or /sentry# — Enable sentry mode (prompt or specify car).\n"
                            "/help — Show this help message.\n"
                            "\n"
                            "Reply with 1 for Car 1 or 2 for Car 2 when prompted.\n"
                            "You can also use the # suffix (e.g., /lock1, /close2, /sentry1) to act on a specific car without a prompt."
                        )
                        send_telegram_message(help_message, markdown=True)
                finally:
                    last_update_id = update_id
                    save_last_update_id(last_update_id)
        except Exception as e:
            print(f"[ERROR] Exception in poll_telegram_commands: {e}", flush=True)
        time.sleep(30)

if __name__ == "__main__":
    import teslapy
    poll_telegram_commands()
