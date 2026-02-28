"""
test_all_modules.py — Single comprehensive test for the MT940 system.

Covers:
  Section 1  : Module imports
  Section 2  : Database connection + schema check
  Section 3  : Utility functions  (utils.py)
  Section 4  : Database queries   (database.py)
  Section 5  : Email module       (email_sender.py)
  Section 6  : MT940 processor signatures
  Section 7  : MT940 processor live runs (all 4 processors)
  Section 8  : Full main.py integration run
  Section 9  : Post-run output verification
  Summary    : Pass / Fail totals

Usage:
  python Test_Scripts\\test_all_modules.py
"""

import sys
import os
import inspect
import traceback
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python_Modules'))

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"
SKIP = "[SKIP]"

results = []


def check(label, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((status, label, detail))
    suffix = f" -- {detail}" if detail else ""
    print(f"  {status} {label}{suffix}")
    return passed


def section(title):
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print(f"{'=' * 65}")


# ===========================================================================
# SECTION 1: MODULE IMPORTS
# ===========================================================================
section("1. MODULE IMPORTS")

try:
    from database import (
        ado_connect, close_connection,
        get_account_config, get_mt940_accounts,
        get_account_transactions, get_swift_trancode,
        check_processing_flag,
        update_mt940_counter, update_mt940_filename,
        insert_summary_record, clear_summary_table, get_summary_report,
        check_sent_flag,
        Recordset,
    )
    # Also grab the database-level email recipient reader under an alias
    from database import get_email_recipients as db_get_email_recipients
    check("database.py imports", True)
except Exception as e:
    check("database.py imports", False, str(e))
    sys.exit(1)

try:
    from utils import (
        format_date_yyyymmdd,
        get_stmdate, get_stmdate2, get_stmdate3,
        pad_zeros, mid_str,
        get_currency_code,
        format_mt940_amount,
        create_directory, check_file_exists,
    )
    check("utils.py imports", True)
except Exception as e:
    check("utils.py imports", False, str(e))
    sys.exit(1)

try:
    from mt940_processor import (
        process_mt940_new, process_mt940_meralco,
        process_mt940_converge, process_mt940_swift,
    )
    check("mt940_processor.py imports", True)
    check("process_mt940_new callable",      callable(process_mt940_new))
    check("process_mt940_meralco callable",  callable(process_mt940_meralco))
    check("process_mt940_converge callable", callable(process_mt940_converge))
    check("process_mt940_swift callable",    callable(process_mt940_swift))
except Exception as e:
    check("mt940_processor.py imports", False, str(e))
    sys.exit(1)

try:
    from email_sender import (
        send_mail, build_email_subject, build_email_body,
        get_email_recipients, update_sent_flag,
        _parse_addresses as parse_recipients,
        _clean_attachment_path as clean_attachment_path,
        SMTP_HOST, SMTP_PORT, FROM_EMAIL, USE_AUTH, USE_TLS,
        SMTP_USERNAME,
    )
    check("email_sender.py imports", True)
    check("SMTP_HOST configured", SMTP_HOST not in ("", "smtp.yourbank.com"), f"Host: {SMTP_HOST}")
    check("FROM_EMAIL configured", "@" in FROM_EMAIL, f"From: {FROM_EMAIL}")
except Exception as e:
    check("email_sender.py imports", False, str(e))

try:
    conv_dir = os.path.join(os.path.dirname(__file__), '..')
    if conv_dir not in sys.path:
        sys.path.insert(0, conv_dir)
    import Python_Modules.main as main_module
    check("main.py importable", True)
except Exception as e:
    check("main.py importable", False, str(e))


# ===========================================================================
# SECTION 2: DATABASE CONNECTION + SCHEMA
# ===========================================================================
section("2. DATABASE CONNECTION + SCHEMA")

conn = ado_connect()
check("SQLite connection established", conn is not None)
if not conn:
    print("\n[ABORT] Cannot continue without a database connection.")
    sys.exit(1)

cursor = conn.cursor()

# Required tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables_found = [r[0] for r in cursor.fetchall()]
check(f"Tables found in database", len(tables_found) > 0, f"{len(tables_found)} tables")

for tbl in ("MT940", "historyfile1_copy", "acctmstr_copy", "codetable"):
    check(f"Table '{tbl}' exists", tbl in tables_found)


# ===========================================================================
# SECTION 3: UTILITY FUNCTIONS
# ===========================================================================
section("3. UTILITY FUNCTIONS")

d      = datetime(2024, 9, 18)
d_str  = format_date_yyyymmdd(d)

check("format_date_yyyymmdd",          d_str == "20240918",           d_str)
check("get_stmdate  (str input)",      get_stmdate(d_str)  == "40918", get_stmdate(d_str))
check("get_stmdate  (datetime input)", get_stmdate(d)      == "40918", get_stmdate(d))
check("get_stmdate2 (str input)",      get_stmdate2(d_str) == "240918", get_stmdate2(d_str))
check("get_stmdate2 (datetime input)", get_stmdate2(d)     == "240918", get_stmdate2(d))
check("get_stmdate3 (str input)",      get_stmdate3(d_str) == "0918",  get_stmdate3(d_str))
check("get_stmdate3 (datetime input)", get_stmdate3(d)     == "0918",  get_stmdate3(d))

check("pad_zeros(7, 3)",    pad_zeros(7, 3)    == "007",  pad_zeros(7, 3))
check("pad_zeros(42, 5)",   pad_zeros(42, 5)   == "00042",pad_zeros(42, 5))
check("pad_zeros(1024, 3)", pad_zeros(1024, 3) == "1024", pad_zeros(1024, 3))

check("mid_str chars 1-3", mid_str("001010039999", 1, 3) == "001",    mid_str("001010039999", 1, 3))
check("mid_str chars 6-6", mid_str("001010039999", 6, 6) == "003999", mid_str("001010039999", 6, 6))
check("mid_str chars 4-2", mid_str("001010039999", 4, 2) == "01",     mid_str("001010039999", 4, 2))

check("get_currency_code PHP (01)", get_currency_code("01") == "PHP", get_currency_code("01"))
check("get_currency_code USD (19)", get_currency_code("19") == "USD", get_currency_code("19"))
check("get_currency_code EUR (16)", get_currency_code("16") == "EUR", get_currency_code("16"))

check("format_mt940_amount 1234.56",  format_mt940_amount(1234.56)   == "1234,56",   format_mt940_amount(1234.56))
check("format_mt940_amount 0.0",      format_mt940_amount(0.0)       == "0,00",      format_mt940_amount(0.0))
check("format_mt940_amount 100000.5", format_mt940_amount(100000.50) == "100000,50", format_mt940_amount(100000.50))

check("check_file_exists (this file)", check_file_exists(__file__))
check("check_file_exists (fake file)", not check_file_exists("nonexistent_xyz99.txt"))

# VB6 reference-number example
stmtacctno = "001010039999"
stmdate_val = "51125"
refnum = f":20:89{stmdate_val}{mid_str(stmtacctno, 1, 3)}{mid_str(stmtacctno, 6, 6)}"
check("VB6 reference number format", refnum == ":20:8951125001003999", refnum)


# ===========================================================================
# SECTION 4: DATABASE QUERIES
# ===========================================================================
section("4. DATABASE QUERIES")

try:
    cursor.execute("SELECT COUNT(*) AS cnt FROM MT940")
    acct_count = cursor.fetchone()["cnt"]
    check("MT940 table readable", acct_count > 0, f"{acct_count} account(s)")
except Exception as e:
    check("MT940 table readable", False, str(e))

try:
    cursor.execute("SELECT COUNT(*) AS cnt FROM historyfile1_copy WHERE delete_flag = 'N'")
    txn_count = cursor.fetchone()["cnt"]
    check("historyfile1_copy readable", True, f"{txn_count} transaction(s)")
except Exception as e:
    check("historyfile1_copy readable", False, str(e))

try:
    cursor.execute("SELECT COUNT(*) AS cnt FROM codetable WHERE emailreport = 'MT940'")
    ct_count = cursor.fetchone()["cnt"]
    check("codetable MT940 entry exists", ct_count > 0, f"{ct_count} row(s)")
except Exception as e:
    check("codetable MT940 entry exists", False, str(e))

try:
    accounts_list = get_mt940_accounts(conn)
    check("get_mt940_accounts works", len(accounts_list) > 0, f"{len(accounts_list)} account(s)")
except Exception as e:
    check("get_mt940_accounts works", False, str(e))

try:
    cfg = get_account_config(conn, "001010039999")
    check("get_account_config works", cfg is not None,
          f"sendingType={cfg['sendingType'] if cfg else 'N/A'}")
except Exception as e:
    check("get_account_config works", False, str(e))

try:
    swift = get_swift_trancode(conn, "CDM")
    check("get_swift_trancode works", swift is not None, f"CDM -> {swift}")
except Exception as e:
    check("get_swift_trancode works", False, str(e))

try:
    recipients = db_get_email_recipients(conn)
    check("db.get_email_recipients works", recipients is not None,
          f"recipient={recipients['emailrecipient'] if recipients else 'None'}")
except Exception as e:
    check("db.get_email_recipients works", False, str(e))

try:
    flag = check_sent_flag(conn)
    check("check_sent_flag works", flag in (0, 1), f"sentflag={flag}")
except Exception as e:
    check("check_sent_flag works", False, str(e))

try:
    should_process = check_processing_flag(conn)
    check("check_processing_flag works", isinstance(should_process, bool), str(should_process))
except Exception as e:
    check("check_processing_flag works", False, str(e))

# Recordset iteration
try:
    rs = Recordset(conn, "SELECT * FROM MT940 LIMIT 3")
    rec_count = 0
    while not rs.eof:
        _ = rs["statementacctno"]
        _ = rs["counter"]
        rs.move_next()
        rec_count += 1
    rs.close()
    check("Recordset iteration works", rec_count > 0, f"{rec_count} row(s) iterated")
except Exception as e:
    check("Recordset iteration works", False, str(e))


# ===========================================================================
# SECTION 5: EMAIL MODULE
# ===========================================================================
section("5. EMAIL MODULE")

check("SMTP_HOST not placeholder",  "yourbank" not in SMTP_HOST, SMTP_HOST)
check("FROM_EMAIL valid",           "@" in FROM_EMAIL, FROM_EMAIL)
check("USE_AUTH is bool",           isinstance(USE_AUTH, bool), str(USE_AUTH))
check("USE_TLS is bool",            isinstance(USE_TLS, bool),  str(USE_TLS))
check("SMTP_PORT is int",           isinstance(SMTP_PORT, int), str(SMTP_PORT))

try:
    subj = build_email_subject("001010039999", "2025-11-25")
    check("build_email_subject", subj == "MT940 for 001010039999 2025-11-25", subj)
except Exception as e:
    check("build_email_subject", False, str(e))

try:
    body = build_email_body("1.2.3")
    check("build_email_body", len(body) > 10, f"{len(body)} chars")
except Exception as e:
    check("build_email_body", False, str(e))

# parse_recipients
for raw, expected, label in [
    ("user1@bank.com;user2@bank.com",        ["user1@bank.com", "user2@bank.com"],  "two recipients"),
    ("single@bank.com",                      ["single@bank.com"],                   "single recipient"),
    ("user1@bank.com; user2@bank.com ; u3@b",["user1@bank.com","user2@bank.com","u3@b"], "with spaces"),
    ("",                                     [],                                    "empty string"),
]:
    try:
        got = parse_recipients(raw)
        check(f"parse_recipients ({label})", got == expected, str(got))
    except Exception as e:
        check(f"parse_recipients ({label})", False, str(e))

# clean_attachment_path
for raw, expected, label in [
    (";c:\\MT940\\file.txt",   "c:\\MT940\\file.txt",  "leading ;c"),
    (";;c:\\MT940\\file.txt",  "c:\\MT940\\file.txt",  "leading ;;c"),
    ("C:\\MT940;;;file.txt",   "C:\\MT940;file.txt",   "triple semicolon"),
    ("C:\\MT940\\file.txt",    "C:\\MT940\\file.txt",  "normal path"),
    ("  ;c:\\MT940\\file.txt ","c:\\MT940\\file.txt",  "with spaces"),
    ("",                       "",                      "empty string"),
]:
    try:
        got = clean_attachment_path(raw)
        check(f"clean_attachment_path ({label})", got == expected, repr(got))
    except Exception as e:
        check(f"clean_attachment_path ({label})", False, str(e))


# ===========================================================================
# SECTION 6: MT940 PROCESSOR SIGNATURES
# ===========================================================================
section("6. MT940 PROCESSOR SIGNATURES")

expected_params = ["conn", "counter", "account_no", "code", "prev_bus_date"]
for fn_name, fn in [
    ("process_mt940_new",      process_mt940_new),
    ("process_mt940_meralco",  process_mt940_meralco),
    ("process_mt940_converge", process_mt940_converge),
    ("process_mt940_swift",    process_mt940_swift),
]:
    params = list(inspect.signature(fn).parameters.keys())
    check(f"{fn_name} signature", params == expected_params, str(params))


# ===========================================================================
# SECTION 7: MT940 PROCESSOR LIVE RUNS
# ===========================================================================
section("7. MT940 PROCESSOR LIVE RUNS")

TEST_ACCOUNT  = "001010039999"
PREV_BUS_DATE = datetime(2024, 9, 18)
DATE_STR      = format_date_yyyymmdd(PREV_BUS_DATE)
OUTPUT_DIR    = os.path.join("C:\\MT940\\Output", DATE_STR)

# Reset counter and clear old test files
try:
    conn.execute("UPDATE MT940 SET counter = 1 WHERE statementacctno = ?", (TEST_ACCOUNT,))
    conn.commit()
    if os.path.isdir(OUTPUT_DIR):
        for f in os.listdir(OUTPUT_DIR):
            if TEST_ACCOUNT in f:
                os.remove(os.path.join(OUTPUT_DIR, f))
    check("Pre-processor reset (counter + old files)", True)
except Exception as e:
    check("Pre-processor reset", False, str(e))

# process_mt940_new
try:
    cfg     = get_account_config(conn, TEST_ACCOUNT)
    code    = str(cfg["code"]) if cfg else "AUBKPHMMAXXX"
    result  = process_mt940_new(conn, 1, TEST_ACCOUNT, code, PREV_BUS_DATE)
    check("process_mt940_new returned filename", result is not None, str(result))
    if result:
        fpath = os.path.join(OUTPUT_DIR, result)
        file_ok = os.path.isfile(fpath)
        check("process_mt940_new file exists on disk", file_ok, fpath)
        if file_ok:
            content = open(fpath).read()
            check("MT940 :20: field",  ":20:" in content)
            check("MT940 :25: field",  ":25:" in content)
            check("MT940 :28C: field", ":28C:" in content)
            check("MT940 :60F/60M:",   ":60F:" in content or ":60M:" in content)
            check("MT940 :62F/62M:",   ":62F:" in content or ":62M:" in content)
            check("MT940 footer -}",   "-}" in content)
            print(f"\n  {INFO} File preview ({len(content.splitlines())} lines):")
            for line in content.splitlines()[:12]:
                print(f"       {line}")
except Exception as e:
    check("process_mt940_new live run", False, str(e))
    traceback.print_exc()

# process_mt940_meralco
try:
    cursor.execute(
        "SELECT statementacctno, counter, code FROM MT940 WHERE code = 'MRALPHMMXXX' LIMIT 1"
    )
    row = cursor.fetchone()
    if row:
        result = process_mt940_meralco(conn, int(row["counter"] or 1),
                                       str(row["statementacctno"]),
                                       str(row["code"]), PREV_BUS_DATE)
        check("process_mt940_meralco live run", result is not None, str(result))
    else:
        result = process_mt940_meralco(conn, 1, "999999999999", "MRALPHMMXXX", PREV_BUS_DATE)
        check("process_mt940_meralco (no Meralco acct — graceful None)", result is None, str(result))
except Exception as e:
    check("process_mt940_meralco live run", False, str(e))

# process_mt940_converge
try:
    cursor.execute(
        "SELECT statementacctno, counter, code FROM MT940 WHERE Format = 'B' LIMIT 1"
    )
    row = cursor.fetchone()
    if row:
        result = process_mt940_converge(conn, int(row["counter"] or 1),
                                        str(row["statementacctno"]),
                                        str(row["code"]), PREV_BUS_DATE)
        check("process_mt940_converge live run", result is not None, str(result))
    else:
        result = process_mt940_converge(conn, 1, "999999999999", "CONVERGE001", PREV_BUS_DATE)
        check("process_mt940_converge (no Converge acct — graceful None)", result is None, str(result))
except Exception as e:
    check("process_mt940_converge live run", False, str(e))

# process_mt940_swift
try:
    cursor.execute(
        "SELECT statementacctno, counter, code FROM MT940 WHERE sendingType = '1' LIMIT 1"
    )
    row = cursor.fetchone()
    if row:
        result = process_mt940_swift(conn, int(row["counter"] or 1),
                                     str(row["statementacctno"]),
                                     str(row["code"]), PREV_BUS_DATE)
        check("process_mt940_swift live run", result is not None, str(result))
    else:
        result = process_mt940_swift(conn, 1, "999999999999", "TESTBIC001", PREV_BUS_DATE)
        check("process_mt940_swift (no Swift acct — graceful None)", result is None, str(result))
except Exception as e:
    check("process_mt940_swift live run", False, str(e))


# ===========================================================================
# SECTION 8: FULL main.py INTEGRATION RUN
# ===========================================================================
section("8. FULL main.py INTEGRATION RUN")

try:
    conn.execute("UPDATE MT940 SET counter = 1 WHERE statementacctno = ?", (TEST_ACCOUNT,))
    conn.execute("UPDATE codetable SET sentflag = '0' WHERE emailreport = 'MT940'")
    conn.commit()
    if os.path.isdir(OUTPUT_DIR):
        for f in os.listdir(OUTPUT_DIR):
            if TEST_ACCOUNT in f:
                os.remove(os.path.join(OUTPUT_DIR, f))
    check("Pre-integration reset complete", True)
except Exception as e:
    check("Pre-integration reset", False, str(e))

# Close connection — SQLite allows only one writer at a time
conn.close()
conn = None

try:
    import importlib
    importlib.reload(main_module)
    run_result = main_module.run_mt940_process(prev_bus_date=PREV_BUS_DATE)
    check("run_mt940_process() returned a value",  run_result is not None,  f"Returned: {run_result}")
    check("run_mt940_process() succeeded",         run_result is True,      f"Result: {run_result}")
except Exception as e:
    check("main.py full integration run", False, str(e))
    traceback.print_exc()

conn = ado_connect()


# ===========================================================================
# SECTION 9: POST-RUN OUTPUT VERIFICATION
# ===========================================================================
section("9. POST-RUN OUTPUT VERIFICATION")

try:
    if os.path.isdir(OUTPUT_DIR):
        generated = [f for f in os.listdir(OUTPUT_DIR) if TEST_ACCOUNT in f]
        check("At least 1 MT940 file generated", len(generated) >= 1,
              f"{len(generated)} file(s): {', '.join(generated)}")
        for fname in sorted(generated):
            size = os.path.getsize(os.path.join(OUTPUT_DIR, fname))
            check(f"File '{fname}' non-empty", size > 0, f"{size} bytes")
    else:
        check("Output directory exists", False, OUTPUT_DIR)
except Exception as e:
    check("Post-run output check", False, str(e))

try:
    post_cursor = conn.cursor()
    post_cursor.execute(
        "SELECT counter FROM MT940 WHERE statementacctno = ?", (TEST_ACCOUNT,)
    )
    row = post_cursor.fetchone()
    new_counter = int(row["counter"]) if row else 0
    check("DB counter incremented after run", new_counter > 1, f"counter={new_counter}")
except Exception as e:
    check("DB counter increment check", False, str(e))


# ===========================================================================
# FINAL SUMMARY
# ===========================================================================
section("FINAL SUMMARY")

passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)
total  = len(results)
pct    = int(passed / total * 100) if total else 0

print(f"\n  Total : {total}")
print(f"  Passed: {passed}")
print(f"  Failed: {failed}")
print(f"  Score : {pct}%")

if failed > 0:
    print(f"\n  Failed checks:")
    for status, label, detail in results:
        if status == FAIL:
            print(f"    {FAIL} {label}" + (f" -- {detail}" if detail else ""))

print()
if failed == 0:
    print("  ALL TESTS PASSED — System is fully operational.")
elif failed <= 3:
    print("  MOSTLY PASSING — Minor issues detected. Review failures above.")
else:
    print("  FAILURES DETECTED — Review the failed checks above.")

conn.close()
