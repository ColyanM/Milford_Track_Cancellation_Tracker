"""Milford Track DOC availability scanner.
I am making this script to check for DOC availabilty on the Milford track after cancellations.
Has to have all 3 huts available. 
"""

import json
from pathlib import Path
import logging
import sys


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

def main(): #Testing before adding more logic
    setup_logging()
    logging.info("Scanner config loaded.")


if __name__ == "__main__":
    main()