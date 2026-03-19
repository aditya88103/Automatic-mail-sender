import queue
import threading
import uuid
from dataclasses import dataclass, field

from flask import Flask, Response, jsonify, render_template, request

from mailer import send_bulk_emails

app = Flask(__name__)


@dataclass
class JobState:
    messages: queue.Queue[str] = field(default_factory=queue.Queue)
    done: bool = False


jobs: dict[str, JobState] = {}


def log_message(job_id: str, message: str) -> None:
    jobs[job_id].messages.put(message)


def run_send_job(
    job_id: str,
    csv_text: str,
    sender_email: str,
    app_password: str,
    subject: str,
    body_template: str,
) -> None:
    try:
        send_bulk_emails(
            csv_text=csv_text,
            sender_email=sender_email,
            app_password=app_password,
            subject=subject,
            body_template=body_template,
            log_callback=lambda message: log_message(job_id, message),
        )
    except Exception as exc:
        log_message(job_id, f"Error: {exc}")
    finally:
        jobs[job_id].done = True
        jobs[job_id].messages.put("__COMPLETE__")


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.post("/api/send")
def start_send() -> Response:
    uploaded_file = request.files.get("csvFile")
    sender_email = (request.form.get("senderEmail") or "").strip()
    app_password = (request.form.get("appPassword") or "").strip()
    subject = (request.form.get("subject") or "").strip()
    body_template = (request.form.get("message") or "").strip()

    if not uploaded_file:
        return jsonify({"error": "Upload email.csv to continue."}), 400

    if uploaded_file.filename.lower() != "email.csv":
        return jsonify({"error": "Only a CSV named email.csv is accepted."}), 400

    if not sender_email or not app_password or not subject or not body_template:
        return jsonify({"error": "Gmail account, app password, subject, and message are required."}), 400

    if not sender_email.endswith("@gmail.com"):
        return jsonify({"error": "Use a Gmail account for SMTP login."}), 400

    try:
        csv_text = uploaded_file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"error": "CSV must be UTF-8 encoded."}), 400

    job_id = uuid.uuid4().hex
    jobs[job_id] = JobState()

    worker = threading.Thread(
        target=run_send_job,
        args=(job_id, csv_text, sender_email, app_password, subject, body_template),
        daemon=True,
    )
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
                message = job.messages.get(timeout=20)
            except queue.Empty:
                if job.done:
                    break
                yield "event: ping\ndata: keepalive\n\n"
                continue

            if message == "__COMPLETE__":
                yield "event: done\ndata: completed\n\n"
                break

            payload = message.replace("\n", " ")
            yield f"data: {payload}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True)
