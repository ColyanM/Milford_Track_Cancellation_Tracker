import json
import smtplib
from email.message import EmailMessage
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    email_cfg = config["email"]

    msg = EmailMessage()
    msg["Subject"] = "Milford DOC scanner test email"
    msg["From"] = email_cfg["from_email"]
    msg["To"] = email_cfg["to_email"]
    msg.set_content(
        "This is a test email from your Milford DOC availability scanner.\n\n"
        "If this arrived in your Yahoo inbox, Gmail-to-Yahoo alerts are working."
    )

    with smtplib.SMTP_SSL(email_cfg["smtp_server"], int(email_cfg["smtp_port"])) as smtp:
        smtp.login(email_cfg["from_email"], email_cfg["app_password"])
        smtp.send_message(msg)

    print("Test email sent.")

if __name__ == "__main__":
    main()
