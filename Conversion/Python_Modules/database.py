import os
import sqlite3
from typing import Optional, List, Any


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def ado_connect():
    try:
        app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_file = os.path.join(app_path, "Database_Config", "casarepconn.txt")

        str_conn = None
        with open(config_file, 'r') as f:
            if f.readline().strip() == "[CONNSTRING]":
                str_conn = f.readline().strip()

        if not str_conn:
            raise ValueError("Connection string not found in casarepconn.txt")

        if not os.path.isabs(str_conn):
            str_conn = os.path.join(app_path, "Database_Config", str_conn)

        conn = sqlite3.connect(str_conn)
        conn.row_factory = sqlite3.Row
        return conn

    except Exception as e:
        print(f"ERROR: Database connection failed — {e}")
        return None


def close_connection(conn: sqlite3.Connection) -> None:
    try:
        if conn:
            conn.close()
    except Exception as e:
        print(f"ERROR closing connection: {e}")


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def execute_query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Optional[sqlite3.Cursor]:
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor
    except Exception as e:
        print(f"ERROR executing query: {e}")
        return None


def fetch_one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchone()
    except Exception as e:
        print(f"ERROR in fetch_one: {e}")
        return None


def fetch_all(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()
    except Exception as e:
        print(f"ERROR in fetch_all: {e}")
        return []


# ---------------------------------------------------------------------------
# MT940 account queries
# ---------------------------------------------------------------------------

def get_mt940_accounts(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """All accounts registered in the MT940 config table."""
    sql = """
        SELECT statementacctno, counter, code, sendingType, extension_type,
               field86_flag, format, filename, date
        FROM MT940
        ORDER BY statementacctno
    """
    return fetch_all(conn, sql)


def get_account_config(conn: sqlite3.Connection, account_no: str) -> Optional[sqlite3.Row]:
    """MT940 configuration row for a specific account."""
    sql = """
        SELECT statementacctno, counter, code, sendingType, extension_type,
               field86_flag, format, filename, date
        FROM MT940
        WHERE statementacctno = ?
    """
    return fetch_one(conn, sql, (account_no,))


def update_mt940_counter(conn: sqlite3.Connection, account_no: str, counter: int, date) -> bool:
    from datetime import datetime
    date_str = date.strftime("%Y-%m-%d") if isinstance(date, datetime) else str(date)
    sql = "UPDATE MT940 SET counter = ?, date = ? WHERE statementacctno = ?"
    return execute_query(conn, sql, (counter, date_str, account_no)) is not None


def update_mt940_filename(conn: sqlite3.Connection, account_no: str, filename: str) -> bool:
    sql = "UPDATE MT940 SET filename = ? WHERE statementacctno = ?"
    return execute_query(conn, sql, (filename, account_no)) is not None


def check_processing_flag(conn: sqlite3.Connection) -> bool:
    result = fetch_one(conn, "SELECT sentflag FROM codetable WHERE emailreport = 'MT940'")
    if result:
        return result['sentflag'] in ('0', 0)
    return False


# ---------------------------------------------------------------------------
# Transaction queries
# ---------------------------------------------------------------------------

def get_account_transactions(conn: sqlite3.Connection, account_no: str,
                             txn_date: str) -> List[sqlite3.Row]:
    sql = """
        SELECT h.acctno, h.txn_date, h.txntype, h.mnem_code,
               h.txnamt, h.ledger_bal, h.refno, h.passbk_recno,
               t.bill_reference
        FROM historyfile1_copy h
        LEFT JOIN tlf_copy t ON h.refno = t.bill_reference
        WHERE h.acctno = ? AND h.txn_date = ? AND h.delete_flag = 'N'
        ORDER BY h.txn_date, CAST(h.passbk_recno AS INTEGER) ASC
    """
    return fetch_all(conn, sql, (account_no, txn_date))


def get_swift_trancode(conn: sqlite3.Connection, mnem_code: str) -> str:
    sql = "SELECT swift_trancode FROM casaSwiftTrancodeMap WHERE mnem_code = ?"
    result = fetch_one(conn, sql, (mnem_code,))
    return result['swift_trancode'] if result else "NMSC"


# ---------------------------------------------------------------------------
# Email / sentflag queries
# ---------------------------------------------------------------------------

def get_email_recipients(conn: sqlite3.Connection, report_name: str = 'MT940') -> Optional[sqlite3.Row]:
    """Read email recipient config from codetable for a given report name."""
    sql = """
        SELECT emailrecipient, emailrecipientcc, emailreport
        FROM codetable
        WHERE emailreport = ?
    """
    return fetch_one(conn, sql, (report_name,))


def update_sent_flag(conn: sqlite3.Connection, report_name: str, flag_value: int = 1) -> bool:
    sql = "UPDATE codetable SET sentflag = ? WHERE emailreport = ?"
    return execute_query(conn, sql, (str(flag_value), report_name)) is not None


def check_sent_flag(conn: sqlite3.Connection, report_name: str = 'MT940') -> int:
    """Returns the current sentflag value (0 = not sent, 1 = sent)."""
    result = fetch_one(conn, "SELECT sentflag FROM codetable WHERE emailreport = ?", (report_name,))
    if result:
        try:
            return int(result['sentflag']) if result['sentflag'] else 0
        except (ValueError, TypeError):
            return 0
    return 0


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def clear_summary_table(conn: sqlite3.Connection) -> bool:
    """Clear MT940_summary_rep before each processing run."""
    return execute_query(conn, "DELETE FROM MT940_summary_rep") is not None


def insert_summary_record(conn: sqlite3.Connection, data: str, code: str,
                          refnum: str, date) -> bool:
    """Insert a beginning/closing balance record into the summary report table."""
    from datetime import datetime
    date_str = date.strftime("%B %d, %Y") if isinstance(date, datetime) else str(date)
    sql = "INSERT INTO MT940_summary_rep (data, code, refnum, date) VALUES (?, ?, ?, ?)"
    return execute_query(conn, sql, (data, code, refnum, date_str)) is not None


def get_summary_report(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return fetch_all(conn, "SELECT * FROM MT940_summary_rep ORDER BY code, date")


# ---------------------------------------------------------------------------
# Recordset — VB6 ADODB.Recordset compatibility wrapper
# ---------------------------------------------------------------------------

class Recordset:
    def __init__(self, conn: sqlite3.Connection, sql: str, params: tuple = ()):
        self.cursor = conn.cursor()
        self.cursor.execute(sql, params)
        self.current_row = None
        self.move_next()

    @property
    def eof(self) -> bool:
        return self.current_row is None

    def move_next(self) -> None:
        self.current_row = self.cursor.fetchone()

    def __getitem__(self, field_name: str) -> Any:
        if self.current_row:
            try:
                return self.current_row[field_name]
            except (KeyError, IndexError):
                return None
        return None

    def close(self) -> None:
        if self.cursor:
            self.cursor.close()
            self.cursor = None
            self.current_row = None
