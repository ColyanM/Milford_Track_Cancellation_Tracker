"""Milford Track DOC availability scanner.
I am making this script to check for DOC availabilty on the Milford track after cancellations.
Has to have all 3 huts available. 
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json" # file you would make with your own info
EXAMPLE_CONFIG_PATH = BASE_DIR / "config.example.json"  #the example to follow


def load_json(path: Path):     #Read JSON and returns parsed data
    if not path.exists():
        raise FileNotFoundError(f"{path.name} was not found.")
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(): #Load the private config if it exists, otherwise load the example config, make sure you make your own configuration file if you want to use this
    path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH
    return load_json(path)


def main(): #Testing before adding more logic
    config = load_config()
    print(f"Loaded {config['track_name']} scanner config.")
    print(f"Party size: {config['party_size']}")


if __name__ == "__main__":
    main()