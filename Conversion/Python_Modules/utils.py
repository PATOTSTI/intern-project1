import os
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

def get_currency_code(product_code: str) -> str:
    """Maps a 2-digit product code to its ISO currency. Defaults to PHP."""
    currency_map = {
        '16': 'EUR',
        '17': 'JPY',
        '18': 'CNY',
        '19': 'USD',
    }
    return currency_map.get(product_code, 'PHP')


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _as_yyyymmdd(date_input) -> str:
    """Accept either a datetime or a pre-formatted YYYYMMDD string."""
    if isinstance(date_input, datetime):
        return date_input.strftime("%Y%m%d")
    return str(date_input)


def format_date_yyyymmdd(date_obj: datetime) -> str:
    """VB6: Format(date, "YYYYMMDD")"""
    return date_obj.strftime("%Y%m%d")


def get_stmdate(date_input) -> str:
    """Last 5 chars of YYYYMMDD — VB6: Right(Format(date,"YYYYMMDD"), 5)"""
    return _as_yyyymmdd(date_input)[-5:]


def get_stmdate2(date_input) -> str:
    """Last 6 chars of YYYYMMDD — VB6: Right(Format(date,"YYYYMMDD"), 6)"""
    return _as_yyyymmdd(date_input)[-6:]


def get_stmdate3(date_input) -> str:
    """Last 4 chars of YYYYMMDD — VB6: Right(Format(date,"YYYYMMDD"), 4)"""
    return _as_yyyymmdd(date_input)[-4:]


# ---------------------------------------------------------------------------
# String helpers (VB6 compatibility — 1-based indexing)
# ---------------------------------------------------------------------------

def pad_zeros(number: int, length: int) -> str:
    """VB6: Format(number, "000") — zero-pads to the given length."""
    return str(number).zfill(length)


def mid_str(text: str, start: int, length: int) -> str:
    """VB6 Mid() — 1-based start position."""
    return text[start - 1: start - 1 + length]


# ---------------------------------------------------------------------------
# Amount formatting
# ---------------------------------------------------------------------------

def format_mt940_amount(amount: float) -> str:
    """
    Format a number for MT940 output, replacing '.' with ',' as the decimal separator.
    VB6: Replace(Format(amount, "########0.00"), ".", ",")
    """
    return f"{amount:.2f}".replace(".", ",")


# ---------------------------------------------------------------------------
# File system
# ---------------------------------------------------------------------------

def check_file_exists(filepath: str) -> bool:
    """VB6: Dir(filepath) <> "" """
    return os.path.exists(filepath)


def create_directory(path: str) -> bool:
    """VB6: MkDir — creates directory if it doesn't already exist."""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        print(f"ERROR creating directory: {e}")
        return False
