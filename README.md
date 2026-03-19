# Automatic Mail Sender

This project now includes a lightweight Flask frontend for sending bulk Gmail messages from a single page. Nothing is stored in a database; the CSV, Gmail address, app password, subject, and message are used in memory for the current send job only.

## Features
- Upload only `email.csv`
- Enter Gmail account and app password in the UI
- Write your own subject and message in the UI
- Preview the first 3 rendered emails before sending
- Auto-skip invalid and duplicate email addresses
- Optional resume attachment upload for every email
- Test mode to send only the first few valid recipients
- Live terminal-style status logs such as `Sent to: careers@example.com`
- Placeholder support in the message: `{{name}}`, `{{company}}`, `{{email}}`

## Requirements
- Python 3.10+
- Gmail account
- 2-Step Verification enabled
- Gmail App Password

## CSV Format
Required:
- `Email`

Optional placeholders:
- `HR_Name` or `Name`
- `Company_Name` or `Company`

Example:
```csv
HR_Name,Email,Company_Name
Priya,priya@example.com,Example Corp
Rohit,rohit@example.com,DataWorks
```

## Install
```powershell
python -m pip install -r requirements.txt
```

## Run The Frontend
```powershell
python app.py
```

Then open `http://127.0.0.1:5000`.

## Built-In Automation
- Preview mode validates the CSV and shows the first 3 rendered emails.
- Duplicate email addresses are skipped automatically.
- Invalid email addresses are skipped automatically.
- Test mode limits sending to the first `N` valid unique rows.
- Resume attachment is uploaded once and reused for the current send job only.
- Live counters show total, queued, sent, failed, invalid, and duplicate counts.

## Gmail App Password Steps
1. Open Gmail.
2. Click your profile photo.
3. Click `Manage your Google Account`.
4. Open `Security`.
5. Enable `2-Step Verification` if it is not already enabled.
6. Search for `App Passwords`.
7. Generate a 16-character app password and paste it into the frontend.

## Optional CLI Mode
You can still send from the terminal with:

```powershell
$env:SENDER_EMAIL="yourname@gmail.com"
$env:APP_PASSWORD="your-app-password"
$env:MAIL_SUBJECT="Your subject"
python send_mail.py
```
