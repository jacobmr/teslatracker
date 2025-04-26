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

```plaintextsudo journalctl -u statusbot.service -f
/tesla-tracker
  ├── tracker.py
  ├── statusbot.py
  ├── creds.json              # Google Sheets API service account credentials
  ├── tesla_token.json         # TeslaPy cached tokens (auto-created after first auth)
  ├── latest_status.json       # Latest Tesla vehicle status (auto-updated)
  ├── venv/                    # Python virtual environment