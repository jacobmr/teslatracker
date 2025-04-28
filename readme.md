# Tesla Tracker + Telegram Status Bot

This project runs two lightweight Python services on a Raspberry Pi to:

- Track Tesla vehicle location, battery, and trip events
- Log data to a Google Sheet (including reverse-geocoded addresses)
- Send trip summaries to a Telegram bot
- Reply to `/status` commands via Telegram with latest vehicle data
- Support for multiple Tesla vehicles with customizable labels and emojis

Designed for headless operation via systemd. No commercial apps needed. Fully open and DIY.

![Tesla Tracker Banner](https://raw.githubusercontent.com/jacobmr/teslatracker/assets/banner.png)

---

## Features

### Real-time tracking of Tesla vehicles including location, battery level, and trip data
### Google Sheet integration for data logging with optional address reverse-geocoding
### Telegram bot commands for status updates and vehicle control
### Trip detection with automatic start/end notifications
### User management with admin-controlled access to the Telegram bot
### Multi-vehicle support with customizable labels and emojis
### Headless operation using systemd services
### Low resource usage suitable for Raspberry Pi deployment

---

## Components

### 1. `tracker.py`

#### Description

Authenticates to Tesla using `TeslaPy`
Polls all Tesla vehicles at configurable intervals
Logs:
  - Timestamp
  - Vehicle name (configurable via CAR_LABELS)
  - Latitude / Longitude
  - Speed (if moving)
  - Battery %
  - Human-readable location (via Google Maps Geocoding API)
Saves data into a Google Sheet
Saves latest status into a local JSON file (`latest_status.json`)
Detects trips (start/stop movement) and sends trip summaries to Telegram

### 2. `statusbot.py`

#### Description

Runs independently
Listens for Telegram commands:
  - `/status` - Get current vehicle status
  - User management commands (admin only)
Replies with current battery %, address, and timestamp for each car
Reads data from `latest_status.json`
Manages user access with admin approval system

---

## Project Structure

```plaintext
/tesla-tracker
  ├── tracker.py              # Main Tesla tracking script
  ├── statusbot.py            # Telegram bot for status and commands
  ├── creds.json              # Google Sheets API service account credentials
  ├── tesla_token.json        # TeslaPy cached tokens (auto-created)
  ├── latest_status.json      # Latest Tesla vehicle status (auto-updated)
  ├── .env                    # Environment variables configuration
  ├── allowed_users.json      # Authorized Telegram users
  ├── pending_adds.json       # Users awaiting approval
  ├── requirements.txt        # Python dependencies
  └── statusbot.service       # Systemd service file
```

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/jacobmr/teslatracker.git
cd teslatracker
```

### 2. Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the **Google Sheets API** and **Google Drive API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for and enable both APIs
4. Create a Service Account:
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Name your service account (e.g., "tesla-tracker")
   - Grant "Editor" role for Google Sheets
   - Create a key (JSON type) and download as `creds.json`
5. Create a Google Sheet:
   - Copy the included sample CSV (`Tesla Tracker - Sheet1 (1).csv`) to create your sheet
   - Share your Sheet with the service account email (it looks like `name@project.iam.gserviceaccount.com`)
   - Note the Sheet name (e.g., "Tesla Tracker")

**Do NOT commit your `creds.json` file to GitHub.**  
Place it in `tesla-tracker/creds.json`.

### 3. Google Sheet Setup

1. Create a Google Sheet with the following columns:

   ```plaintext
   Timestamp, Label, Latitude, Longitude, Speed, Battery, Address
   ```

2. **[Optional] Add Map Integration**:
   - Open your Google Sheet
   - Go to Extensions > Apps Script
   - Paste contents of the included `trackersheet.gs` script
   - Replace `YOUR_GOOGLE_MAPS_API_KEY` with your key from [Google Maps Platform](https://cloud.google.com/maps-platform/)
   - Save and authorize the script
   - This will add map images and address lookups to your sheet

### 4. Tesla API Setup

1. Create a `.env` file in the `tesla-tracker` directory with your Tesla credentials:

   ```makefile
   TESLA_EMAIL=your.email@example.com
   TESLA_TOKEN_CACHE=/path/to/tesla-tracker/tesla_token.json
   ```

2. The first time you run the tracker, it will prompt you to log in to your Tesla account
3. After successful login, your token will be cached in `tesla_token.json` for future use

### 5. Telegram Bot Setup

1. Create a new Telegram bot:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Use the `/newbot` command and follow the instructions
   - BotFather will give you a token (keep this private)

2. Find your Telegram Chat ID:
   - Message [@userinfobot](https://t.me/userinfobot) on Telegram
   - It will reply with your user ID

3. Add to your `.env` file:

   ```makefile
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   TELEGRAM_ADMIN_USER_ID=your_user_id_here
   ```

### 6. Complete Environment Configuration

Create or edit your `.env` file with all required variables:

```bash
# Tesla API credentials
TESLA_EMAIL=your.email@example.com
TESLA_TOKEN_CACHE=/path/to/tesla-tracker/tesla_token.json

# Telegram configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
TELEGRAM_ADMIN_USER_ID=your_user_id_here

# Google integration
GOOGLE_CREDS_JSON=/path/to/tesla-tracker/creds.json
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
SHEET_NAME=Tesla Tracker

# Vehicle configuration
CAR_LABELS=Car1,Car2
CAR_COLORS=🔵,⚪

# Application settings
LATEST_STATUS_FILE=/path/to/tesla-tracker/latest_status.json
POLL_INTERVAL=60
```

Adjust all paths to match your installation directory.

### 7. Install Dependencies

```bash
cd tesla-tracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The required dependencies are:

- teslapy
- gspread
- requests
- oauth2client
- python-dotenv

### 8. Run the Tracker and Status Bot

**For testing:**

```bash
# Start the tracker (in one terminal)
cd tesla-tracker
source venv/bin/activate
python tracker.py

# Start the status bot (in another terminal)
cd tesla-tracker
source venv/bin/activate
python statusbot.py
```

**For production (headless on Linux):**

1. Edit the provided `statusbot.service` file to match your installation paths
2. Create a similar service file for tracker.py
3. Copy both service files to `/etc/systemd/system/`
4. Enable and start the services:

```bash
sudo systemctl enable statusbot.service
sudo systemctl start statusbot.service
sudo systemctl enable tesla-tracker.service
sudo systemctl start tesla-tracker.service
```

---

## Troubleshooting

### Common Issues

#### Tesla API Authentication

- If you get authentication errors, delete `tesla_token.json` and restart the tracker to re-authenticate
- Tesla API rate limits can cause temporary failures; the app will retry automatically

#### Google Sheets Integration

- If data isn't being written to your sheet, verify:
  1. Your service account has Editor access to the sheet
  2. The sheet name in `.env` matches your actual sheet name exactly
  3. The `creds.json` file is valid and not corrupted

#### Telegram Bot Issues

- If you don't receive messages, ensure:
  1. You've messaged your bot at least once
  2. Your TELEGRAM_CHAT_ID is correct
  3. The bot token is valid

### Logs

- Check `statusbot_debug.log` for Telegram bot issues
- For systemd service issues: `sudo journalctl -u statusbot.service -f`

---

## Security

### Protecting Sensitive Data

- **NEVER commit sensitive files** to GitHub:
  - `.env` file with credentials
  - `creds.json` Google service account
  - `tesla_token.json` Tesla credentials

- The `.gitignore` file is pre-configured to exclude these files
- Consider restricting file permissions:

  ```bash
  chmod 600 .env creds.json tesla_token.json
  ```

### Data Breach Response

- If you accidentally committed sensitive information, immediately:
  1. Revoke and regenerate all affected credentials
  2. Use tools like BFG Repo-Cleaner to purge sensitive data from Git history

---

## Customization

### Common Customizations

- **Add new commands** by modifying `statusbot.py`
- **Change tracking frequency** by adjusting the POLL_INTERVAL in `.env`
- **Customize vehicle labels** and emojis using CAR_LABELS and CAR_COLORS in `.env`
- **Extend data logging** by adding additional fields to `tracker.py` and your Google Sheet

---

## Contributing

Pull requests are welcome! Some ideas for contributions:

- Additional Tesla API commands (climate control, door locks, etc.)
- Enhanced visualizations in Google Sheets
- Better trip statistics and reporting
- Fuel savings calculator based on trip data

Please open an issue first to discuss major changes.

---

## License

MIT License  
 Jacob Reider, 2025

---

## Credits

- [TeslaPy](https://github.com/tdorssers/TeslaPy) - Python Tesla API interface
- [Google Sheets API](https://developers.google.com/sheets/api) - Data storage and visualization
- [Telegram Bot API](https://core.telegram.org/bots/api) - Command interface and notifications

---

## Questions or Issues?

Open an issue on GitHub or contact [jacob@reider.us](mailto:jacob@reider.us).