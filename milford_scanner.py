"""Milford Track DOC availability scanner.
I am making this script to check for DOC availabilty on the Milford track after cancellations.
Has to have all 3 huts available. 
"""

import json
from pathlib import Path
import logging
import sys
from datetime import date, datetime
from datetime import timedelta


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json" # file you would make with your own info
EXAMPLE_CONFIG_PATH = BASE_DIR / "config.example.json"  #the example to follow
LOG_PATH = BASE_DIR / "milford_scanner.log" #Makes a file that tracks scanning history for records
STATE_PATH = BASE_DIR / "scanner_state.json" #Tracks the last status email time and any dates that are alerted


def load_json(path: Path):     #Read JSON and returns parsed data
    if not path.exists():
        raise FileNotFoundError(f"{path.name} was not found.")
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(): #Load the private config if it exists, otherwise load the example config, make sure you make your own configuration file if you want to use this
    path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH
    return load_json(path)

def setup_logging(): #Writes the messages in the terminal and the log file (see above)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

def parse_date(s: str) -> date: #Converts a YYYY-MM-DD into an object
    return datetime.strptime(s, "%Y-%m-%d").date()


def yyyy_mm_dd(d: date) -> str: #Formats objet from above as YYYY-MM-DD
    return d.strftime("%Y-%m-%d")

def weekday_name_from_text(date_text: str) -> str: #Returns weekday name for the date
    return datetime.strptime(date_text, "%Y-%m-%d").strftime("%A")

def save_json(path: Path, data):
    """Write JSON data in a readable format."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_state():
    """Load alert history so the scanner does not email repeatedly."""
    if STATE_PATH.exists():
        return load_json(STATE_PATH)
    return {"alerts": {}}

def should_alert(state, start_date_text, cooldown_hours): #Date hasn't been alerted during cooldown period (can be whatever time period)
    prior = state.get("alerts", {}).get(start_date_text)
    if not prior:
        return True

    prior_time = datetime.fromisoformat(prior)
    return datetime.now() - prior_time > timedelta(hours=cooldown_hours)


def mark_alerted(state, start_date_text): #Records an alert sent for a date
    state.setdefault("alerts", {})[start_date_text] = datetime.now().isoformat(timespec="seconds")
    save_json(STATE_PATH, state)


def max_hut_offset(config): #Finds the last night to offset properly
    return max(int(h["night_offset"]) for h in config["hut_sequence"])


def make_hut_dates(config, start_date: date): #Makes the hut and dates, milford is just one version
    return [
        {
            "hut_name": h["hut_name"],
            "date": start_date + timedelta(days=int(h["night_offset"])),
            "night_offset": int(h["night_offset"]),
        }
        for h in config["hut_sequence"]
    ]

def window_step_days(config): #Calculates how far the window can go (shows 11 nights on desktop screen)
    api_nights = int(config["availability_api"].get("nights", 11))
    step = api_nights - max_hut_offset(config) + 1

    if step < 1:
        raise ValueError("API nights must be larger than the maximum hut night_offset.")

    return step


def iter_window_starts(config): #Start date for each multi day window
    scan_start = parse_date(config["scan_start_date"])
    scan_end = parse_date(config["scan_last_departure_date"])
    step = window_step_days(config)

    current = scan_start
    while current <= scan_end:
        yield current
        current += timedelta(days=step)


def iter_starts_inside_window(config, window_start: date): #All possible start dates with one API. Doing this so I call less API calls vs calling every day
    scan_end = parse_date(config["scan_last_departure_date"])
    max_offset = max_hut_offset(config)
    api_nights = int(config["availability_api"].get("nights", 11))

    latest_start_in_window = min(
        window_start + timedelta(days=api_nights - max_offset),
        scan_end,
    )

    current = window_start
    while current <= latest_start_in_window:
        yield current
        current += timedelta(days=1)

def main(): #Testing how many windows and start dates scanned
    setup_logging()
    config = load_config()

    windows = list(iter_window_starts(config))
    checked_starts = sum(
        1
        for window_start in windows
        for _ in iter_starts_inside_window(config, window_start)
    )

    print(f"Loaded {config['track_name']} scanner config.")
    print(f"Window step: {window_step_days(config)} days")
    print(f"Windows to check: {len(windows)}")
    print(f"Possible start dates to check: {checked_starts}")

if __name__ == "__main__":
    main()