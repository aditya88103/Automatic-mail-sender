import csv
import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from io import StringIO
from typing import Callable

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
TOKEN_PATTERN = re.compile(r"{{\s*([A-Za-z0-9_]+)\s*}}")
REQUIRED_COLUMNS = {"Email"}
OPTIONAL_COLUMN_MAP = {
    "name": ("HR_Name", "Name"),
    "company": ("Company_Name", "Company"),
    "city": ("City",),
    "job_role": ("Job_Role", "Role"),
    "source_link": ("Source_Link", "Link"),
}


@dataclass
class Recipient:
    row_number: int
    email: str
    row: dict[str, str]


@dataclass
class PreparedRecipients:
    fieldnames: list[str]
    valid_recipients: list[Recipient]
    invalid_rows: list[dict[str, str]]
    duplicate_rows: list[dict[str, str]]
    total_rows: int


ProgressCallback = Callable[[dict[str, object]], None]


def _clean_row(row: dict[str, str]) -> dict[str, str]:
    return {key: (value or "").strip() for key, value in row.items()}


def _get_value(row: dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return default


def _build_context(row: dict[str, str], email: str) -> dict[str, str]:
    context = {key: value.strip() for key, value in row.items()}
    context.update({key.lower(): value for key, value in context.items()})
    context["email"] = email
    context["name"] = _get_value(row, *OPTIONAL_COLUMN_MAP["name"], default="Hiring Team")
    context["company"] = _get_value(row, *OPTIONAL_COLUMN_MAP["company"], default="your company")
    context["city"] = _get_value(row, *OPTIONAL_COLUMN_MAP["city"], default="")
    context["job_role"] = _get_value(row, *OPTIONAL_COLUMN_MAP["job_role"], default="")
    context["source_link"] = _get_value(row, *OPTIONAL_COLUMN_MAP["source_link"], default="")
    return context


def render_template(template: str, row: dict[str, str], email: str) -> str:
    context = _build_context(row, email)

    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        return context.get(token, context.get(token.lower(), match.group(0)))

    return TOKEN_PATTERN.sub(replace, template)


def prepare_recipients(csv_text: str) -> PreparedRecipients:
    reader = csv.DictReader(StringIO(csv_text))
    if not reader.fieldnames:
        raise ValueError("CSV is empty.")

    missing_columns = REQUIRED_COLUMNS.difference(reader.fieldnames)
    if missing_columns:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing_columns))}")

    valid_recipients: list[Recipient] = []
    invalid_rows: list[dict[str, str]] = []
    duplicate_rows: list[dict[str, str]] = []
    seen_emails: set[str] = set()
    total_rows = 0

    for index, row in enumerate(reader, start=2):
        total_rows += 1
        cleaned = _clean_row(row)
        email = cleaned.get("Email", "")
        normalized = email.lower()

        if not EMAIL_PATTERN.match(email):
            invalid_rows.append({"row_number": str(index), "email": email or "[empty]"})
            continue

        if normalized in seen_emails:
            duplicate_rows.append({"row_number": str(index), "email": email})
            continue

        seen_emails.add(normalized)
        valid_recipients.append(Recipient(row_number=index, email=email, row=cleaned))

    return PreparedRecipients(
        fieldnames=list(reader.fieldnames),
        valid_recipients=valid_recipients,
        invalid_rows=invalid_rows,
        duplicate_rows=duplicate_rows,
        total_rows=total_rows,
    )


def build_preview(
    csv_text: str,
    subject_template: str,
    body_template: str,
    preview_count: int = 3,
) -> dict[str, object]:
    prepared = prepare_recipients(csv_text)
    preview_items = []

    for recipient in prepared.valid_recipients[:preview_count]:
        preview_items.append(
            {
                "rowNumber": recipient.row_number,
                "email": recipient.email,
                "subject": render_template(subject_template, recipient.row, recipient.email),
                "body": render_template(body_template, recipient.row, recipient.email),
            }
        )

    return {
        "preview": preview_items,
        "stats": {
            "totalRows": prepared.total_rows,
            "validRecipients": len(prepared.valid_recipients),
            "invalidEmails": len(prepared.invalid_rows),
            "duplicates": len(prepared.duplicate_rows),
        },
        "issues": {
            "invalidRows": prepared.invalid_rows[:10],
            "duplicateRows": prepared.duplicate_rows[:10],
        },
        "headers": prepared.fieldnames,
    }


def send_bulk_emails(
    csv_text: str,
    sender_email: str,
    app_password: str,
    subject_template: str,
    body_template: str,
    progress_callback: ProgressCallback,
    attachment_name: str | None = None,
    attachment_bytes: bytes | None = None,
    attachment_mime_type: str = "application/pdf",
    test_mode_limit: int | None = None,
) -> None:
    prepared = prepare_recipients(csv_text)
    recipients = prepared.valid_recipients
    if test_mode_limit:
        recipients = recipients[:test_mode_limit]

    summary = {
        "totalRows": prepared.total_rows,
        "validRecipients": len(prepared.valid_recipients),
        "queuedRecipients": len(recipients),
        "invalidEmails": len(prepared.invalid_rows),
        "duplicates": len(prepared.duplicate_rows),
        "sent": 0,
        "failed": 0,
        "remaining": len(recipients),
    }

    progress_callback({"type": "summary", "stats": summary.copy()})
    if prepared.invalid_rows:
        progress_callback(
            {
                "type": "log",
                "level": "info",
                "message": f"Skipped invalid emails: {len(prepared.invalid_rows)}",
            }
        )
    if prepared.duplicate_rows:
        progress_callback(
            {
                "type": "log",
                "level": "info",
                "message": f"Skipped duplicate emails: {len(prepared.duplicate_rows)}",
            }
        )

    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
    try:
        server.starttls()
        server.login(sender_email, app_password)
        progress_callback({"type": "log", "level": "info", "message": f"Connected as: {sender_email}"})

        for recipient in recipients:
            try:
                rendered_subject = render_template(subject_template, recipient.row, recipient.email)
                rendered_body = render_template(body_template, recipient.row, recipient.email)

                message = EmailMessage()
                message["Subject"] = rendered_subject
                message["From"] = sender_email
                message["To"] = recipient.email
                message.set_content(rendered_body)

                if attachment_name and attachment_bytes:
                    maintype, subtype = attachment_mime_type.split("/", maxsplit=1)
                    message.add_attachment(
                        attachment_bytes,
                        maintype=maintype,
                        subtype=subtype,
                        filename=attachment_name,
                    )

                server.send_message(message)
                summary["sent"] += 1
                progress_callback(
                    {"type": "log", "level": "success", "message": f"Sent to: {recipient.email}"}
                )
            except Exception as exc:
                summary["failed"] += 1
                progress_callback(
                    {
                        "type": "log",
                        "level": "error",
                        "message": f"Failed to send to: {recipient.email} ({exc})",
                    }
                )
            finally:
                summary["remaining"] -= 1
                progress_callback({"type": "summary", "stats": summary.copy()})

        progress_callback(
            {
                "type": "log",
                "level": "success",
                "message": (
                    f"Completed. Sent: {summary['sent']}, Failed: {summary['failed']}, "
                    f"Invalid: {summary['invalidEmails']}, Duplicates: {summary['duplicates']}"
                ),
            }
        )
    finally:
        server.quit()
