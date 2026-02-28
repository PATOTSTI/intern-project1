# 📧 Gmail Testing Guide - Full MT940 System

**Purpose**: Run the complete MT940 system and send test emails to your Gmail account

---

## ✅ Prerequisites

Your email configuration is already set up in `email_sender.py`:
- ✅ SMTP_HOST = "smtp.gmail.com"
- ✅ SMTP_PORT = 587
- ✅ USE_TLS = True
- ✅ **USE_AUTH = True** (✅ Already correct for Gmail!)
- ✅ FROM_EMAIL = "adisneyplus8@gmail.com"
- ✅ SMTP_USERNAME = "adisneyplus8@gmail.com"
- ✅ SMTP_PASSWORD = "igrt wgnm xwmd cakd"

---

## 🚀 STEP-BY-STEP TESTING

### Step 1: Configure Database for Testing

Run the setup script to configure the database to send emails to your Gmail:

```bash
cd Conversion
python Test_Scripts\setup_test_email.py
```

**What this does**:
- Resets the `sentflag` to 0 (allows system to run)
- Sets your Gmail as the email recipient
- Prepares the database for testing

**Expected Output**:
```
MT940 TESTING SETUP - Gmail Configuration
======================================================================
[STEP 1] Resetting sentflag to allow processing...
[OK] sentflag reset to 0

[STEP 2] Checking current email configuration...
[INFO] Found X existing email configurations

[STEP 3] Setting up test email recipient...
[INFO] Test account: 001010039999
[OK] Email recipient set to: adisneyplus8@gmail.com

[STEP 4] Final configuration:
  MT940 for 001010039999
    Recipient: adisneyplus8@gmail.com
    Sentflag: 0

[SUCCESS] Test email configuration complete!
```

---

### Step 2: Run the Full MT940 System

```bash
cd Conversion\Python_Modules
python main.py
```

**What this does**:
1. Connects to database ✅
2. Checks if processing should run (sentflag = 0) ✅
3. Queries accounts to process ✅
4. For each account:
   - Generates MT940 file in `C:\MT940\Output\YYYYMMDD\`
   - Sends email to your Gmail with MT940 file attached
   - Updates sentflag to prevent duplicate runs

**Expected Output**:
```
**********************************************************************
*           MT940 SWIFT Statement Generator - Python Version         *
**********************************************************************

======================================================================
  MT940 AUTOMATED PROCESSING
======================================================================
[INFO] Processing date: 2025-11-25

[STEP 1] Connecting to database...
[OK] Database connected successfully

[STEP 2] Checking if processing should run...
[OK] Processing conditions met - proceeding

[STEP 3] Clearing summary table...
[OK] Summary table cleared

[STEP 4] Querying accounts to process...
[OK] Found accounts to process

[STEP 5] Processing accounts...
----------------------------------------------------------------------

[ACCOUNT 1] Processing: 001010039999
  Counter: 1024, Code: XXXXXXXXXXXX, SendingType: 2
  [ROUTE] Using ProcessMT940New
  [OK] File generated: AUB20881_20251125_001010039999_1024.txt
  [SEND] Email delivery mode
  [EMAIL] Sending to: adisneyplus8@gmail.com
  [OK] Email sent successfully

[COMPLETE] Processed 1 accounts, 1 emails sent
----------------------------------------------------------------------
[SUCCESS] MT940 processing completed successfully
======================================================================
```

---

### Step 3: Check Your Gmail Inbox

1. Open Gmail: https://mail.google.com
2. Look for email with subject: "MT940 for 001010039999 2025-11-25"
3. Check the attachment: `AUB20881_20251125_001010039999_1024.txt`

**Email Details**:
- **From**: MT940 System (adisneyplus8@gmail.com)
- **Subject**: MT940 for [Account Number] [Date]
- **Body**: "This is a system generated message. (version:1.0.0)"
- **Attachment**: MT940 file (SWIFT format)

---

### Step 4: Verify MT940 File

The MT940 file should contain SWIFT format data:

```
{1:F01AUBKPHMMAXXX0000000000}{2:I940XXXXXXXXXXXXXN2020}{4:
:20:8951125001003999
:25:001010039999
:28C:01025
:60F:C251125PHP129310383,19
:61:251125C100000,00NMSC2233720006
... (transactions)
:62F:C251125PHP136162919,99
-}
```

---

## 🔄 Running Multiple Tests

If you want to run the system again:

### Option A: Quick Reset (Reset sentflag only)

```bash
cd Conversion
python Test_Scripts\setup_test_email.py
```

Then run main.py again.

---

### Option B: Manual Database Reset

```bash
cd Conversion
python
```

```python
from Python_Modules.database import ado_connect, close_connection

conn = ado_connect()
cursor = conn.cursor()

# Reset sentflag
cursor.execute("UPDATE codetable SET sentflag = '0' WHERE emailreport = 'MT940'")
cursor.execute("UPDATE codetable SET sentflag = '0' WHERE emailreport LIKE 'MT940 for%'")
conn.commit()

print("Sentflag reset - system ready to run again")
close_connection(conn)
```

---

## 🐛 TROUBLESHOOTING

### Issue 1: "Processing already completed (sentflag != 0)"

**Cause**: System has already run, sentflag is set to prevent duplicate runs

**Solution**: Run the setup script to reset sentflag:
```bash
python Test_Scripts\setup_test_email.py
```

---

### Issue 2: No email received

**Check**:
1. ✅ Gmail credentials correct in `email_sender.py`?
2. ✅ USE_AUTH = True?
3. ✅ Check spam folder
4. ✅ Check console output for errors

**Debug**:
```bash
# Test email sending directly
cd Conversion
python Test_Scripts\test_email_sender.py
```

---

### Issue 3: "Authentication failed"

**Cause**: Gmail App Password incorrect or expired

**Solution**:
1. Generate new Gmail App Password:
   - Go to Google Account → Security
   - Enable 2FA if not enabled
   - Go to "App passwords"
   - Generate new password for "Mail"
2. Update `SMTP_PASSWORD` in `email_sender.py`

---

### Issue 4: No accounts to process

**Cause**: Database may not have accounts with transactions

**Check**:
```bash
cd Conversion
python
```

```python
from Python_Modules.database import ado_connect, close_connection

conn = ado_connect()
cursor = conn.cursor()

# Check accounts
cursor.execute("SELECT statementacctno, sendingType FROM MT940 LIMIT 5")
accounts = cursor.fetchall()
print("Accounts found:", accounts)

# Check transactions
cursor.execute("SELECT COUNT(*) FROM historyfile1_copy")
txn_count = cursor.fetchone()[0]
print("Transaction count:", txn_count)

close_connection(conn)
```

---

## 📊 WHAT TO EXPECT

### Files Created:
```
C:\MT940\Output\
└── 20251125\                    (Date: YYYYMMDD)
    └── AUB20881_20251125_001010039999_1024.txt
```

### Email Sent:
- **To**: adisneyplus8@gmail.com
- **Attachment**: MT940 file (SWIFT format)
- **Size**: ~1-2 KB per file

### Database Updates:
- `sentflag` updated to '1' (prevents duplicate processing)
- `filename` updated in MT940 table
- Counter incremented for next run

---

## 📋 QUICK REFERENCE

### Run Full System
```bash
cd Conversion\Python_Modules
python main.py
```

### Reset for Another Test
```bash
cd Conversion
python Test_Scripts\setup_test_email.py
```

### Check Generated Files
```bash
dir C:\MT940\Output\20251125\
```

### Test Email Only (Dry-run)
```bash
cd Conversion
python Test_Scripts\test_email_sender.py
```

---

## 🎯 SUCCESS CRITERIA

✅ **System runs without errors**  
✅ **MT940 file generated in C:\MT940\Output\YYYYMMDD\**  
✅ **Email received in Gmail inbox**  
✅ **MT940 file attached to email**  
✅ **File contains valid SWIFT format data**  
✅ **sentflag updated to '1' in database**

---

## 📝 NOTES

### VB6 vs Testing Difference

**VB6 Original** (Bank production):
- USE_AUTH = False (internal bank SMTP, no authentication)
- Sends to bank email addresses

**Your Testing Setup**:
- USE_AUTH = True (Gmail requires authentication) ✅
- Sends to your Gmail for testing ✅

**For Production**: Bank IT will revert to `USE_AUTH = False` and use bank's internal SMTP.

---

## 🎊 YOU'RE READY!

Your system is fully configured for Gmail testing. Just run:

```bash
# Step 1: Setup
cd Conversion
python Test_Scripts\setup_test_email.py

# Step 2: Run
cd Python_Modules
python main.py

# Step 3: Check Gmail inbox!
```

---

**Last Updated**: 2026-02-18  
**Email Config**: ✅ Gmail Ready  
**System Status**: ✅ Operational
