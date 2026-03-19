import os
from pathlib import Path

from mailer import send_bulk_emails


def main() -> None:
    sender_email = os.getenv("SENDER_EMAIL")
    app_password = os.getenv("APP_PASSWORD")
    subject = os.getenv("MAIL_SUBJECT", "Bulk Email")

    if not sender_email or not app_password:
        raise SystemExit("Set SENDER_EMAIL and APP_PASSWORD environment variables before running.")

    csv_path = Path("email.csv")
    if not csv_path.exists():
        raise SystemExit("Missing email.csv in the project root.")

    body_template = """Hi {{name}},

I wanted to connect with {{company}} regarding the available opportunity.

Best regards,
Your Name
"""

    send_bulk_emails(
        csv_text=csv_path.read_text(encoding="utf-8-sig"),
        sender_email=sender_email,
        app_password=app_password,
        subject=subject,
        body_template=body_template,
        log_callback=print,
    )


if __name__ == "__main__":
    main()
