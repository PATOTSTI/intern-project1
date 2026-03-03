""" Check what SMTP configuration Python actually sees """

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python_Modules'))

# Delete any cached imports
if 'email_sender' in sys.modules:
    del sys.modules['email_sender']

# Import fresh
import email_sender

print("Current SMTP Configuration:")
print(f"  SMTP_HOST: {email_sender.SMTP_HOST}")
print(f"  SMTP_PORT: {email_sender.SMTP_PORT}")
print(f"  USE_TLS: {email_sender.USE_TLS}")
print(f"  USE_AUTH: {email_sender.USE_AUTH}")
print(f"  FROM_EMAIL: {email_sender.FROM_EMAIL}")
print(f"  SMTP_USERNAME: {email_sender.SMTP_USERNAME}")
print(f"  SMTP_PASSWORD: {email_sender.SMTP_PASSWORD[:4]}...")
