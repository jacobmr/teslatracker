# TeslaTracker

TeslaTracker is a personal project for tracking Tesla vehicle data using a Raspberry Pi. This project serves as a proof-of-concept for the commercial EVTrak service.

## Overview

TeslaTracker connects to the Tesla API to collect vehicle data, track trips, and store information locally on a Raspberry Pi. It provides insights into vehicle usage, charging patterns, and travel history.

## Features

- Tesla API integration for vehicle data collection
- Trip tracking and distance calculation
- Local data storage on Raspberry Pi
- Basic reporting and visualization
- Telegram bot integration for notifications

## Technical Stack

- **Language**: Python
- **Database**: SQLite
- **Hardware**: Raspberry Pi
- **Notifications**: Telegram API

## Setup

1. Clone this repository to your Raspberry Pi
2. Install dependencies: `pip install -r requirements.txt`
3. Configure your Tesla API credentials in `.env`
4. Run the tracker: `python tesla_tracker.py`

## Development

This project is maintained by Jacob Reider (jacob@reider.us) as a personal tool and proof-of-concept.

## Related Projects

This project served as the inspiration for [EVTrak](https://github.com/jacobmr/evtrak), a commercial service that helps Oregon EV owners track mileage and automatically file for OReGO road usage charge refunds.

---

*Note: This is a personal project and not intended for commercial use. For a commercial solution, see the EVTrak project.*