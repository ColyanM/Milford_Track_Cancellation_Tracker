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

def main(): #Just testing still will update later
    setup_logging()
    config = load_config()

    start_date = parse_date(config["scan_start_date"])
    hut_dates = make_hut_dates(config, start_date)

    print(f"Loaded {config['track_name']} scanner config.")
    print(f"Maximum hut offset: {max_hut_offset(config)}")

    for hut in hut_dates:
        print(f"{yyyy_mm_dd(hut['date'])}: {hut['hut_name']}")

if __name__ == "__main__":
    main()