import os
import sys
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

from database import (
    get_account_config,
    get_swift_trancode,
    update_mt940_counter,
    update_mt940_filename,
    insert_summary_record,
    Recordset,
)
from utils import (
    format_date_yyyymmdd,
    get_stmdate,
    get_stmdate2,
    get_stmdate3,
    pad_zeros,
    mid_str,
    get_currency_code,
    format_mt940_amount,
    create_directory,
    check_file_exists,
)


# ---------------------------------------------------------------------------
# Shared helpers used across all four processors
# ---------------------------------------------------------------------------

def _bal_line(tag: str, stmdate2: str, currency: str, amount: float) -> str:
    if amount < 0:
        return f":{tag}:D{stmdate2}{currency}{format_mt940_amount(abs(amount))}"
    return f":{tag}:C{stmdate2}{currency}{format_mt940_amount(amount)}"


def _resolve_ref(raw) -> str:
    """Return 'NonRef' for NULL/empty refno values — VB6 does the same."""
    if raw is None or str(raw).strip() == "":
        return "NonRef"
    return str(raw)


def _resolve_bill_ref(raw) -> str:
    """Return 'NonRef' if bill_reference is NULL, empty, or fewer than 2 chars."""
    if raw is None or len(str(raw).strip()) < 2:
        return "NonRef"
    return str(raw)


# ---------------------------------------------------------------------------
# Standard processor
# ---------------------------------------------------------------------------

def process_mt940_new(conn, counter: int, account_no: str, code: str,
                      prev_bus_date: datetime) -> Optional[str]:
    try:
        config = get_account_config(conn, account_no)
        if not config:
            print(f"ERROR: Account {account_no} not found in MT940 table")
            return None

        sen_typ        = str(config['sendingType'])
        code_prod      = str(config['code'])
        extension_type = config['extension_type'] or ''
        field86_flag   = config['field86_flag']
        is_first       = True
        new_str_ctr    = pad_zeros(counter, 3)

        print(f"[INFO] Processing account: {account_no}, Counter: {new_str_ctr}")

        date_str      = format_date_yyyymmdd(prev_bus_date)
        output_dir    = os.path.join("C:\\MT940\\Output", date_str)
        create_directory(output_dir)

        filename      = f"AUB20881_{date_str}_{account_no}_{new_str_ctr}{extension_type}"
        output_path   = os.path.join(output_dir, filename)

        # Abort if a file from the previous counter already exists — prevents duplicate sends
        last_count    = pad_zeros(counter - 1, 3)
        last_base     = f"AUB20881_{date_str}_{account_no}_{last_count}"
        if (check_file_exists(os.path.join(output_dir, last_base)) or
                check_file_exists(os.path.join(output_dir, last_base + extension_type))):
            print(f"WARNING: MT940 for {account_no} already generated (counter {last_count}). Will not proceed.")
            return None

        print(f"[INFO] Output file: {filename}")
        print(f"[INFO] Full path: {output_path}")

        stmdate  = get_stmdate(date_str)
        stmdate2 = get_stmdate2(date_str)
        stmdate3 = get_stmdate3(date_str)

        update_mt940_filename(conn, account_no, filename)
        update_mt940_counter(conn, account_no, counter + 1, prev_bus_date)

        ref_num     = f":20:89{stmdate}{mid_str(account_no, 1, 3)}{mid_str(account_no, 6, 6)}"
        str_currency = get_currency_code(mid_str(account_no, 4, 2))

        print(f"[INFO] MT940 header written successfully")
        print(f"[INFO] Reference number: {ref_num}")
        print(f"[INFO] Sequence number: {pad_zeros(counter + 1, 5)}")
        print(f"[INFO] Product code: {mid_str(account_no, 4, 2)}, Currency: {str_currency}")

        # BIC fix: insert 'X' after the 8th character — added by joshua to correct SWIFT BIC format
        bic = mid_str(code, 1, 8) + "X" + mid_str(code, 9, 11)

        txn_query = """
            SELECT historyfile1_copy.*, tlf_copy.bill_reference
            FROM historyfile1_copy
            LEFT JOIN tlf_copy ON historyfile1_copy.acctno = tlf_copy.acctno
            WHERE historyfile1_copy.acctno = ?
              AND historyfile1_copy.txn_date = ?
              AND historyfile1_copy.delete_flag = 'N'
            ORDER BY historyfile1_copy.txn_date, CAST(passbk_recno AS INTEGER) ASC
        """
        conn2 = Recordset(conn, txn_query, (account_no, date_str))

        print(f"[INFO] Transaction query executed for date: {date_str}")
        print(f"[INFO] Opening balance initialized to 0.0")
        if not conn2.eof:
            print(f"[INFO] Transactions found for processing")

        cur_opening_bal = 0.0
        beg_bal_summary = ""
        end_bal_summary = ""

        with open(output_path, 'w') as fh:
            fh.write(f"{{1:F01AUBKPHMMAXXX0000000000}}{{2:I940{bic}N2020}}{{4:\n")
            fh.write(f"{ref_num}\n")
            fh.write(f":25:{account_no}\n")
            fh.write(f":28C:{pad_zeros(counter + 1, 5)}\n")

            if not conn2.eof:
                while not conn2.eof:
                    txn_type  = str(conn2["txntype"])
                    mnem_code = str(conn2["mnem_code"])
                    swift_mnem = get_swift_trancode(conn, mnem_code)
                    txn_amt    = float(conn2["Txnamt"])
                    ledger_bal = float(conn2["ledger_bal"])
                    ref_no     = _resolve_ref(conn2["refno"])
                    if len(ref_no) > 16:
                        ref_no = ref_no[-14:]

                    if is_first:
                        cur_opening_bal = (ledger_bal + txn_amt) if txn_type == "D" else (ledger_bal - txn_amt)
                        beg_bal_line    = _bal_line("60F", stmdate2, str_currency, cur_opening_bal)
                        beg_bal_summary = beg_bal_line
                        fh.write(beg_bal_line + "\n")
                        is_first = False
                        print(f"[INFO] Opening balance calculated: {cur_opening_bal:.2f} {str_currency}")

                    fh.write(f":61:{stmdate2}{stmdate3}{txn_type}{format_mt940_amount(txn_amt)}{swift_mnem}{ref_no}\n")

                    if field86_flag == "Y":
                        fh.write(f":86:{_resolve_bill_ref(conn2['bill_reference'])}\n")

                    cur_opening_bal = cur_opening_bal + txn_amt if txn_type == "C" else cur_opening_bal - txn_amt
                    conn2.move_next()

                end_bal_line    = _bal_line("62F", stmdate2, str_currency, cur_opening_bal)
                end_bal_summary = end_bal_line
                fh.write(end_bal_line + "\n")
                fh.write("-}\n")

                print(f"[INFO] Closing balance: {cur_opening_bal:.2f} {str_currency}")
                print(f"[INFO] MT940 file generation complete")

                if sen_typ == "1":
                    insert_summary_record(conn, beg_bal_summary, code_prod, ref_num, prev_bus_date)
                    insert_summary_record(conn, end_bal_summary, code_prod, ref_num, prev_bus_date)

            else:
                # No transactions — write zero-movement statement from acctmstr_copy
                rs = Recordset(conn, "SELECT ledger_bal, available_bal FROM acctmstr_copy WHERE accountno = ?", (account_no,))
                if rs.eof:
                    print(f"ERROR: Account {account_no} not found in acctmstr_copy")
                    return None

                bal = float(rs["ledger_bal"])
                fh.write(_bal_line("60F", stmdate2, str_currency, bal) + "\n")
                fh.write(_bal_line("62F", stmdate2, str_currency, bal) + "\n")
                fh.write("-}\n")

                print(f"[INFO] No transactions found — no-movement file written (balance {bal:.2f})")

                if sen_typ == "1":
                    insert_summary_record(conn, _bal_line("60F", stmdate2, str_currency, bal), code_prod, ref_num, prev_bus_date)
                    insert_summary_record(conn, _bal_line("62F", stmdate2, str_currency, bal), code_prod, ref_num, prev_bus_date)

        print(f"[SUCCESS] MT940 file generated: {filename}")
        return filename

    except Exception as e:
        print(f"ERROR in process_mt940_new: {e}")
        import traceback
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Meralco variant
# ---------------------------------------------------------------------------

def process_mt940_meralco(conn, counter: int, account_no: str, code: str,
                          prev_bus_date: datetime) -> Optional[str]:
    try:
        config = get_account_config(conn, account_no)
        if not config:
            print(f"ERROR: Account {account_no} not found in MT940 table")
            return None

        sen_typ        = str(config['sendingType'])
        code_prod      = str(config['code'])
        extension_type = config['extension_type'] or ''
        field86_flag   = config['field86_flag']
        is_first       = True
        new_str_ctr    = pad_zeros(counter, 3)

        print(f"[INFO] Processing Meralco account: {account_no}, Counter: {new_str_ctr}")

        date_str    = format_date_yyyymmdd(prev_bus_date)
        output_dir  = os.path.join("C:\\MT940\\Output", date_str)
        create_directory(output_dir)

        filename    = f"AUB20881_{date_str}_{account_no}_{new_str_ctr}{extension_type}"
        output_path = os.path.join(output_dir, filename)

        last_count = pad_zeros(counter - 1, 3)
        last_base  = f"AUB20881_{date_str}_{account_no}_{last_count}"
        if (check_file_exists(os.path.join(output_dir, last_base)) or
                check_file_exists(os.path.join(output_dir, last_base + extension_type))):
            print(f"WARNING: MT940 for {account_no} already generated (counter {last_count}). Will not proceed.")
            return None

        print(f"[INFO] Output file: {filename}")

        stmdate  = get_stmdate(prev_bus_date)
        stmdate2 = get_stmdate2(prev_bus_date)
        stmdate3 = get_stmdate3(prev_bus_date)

        update_mt940_filename(conn, account_no, filename)
        update_mt940_counter(conn, account_no, counter + 1, prev_bus_date)

        ref_num      = f":20:89{stmdate}{mid_str(account_no, 1, 3)}{mid_str(account_no, 6, 6)}"
        str_currency = get_currency_code(mid_str(account_no, 4, 2))

        txn_query = """
            SELECT historyfile1_copy.*, tlf_copy.bill_reference
            FROM historyfile1_copy
            LEFT JOIN tlf_copy ON historyfile1_copy.acctno = tlf_copy.acctno
            WHERE historyfile1_copy.acctno = ?
              AND historyfile1_copy.txn_date = ?
              AND historyfile1_copy.delete_flag = 'N'
            ORDER BY historyfile1_copy.txn_date, CAST(passbk_recno AS INTEGER) ASC
        """
        conn2 = Recordset(conn, txn_query, (account_no, date_str))

        cur_opening_bal = 0.0
        beg_bal_summary = ""
        end_bal_summary = ""

        with open(output_path, 'w') as fh:
            # Meralco header is REVERSED — {1:I940...}{2:F01...} — unlike all other variants
            fh.write(f"{{1:I940{code}XN2020}}{{2:F01AUBKPHMMAXXX0000000000}}{{4:\n")
            fh.write(f"{ref_num}\n")
            fh.write(f":25:{account_no}\n")
            fh.write(f":28C:{pad_zeros(counter + 1, 5)}\n")

            if not conn2.eof:
                while not conn2.eof:
                    txn_type   = str(conn2["txntype"])
                    mnem_code  = str(conn2["mnem_code"])
                    swift_mnem = get_swift_trancode(conn, mnem_code)
                    txn_amt    = float(conn2["Txnamt"])
                    ledger_bal = float(conn2["ledger_bal"])
                    ref_no     = _resolve_ref(conn2["refno"])
                    if len(ref_no) > 16:
                        ref_no = ref_no[:16]

                    if is_first:
                        cur_opening_bal = (ledger_bal + txn_amt) if txn_type == "D" else (ledger_bal - txn_amt)
                        beg_bal_line    = _bal_line("60F", stmdate2, str_currency, cur_opening_bal)
                        beg_bal_summary = beg_bal_line
                        fh.write(beg_bal_line + "\n")
                        is_first = False
                        print(f"[INFO] Opening balance: {cur_opening_bal:.2f} {str_currency}")

                    fh.write(f":61:{stmdate2}{stmdate3}{txn_type}{format_mt940_amount(txn_amt)}{swift_mnem}{ref_no}\n")

                    if field86_flag == "Y":
                        fh.write(f":86:{_resolve_bill_ref(conn2['bill_reference'])}\n")

                    cur_opening_bal = cur_opening_bal + txn_amt if txn_type == "C" else cur_opening_bal - txn_amt
                    conn2.move_next()

                end_bal_line    = _bal_line("62F", stmdate2, str_currency, cur_opening_bal)
                end_bal_summary = end_bal_line
                fh.write(end_bal_line + "\n")
                fh.write("-}\n")

                print(f"[INFO] Closing balance: {cur_opening_bal:.2f} {str_currency}")
                print(f"[INFO] MT940 Meralco file generation complete")

                if sen_typ == "1":
                    insert_summary_record(conn, beg_bal_summary, code_prod, ref_num, prev_bus_date)
                    insert_summary_record(conn, end_bal_summary, code_prod, ref_num, prev_bus_date)

            else:
                # Meralco no-movement uses acctmstrbefclr_copy AND writes :64: available balance
                rs = Recordset(conn,
                               "SELECT ledger_bal, available_bal FROM acctmstrbefclr_copy WHERE accountno = ?",
                               (account_no,))
                if rs.eof:
                    print(f"ERROR: Account {account_no} not in acctmstrbefclr_copy")
                    return None

                ledger_bal = float(rs["ledger_bal"])
                avail_bal  = float(rs["available_bal"])

                fh.write(_bal_line("60F", stmdate2, str_currency, ledger_bal) + "\n")
                fh.write(_bal_line("62F", stmdate2, str_currency, ledger_bal) + "\n")
                fh.write(_bal_line("64",  stmdate2, str_currency, avail_bal)  + "\n")
                fh.write("-}\n")

        print(f"[SUCCESS] MT940 Meralco file generated: {filename}")
        return filename

    except Exception as e:
        print(f"ERROR in process_mt940_meralco: {e}")
        import traceback
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Converge variant
# ---------------------------------------------------------------------------

def process_mt940_converge(conn, counter: int, account_no: str, code: str,
                           prev_bus_date: datetime) -> Optional[str]:
    try:
        config = get_account_config(conn, account_no)
        if not config:
            print(f"ERROR: Account {account_no} not found in MT940 table")
            return None

        sen_typ        = str(config['sendingType'])
        code_prod      = str(config['code'])
        extension_type = config['extension_type'] or ''
        field86_flag   = config['field86_flag']
        is_first       = True
        new_str_ctr    = pad_zeros(counter, 3)

        print(f"[INFO] Processing Converge account: {account_no}, Counter: {new_str_ctr}")

        date_str    = format_date_yyyymmdd(prev_bus_date)
        output_dir  = os.path.join("C:\\MT940\\Output", date_str)
        create_directory(output_dir)

        filename    = f"AUB20881_{date_str}_{account_no}_{new_str_ctr}{extension_type}"
        output_path = os.path.join(output_dir, filename)

        last_count = pad_zeros(counter - 1, 3)
        last_base  = f"AUB20881_{date_str}_{account_no}_{last_count}"
        if (check_file_exists(os.path.join(output_dir, last_base)) or
                check_file_exists(os.path.join(output_dir, last_base + extension_type))):
            print(f"WARNING: MT940 for {account_no} already generated (counter {last_count}). Will not proceed.")
            return None

        print(f"[INFO] Output file: {filename}")

        stmdate  = get_stmdate(prev_bus_date)
        stmdate2 = get_stmdate2(prev_bus_date)
        stmdate3 = get_stmdate3(prev_bus_date)

        update_mt940_filename(conn, account_no, filename)
        update_mt940_counter(conn, account_no, counter + 1, prev_bus_date)

        ref_num      = f":20:89{stmdate}{mid_str(account_no, 1, 3)}{mid_str(account_no, 6, 6)}"
        str_currency = get_currency_code(mid_str(account_no, 4, 2))

        txn_query = """
            SELECT historyfile1_copy.*, tlf_copy.bill_reference
            FROM historyfile1_copy
            LEFT JOIN tlf_copy ON historyfile1_copy.acctno = tlf_copy.acctno
            WHERE historyfile1_copy.acctno = ?
              AND historyfile1_copy.txn_date = ?
              AND historyfile1_copy.delete_flag = 'N'
            ORDER BY historyfile1_copy.txn_date, CAST(passbk_recno AS INTEGER) ASC
        """
        conn2 = Recordset(conn, txn_query, (account_no, date_str))

        cur_opening_bal = 0.0
        beg_bal_summary = ""
        end_bal_summary = ""

        with open(output_path, 'w') as fh:
            fh.write(f"{{1:F01AUBKPHMMAXXX0000000000}}{{2:I940{code}XN2020}}{{4:\n")
            fh.write(f"{ref_num}\n")
            fh.write(f":25:{account_no}\n")
            fh.write(f":28C:{pad_zeros(counter + 1, 5)}\n")

            if not conn2.eof:
                while not conn2.eof:
                    txn_type   = str(conn2["txntype"])
                    mnem_code  = str(conn2["mnem_code"])
                    swift_mnem = get_swift_trancode(conn, mnem_code)
                    txn_amt    = float(conn2["Txnamt"])
                    ledger_bal = float(conn2["ledger_bal"])
                    ref_no     = _resolve_ref(conn2["refno"])
                    if len(ref_no) > 16:
                        ref_no = ref_no[:16]

                    if is_first:
                        cur_opening_bal = (ledger_bal + txn_amt) if txn_type == "D" else (ledger_bal - txn_amt)
                        beg_bal_line    = _bal_line("60F", stmdate2, str_currency, cur_opening_bal)
                        beg_bal_summary = beg_bal_line
                        fh.write(beg_bal_line + "\n")
                        is_first = False
                        print(f"[INFO] Opening balance: {cur_opening_bal:.2f} {str_currency}")

                    fh.write(f":61:{stmdate2}{stmdate3}{txn_type}{format_mt940_amount(txn_amt)}{swift_mnem}{ref_no}\n")

                    if field86_flag == "Y":
                        fh.write(f":86:{_resolve_bill_ref(conn2['bill_reference'])}\n")

                    cur_opening_bal = cur_opening_bal + txn_amt if txn_type == "C" else cur_opening_bal - txn_amt
                    conn2.move_next()

                # VB6 Line 925 checks curOpeningBal (not curLedgerBal) for sign — kept as-is
                end_bal_line    = _bal_line("62F", stmdate2, str_currency, cur_opening_bal)
                end_bal_summary = end_bal_line
                fh.write(end_bal_line + "\n")
                fh.write("-}\n")

                print(f"[INFO] Closing balance: {cur_opening_bal:.2f} {str_currency}")
                print(f"[INFO] MT940 Converge file generation complete")

                if sen_typ == "1":
                    insert_summary_record(conn, beg_bal_summary, code_prod, ref_num, prev_bus_date)
                    insert_summary_record(conn, end_bal_summary, code_prod, ref_num, prev_bus_date)

            else:
                # Converge no-movement uses acctmstrbefclr_copy but does NOT write :64:
                rs = Recordset(conn,
                               "SELECT ledger_bal FROM acctmstrbefclr_copy WHERE accountno = ?",
                               (account_no,))
                if rs.eof:
                    print(f"ERROR: Account {account_no} not in acctmstrbefclr_copy")
                    return None

                bal = float(rs["ledger_bal"])
                fh.write(_bal_line("60F", stmdate2, str_currency, bal) + "\n")
                fh.write(_bal_line("62F", stmdate2, str_currency, bal) + "\n")
                fh.write("-}\n")

        print(f"[SUCCESS] MT940 Converge file generated: {filename}")
        return filename

    except Exception as e:
        print(f"ERROR in process_mt940_converge: {e}")
        import traceback
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# SWIFT variant (file splitting)
# ---------------------------------------------------------------------------

def process_mt940_swift(conn, counter: int, account_no: str, code: str,
                        prev_bus_date: datetime) -> Optional[str]:
    try:
        config = get_account_config(conn, account_no)
        if not config:
            print(f"ERROR: Account {account_no} not found in MT940 table")
            return None

        extension_type = config['extension_type'] or ''
        field86_flag   = config['field86_flag']

        date_str   = format_date_yyyymmdd(prev_bus_date)
        output_dir = os.path.join("C:\\MT940\\Output", date_str)
        create_directory(output_dir)
        new_str_ctr = pad_zeros(counter, 3)

        # Count transactions for the chosen date to determine how many files to generate
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) AS recordCount FROM historyfile1_copy WHERE acctno = ? AND txn_date = ? AND delete_flag = 'N'",
            (account_no, date_str)
        )
        row = cursor.fetchone()
        rec_count = int(row["recordCount"]) if row else 0

        print(f"[INFO] Processing Swift account: {account_no}, Total transactions: {rec_count}")

        # Duplicate check uses _1 suffix since Swift always adds a sequence number
        last_count = pad_zeros(counter - 1, 3)
        last_file  = f"AUB20881_{date_str}_{account_no}_{last_count}_1"
        if (check_file_exists(os.path.join(output_dir, last_file)) or
                check_file_exists(os.path.join(output_dir, last_file + extension_type))):
            print(f"WARNING: MT940 for {account_no} already generated (counter {last_count}). Will not proceed.")
            return None

        bic = mid_str(code, 1, 8) + "X" + mid_str(code, 9, 11)
        stmdate  = get_stmdate(prev_bus_date)
        stmdate2 = get_stmdate2(prev_bus_date)
        ref_num  = f":20:89{stmdate}{mid_str(account_no, 1, 3)}{mid_str(account_no, 6, 6)}"
        str_currency = get_currency_code(mid_str(account_no, 4, 2))

        first_filename = None
        conn2 = None

        if rec_count > 0:
            txn_count = 0
            seq_count = 0

            while txn_count < rec_count:
                sen_typ   = str(config['sendingType'])
                code_prod = str(config['code'])
                is_first  = True

                filename    = f"AUB20881_{date_str}_{account_no}_{new_str_ctr}_{seq_count + 1}{extension_type}"
                output_path = os.path.join(output_dir, filename)
                if first_filename is None:
                    first_filename = filename

                print(f"[INFO] Generating file {seq_count + 1}: {filename}")

                # Query transactions only on the first iteration; conn2 advances across files
                if txn_count == 0:
                    conn2 = Recordset(conn, """
                        SELECT historyfile1_copy.*, tlf_copy.bill_reference
                        FROM historyfile1_copy
                        LEFT JOIN tlf_copy ON historyfile1_copy.acctno = tlf_copy.acctno
                        WHERE historyfile1_copy.acctno = ?
                          AND historyfile1_copy.txn_date = ?
                          AND historyfile1_copy.delete_flag = 'N'
                        ORDER BY historyfile1_copy.txn_date, CAST(passbk_recno AS INTEGER) ASC
                    """, (account_no, date_str))

                cur_opening_bal = 0.0
                count_limit     = 0
                beg_bal_line    = ""
                end_bal_line    = ""

                with open(output_path, 'w') as fh:
                    fh.write(f"{{1:F01AUBKPHMMAXXX0000000000}}{{2:I940{bic}N2020}}{{4:\n")
                    fh.write(f":20:89{stmdate}{mid_str(account_no, 1, 3)}{mid_str(account_no, 6, 6)}\n")
                    fh.write(f":25:{account_no}\n")
                    fh.write(f":28C:{pad_zeros(counter + 1, 5)}/{seq_count + 1}\n")

                    while conn2 and not conn2.eof and count_limit < 33:
                        txn_type   = str(conn2["txntype"])
                        mnem_code  = str(conn2["mnem_code"])
                        swift_mnem = get_swift_trancode(conn, mnem_code)
                        txn_amt    = float(conn2["Txnamt"])
                        ledger_bal = float(conn2["ledger_bal"])
                        ref_no     = _resolve_ref(conn2["refno"])
                        # Swift keeps the LAST 15 chars when truncating — different from other variants
                        if len(ref_no) > 16:
                            ref_no = ref_no[-15:]

                        if is_first:
                            cur_opening_bal = (ledger_bal + txn_amt) if txn_type == "D" else (ledger_bal - txn_amt)
                            # First file: :60F:, subsequent files: :60M:
                            tag          = "60F" if txn_count == 0 else "60M"
                            beg_bal_line = _bal_line(tag, stmdate2, str_currency, cur_opening_bal)
                            fh.write(beg_bal_line + "\n")
                            is_first = False

                        # Swift :61: does NOT include stmdate3 — different from Meralco and Converge
                        fh.write(f":61:{stmdate2}{txn_type}{format_mt940_amount(txn_amt)}{swift_mnem}{ref_no}\n")

                        if field86_flag == "Y":
                            fh.write(f":86:{_resolve_bill_ref(conn2['bill_reference'])}\n")

                        cur_opening_bal = cur_opening_bal + txn_amt if txn_type == "C" else cur_opening_bal - txn_amt
                        txn_count   += 1
                        count_limit += 1
                        conn2.move_next()

                    # Last file: :62F:, intermediate: :62M:
                    if txn_count == rec_count:
                        print(f"[INFO] Final file — writing :62F:")
                        end_bal_line = _bal_line("62F", stmdate2, str_currency, cur_opening_bal)
                    else:
                        print(f"[INFO] Intermediate file — writing :62M:")
                        end_bal_line = _bal_line("62M", stmdate2, str_currency, cur_opening_bal)

                    fh.write(end_bal_line + "\n")
                    fh.write("-}\n")

                print(f"[INFO] File {seq_count + 1} written successfully")

                if sen_typ == "1":
                    insert_summary_record(conn, beg_bal_line, code_prod, ref_num, prev_bus_date)
                    insert_summary_record(conn, end_bal_line, code_prod, ref_num, prev_bus_date)

                update_mt940_filename(conn, account_no, filename)
                seq_count += 1

        else:
            # No transactions — single file with _1 suffix
            sen_typ   = str(config['sendingType'])
            code_prod = str(config['code'])
            filename    = f"AUB20881_{date_str}_{account_no}_{new_str_ctr}_1{extension_type}"
            output_path = os.path.join(output_dir, filename)
            first_filename = filename

            rs = Recordset(conn,
                           "SELECT ledger_bal, available_bal FROM acctmstrbefclr_copy WHERE accountno = ?",
                           (account_no,))

            with open(output_path, 'w') as fh:
                fh.write(f"{{1:F01AUBKPHMMAXXX0000000000}}{{2:I940{bic}N2020}}{{4:\n")
                fh.write(f":20:89{stmdate}{mid_str(account_no, 1, 3)}{mid_str(account_no, 6, 6)}\n")
                fh.write(f":25:{account_no}\n")
                fh.write(f":28C:{pad_zeros(counter + 1, 5)}/1\n")

                if not rs.eof:
                    bal = float(rs["ledger_bal"])
                    beg = _bal_line("60F", stmdate2, str_currency, bal)
                    end = _bal_line("62F", stmdate2, str_currency, bal)
                else:
                    beg = f":60F:C{stmdate2}{str_currency}0,00"
                    end = f":62F:C{stmdate2}{str_currency}0,00"

                fh.write(beg + "\n")
                fh.write(end + "\n")
                fh.write("-}\n")

            if sen_typ == "1" and not rs.eof:
                insert_summary_record(conn, beg, code_prod, ref_num, prev_bus_date)
                insert_summary_record(conn, end, code_prod, ref_num, prev_bus_date)

            update_mt940_filename(conn, account_no, filename)

        # Counter update happens AFTER all files are generated — different from other processors
        update_mt940_counter(conn, account_no, counter + 1, prev_bus_date)

        print(f"[SUCCESS] MT940 Swift generation complete: first file = {first_filename}")
        return first_filename

    except Exception as e:
        print(f"ERROR in process_mt940_swift: {e}")
        import traceback
        traceback.print_exc()
        return None
