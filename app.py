import json
import queue
import threading
import uuid
from dataclasses import dataclass, field

from flask import Flask, Response, jsonify, render_template, request

from mailer import build_preview, send_bulk_emails

app = Flask(__name__)


@dataclass
class JobState:
    messages: queue.Queue[dict[str, object]] = field(default_factory=queue.Queue)
    done: bool = False


jobs: dict[str, JobState] = {}


def queue_event(job_id: str, payload: dict[str, object]) -> None:
    jobs[job_id].messages.put(payload)


def parse_mail_form(require_credentials: bool = True):
    uploaded_file = request.files.get("csvFile")
    resume_file = request.files.get("resumeFile")
    sender_email = (request.form.get("senderEmail") or "").strip()
    app_password = (request.form.get("appPassword") or "").strip()
    subject = (request.form.get("subject") or "").strip()
    body_template = (request.form.get("message") or "").strip()
    test_mode = (request.form.get("testMode") or "").strip().lower() == "true"
    test_limit_raw = (request.form.get("testLimit") or "").strip()

    if not uploaded_file:
        raise ValueError("Upload email.csv to continue.")
    if uploaded_file.filename.lower() != "email.csv":
        raise ValueError("Only a CSV named email.csv is accepted.")
    if not subject or not body_template:
        raise ValueError("Subject and message are required.")
    if require_credentials:
        if not sender_email or not app_password:
            raise ValueError("Gmail account and app password are required.")
        if not sender_email.endswith("@gmail.com"):
            raise ValueError("Use a Gmail account for SMTP login.")

    try:
        csv_text = uploaded_file.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded.") from exc

    test_limit = None
    if test_mode:
        try:
            test_limit = int(test_limit_raw or "5")
        except ValueError as exc:
            raise ValueError("Test mode limit must be a whole number.") from exc
        if test_limit <= 0:
            raise ValueError("Test mode limit must be greater than zero.")

    attachment_name = None
    attachment_bytes = None
    attachment_mime_type = "application/pdf"
    if resume_file and resume_file.filename:
        attachment_name = resume_file.filename
        attachment_mime_type = resume_file.mimetype or "application/octet-stream"
        attachment_bytes = resume_file.read()

    return {
        "csv_text": csv_text,
        "sender_email": sender_email,
        "app_password": app_password,
        "subject": subject,
        "body_template": body_template,
        "test_mode": test_mode,
        "test_limit": test_limit,
        "attachment_name": attachment_name,
        "attachment_bytes": attachment_bytes,
        "attachment_mime_type": attachment_mime_type,
    }


def run_send_job(job_id: str, payload: dict[str, object]) -> None:
    try:
        send_bulk_emails(
            csv_text=payload["csv_text"],
            sender_email=payload["sender_email"],
            app_password=payload["app_password"],
            subject_template=payload["subject"],
            body_template=payload["body_template"],
            progress_callback=lambda event: queue_event(job_id, event),
            attachment_name=payload["attachment_name"],
            attachment_bytes=payload["attachment_bytes"],
            attachment_mime_type=payload["attachment_mime_type"],
            test_mode_limit=payload["test_limit"],
        )
    except Exception as exc:
        queue_event(job_id, {"type": "log", "level": "error", "message": f"Error: {exc}"})
    finally:
        jobs[job_id].done = True
        jobs[job_id].messages.put({"type": "done"})


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.post("/api/preview")
def preview_send() -> Response:
    try:
        payload = parse_mail_form(require_credentials=False)
        result = build_preview(
            csv_text=payload["csv_text"],
            subject_template=payload["subject"],
            body_template=payload["body_template"],
        )
        if payload["test_mode"]:
            result["stats"]["queuedRecipients"] = min(
                result["stats"]["validRecipients"], payload["test_limit"]
            )
        else:
            result["stats"]["queuedRecipients"] = result["stats"]["validRecipients"]
        result["attachment"] = payload["attachment_name"]
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/send")
def start_send() -> Response:
    try:
        payload = parse_mail_form(require_credentials=True)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    job_id = uuid.uuid4().hex
    jobs[job_id] = JobState()

    worker = threading.Thread(target=run_send_job, args=(job_id, payload), daemon=True)
    worker.start()

    return jsonify({"jobId": job_id})


@app.get("/api/stream/<job_id>")
def stream_logs(job_id: str) -> Response:
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job id."}), 404

    def event_stream():
        while True:
            try:
                event = job.messages.get(timeout=20)
            except queue.Empty:
                if job.done:
                    break
                yield "event: ping\ndata: keepalive\n\n"
                continue

            event_type = str(event.get("type", "log"))
            if event_type == "done":
                yield "event: done\ndata: completed\n\n"
                break

            yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True)
