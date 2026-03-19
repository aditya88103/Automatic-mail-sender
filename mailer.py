import csv
import re
import smtplib
from email.mime.text import MIMEText
from io import StringIO
from typing import Callable

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
REQUIRED_COLUMNS = {"Email"}
OPTIONAL_COLUMN_MAP = {
    "name": ("HR_Name", "Name"),
    "company": ("Company_Name", "Company"),
}


def _get_value(row: dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return default


def _render_body(template: str, row: dict[str, str], email: str) -> str:
    name = _get_value(row, *OPTIONAL_COLUMN_MAP["name"], default="Hiring Team")
    company = _get_value(row, *OPTIONAL_COLUMN_MAP["company"], default="your company")
    return (
        template.replace("{{name}}", name)
        .replace("{{company}}", company)
        .replace("{{email}}", email)
    )


def send_bulk_emails(
    csv_text: str,
    sender_email: str,
    app_password: str,
    subject: str,
    body_template: str,
    log_callback: Callable[[str], None],
) -> None:
    reader = csv.DictReader(StringIO(csv_text))
    if not reader.fieldnames:
        raise ValueError("CSV is empty.")

    missing_columns = REQUIRED_COLUMNS.difference(reader.fieldnames)
    if missing_columns:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing_columns))}")

    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
    try:
        server.starttls()
        server.login(sender_email, app_password)
        log_callback(f"Connected as: {sender_email}")

        sent_count = 0
        skipped_count = 0

        for row in reader:
            email = (row.get("Email") or "").strip()
            if not EMAIL_PATTERN.match(email):
                skipped_count += 1
                log_callback(f"Skipped invalid email: {email or '[empty]'}")
                continue

            message = MIMEText(_render_body(body_template, row, email), _charset="utf-8")
            message["Subject"] = subject
            message["From"] = sender_email
            message["To"] = email

            server.sendmail(sender_email, email, message.as_string())
            sent_count += 1
            log_callback(f"Sent to: {email}")

        log_callback(f"Completed. Sent: {sent_count}, Skipped: {skipped_count}")
    finally:
        server.quit()
