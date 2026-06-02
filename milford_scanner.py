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
import requests
import smtplib
from email.message import EmailMessage
import random
import time


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

def save_json(path: Path, data): #Makes JSON readable
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_state(): #Loads alert history
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

def build_payload(config, window_start: date): #JSON that DOC website expects
    api = config["availability_api"]

    return {
        "accomodation": api.get("accomodation", ""),
        "placeId": int(api["placeId"]),
        "customerClassificationId": int(api.get("customerClassificationId", 0)),
        "arrivalDate": yyyy_mm_dd(window_start),
        "nights": int(api.get("nights", 11)),
    }

def save_bad_response(config, window_start, payload, response, text): #Having issues so making bad responses save to review
    debug_dir = BASE_DIR / config.get("advanced", {}).get("debug_folder", "debug_snapshots")
    debug_dir.mkdir(exist_ok=True)

    body = {
        "window_start": yyyy_mm_dd(window_start),
        "request_payload": payload,
        "status": response.status_code,
        "headers": dict(response.headers),
        "response_text": text,
    }

    (debug_dir / f"BAD_RESPONSE_{yyyy_mm_dd(window_start)}.txt").write_text(
        json.dumps(body, indent=2, ensure_ascii=False),
        encoding="utf-8",
        errors="replace",
    )

def fetch_window_availability(session, config, window_start: date): #Requests the full grid view from DOC
    api = config["availability_api"]
    payload = build_payload(config, window_start)
    timeout = int(config.get("http", {}).get("timeout_seconds", 90))

    response = session.post(
        api["url"],
        json=payload,
        headers={
            "accept": "application/json, text/plain, */*",
            "origin": "https://bookings.doc.govt.nz",
            "referer": "https://bookings.doc.govt.nz/Web/Default.aspx",
        },
        timeout=timeout,
    )

    text = response.text

    if not response.ok:
        save_bad_response(config, window_start, payload, response, text)
        raise RuntimeError(f"API returned HTTP {response.status_code}. Saved BAD_RESPONSE file.")

    try:
        return response.json(), payload
    except ValueError as exc:
        save_bad_response(config, window_start, payload, response, text)
        raise RuntimeError(
            f"API did not return JSON. status={response.status_code}. "
            f"response_length={len(text)}. Saved BAD_RESPONSE file."
        ) from exc

def find_facility(data, facility_name): #Find the specific hut in the API
    for facility in data.get("GreatWalkFacilityData", []):
        if facility.get("FacilityName", "").strip().lower() == facility_name.strip().lower():
            return facility
    return None


def find_facility_date(facility, target_date: date): #One hut on that date
    target_prefix = yyyy_mm_dd(target_date)

    for row in facility.get("GreatWalkFacilityDateData", []):
        arrival = row.get("ArrivalDate", "")
        if arrival.startswith(target_prefix):
            return row

    return None

def analyse_start_date(config, data, start_date: date): #Checks if all 3 huts are available 
    rules = config.get("availability_rules", {})
    require_is_available = bool(rules.get("require_is_available", True))
    require_total = bool(rules.get("require_total_available_for_party_size", True))
    party_size = int(config.get("party_size", 1))

    hut_results = []

    for hd in make_hut_dates(config, start_date):
        hut_name = hd["hut_name"]
        hut_date = hd["date"]

        facility = find_facility(data, hut_name)
        row = find_facility_date(facility, hut_date) if facility else None

        if not facility:
            hut_results.append({
                "hut_name": hut_name,
                "date": yyyy_mm_dd(hut_date),
                "found_facility": False,
                "found_date": False,
                "is_available": False,
                "total_available": None,
                "passes": False,
                "reason": "Facility not found in JSON",
            })
            continue

        if not row:
            hut_results.append({
                "hut_name": hut_name,
                "date": yyyy_mm_dd(hut_date),
                "found_facility": True,
                "found_date": False,
                "is_available": False,
                "total_available": None,
                "passes": False,
                "reason": "Date not found for facility in JSON",
            })
            continue

        is_available = bool(row.get("IsAvailable", False))
        total_available = row.get("TotalAvailable", None)

        passes = True
        reasons = []

        if require_is_available and not is_available:
            passes = False
            reasons.append("IsAvailable is false")

        if require_total:
            try:
                if int(total_available) < party_size:
                    passes = False
                    reasons.append(f"TotalAvailable {total_available} is below party size {party_size}")
            except Exception:
                passes = False
                reasons.append(f"TotalAvailable was not numeric: {total_available}")

        if passes:
            reasons.append("Passes configured availability rules")

        hut_results.append({
            "hut_name": hut_name,
            "date": yyyy_mm_dd(hut_date),
            "found_facility": True,
            "found_date": True,
            "is_available": is_available,
            "total_available": total_available,
            "passes": passes,
            "reason": "; ".join(reasons),
            "raw_row": row,
        })

    all_pass = all(h.get("passes", False) for h in hut_results)

    return {
        "start_date": yyyy_mm_dd(start_date),
        "is_possible_match": all_pass,
        "hut_results": hut_results,
    }

def send_email(config, subject, body):     #Send an email alert, or log the alert body when email is set to false
    email_cfg = config["email"]
    if not email_cfg.get("enabled", False):
        logging.info("Email disabled. Alert body:\n%s", body)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_cfg["from_email"]
    msg["To"] = email_cfg["to_email"]
    msg.set_content(body)

    with smtplib.SMTP_SSL(email_cfg["smtp_server"], int(email_cfg["smtp_port"])) as smtp:
        smtp.login(email_cfg["from_email"], email_cfg["app_password"])
        smtp.send_message(msg)

def maybe_send_status_email(config, state, stats): #Handles the hourly status email
    now = datetime.now()
    last_status = state.get("last_status_email")

    if last_status:
        last_status_time = datetime.fromisoformat(last_status)
        if now - last_status_time < timedelta(hours=1):
            return

    subject = "Milford scanner still running"

    body = "\n".join([
        "Milford DOC scanner is still running.",
        "",
        f"Last full scan completed: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Windows checked: {stats.get('windows')}",
        f"Start dates checked: {stats.get('checked_starts')}",
        f"Possible matches found this scan: {stats.get('matches')}",
        "",
        "No action needed. This is just a status email.",
    ])

    send_email(config, subject, body)

    state["last_status_email"] = now.isoformat(timespec="seconds")
    save_json(STATE_PATH, state)

def build_alert(config, result): #Build the email body for a possible match from cancellation 
    lines = [
        "Milford Track DOC availability may be open!!!",
        "",
        f"Party size configured: {config['party_size']}",
        f"Start date: {result['start_date']} ({weekday_name_from_text(result['start_date'])})",
        "",
        "Required hut sequence:",
    ]

    for h in result["hut_results"]:
        lines.append(
            f"- {h['date']} ({weekday_name_from_text(h['date'])}): {h['hut_name']} | "
            f"IsAvailable={h.get('is_available')} | "
            f"TotalAvailable={h.get('total_available')}"
        )

    lines += [
        "",
        "Book manually here:",
        config.get("doc_booking_home", "https://bookings.doc.govt.nz/Web/Default.aspx"),
        "",
        "Verify the date on DOC before changing travel plans.",
    ]

    return "\n".join(lines)

def run_once(config, session, state): #Run a complete scan across all grids/windows
    debug_dir = BASE_DIR / config.get("advanced", {}).get("debug_folder", "debug_snapshots")
    debug_dir.mkdir(exist_ok=True)
    save_each_window = bool(config.get("advanced", {}).get("save_each_window_sample", False))

    checked_starts = 0
    matches = 0
    windows = 0

    for window_start in iter_window_starts(config):
        windows += 1

        try:
            data, payload = fetch_window_availability(session, config, window_start)

            if windows == 1 or save_each_window:
                (debug_dir / f"{yyyy_mm_dd(window_start)}_window_response.json").write_text(
                    json.dumps(data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

            window_checked = 0
            window_matches = 0
            last_start_text = None

            for start_date in iter_starts_inside_window(config, window_start):
                checked_starts += 1
                window_checked += 1
                start_text = yyyy_mm_dd(start_date)
                last_start_text = start_text

                result = analyse_start_date(config, data, start_date)

                summary = ", ".join(
                    f"{h['hut_name']}:{h.get('is_available')}/total={h.get('total_available')}"
                    for h in result["hut_results"]
                )

                logging.info("Checked %s possible=%s | %s", start_text, result["is_possible_match"], summary)

                if result["is_possible_match"]:
                    matches += 1
                    window_matches += 1

                    (debug_dir / f"MATCH_{start_text}.json").write_text(
                        json.dumps(result, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )

                    cooldown = int(config.get("cooldown_hours_per_date", 0))

                    if should_alert(state, start_text, cooldown):
                        send_email(
                            config,
                            f"Milford availability possible: {start_text} ({weekday_name_from_text(start_text)})",
                            build_alert(config, result),
                        )
                        mark_alerted(state, start_text)
                        logging.info("Sent alert for %s", start_text)
                    else:
                        logging.info("Already alerted recently for %s", start_text)

            logging.info(
                "Window %s to %s checked_starts=%s matches=%s",
                yyyy_mm_dd(window_start),
                last_start_text or yyyy_mm_dd(window_start),
                window_checked,
                window_matches,
            )

            time.sleep(0.7)

        except Exception as exc:
            logging.exception("Error checking window starting %s: %s", yyyy_mm_dd(window_start), exc)

    logging.info(
        "Completed scan. windows=%s checked_starts=%s possible_matches=%s",
        windows,
        checked_starts,
        matches,
    )

    return {
        "windows": windows,
        "checked_starts": checked_starts,
        "matches": matches,
    }

def main(): #Runs the scanner constantly 
    setup_logging()
    config = load_config()

    session = requests.Session()
    session.headers.update({
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    })

    interval = int(config.get("check_interval_seconds", 180))

    logging.info("Milford scanner started. Interval=%s seconds", interval)
    logging.info("Using DOC JSON endpoint: %s", config["availability_api"]["url"])

    while True:
        state = load_state()
        stats = run_once(config, session, state)

        state = load_state()
        maybe_send_status_email(config, state, stats)

        sleep_seconds = random.randint(120, 200)
        logging.info("Sleeping %s seconds.", sleep_seconds)
        time.sleep(sleep_seconds)

if __name__ == "__main__":
    main()