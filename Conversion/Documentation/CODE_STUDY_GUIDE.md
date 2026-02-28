# MT940 System - Code Study Guide
## How the Python Code Works (Technical Deep-Dive)

**Purpose**: This guide explains how the MT940 Python system works internally  
**Audience**: Developers learning the codebase  
**Prerequisite Knowledge**: Basic Python, SQL, file I/O  

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Module 1: database.py](#2-module-1-databasepy)
3. [Module 2: utils.py](#3-module-2-utilspy)
4. [Module 3: mt940_processor.py](#4-module-3-mt940_processorpy)
5. [Module 4: email_sender.py](#5-module-4-email_senderpy)
6. [Module 5: main.py](#6-module-5-mainpy)
7. [Data Flow Examples](#7-data-flow-examples)
8. [Common Tasks & How-Tos](#8-common-tasks--how-tos)
9. [Troubleshooting](#9-troubleshooting)
10. [Advanced Topics](#10-advanced-topics)

---

## 1. System Overview

### 1.1 What Does This System Do?

The MT940 system generates bank statement files in **SWIFT MT940 format** and sends them to external partners.

**Simple Analogy**: Think of it like an automated report generator:
1. You have transaction data in a database (like an Excel sheet)
2. The system reads that data
3. Formats it into a specific format (MT940 - like a PDF template)
4. Emails the file to recipients

**Real-World Flow**:
```
Bank Database → Python Program → MT940 File → Email → Customer
```

### 1.2 Key Concepts

**MT940 Format**: A standardized bank statement format used internationally  
**SWIFT**: Society for Worldwide Interbank Financial Telecommunication  
**Modular Design**: Code split into separate files, each with one job

### 1.3 File Organization

```
5 Python Modules (the "workers"):
├── main.py           → The "manager" - coordinates everything
├── database.py       → The "data clerk" - gets data from database
├── utils.py          → The "toolbox" - helper functions
├── mt940_processor.py → The "report writer" - creates MT940 files
└── email_sender.py   → The "mail room" - sends emails
```

---

## 2. Module 1: database.py

### 2.1 Purpose

**Job**: Talk to the SQLite database and get/update data

**Why It Exists**: 
- All database code in ONE place
- Easy to switch databases later (SQLite → MySQL, etc.)
- Prevents SQL injection attacks

### 2.2 Key Concept: Database Connection

**The Connection String**:
```python
# Step 1: Read where database is located
with open('casarepconn.txt', 'r') as f:
    database_path = f.read().strip()  # e.g., "mt940_test.db"

# Step 2: Connect to database
conn = sqlite3.connect(database_path)

# Step 3: Use connection to query data
cursor = conn.cursor()
cursor.execute("SELECT * FROM MT940")
```

**Why Read from File?**  
So you can change the database location WITHOUT changing code!

### 2.3 Core Function: ado_connect()

```python
def ado_connect():
    """
    Opens connection to database
    
    Steps:
    1. Find casarepconn.txt file
    2. Read database path from it
    3. Connect to SQLite database
    4. Return connection object
    """
    try:
        # Find the config file
        app_path = os.path.dirname(__file__)  # Current folder
        conn_file = os.path.join(app_path, "..", "Database_Config", "casarepconn.txt")
        
        # Read database path
        with open(conn_file, 'r') as f:
            # ... (read logic)
            str_conn = ...  # e.g., "mt940_test.db"
        
        # Connect
        conn = sqlite3.connect(str_conn)
        conn.row_factory = sqlite3.Row  # Makes results like dictionaries
        return conn
        
    except Exception as e:
        print(f"Error: {e}")
        return None
```

**Key Learning**: 
- `with open()` automatically closes file (even if error happens)
- `conn.row_factory = sqlite3.Row` lets you access columns by name

### 2.4 Parameterized Queries (Security!)

**BAD (Dangerous)**:
```python
# DON'T DO THIS - SQL Injection risk!
account = "12345"
query = f"SELECT * FROM MT940 WHERE account = '{account}'"
cursor.execute(query)
```

**GOOD (Safe)**:
```python
# DO THIS - Safe from SQL injection
account = "12345"
query = "SELECT * FROM MT940 WHERE account = ?"
cursor.execute(query, (account,))  # Parameterized
```

**Why?** If someone enters `' OR '1'='1` as account, the BAD code would return ALL records!

### 2.5 The Recordset Class (VB6 Compatibility)

VB6 had a `Recordset` object that could navigate records like this:
```vb6
rs.MoveNext        ' Go to next record
If rs.EOF Then     ' Check if at end
```

We created a Python version:

```python
class Recordset:
    """
    Emulates VB6 ADODB.Recordset behavior
    
    Makes it easier to convert VB6 code:
    - rs.eof → Check if no more records
    - rs["column"] → Get column value
    - rs.move_next() → Go to next record
    """
    
    def __init__(self, conn, sql, params=None):
        self.cursor = conn.cursor()
        if params:
            self.cursor.execute(sql, params)
        else:
            self.cursor.execute(sql)
        
        self.rows = self.cursor.fetchall()
        self.position = 0  # Current row index
    
    @property
    def eof(self):
        """Check if at end of records"""
        return self.position >= len(self.rows)
    
    def __getitem__(self, key):
        """Get column value: rs["account"]"""
        if self.eof:
            return None
        return self.rows[self.position][key]
    
    def move_next(self):
        """Go to next record"""
        self.position += 1
```

**Usage Example**:
```python
# Query accounts
rs = Recordset(conn, "SELECT * FROM MT940")

# Loop through results (VB6-style)
while not rs.eof:
    account = rs["statementacctno"]
    print(f"Account: {account}")
    rs.move_next()
```

### 2.6 Common Database Functions

```python
# 1. Get single record
def get_account_config(conn, account_no):
    """Get configuration for one account"""
    sql = "SELECT * FROM MT940 WHERE statementacctno = ?"
    cursor = conn.cursor()
    cursor.execute(sql, (account_no,))
    return cursor.fetchone()  # Returns one row or None

# 2. Get multiple records
def get_transaction_history(conn, account_no):
    """Get all transactions for account"""
    sql = """
        SELECT * FROM historyfile1_copy 
        WHERE acctno = ? AND delete_flag = 'N'
        ORDER BY txn_date
    """
    return Recordset(conn, sql, (account_no,))

# 3. Update database
def update_mt940_counter(conn, account_no, new_counter):
    """Increment statement counter"""
    sql = "UPDATE MT940 SET counter = ? WHERE statementacctno = ?"
    cursor = conn.cursor()
    cursor.execute(sql, (new_counter, account_no))
    conn.commit()  # IMPORTANT: Save changes!
```

**Key Learning**:
- `fetchone()` → One row (or None)
- `fetchall()` → All rows (list)
- `cursor.execute()` → Run query
- `conn.commit()` → Save changes (for UPDATE/INSERT/DELETE)

---

## 3. Module 2: utils.py

### 3.1 Purpose

**Job**: Provide reusable helper functions

**Why It Exists**:
- Don't repeat code
- Easy to test
- Easy to fix bugs (change one place)

### 3.2 Date Formatting Functions

VB6 had `Format(date, "YYYYMMDD")` to format dates.  
Python uses `strftime()`:

```python
from datetime import datetime

def format_date_yyyymmdd(date: datetime) -> str:
    """
    Convert date to YYYYMMDD format
    
    Example:
        date = datetime(2025, 11, 25)
        result = format_date_yyyymmdd(date)
        # result = "20251125"
    
    VB6 equivalent: Format(date, "YYYYMMDD")
    """
    return date.strftime("%Y%m%d")

# Usage
today = datetime.now()
filename = f"MT940_{format_date_yyyymmdd(today)}.txt"
# filename = "MT940_20251125.txt"
```

**Date Format Codes**:
- `%Y` = 4-digit year (2025)
- `%m` = 2-digit month (11)
- `%d` = 2-digit day (25)
- `%H` = Hour, `%M` = Minute, `%S` = Second

### 3.3 String Functions (VB6 Compatibility)

**VB6's Mid(), Left(), Right()** functions extract parts of strings.  
**Important**: VB6 uses **1-based indexing** (first character is position 1)  
Python uses **0-based indexing** (first character is position 0)

```python
def mid_str(string: str, start: int, length: int = None) -> str:
    """
    Extract substring (VB6 Mid function)
    
    VB6: Mid("HELLO", 2, 3) = "ELL"
    Python: Need to convert 1-based to 0-based
    
    Args:
        string: Source string
        start: Starting position (1-based, like VB6!)
        length: Number of characters (optional)
    
    Example:
        mid_str("HELLO", 2, 3) → "ELL"
        mid_str("HELLO", 2)    → "ELLO"
    """
    # Convert 1-based to 0-based
    start_index = start - 1
    
    if length is None:
        return string[start_index:]  # From start to end
    else:
        end_index = start_index + length
        return string[start_index:end_index]

# Comparison:
# VB6:    Mid("HELLO", 2, 3) = "ELL"
# Python: mid_str("HELLO", 2, 3) = "ELL"  ✅ Same!
```

**String Slicing in Python**:
```python
text = "HELLO"

# [start:end]
text[0:3]   # "HEL" (positions 0, 1, 2)
text[1:4]   # "ELL" (positions 1, 2, 3)

# [start:] - from start to end
text[2:]    # "LLO"

# [:end] - from beginning to end
text[:3]    # "HEL"

# [-n:] - last n characters
text[-2:]   # "LO" (last 2)
```

### 3.4 Currency Mapping (Dictionary Usage)

**VB6 used Select Case**:
```vb6
' VB6
Select Case code
    Case "16": currency = "EUR"
    Case "17": currency = "JPY"
    Case "18": currency = "CNY"
    Case "19": currency = "USD"
    Case Else: currency = "PHP"
End Select
```

**Python uses Dictionary** (faster, more Pythonic):
```python
def get_currency_code(code: str) -> str:
    """
    Map product code to currency code
    
    Migration guide rule: Use dictionaries instead of Select Case
    
    Product Codes:
        16 → EUR (Euro)
        17 → JPY (Japanese Yen)
        18 → CNY (Chinese Yuan)
        19 → USD (US Dollar)
        Other → PHP (Philippine Peso)
    """
    currency_map = {
        '16': 'EUR',
        '17': 'JPY',
        '18': 'CNY',
        '19': 'USD'
    }
    # .get(key, default) returns default if key not found
    return currency_map.get(code, 'PHP')

# Examples:
get_currency_code('16')  # → "EUR"
get_currency_code('99')  # → "PHP" (default)
```

**Key Learning**: 
- Dictionaries are like lookup tables
- `dict.get(key, default)` is safe (doesn't crash if key missing)

### 3.5 Amount Formatting

```python
def format_mt940_amount(amount: float) -> str:
    """
    Format amount for MT940 SWIFT format
    
    Rules:
    - 2 decimal places
    - Use comma as decimal separator (MT940 standard)
    - No thousands separator
    
    Example:
        amount = 1234567.89
        result = format_mt940_amount(amount)
        # result = "1234567,89"
    """
    # Format with 2 decimals
    formatted = f"{abs(amount):.2f}"
    
    # Replace . with ,
    formatted = formatted.replace('.', ',')
    
    return formatted

# Usage:
balance = 129310383.19
mt940_format = format_mt940_amount(balance)
# mt940_format = "129310383,19"
```

### 3.6 File System Operations

```python
import os

def check_file_exists(filepath: str) -> bool:
    """Check if file exists (VB6 Dir function)"""
    return os.path.exists(filepath)

def create_directory(path: str):
    """Create directory if doesn't exist (VB6 MkDir)"""
    os.makedirs(path, exist_ok=True)
    # exist_ok=True → Don't error if already exists

# Usage:
output_dir = "C:\\MT940\\Output\\20251125"
if not check_file_exists(output_dir):
    create_directory(output_dir)
```

---

## 4. Module 3: mt940_processor.py

### 4.1 Purpose

**Job**: Generate MT940 SWIFT statement files

**This is the CORE of the system** - the most complex module.

### 4.2 MT940 Format Explained

MT940 is a SWIFT message format for bank statements. Think of it like a template:

```
{1:F01AUBKPHMMAXXX0000000000}           ← Block 1: Basic Header
{2:I940AUBKPHMMXXXXN2020}              ← Block 2: Application Header
{4:                                     ← Block 4: Text Block (main content)
:20:8951125001003999                    ← Transaction Reference
:25:001010039999                        ← Account Number
:28C:01025                              ← Statement Number
:60F:C251125PHP129310383,19            ← Opening Balance
:61:251125C100000,00NMSC2233720006     ← Transaction 1
:61:251125D52536,80NMSC//NonRef        ← Transaction 2
:62F:C251125PHP136162919,99            ← Closing Balance
-}                                      ← End of message
```

**Field Breakdown**:
- `:20:` = Transaction reference (unique ID)
- `:25:` = Account number
- `:28C:` = Statement sequence number
- `:60F:` = Opening balance
  - `C` = Credit (positive)
  - `D` = Debit (negative)
  - `251125` = Date (YYMMDD)
  - `PHP` = Currency
  - `129310383,19` = Amount
- `:61:` = Transaction details
  - `251125` = Date
  - `C` = Credit, `D` = Debit
  - `100000,00` = Amount
  - `NMSC` = Transaction type code
  - `2233720006` = Reference
- `:62F:` = Closing balance (same format as :60F:)

### 4.3 Main Function: process_mt940_new()

This function has **10 sections** (like 10 steps in a recipe):

```python
def process_mt940_new(conn, counter, account_no, code, prev_bus_date):
    """
    Generate MT940 file for account
    
    Args:
        conn: Database connection
        counter: Statement counter (e.g., 1, 2, 3...)
        account_no: Account number (e.g., "001010039999")
        code: SWIFT BIC code
        prev_bus_date: Statement date
    
    Returns:
        filename if success, None if error
    
    Steps:
        1. Read configuration
        2. Generate filename
        3. Format dates
        4. Write file header
        5. Get currency & transactions
        6. Calculate opening balance
        7. Loop through transactions
        8. Write closing balance
        9. Insert summary records (if needed)
       10. Handle no-movement accounts
    """
```

### 4.4 Section-by-Section Breakdown

**SECTION 1: Initialization**
```python
# Read account config from database
config = get_account_config(conn, account_no)

# Extract settings
sen_typ = str(config['sendingType'])      # Email or SFTP?
code_prod = str(config['code'])           # SWIFT code
extension_type = config['extension_type']  # File extension (.txt)
field86_flag = config['field86_flag']     # Include :86: field?

# Initialize flags
is_first = True  # Is this the first transaction?
```

**SECTION 2: Filename Generation**
```python
# Build filename: AUB20881_YYYYMMDD_ACCTNO_COUNTER.txt
date_str = format_date_yyyymmdd(prev_bus_date)  # "20251125"
counter_str = pad_zeros(counter, 3)             # "001"

filename = f"AUB20881_{date_str}_{account_no}_{counter_str}.txt"
# Result: "AUB20881_20251125_001010039999_001.txt"

# Build full path
output_path = f"C:\\MT940\\Output\\{date_str}\\"
full_path = output_path + filename

# Create directory if needed
create_directory(output_path)
```

**SECTION 3-4: Write File Header**
```python
# Open file for writing
with open(full_path, 'w') as file_handle:
    
    # Block 1: Basic Header
    file_handle.write("{1:F01AUBKPHMMAXXX0000000000}")
    
    # Block 2: Application Header
    file_handle.write("{2:I940")
    file_handle.write(mid_str(code, 1, 8))  # First 8 chars of SWIFT code
    file_handle.write("X")
    file_handle.write(mid_str(code, 9, 11))  # Last 11 chars
    file_handle.write("N2020}{4:\n")
    
    # :20: Transaction Reference
    stmdate = get_stmdate(prev_bus_date)  # Last 5 digits of date
    ref_no = f"89{stmdate}{mid_str(account_no, 1, 3)}{mid_str(account_no, 6, 6)}"
    file_handle.write(f":20:{ref_no}\n")
    
    # :25: Account Number
    file_handle.write(f":25:{account_no}\n")
    
    # :28C: Statement Sequence
    padded_counter = pad_zeros(counter + 1, 5)  # 5 digits
    file_handle.write(f":28C:0{padded_counter}\n")
```

**SECTION 5: Get Currency & Transactions**
```python
# Extract product code from account number (positions 4-5)
product_code = mid_str(account_no, 4, 2)  # e.g., "01"

# Map to currency
currency = get_currency_code(product_code)  # "PHP"

# Query transactions
transactions = get_transaction_history(conn, account_no)
```

**SECTION 6-7: Process Transactions**
```python
# Initialize running balance
ledger_balance = 0.0
is_first = True

# Loop through transactions
while not transactions.eof:
    # Get transaction details
    txn_type = transactions["txn_type"]      # "D" or "C"
    txn_amount = float(transactions["txn_amt"])
    ledger_bal = float(transactions["ledger_bal"])
    ref_no = transactions["refno"] or "NonRef"
    
    # First transaction? Calculate opening balance
    if is_first:
        if txn_type == "D":
            opening_bal = ledger_bal + txn_amount
        else:
            opening_bal = ledger_bal - txn_amount
        
        # Write :60F: Opening Balance
        bal_indicator = "C" if opening_bal >= 0 else "D"
        file_handle.write(f":60F:{bal_indicator}")
        file_handle.write(f"{stmdate2}{currency}")
        file_handle.write(f"{format_mt940_amount(opening_bal)}\n")
        
        is_first = False
    
    # Write :61: Transaction Line
    file_handle.write(f":61:{stmdate2}{txn_type}")
    file_handle.write(f"{format_mt940_amount(txn_amount)}")
    file_handle.write(f"NMSC{ref_no}\n")
    
    # Write :86: Supplementary Info (if enabled)
    if field86_flag == "Y":
        file_handle.write(f":86:{txn_type} transaction\n")
    
    # Update running balance
    if txn_type == "C":
        ledger_balance += txn_amount
    else:
        ledger_balance -= txn_amount
    
    transactions.move_next()
```

**SECTION 8: Write Closing Balance**
```python
# Write :62F: Closing Balance
final_balance = ledger_balance
bal_indicator = "C" if final_balance >= 0 else "D"

file_handle.write(f":62F:{bal_indicator}{stmdate2}{currency}")
file_handle.write(f"{format_mt940_amount(abs(final_balance))}\n")

# Write footer
file_handle.write("-}\n")

# File automatically closes here (with statement)
```

### 4.5 Key Concepts

**Context Manager (with statement)**:
```python
# Old way (manual close)
file = open("test.txt", 'w')
file.write("Hello")
file.close()  # Must remember to close!

# New way (automatic close)
with open("test.txt", 'w') as file:
    file.write("Hello")
# File automatically closes, even if error occurs!
```

**Running Balance Calculation**:
```
Opening Balance: 1000.00
+ Credit 100.00 → 1100.00
- Debit 50.00   → 1050.00
+ Credit 200.00 → 1250.00
= Closing Balance: 1250.00
```

---

## 5. Module 4: email_sender.py

### 5.1 Purpose

**Job**: Send MT940 files via email

### 5.2 Email Configuration

```python
# SMTP Settings (at top of file)
SMTP_HOST = "smtp.gmail.com"      # Email server
SMTP_PORT = 587                    # Port (587 for TLS)
USE_TLS = True                     # Use encryption?
USE_AUTH = True                    # Need username/password?

# Sender Info
FROM_EMAIL = "mt940@bank.com"
FROM_NAME = "MT940 System"

# Authentication
SMTP_USERNAME = "mt940@bank.com"
SMTP_PASSWORD = "secret_password"
```

### 5.3 Email Workflow

```python
def send_mail(to, cc, subject, body, attachment_path):
    """
    Send email with MT940 file attached
    
    Steps:
    1. Create email message (MIME format)
    2. Add recipient, subject, body
    3. Attach MT940 file
    4. Connect to SMTP server
    5. Send email
    6. Disconnect
    """
    
    # STEP 1: Create Message
    msg = MIMEMultipart()
    msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg['To'] = to
    msg['Cc'] = cc
    msg['Subject'] = subject
    
    # STEP 2: Add Body
    msg.attach(MIMEText(body, 'html'))
    
    # STEP 3: Attach File
    if os.path.exists(attachment_path):
        with open(attachment_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition',
                          f'attachment; filename={os.path.basename(attachment_path)}')
            msg.attach(part)
    
    # STEP 4-6: Send Email
    try:
        if USE_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()  # Encrypt connection
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        
        if USE_AUTH:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
        
        all_recipients = [to] + ([cc] if cc else [])
        server.sendmail(FROM_EMAIL, all_recipients, msg.as_string())
        server.quit()
        
        return True  # Success!
        
    except Exception as e:
        print(f"Email failed: {e}")
        return False
```

### 5.4 MIME Explained (Simplified)

**MIME** = Multipurpose Internet Mail Extensions (format for emails)

```
Think of email like a package:
┌─────────────────────────┐
│ Envelope:               │  ← Headers (From, To, Subject)
│  From: sender@bank.com  │
│  To: recipient@bank.com │
│  Subject: MT940         │
├─────────────────────────┤
│ Letter (Body):          │  ← Body text
│  "Dear Customer..."     │
├─────────────────────────┤
│ Attachment:             │  ← Attached files
│  [MT940 file]           │
└─────────────────────────┘
```

---

## 6. Module 5: main.py

### 6.1 Purpose

**Job**: Coordinate everything (the "conductor" of the orchestra)

### 6.2 Main Workflow

```python
def run_mt940_process(prev_bus_date):
    """
    Main MT940 processing workflow
    
    Think of it like a factory assembly line:
    
    1. Check if factory should run today
    2. Get list of products to make
    3. For each product:
       - Make it (generate MT940)
       - Package it (prepare email)
       - Ship it (send email)
    4. Clean up and report results
    """
    
    # STEP 1: Connect to Database
    conn = ado_connect()
    if not conn:
        return False  # Can't work without data!
    
    # STEP 2: Should we run? (Check sentflag)
    willProcess = Recordset(conn, "SELECT sentflag FROM codetable WHERE emailreport = 'MT940'")
    if willProcess.eof or willProcess["sentflag"] != "0":
        print("Already processed today")
        return True  # Exit gracefully
    
    # STEP 3: Get Accounts to Process
    accounts = Recordset(conn, "SELECT * FROM MT940")
    
    # STEP 4: Process Each Account
    while not accounts.eof:
        account_no = accounts["statementacctno"]
        counter = accounts["counter"]
        code = accounts["code"]
        sending_type = accounts["sendingType"]
        
        # Route to correct processor (routing logic)
        if code == "MRALPHMMXXX":
            filename = process_mt940_meralco(...)
        elif sending_type == "1":
            filename = process_mt940_swift(...)
        else:
            filename = process_mt940_new(...)  # Default
        
        # Send based on sendingType
        if sending_type == "2":  # Email
            recipients = get_email_recipients(conn, account_no)
            send_mail(recipients, subject, body, filename)
            update_sent_flag(conn, account_no)
        
        accounts.move_next()
    
    # STEP 5: Cleanup
    close_connection(conn)
    return True
```

### 6.3 Routing Logic Explained

```
Account Request
     │
     ├─ Is it Meralco account? (code = "MRALPHMMXXX")
     │   ├─ YES → Use Meralco processor
     │   └─ NO → Continue checking...
     │
     ├─ Is it Converge format? (Format = "B")
     │   ├─ YES → Use Converge processor
     │   └─ NO → Continue checking...
     │
     ├─ Is it SWIFT type? (sendingType = "1")
     │   ├─ YES → Use SWIFT processor
     │   └─ NO → Use standard processor
```

---

## 7. Data Flow Examples

### 7.1 Example 1: Full Processing Flow

**Scenario**: Process account 001010039999

```
START
  │
  ├─ main.py
  │   └─ run_mt940_process()
  │       │
  │       ├─ [1] Connect Database
  │       │   └─ database.py → ado_connect()
  │       │       └─ Returns: conn
  │       │
  │       ├─ [2] Check sentflag
  │       │   └─ database.py → Recordset(...)
  │       │       └─ Returns: sentflag = "0" (OK to run)
  │       │
  │       ├─ [3] Query Account
  │       │   └─ database.py → Recordset("SELECT * FROM MT940")
  │       │       └─ Returns: account_no = "001010039999"
  │       │                   counter = 1
  │       │                   sendingType = "2"
  │       │
  │       ├─ [4] Generate MT940
  │       │   └─ mt940_processor.py → process_mt940_new(...)
  │       │       │
  │       │       ├─ utils.py → format_date_yyyymmdd()
  │       │       │   └─ Returns: "20251125"
  │       │       │
  │       │       ├─ database.py → get_transaction_history()
  │       │       │   └─ Returns: 30 transactions
  │       │       │
  │       │       ├─ utils.py → get_currency_code("01")
  │       │       │   └─ Returns: "PHP"
  │       │       │
  │       │       └─ Write file to:
  │       │           C:\MT940\Output\20251125\
  │       │           AUB20881_20251125_001010039999_001.txt
  │       │
  │       └─ [5] Send Email
  │           └─ email_sender.py → send_mail(...)
  │               │
  │               ├─ database.py → get_email_recipients()
  │               │   └─ Returns: "user@example.com"
  │               │
  │               ├─ Build email message
  │               ├─ Attach MT940 file
  │               └─ Send via SMTP
  │                   └─ Success!
  │
END (File generated and emailed)
```

### 7.2 Example 2: Balance Calculation

**Scenario**: Account with 3 transactions

```
Database Data:
┌─────────────┬──────────┬────────────┬──────────────┐
│ Transaction │ Type     │ Amount     │ Ledger Bal   │
├─────────────┼──────────┼────────────┼──────────────┤
│ 1           │ C (Cred) │ 1000.00    │ 5000.00      │
│ 2           │ D (Deb)  │ 500.00     │ 4500.00      │
│ 3           │ C (Cred) │ 2000.00    │ 6500.00      │
└─────────────┴──────────┴────────────┴──────────────┘

Processing:
1. First Transaction (ledger_bal = 5000, txn_amt = 1000, type = C)
   → Opening Balance = ledger_bal - txn_amt
   → Opening Balance = 5000 - 1000 = 4000.00
   → Write: ":60F:C251125PHP4000,00"

2. Transaction 1
   → Write: ":61:251125C1000,00NMSC..."
   → Running Balance = 4000 + 1000 = 5000.00

3. Transaction 2
   → Write: ":61:251125D500,00NMSC..."
   → Running Balance = 5000 - 500 = 4500.00

4. Transaction 3
   → Write: ":61:251125C2000,00NMSC..."
   → Running Balance = 4500 + 2000 = 6500.00

5. Closing Balance
   → Write: ":62F:C251125PHP6500,00"
```

---

## 8. Common Tasks & How-Tos

### 8.1 How to Add a New Utility Function

**Example**: Add function to format phone numbers

```python
# In utils.py

def format_phone_number(phone: str) -> str:
    """
    Format phone number to standard format
    
    Args:
        phone: Raw phone number (e.g., "09171234567")
    
    Returns:
        Formatted phone (e.g., "+63-917-123-4567")
    
    Example:
        format_phone_number("09171234567")
        # Returns: "+63-917-123-4567"
    """
    # Remove leading 0
    if phone.startswith('0'):
        phone = phone[1:]
    
    # Format: +63-917-123-4567
    return f"+63-{phone[:3]}-{phone[3:6]}-{phone[6:]}"
```

### 8.2 How to Add a New Database Query

**Example**: Get accounts by currency

```python
# In database.py

def get_accounts_by_currency(conn: sqlite3.Connection, currency: str):
    """
    Get all accounts using specific currency
    
    Args:
        conn: Database connection
        currency: Currency code (e.g., "PHP", "USD")
    
    Returns:
        Recordset of matching accounts
    """
    # Extract product codes for this currency
    # (Reverse lookup from get_currency_code)
    currency_codes = {
        'EUR': '16',
        'JPY': '17',
        'CNY': '18',
        'USD': '19',
        'PHP': '01'  # Default
    }
    
    product_code = currency_codes.get(currency, '01')
    
    # Query accounts where positions 4-5 match product code
    sql = """
        SELECT * FROM MT940 
        WHERE SUBSTR(statementacctno, 4, 2) = ?
    """
    
    return Recordset(conn, sql, (product_code,))

# Usage:
usd_accounts = get_accounts_by_currency(conn, "USD")
while not usd_accounts.eof:
    print(usd_accounts["statementacctno"])
    usd_accounts.move_next()
```

### 8.3 How to Debug MT940 Generation

**Problem**: MT940 file looks wrong

**Solution**: Add debug prints

```python
# In mt940_processor.py, add prints:

def process_mt940_new(...):
    # ... existing code ...
    
    # Debug: Print what we're about to write
    print(f"DEBUG: Opening Balance = {opening_bal}")
    print(f"DEBUG: Currency = {currency}")
    print(f"DEBUG: Transaction Count = {len(transactions.rows)}")
    
    # Write opening balance
    file_handle.write(f":60F:...")
    print(f"DEBUG: Wrote opening balance line")
    
    # Loop transactions
    while not transactions.eof:
        txn_amt = transactions["txn_amt"]
        print(f"DEBUG: Processing txn amount = {txn_amt}")
        # ... existing code ...
```

### 8.4 How to Test Without Sending Real Emails

**Option 1**: Use Dry-Run Flag

```python
# In email_sender.py, add DRY_RUN flag
DRY_RUN = True  # Set to False for real sending

def send_mail(...):
    if DRY_RUN:
        print("[DRY RUN] Would send email:")
        print(f"  To: {to}")
        print(f"  Subject: {subject}")
        print(f"  Attachment: {attachment_path}")
        return True  # Pretend success
    
    # Real sending code...
```

**Option 2**: Use Mailtrap (Testing Service)

```python
# Change SMTP settings
SMTP_HOST = "smtp.mailtrap.io"
SMTP_PORT = 2525
SMTP_USERNAME = "your_mailtrap_username"
SMTP_PASSWORD = "your_mailtrap_password"

# Emails will be captured in Mailtrap inbox (not sent to real recipients)
```

---

## 9. Troubleshooting

### 9.1 Common Errors & Solutions

**Error 1**: `FileNotFoundError: casarepconn.txt not found`

**Cause**: Program can't find database connection file

**Solution**:
```python
# Check path in ado_connect():
app_path = os.path.dirname(__file__)
conn_file = os.path.join(app_path, "..", "Database_Config", "casarepconn.txt")

# Make sure file exists at:
# Conversion/Database_Config/casarepconn.txt
```

**Error 2**: `sqlite3.OperationalError: no such column: acctno`

**Cause**: Column name doesn't exist in database

**Solution**:
```bash
# Check actual column names
python
>>> from Python_Modules.database import ado_connect
>>> conn = ado_connect()
>>> cursor = conn.cursor()
>>> cursor.execute("PRAGMA table_info(MT940)")
>>> for row in cursor.fetchall():
...     print(row[1])  # Print column names
```

**Error 3**: `UnicodeEncodeError: 'charmap' codec can't encode...`

**Cause**: Trying to print special characters (emojis, arrows)

**Solution**:
```python
# Replace emojis with text
print("[OK]")   # Instead of print("✅")
print("[FAIL]") # Instead of print("❌")
```

**Error 4**: `smtplib.SMTPAuthenticationError: Username and Password not accepted`

**Cause**: Wrong email credentials or Gmail security blocking

**Solution for Gmail**:
1. Enable 2-Factor Authentication
2. Generate App Password (not regular password)
3. Use App Password in code

### 9.2 Debugging Techniques

**Technique 1**: Add Print Statements

```python
# At start of function
print(f"[DEBUG] Function called with: account={account_no}, counter={counter}")

# Before database query
print(f"[DEBUG] About to query: {sql}")

# After getting results
print(f"[DEBUG] Query returned {len(results)} rows")

# Before file write
print(f"[DEBUG] Writing to file: {filename}")
```

**Technique 2**: Use Python Debugger (pdb)

```python
import pdb

def process_mt940_new(...):
    # ... some code ...
    
    # Pause here and inspect variables
    pdb.set_trace()  # Program stops here
    
    # ... rest of code ...

# When running:
# (Pdb) print account_no      # Print variable
# (Pdb) print transactions.rows  # Print list
# (Pdb) c                    # Continue
# (Pdb) q                    # Quit
```

**Technique 3**: Write to Log File

```python
import datetime

def log(message):
    """Write debug message to log file"""
    with open("debug.log", "a") as f:
        timestamp = datetime.datetime.now()
        f.write(f"[{timestamp}] {message}\n")

# Usage:
log(f"Processing account {account_no}")
log(f"Generated file: {filename}")
```

---

## 10. Advanced Topics

### 10.1 Type Hints Explained

Python is dynamically typed (don't need to declare types), but type hints help:

```python
# Without type hints
def add(a, b):
    return a + b

# With type hints
def add(a: int, b: int) -> int:
    return a + b

# Benefits:
# 1. Self-documenting (you know what types are expected)
# 2. IDE can autocomplete better
# 3. Catch errors before running
```

**Common Type Hints**:
```python
from typing import Optional, List, Tuple, Dict

def get_user(user_id: int) -> Optional[str]:
    """
    Get username by ID
    
    Returns: str if found, None if not found
    """
    # Optional[str] means: str or None
    pass

def get_transactions() -> List[Dict[str, any]]:
    """
    Get list of transactions
    
    Returns: List of dictionaries
    """
    # List[Dict[str, any]] means: list of dicts
    pass

def get_balance() -> Tuple[float, str]:
    """
    Get balance and currency
    
    Returns: (amount, currency)
    """
    # Tuple[float, str] means: tuple of (number, string)
    pass
```

### 10.2 Context Managers Deep-Dive

**What is `with` statement?**

```python
# Without with (old way):
f = open("file.txt", "r")
try:
    content = f.read()
    # ... do stuff ...
finally:
    f.close()  # Always close, even if error

# With with (new way):
with open("file.txt", "r") as f:
    content = f.read()
    # ... do stuff ...
# File automatically closed here!
```

**How it works**:
```python
# Any object with __enter__ and __exit__ can be used with "with"

class DatabaseConnection:
    def __enter__(self):
        print("Opening connection")
        self.conn = sqlite3.connect("db.sqlite")
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Closing connection")
        self.conn.close()

# Usage:
with DatabaseConnection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM MT940")
# Connection automatically closed
```

### 10.3 List Comprehensions

**Quick way to create lists**:

```python
# Old way (loop):
numbers = []
for i in range(10):
    numbers.append(i * 2)
# Result: [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

# New way (list comprehension):
numbers = [i * 2 for i in range(10)]
# Same result, one line!

# With condition:
even_numbers = [i for i in range(20) if i % 2 == 0]
# Result: [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

# Real example from our code:
accounts = ["001010039999", "001011026318", "001190039692"]
formatted = [f"Account: {acc}" for acc in accounts]
# Result: ["Account: 001010039999", "Account: 001011026318", ...]
```

### 10.4 Dictionary Comprehensions

```python
# Create dictionary from list
accounts = ["001010039999", "001011026318"]
account_dict = {acc: len(acc) for acc in accounts}
# Result: {"001010039999": 12, "001011026318": 12}

# Filter dictionary
config = {"USE_TLS": True, "USE_AUTH": False, "PORT": 587}
enabled_only = {k: v for k, v in config.items() if v == True}
# Result: {"USE_TLS": True}
```

### 10.5 Lambda Functions

**Quick one-line functions**:

```python
# Regular function:
def add(a, b):
    return a + b

# Lambda function (anonymous):
add = lambda a, b: a + b

# Useful with sorted():
accounts = [
    {"name": "Alice", "balance": 5000},
    {"name": "Bob", "balance": 3000},
    {"name": "Charlie", "balance": 7000}
]

# Sort by balance
sorted_accounts = sorted(accounts, key=lambda x: x["balance"])
# Result: Bob (3000), Alice (5000), Charlie (7000)
```

---

## 11. Summary & Quick Reference

### 11.1 Module Responsibilities

| Module | Job | Key Functions |
|--------|-----|---------------|
| **main.py** | Orchestrate | run_mt940_process() |
| **database.py** | Data access | ado_connect(), Recordset, get_*(), update_*() |
| **utils.py** | Helpers | format_date_*(), get_currency_code(), mid_str() |
| **mt940_processor.py** | Generate files | process_mt940_new() |
| **email_sender.py** | Send emails | send_mail(), get_email_recipients() |

### 11.2 Common Patterns

**Pattern 1: Database Query**
```python
conn = ado_connect()
rs = Recordset(conn, "SELECT * FROM table WHERE id = ?", (id,))
if not rs.eof:
    value = rs["column"]
close_connection(conn)
```

**Pattern 2: File Writing**
```python
with open(filepath, 'w') as f:
    f.write("content")
# File auto-closes
```

**Pattern 3: Error Handling**
```python
try:
    # Risky code
    result = do_something()
except Exception as e:
    print(f"Error: {e}")
    return False
else:
    # Runs if no error
    return True
finally:
    # Always runs
    cleanup()
```

### 11.3 Key Takeaways

1. ✅ **Modular design** = Easy to maintain
2. ✅ **Parameterized queries** = Secure
3. ✅ **Context managers** = Safe resource handling
4. ✅ **Type hints** = Self-documenting code
5. ✅ **VB6 compatibility layer** = Easier migration

---

## 12. Further Learning

### 12.1 Python Concepts to Study

1. **Object-Oriented Programming (OOP)**
   - Classes and objects
   - Inheritance
   - Encapsulation

2. **Decorators**
   - `@property`
   - `@staticmethod`
   - Custom decorators

3. **Generators**
   - `yield` keyword
   - Memory-efficient iteration

4. **Async/Await**
   - Asynchronous programming
   - `asyncio` library

### 12.2 Recommended Resources

**Books**:
- "Python Crash Course" by Eric Matthes (beginner)
- "Fluent Python" by Luciano Ramalho (advanced)
- "Effective Python" by Brett Slatkin (best practices)

**Online**:
- Python.org official tutorial
- Real Python (realpython.com)
- Python documentation (docs.python.org)

**Practice**:
- LeetCode (leetcode.com) - coding problems
- Project Euler - math/programming challenges
- GitHub - read open source code

---

## Conclusion

This MT940 system demonstrates:
- ✅ Clean modular architecture
- ✅ VB6 to Python migration patterns
- ✅ Database operations
- ✅ File generation
- ✅ Email integration
- ✅ Error handling
- ✅ Testing practices

**Keep Learning!** The best way to understand code is to:
1. Read it
2. Modify it
3. Break it (intentionally!)
4. Fix it

Good luck with your Python journey! 🚀

---

**Document Version**: 1.0  
**Last Updated**: February 18, 2026  
**For**: Vincent (Intern Study Guide)
