# Tesla Tracker + Telegram Status Bot

This project runs two lightweight Python services on a Raspberry Pi to:
- Track Tesla vehicle location, battery, and trip events
- Log data to a Google Sheet (including reverse-geocoded addresses)
- Send trip summaries to a Telegram bot
- Reply to `/status` commands via Telegram with latest vehicle data

Designed for headless operation via systemd. No commercial apps needed. Fully open and DIY.

---

## 🚗 Components

### 1. `tracker.py`
- Authenticates to Tesla using `TeslaPy`
- Polls both Tesla vehicles every minute
- Logs:
  - Timestamp
  - Vehicle name ("Car1", "Car2")
  - Latitude / Longitude
  - Speed (if moving)
  - Battery %
  - Human-readable location (via Google Maps Geocoding API)
- Saves data into a Google Sheet
- Saves latest status into a local JSON file (`latest_status.json`)
- Detects trips (start/stop movement) and sends trip summaries to Telegram

### 2. `statusbot.py`
- Runs independently
- Listens for `/status` Telegram commands
- Replies with current battery %, address, and timestamp for each car
- Reads data from `latest_status.json`

---

## 📋 Project Structure

```plaintext
/tesla-tracker
  ├── tracker.py
  ├── statusbot.py
  ├── creds.json              # Google Sheets API service account credentials
  ├── tesla_token.json         # TeslaPy cached tokens (auto-created after first auth)
  ├── latest_status.json       # Latest Tesla vehicle status (auto-updated)
  ├── venv/                    # Python virtual environment
```

# Tesla Tracker

A headless, open-source Tesla vehicle logger and Telegram status bot.  
Tracks your Tesla’s location, status, and logs data to a Google Sheet, with live updates and commands via Telegram.

---

## Features

- Logs vehicle location, battery, speed, and more to Google Sheets.
- Sends live status and location (with map links) to Telegram.
- Rich /status command: battery, odometer, charging, climate, security, tire pressure, doors/windows, heading, and more.
- Easily extensible for interactive commands (lock/unlock, climate, etc.).
- Designed to run headlessly (e.g., on a Raspberry Pi).

---

## Quick Start

### 1. Clone the Repo

```sh
git clone https://github.com/jacobmr/teslatracker.git
cd teslatracker
```

---

### 2. Google Cloud Setup

- Go to [Google Cloud Console](https://console.cloud.google.com/).
- Create a new project.
- Enable the **Google Sheets API** and **Google Drive API**.
- Create a **Service Account** and download the `creds.json` file.
- Share your Google Sheet with the service account email.

**Do NOT commit your `creds.json` file.**  
Place it in `tesla-tracker/creds.json`.

---

### 3. Google Sheet Setup

- Copy the included sample CSV (`Tesla Tracker - Sheet1 (1).csv`) to create your own Google Sheet.
- Columns should be:  
  `Timestamp, Label, Latitude, Longitude, Speed, Battery, Address`
- [Optional] Use the included Google Apps Script (`trackersheet.gs`) in your sheet for address lookup and map images:
  1. Open your Google Sheet.
  2. Extensions > Apps Script.
  3. Paste contents of `trackersheet.gs`.
  4. Replace `YOUR_GOOGLE_MAPS_API_KEY` with your own key.
  5. Save and run the script.

---

### 4. Tesla API Setup

- Create a Tesla account at [Tesla.com](https://www.tesla.com/).
- You’ll need your account email and password for first-time auth.
- The bot uses [TeslaPy](https://teslapy.readthedocs.io/) for API access.

---

### 5. Telegram Bot Setup

- Create a bot at [BotFather](https://t.me/botfather) on Telegram.
- Get your bot token and chat ID.
- Set these as environment variables or edit directly in `statusbot.py` and `tracker.py`.

---

### 6. Install Dependencies

```sh
cd tesla-tracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### 7. Run the Tracker and Status Bot

- Start the tracker:
  ```sh
  python tracker.py
  ```
- Start the Telegram status bot:
  ```sh
  python statusbot.py
  ```
- [Optional] Use systemd service files for auto-start on boot (`statusbot.service`, `tesla-tracker.service`).

---

## Security

- **Never** commit your `creds.json` or Tesla tokens.
- [.gitignore](.gitignore) is pre-configured to help.
- If you accidentally committed secrets, revoke and regenerate them.

---

## Customization

- Edit `tracker.py` and `statusbot.py` to add new features (e.g., interactive commands).
- Use the Apps Script to enhance your Google Sheet with maps and addresses.

---

## Contributing

Pull requests welcome!  
Open an issue or PR for improvements, bug fixes, or new features.

---

## License

MIT License.  
(c) Jacob Reider, 2025

---

## Credits

- [TeslaPy](https://github.com/tdorssers/TeslaPy)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [Telegram Bot API](https://core.telegram.org/bots/api)

---

**Questions?**  
Open an issue on GitHub or email jacob@reider.us