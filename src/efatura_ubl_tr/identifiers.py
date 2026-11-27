"""Identifier helpers: VKN / TCKN checksums, invoice numbers and ETTN (UUID).

All checks here are purely *algorithmic*. A number that passes the checksum is
well-formed, it is **not** proof that the person or company exists or is
registered for e-Fatura. Use GİB / your integrator's user list (mükellef
sorgulama) for that.
"""

from __future__ import annotations

import re
import uuid
from typing import Literal

__all__ = [
    "INVOICE_NUMBER_PATTERN",
    "NIHAI_TUKETICI_TCKN",
    "identify_tax_id",
    "is_valid_invoice_number",
    "is_valid_tckn",
    "is_valid_uuid",
    "is_valid_vkn",
    "make_invoice_number",
    "new_uuid",
    "next_invoice_number",
    "parse_invoice_number",
    "tckn_check_digits",
    "vkn_check_digit",
]

#: Placeholder TCKN conventionally used for final consumers without an ID on e-Arşiv
#: invoices ("nihai tüketici"). It intentionally does *not* pass the TCKN checksum.
NIHAI_TUKETICI_TCKN = "11111111111"

#: GİB format: 3 alphanumeric characters + 4-digit year (20xx) + 9-digit sequence.
INVOICE_NUMBER_PATTERN = re.compile(r"^[A-Z0-9]{3}20[0-9]{2}[0-9]{9}$")

_UUID_PATTERN = re.compile(
    r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
)


def _digits(value: str, length: int) -> list[int] | None:
    if not isinstance(value, str) or len(value) != length:
        return None
    if not (value.isascii() and value.isdigit()):
        return None
    return [int(ch) for ch in value]


def vkn_check_digit(first_nine: str) -> str:
    """Return the 10th (check) digit for the first nine digits of a VKN."""
    digits = _digits(first_nine, 9)
    if digits is None:
        raise ValueError("first_nine must be exactly 9 ASCII digits")
    total = 0
    for index, digit in enumerate(digits):
        tmp = (digit + 9 - index) % 10
        value = (tmp * 2 ** (9 - index)) % 9
        if tmp != 0 and value == 0:
            value = 9
        total += value
    return str((10 - total % 10) % 10)


def is_valid_vkn(value: str) -> bool:
    """Validate a 10-digit Vergi Kimlik Numarası (tax ID) with the official checksum."""
    digits = _digits(value, 10)
    if digits is None:
        return False
    return vkn_check_digit(value[:9]) == value[9]


def tckn_check_digits(first_nine: str) -> str:
    """Return the two check digits (10th and 11th) for the first nine TCKN digits."""
    digits = _digits(first_nine, 9)
    if digits is None or digits[0] == 0:
        raise ValueError("first_nine must be 9 ASCII digits and must not start with 0")
    odd = sum(digits[0:9:2])
    even = sum(digits[1:8:2])
    tenth = (odd * 7 - even) % 10
    eleventh = (sum(digits) + tenth) % 10
    return f"{tenth}{eleventh}"


def is_valid_tckn(value: str) -> bool:
    """Validate an 11-digit T.C. Kimlik Numarası with the official checksum."""
    digits = _digits(value, 11)
    if digits is None or digits[0] == 0:
        return False
    return tckn_check_digits(value[:9]) == value[9:]


def identify_tax_id(value: str) -> Literal["VKN", "TCKN"] | None:
    """Return ``"VKN"`` or ``"TCKN"`` if *value* is a well-formed ID, otherwise ``None``."""
    if is_valid_vkn(value):
        return "VKN"
    if is_valid_tckn(value):
        return "TCKN"
    return None


def make_invoice_number(prefix: str, year: int, sequence: int) -> str:
    """Build a GİB-style invoice number, e.g. ``make_invoice_number("ABC", 2026, 1)``.

    >>> make_invoice_number("ABC", 2026, 1)
    'ABC2026000000001'
    """
    prefix = prefix.upper()
    if not re.fullmatch(r"[A-Z0-9]{3}", prefix):
        raise ValueError("prefix must be exactly 3 characters A-Z / 0-9")
    if not 2000 <= year <= 2099:
        raise ValueError("year must be between 2000 and 2099")
    if not 1 <= sequence <= 999_999_999:
        raise ValueError("sequence must be between 1 and 999999999")
    return f"{prefix}{year:04d}{sequence:09d}"


def is_valid_invoice_number(number: str) -> bool:
    """Check the GİB invoice number format (``ABC2026000000001``)."""
    return bool(isinstance(number, str) and INVOICE_NUMBER_PATTERN.fullmatch(number))


def parse_invoice_number(number: str) -> tuple[str, int, int]:
    """Split an invoice number into ``(prefix, year, sequence)``."""
    if not is_valid_invoice_number(number):
        raise ValueError(f"invalid invoice number: {number!r} (expected e.g. ABC2026000000001)")
    return number[:3], int(number[3:7]), int(number[7:])


def next_invoice_number(last_number: str, *, year: int | None = None) -> str:
    """Return the next number in the series.

    If *year* is given and differs from the year of *last_number*, the sequence
    restarts at 1 (invoice series are normally reset every calendar year).
    """
    prefix, last_year, sequence = parse_invoice_number(last_number)
    if year is not None and year != last_year:
        return make_invoice_number(prefix, year, 1)
    return make_invoice_number(prefix, last_year, sequence + 1)


def new_uuid() -> str:
    """Generate a new ETTN (random UUID v4, upper-case as in GİB samples)."""
    return str(uuid.uuid4()).upper()


def is_valid_uuid(value: str) -> bool:
    """Check the ETTN / UUID format used by UBL-TR (8-4-4-4-12 hexadecimal)."""
    return bool(isinstance(value, str) and _UUID_PATTERN.fullmatch(value))
