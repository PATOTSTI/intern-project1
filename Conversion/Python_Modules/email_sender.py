"""
Email sender — handles all MT940 email delivery.
Replaces VB6 vbSendMail component (sendMail function, Lines 187-267).
"""

import os
import smtplib
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# SMTP configuration — bank IT should replace these before production
# ---------------------------------------------------------------------------

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
USE_TLS   = True
USE_AUTH  = True

FROM_EMAIL    = "adisneyplus8@gmail.com"
FROM_NAME     = "MT940 System"
SMTP_USERNAME = "adisneyplus8@gmail.com"
SMTP_PASSWORD = "igrt wgnm xwmd cakd"

SEND_AS_HTML = True


# ---------------------------------------------------------------------------
# Recipient queries
# ---------------------------------------------------------------------------

def get_email_recipients(conn: sqlite3.Connection, account_no: str) -> Optional[Tuple[str, str, str]]:
    """
    Look up the email recipient for a given MT940 account.
    Returns (recipient, cc, sentflag) or None if not configured.
    VB6: rsrecipient2.Open — queries codetable by 'MT940 for {account_no}'.
    """
    try:
        sql = """
            SELECT emailrecipient, emailrecipientcc, sentflag
            FROM codetable
            WHERE emailreport LIKE ?
              AND emailtag = 'Y'
              AND emailsched = 'daily'
        """
        cursor = conn.cursor()
        cursor.execute(sql, (f"MT940 for {account_no}",))
        result = cursor.fetchone()

        if result is None:
            return None

        recipient = result[0].strip() if result[0] else ""
        cc        = result[1].strip() if result[1] else ""
        sent_flag = result[2].strip() if result[2] else ""
        return (recipient, cc, sent_flag)

    except Exception as e:
        print(f"ERROR in get_email_recipients: {e}")
        return None


def update_sent_flag(conn: sqlite3.Connection, account_no: str) -> bool:
    """
    Mark an account's MT940 email as sent so we don't resend on the same day.
    VB6: UPDATE codetable SET sentflag = '1' WHERE emailreport like 'MT940 for {account_no}'
    """
    try:
        sql = "UPDATE codetable SET sentflag = '1' WHERE emailreport LIKE ?"
        cursor = conn.cursor()
        cursor.execute(sql, (f"MT940 for {account_no}",))
        conn.commit()
        print(f"[INFO] Email sent flag updated for account {account_no}")
        return True
    except Exception as e:
        print(f"ERROR in update_sent_flag: {e}")
        return False


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------

def build_email_subject(account_no: str, date: str) -> str:
    """VB6: "MT940 for " & stmtacctno & " " & PrevBusDate"""
    return f"MT940 for {account_no} {date}"


def build_email_body(version: str = "1.0.0") -> str:
    """VB6: " This is a system generated message. (version:x.y.z)" """
    return f" This is a system generated message.  (version:{version})"


def _parse_addresses(address_string: str) -> list:
    """Split a semicolon-delimited address string into a clean list."""
    if not address_string:
        return []
    return [a.strip() for a in address_string.split(";") if a.strip()]


def _clean_attachment_path(attachment: str) -> str:
    """
    Strip leading semicolons from attachment paths.
    Added by KC 04/08/2014 in VB6 to handle malformed path strings like ";c:\\file.txt".
    """
    if not attachment:
        return ""
    s = attachment.strip()
    if s.lower().startswith(";;;c"):
        return s[3:]
    if s.lower().startswith(";;c"):
        return s[2:]
    if s.lower().startswith(";c"):
        return s[1:]
    return s.replace(";;;", ";").replace(";;", ";")


# ---------------------------------------------------------------------------
# Core send function
# ---------------------------------------------------------------------------

def send_mail(recipient: str, cc_recipient: str, subject: str,
              message: str, attachment: str) -> bool:
    """
    Send an MT940 file by email.
    Mirrors VB6 sendMail(recipientEmail, ccEmail, subjectEmail, messageEmail, attachmentEmail).

    Supports multiple recipients and CC addresses (semicolon-delimited).
    Attachment paths are cleaned of legacy semicolon artifacts before attaching.
    """
    try:
        recipient_list = _parse_addresses(recipient)
        cc_list        = _parse_addresses(cc_recipient)

        if not recipient_list:
            print("[ERROR] No valid recipients provided")
            return False

        msg = MIMEMultipart('alternative' if SEND_AS_HTML else 'mixed')
        msg.attach(MIMEText(message, 'html' if SEND_AS_HTML else 'plain'))
        msg['From']    = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg['To']      = ', '.join(recipient_list)
        msg['Subject'] = subject
        if cc_list:
            msg['Cc'] = ', '.join(cc_list)

        # Attach file(s)
        attachment_path = _clean_attachment_path(attachment)
        if attachment_path:
            for file_path in _parse_addresses(attachment_path):
                if not os.path.exists(file_path):
                    print(f"[WARNING] Attachment not found: {file_path}")
                    continue
                with open(file_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition',
                                f'attachment; filename= {os.path.basename(file_path)}')
                msg.attach(part)
                print(f"[INFO] Attached file: {os.path.basename(file_path)}")

        # Connect and send
        print(f"[INFO] Connecting to SMTP server: {SMTP_HOST}:{SMTP_PORT}")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        if USE_TLS:
            server.starttls()
        if USE_AUTH:
            print(f"[INFO] Authenticating as: {SMTP_USERNAME}")
            server.login(SMTP_USERNAME, SMTP_PASSWORD)

        print(f"[INFO] Sending email to: {', '.join(recipient_list)}")
        server.send_message(msg, FROM_EMAIL, recipient_list + cc_list)
        server.quit()

        print("[SUCCESS] Email sent successfully")
        return True

    except smtplib.SMTPException as e:
        print(f"[ERROR] SMTP error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        import traceback
        traceback.print_exc()
        return False
