"""
send_email.py
Emails the 4 generated HTML screener reports as attachments via Gmail SMTP.

Requires 3 environment variables (set as GitHub Secrets, never hardcoded):
  GMAIL_USER          - the Gmail address sending the email
  GMAIL_APP_PASSWORD   - a Gmail App Password (NOT your normal password -
                          generate one at myaccount.google.com/apppasswords,
                          requires 2-Step Verification enabled on the account)
  RECIPIENT_EMAIL      - the email address to receive the reports
                          (can be the same as GMAIL_USER)
"""

import os
import smtplib
import glob
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]

REPORTS_DIR = "reports"


def build_email():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = f"Screener Reports — {timestamp}"

    report_files = sorted(glob.glob(os.path.join(REPORTS_DIR, "*.html")))

    if not report_files:
        body = "No report files were found - one or more screener scripts may have failed before generating output. Check the GitHub Actions run log."
    else:
        names = "\n".join(f"  - {os.path.basename(f)}" for f in report_files)
        body = f"Attached: {len(report_files)} screener report(s) generated at {timestamp}.\n\n{names}\n\nOpen each HTML file in a browser to view the color-coded table."

    msg.attach(MIMEText(body, "plain"))

    for filepath in report_files:
        with open(filepath, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(filepath)}")
        msg.attach(part)

    return msg, len(report_files)


def send_email(msg):
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)


if __name__ == "__main__":
    message, count = build_email()
    send_email(message)
    print(f"Email sent to {RECIPIENT_EMAIL} with {count} attachment(s).")
