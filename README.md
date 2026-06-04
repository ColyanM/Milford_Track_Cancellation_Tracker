Milford Cancellation Tracker
============================

This is a small Python script for checking DOC booking availability on the
Milford Track. It looks for a full hut sequence becoming available again after
cancellations, then sends an email alert.

What it checks
--------------

By default the scanner checks these hut nights: This is beacuse Milford has no campsites and is only one direction

- Start date + 0 nights: Clinton Hut
- Start date + 1 night: Mintaro Hut
- Start date + 2 nights: Dumpling Hut

It only treats a start date as a possible match when every hut in the sequence
has enough available spaces for the configured party size.

Setup
-----

Install Python dependencies:

```bash
pip install -r requirements.txt
```

The real `config.json` file is not included in the repo because it contains
personal details like email settings. Make your own by copying
`config.example.json` to `config.json`, then update it with your dates, party
size, and email info.

`config.example.json` is only a template. It has placeholder email values and
email alerts are disabled by default because of this.

The main settings to check are:

- `party_size`
- `scan_start_date`
- `scan_last_departure_date`
- `cooldown_hours_per_date`
- the `email` section

Email
-----

Email is disabled in the example config. To send real alerts, set:

```json
"enabled": true
```

Use an app password for the email account. Do not use your normal email
password.

You can test email separately with:

```bash
python test_email.py
```

Running the scanner
-------------------

Run:

```bash
python milford_scanner.py
```

The scanner runs continuously until you stop it. It checks the configured date
range, logs the results, sends alerts for possible matches, then waits before
checking again.

Files created while running
---------------------------

These files are created by the scanner and are ignored by git:

- `config.json` - your private local config
- `scanner_state.json` - remembers alert cooldowns and status email timing
- `milford_scanner.log` - scan history and errors
- `debug_snapshots/` - saved API responses and possible match details

Notes
-----

Always verify availability on the DOC booking site before changing travel
plans, at times the API can be slightly behind the real time information 
and the availability is already gone. This is the Milford Track we are
talking about here!
