"""Milford Track DOC availability scanner.
I am making this script to check for DOC availabilty on the Milford track after cancellations.
Has to have all 3 huts available. 
"""

import json
from pathlib import Path
import logging
import sys
from datetime import date, datetime


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json" # file you would make with your own info
EXAMPLE_CONFIG_PATH = BASE_DIR / "config.example.json"  #the example to follow
LOG_PATH = BASE_DIR / "milford_scanner.log" #Makes a file that tracks scanning history for records


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

def main(): #Testing before adding more logic
    setup_logging()
    logging.info("Scanner config loaded.")


if __name__ == "__main__":
    main()