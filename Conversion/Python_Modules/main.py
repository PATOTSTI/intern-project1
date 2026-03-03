import os
import sys
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

from database import ado_connect, close_connection, Recordset
from mt940_processor import (
    process_mt940_new,
    process_mt940_meralco,
    process_mt940_converge,
    process_mt940_swift,
)
from email_sender import (
    get_email_recipients,
    send_mail,
    update_sent_flag,
    build_email_subject,
    build_email_body,
)
from utils import format_date_yyyymmdd


APP_VERSION = "1.0.0"

# Fallback date used only if run_mt940_process() is called programmatically without a date.
# In normal operation, the operator always provides the date via prompt_processing_date().
DEFAULT_PREV_BUS_DATE = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)


def prompt_processing_date() -> datetime:
    """
    Prompt the operator for the processing date in YYYYMMDD format.
    Keeps asking until a valid date is entered.
    """
    while True:
        raw = input("Enter processing date (YYYYMMDD): ").strip()
        if len(raw) == 8 and raw.isdigit():
            try:
                return datetime.strptime(raw, "%Y%m%d")
            except ValueError:
                pass
        print(f"  [ERROR] '{raw}' is not a valid date. Please use YYYYMMDD (e.g. 20260210).")


def run_mt940_process(prev_bus_date: Optional[datetime] = None) -> bool:
    if prev_bus_date is None:
        prev_bus_date = DEFAULT_PREV_BUS_DATE

    print("=" * 70)
    print("  MT940 AUTOMATED PROCESSING")
    print("=" * 70)
    print(f"[INFO] Processing date: {prev_bus_date.strftime('%Y-%m-%d')}")
    print()

    try:
        # --- Connect ---
        print("[STEP 1] Connecting to database...")
        conn = ado_connect()
        if not conn:
            print("[ERROR] Failed to connect to database")
            return False
        print("[OK] Database connected successfully")
        print()

        # --- Guard: skip if already sent today (VB6 Lines 28-36) ---
        print("[STEP 2] Checking if processing should run...")

        will_process = Recordset(conn, "SELECT sentflag FROM codetable WHERE emailreport = 'MT940'")

        if will_process.eof or will_process["sentflag"] != "0":
            print("[INFO] Processing already completed (sentflag != 0)")
            close_connection(conn)
            return True

        print("[OK] Processing conditions met - proceeding")
        print()

        # --- Clear summary table before each run (VB6 Line 38) ---
        print("[STEP 3] Clearing summary table...")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM MT940_summary_rep")
        conn.commit()
        print("[OK] Summary table cleared")
        print()

        # --- Load accounts ---
        print("[STEP 4] Querying accounts to process...")

        # Production: replace with the hardcoded account list from VB6 (Lines 41-43)
        # e.g. WHERE statementacctno IN ('001011026318', '001011026478', ...)
        get_account_mt940 = Recordset(conn, "SELECT * FROM MT940")

        if get_account_mt940.eof:
            print("[INFO] No accounts found to process")
            close_connection(conn)
            return True

        print("[OK] Found accounts to process")
        print()

        # --- Main loop ---
        print("[STEP 5] Processing accounts...")
        print("-" * 70)

        account_count = 0
        success_count = 0

        while not get_account_mt940.eof:
            account_count += 1

            account_no   = str(get_account_mt940["statementacctno"])
            counter      = int(get_account_mt940["counter"])
            code         = str(get_account_mt940["code"])
            sending_type = str(get_account_mt940["sendingType"])

            print(f"\n[ACCOUNT {account_count}] Processing: {account_no}")
            print(f"  Counter: {counter}, Code: {code}, SendingType: {sending_type}")

            # Route to the correct processor (VB6 Lines 45-61)
            generated_filename = None

            if code == "MRALPHMMXXX":
                print("  [ROUTE] Using ProcessMT940New_Meralco")
                generated_filename = process_mt940_meralco(conn, counter, account_no, code, prev_bus_date)

            elif get_account_mt940["Format"] == "B":
                print("  [ROUTE] Using ProcessMT940_Converge")
                generated_filename = process_mt940_converge(conn, counter, account_no, code, prev_bus_date)

            elif sending_type == "1":
                print("  [ROUTE] Using ProcessMT940Swift")
                generated_filename = process_mt940_swift(conn, counter, account_no, code, prev_bus_date)

            else:
                print("  [ROUTE] Using ProcessMT940New")
                generated_filename = process_mt940_new(conn, counter, account_no, code, prev_bus_date)

            if not generated_filename:
                print(f"  [WARNING] File generation failed for {account_no}")
                get_account_mt940.move_next()
                continue

            print(f"  [OK] File generated: {generated_filename}")

            # Delivery (VB6 Lines 73-113)
            date_str      = format_date_yyyymmdd(prev_bus_date)
            attach_path   = f"C:\\MT940\\Output\\{date_str}\\{generated_filename}"

            if sending_type in ("2", "4"):
                print("  [SEND] Email delivery mode")
                recipients = get_email_recipients(conn, account_no)

                if recipients:
                    email_to, email_cc, sent_flag = recipients

                    if email_to and sent_flag == "0":
                        subject = build_email_subject(account_no, prev_bus_date.strftime("%Y-%m-%d"))
                        body    = build_email_body(APP_VERSION)
                        print(f"  [EMAIL] Sending to: {email_to}")
                        if send_mail(email_to, email_cc, subject, body, attach_path):
                            print("  [OK] Email sent successfully")
                            update_sent_flag(conn, account_no)
                            success_count += 1
                        else:
                            print("  [WARNING] Email sending failed")

                    elif sent_flag != "0":
                        print(f"  [SKIP] Email already sent (sentflag = {sent_flag})")

                    else:
                        # No recipient on file — fall back to internal distribution list
                        default_to = "biceentandreei@gmail.com;vs03262004@gmail.com;adisneyplus8@gmail.com"
                        subject    = build_email_subject(account_no, prev_bus_date.strftime("%Y-%m-%d"))
                        body       = build_email_body(APP_VERSION)
                        if send_mail(default_to, email_cc, subject, body, attach_path):
                            print("  [OK] Email sent to default recipients")
                            update_sent_flag(conn, account_no)
                            success_count += 1
                else:
                    print("  [WARNING] No email recipients found in database")

            elif sending_type == "3":
                print("  [SEND] SFTP delivery mode")
                # TODO: call SFTP handler when implemented
                print("  [INFO] SFTP handler not yet implemented")

            else:
                print(f"  [INFO] SendingType {sending_type} — no delivery action")

            get_account_mt940.move_next()

        print()
        print("-" * 70)
        print(f"[COMPLETE] Processed {account_count} accounts, {success_count} emails sent")
        print()

        close_connection(conn)
        print("[INFO] Database connection closed")
        print()
        print("=" * 70)
        print("[SUCCESS] MT940 processing completed successfully")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"[ERROR] MT940 processing failed: {e}")
        import traceback
        traceback.print_exc()
        try:
            if 'conn' in locals():
                close_connection(conn)
        except Exception:
            pass
        return False


if __name__ == "__main__":
    print()
    print("*" * 70)
    print("*" + "  MT940 SWIFT Statement Generator — Python".center(68) + "*")
    print("*" + "  Converted from VB6 Legacy System".center(68) + "*")
    print("*" * 70)
    print()

    processing_date = prompt_processing_date()
    print(f"[INFO] Date accepted: {processing_date.strftime('%Y-%m-%d')}")
    print()

    success   = run_mt940_process(processing_date)
    exit_code = 0 if success else 1
    print(f"\n[EXIT] Process completed with code: {exit_code}")
    sys.exit(exit_code)
