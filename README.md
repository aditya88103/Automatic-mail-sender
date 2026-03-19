# Automatic Mail Sender

Send personalized emails in bulk from a CSV file using Gmail SMTP. The script reads recipient data, fills a simple template, validates email addresses, and sends messages one by one.

## Features
- Personalized emails using `Name` and `Company`
- CSV-driven recipient list
- Simple email validation to skip malformed addresses
- SMTP over TLS (Gmail)

## Requirements
- Python 3.8+
- Gmail account with App Password enabled (2-Step Verification required)

## Project Structure
- `send_mail.py` - main script
- `emails.csv` - recipient list

## CSV Format
The CSV must include these headers:
- `Name`
- `Email`
- `Company`

Example:
```csv
Name,Email,Company
Priya,priya@example.com,Example Corp
Rohit,rohit@example.com,DataWorks
```

## Setup
1. Create a Gmail App Password (Google Account > Security > App Passwords).
2. Open `send_mail.py` and update:
   - `sender_email`
   - `app_password`
3. Update `emails.csv` with your recipients.

## Run
```powershell
python send_mail.py
```

## Notes
- Invalid emails are skipped with a console message.
- Gmail SMTP: `smtp.gmail.com:587`.
- For safety, do not commit real app passwords to public repos.

## Roadmap
- Load `sender_email` and `app_password` from environment variables
- Add attachment support
- Add HTML templates
