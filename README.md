# MT940 SWIFT Statement Generator

A Python conversion of a legacy VB6 system that generates SWIFT MT940 bank statement files and delivers them by email. Converted by Vincent (OJT Intern), March 2026.

---

## What It Does

Reads daily transaction records from a SQLite database, generates a properly formatted MT940 text file for each configured bank account, and sends the file to the recipient via email.

---

## Program Flow

```
python main.py
    │
    ├── 1. Prompt for processing date (YYYYMMDD)
    ├── 2. Connect to SQLite database
    ├── 3. Check if already processed today → skip if yes
    ├── 4. Load all accounts from MT940 table
    │
    └── 5. For each account:
            ├── Pick processor based on account type
            │     ├── Meralco  (code = MRALPHMMXXX)
            │     ├── Converge (format = B)
            │     ├── SWIFT    (sendingType = 1)
            │     └── Standard (all others)
            │
            ├── Query transactions for the date
            ├── Write MT940 file → C:\MT940\Output\YYYYMMDD\
            └── Send file by email
```

---

## How to Run

```bash
cd Conversion/Python_Modules
python main.py
```

Requires Python 3.8+ and the SQLite database file placed in `Conversion/Database_Config/`.  
See `Conversion/Documentation/HANDOVER_GUIDE.md` for full setup instructions.
