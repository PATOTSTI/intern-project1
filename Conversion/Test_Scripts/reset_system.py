import sys
import os
import glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python_Modules'))

from database import ado_connect, close_connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _connect():
    conn = ado_connect()
    if not conn:
        print("[ERROR] Could not connect to the database. Aborting.")
        sys.exit(1)
    return conn


def show_current_status(cursor):
    """Print a summary of accounts and email configs."""
    print()
    print("[STATUS] MT940 accounts:")
    print("-" * 70)
    cursor.execute("SELECT statementacctno, counter, sendingType FROM MT940")
    for acc in cursor.fetchall():
        print(f"  Account: {acc[0]}  Counter: {acc[1]}  SendingType: {acc[2]}")

    print()
    print("[STATUS] Email configurations (codetable):")
    print("-" * 70)
    cursor.execute(
        "SELECT emailreport, emailrecipient, sentflag "
        "FROM codetable WHERE emailreport LIKE 'MT940%'"
    )
    for cfg in cursor.fetchall():
        print(f"  {cfg[0]}")
        if cfg[1]:
            print(f"    Recipient : {cfg[1]}")
        print(f"    Sentflag  : {cfg[2]}")
    print()


# ---------------------------------------------------------------------------
# Reset actions
# ---------------------------------------------------------------------------

def delete_output_files():
    """Delete all generated MT940 .txt files from every dated sub-folder."""
    base = "C:\\MT940\\Output"
    if not os.path.exists(base):
        print("[INFO] Output directory C:\\MT940\\Output does not exist — nothing to delete.")
        return

    all_files = glob.glob(os.path.join(base, "**", "*.txt"), recursive=True)
    if not all_files:
        print("[INFO] No MT940 output files found.")
        return

    for f in all_files:
        os.remove(f)
        print(f"  Deleted: {os.path.relpath(f, base)}")
    print(f"[OK] Deleted {len(all_files)} file(s).")


def reset_counter(cursor, conn):
    """Reset the MT940 sequence counter back to 1 for all accounts."""
    cursor.execute("UPDATE MT940 SET counter = 1")
    print(f"[OK] Counter reset to 1 for {cursor.rowcount} account(s).")
    conn.commit()


def reset_all_sentflags(cursor, conn):
    """Set sentflag = '0' for every row in codetable."""
    cursor.execute("UPDATE codetable SET sentflag = '0'")
    print(f"[OK] sentflag reset to '0' for {cursor.rowcount} row(s).")
    conn.commit()


def fix_main_sentflag(cursor, conn):
    """Ensure the master MT940 sentflag record exists in codetable."""
    cursor.execute("SELECT COUNT(*) FROM codetable WHERE emailreport = 'MT940'")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO codetable (emailreport, sentflag, emailtag, emailsched) "
            "VALUES ('MT940', '0', 'Y', 'daily')"
        )
        print("[OK] Created master MT940 sentflag record in codetable.")
    else:
        cursor.execute("UPDATE codetable SET sentflag = '0' WHERE emailreport = 'MT940'")
        print("[OK] Master MT940 sentflag record already exists — reset to '0'.")
    conn.commit()


def ensure_account_email_config(cursor, conn, recipient="adisneyplus8@gmail.com"):
    """Ensure at least the first account has an email config row."""
    cursor.execute("SELECT statementacctno FROM MT940 LIMIT 1")
    row = cursor.fetchone()
    if not row:
        print("[WARNING] No accounts found in MT940 table — skipping account email config.")
        return

    account_no = row[0]
    key = f"MT940 for {account_no}"

    cursor.execute("SELECT COUNT(*) FROM codetable WHERE emailreport = ?", (key,))
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO codetable "
            "(emailreport, emailrecipient, sentflag, emailtag, emailsched) "
            "VALUES (?, ?, '0', 'Y', 'daily')",
            (key, recipient),
        )
        print(f"[OK] Created email config for account {account_no} → {recipient}")
    else:
        cursor.execute(
            "UPDATE codetable "
            "SET emailrecipient = ?, sentflag = '0' "
            "WHERE emailreport = ?",
            (recipient, key),
        )
        print(f"[OK] Updated email config for account {account_no} → {recipient}")
    conn.commit()


def setup_test_email(cursor, conn, email_address):
    """Set the test recipient email for every MT940 account config row."""
    cursor.execute(
        "SELECT statementacctno FROM MT940"
    )
    accounts = cursor.fetchall()

    if not accounts:
        print("[WARNING] No accounts found in MT940 table.")
        return

    for (account_no,) in accounts:
        key = f"MT940 for {account_no}"
        cursor.execute("SELECT COUNT(*) FROM codetable WHERE emailreport = ?", (key,))
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO codetable "
                "(emailreport, emailrecipient, emailrecipientcc, sentflag, emailtag, emailsched) "
                "VALUES (?, ?, '', '0', 'Y', 'daily')",
                (key, email_address),
            )
            print(f"[OK] Created email config for {account_no} → {email_address}")
        else:
            cursor.execute(
                "UPDATE codetable "
                "SET emailrecipient = ?, emailrecipientcc = '', sentflag = '0', "
                "    emailtag = 'Y', emailsched = 'daily' "
                "WHERE emailreport = ?",
                (email_address, key),
            )
            print(f"[OK] Updated email config for {account_no} → {email_address}")
    conn.commit()


# ---------------------------------------------------------------------------
# Menu-driven entry point
# ---------------------------------------------------------------------------

MENU = """
Select reset option:

  [1] Quick reset     — sentflags only (fastest, keeps files and counter)
  [2] Full reset      — delete output files + reset counter + sentflags + DB config
  [3] Fix DB only     — ensure master sentflag record exists, reset all sentflags
  [4] Set test email  — change the recipient email used for testing
  [5] Exit

"""


def main():
    print("=" * 70)
    print("  MT940 SYSTEM RESET UTILITY")
    print("=" * 70)
    print(MENU)

    choice = input("Enter option (1-5): ").strip()

    if choice == "5":
        print("\n[EXIT] Cancelled.")
        sys.exit(0)

    conn = _connect()
    cursor = conn.cursor()

    if choice == "1":
        # ------------------------------------------------------------------ #
        print("\n[QUICK RESET] Resetting sentflags only...")
        reset_all_sentflags(cursor, conn)

    elif choice == "2":
        # ------------------------------------------------------------------ #
        print("\n[FULL RESET] Starting full system reset...")
        print()
        print("[STEP 1] Deleting generated MT940 output files...")
        delete_output_files()
        print()
        print("[STEP 2] Resetting MT940 counter...")
        reset_counter(cursor, conn)
        print()
        print("[STEP 3] Resetting sentflags...")
        reset_all_sentflags(cursor, conn)
        print()
        print("[STEP 4] Ensuring master sentflag record exists...")
        fix_main_sentflag(cursor, conn)
        print()
        print("[STEP 5] Ensuring account email config exists...")
        ensure_account_email_config(cursor, conn)

    elif choice == "3":
        # ------------------------------------------------------------------ #
        print("\n[FIX DB] Fixing sentflag records...")
        fix_main_sentflag(cursor, conn)
        reset_all_sentflags(cursor, conn)

    elif choice == "4":
        # ------------------------------------------------------------------ #
        current_email = ""
        cursor.execute(
            "SELECT emailrecipient FROM codetable "
            "WHERE emailreport LIKE 'MT940 for %' LIMIT 1"
        )
        row = cursor.fetchone()
        if row and row[0]:
            current_email = row[0]

        print(f"\n[SET TEST EMAIL] Current recipient: {current_email or '(none)'}")
        new_email = input("Enter new test email address (or press Enter to keep current): ").strip()

        if not new_email:
            if current_email:
                print("[INFO] No change made.")
                close_connection(conn)
                sys.exit(0)
            else:
                print("[ERROR] No existing email and no new email entered.")
                close_connection(conn)
                sys.exit(1)

        confirm = input(f"Set all account recipients to '{new_email}'? (yes/no): ").strip().lower()
        if confirm not in ("yes", "y"):
            print("[CANCELLED]")
            close_connection(conn)
            sys.exit(0)

        setup_test_email(cursor, conn, new_email)
        reset_all_sentflags(cursor, conn)

    else:
        print("[ERROR] Invalid option. Please run the script again and choose 1-5.")
        close_connection(conn)
        sys.exit(1)

    # Show final status for all options that made changes
    print()
    show_current_status(cursor)
    close_connection(conn)

    print("=" * 70)
    print("[SUCCESS] Reset complete!")
    print("=" * 70)
    print()
    print("Next step: python Python_Modules\\main.py")
    print()


if __name__ == "__main__":
    main()
