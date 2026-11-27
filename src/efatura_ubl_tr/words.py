"""Turkish amount-in-words ("Yalnız ... Türk Lirası ... Kuruş").

Rules implemented (Türkçe yazım kuralları):

* 100 is "yüz" (not "bir yüz") and 1000 is "bin" (not "bir bin"),
  but 1 000 000 is "bir milyon".
* The amount is rounded to 2 decimals with ROUND_HALF_UP before conversion.
* The sub-unit (kuruş / sent) part is omitted when it is zero; the main unit is
  omitted when it is zero but the sub-unit is not (``0.50 TRY`` -> "Elli Kuruş").
* Case-folding is Turkish-aware (``i -> İ``, ``ı -> I``).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from .codes import CURRENCY_NAMES

__all__ = ["amount_in_words", "number_to_words", "yalniz_note"]

_ONES = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
_TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]
_SCALES = ["", "bin", "milyon", "milyar", "trilyon", "katrilyon", "kentilyon"]

Case = Literal["title", "upper", "lower"]


def _below_thousand(n: int) -> list[str]:
    words: list[str] = []
    hundreds, rest = divmod(n, 100)
    if hundreds:
        if hundreds > 1:
            words.append(_ONES[hundreds])
        words.append("yüz")
    tens, ones = divmod(rest, 10)
    if tens:
        words.append(_TENS[tens])
    if ones:
        words.append(_ONES[ones])
    return words


def _number_words(n: int) -> list[str]:
    if n < 0:
        raise ValueError("negative numbers are not supported")
    if n == 0:
        return ["sıfır"]
    groups: list[int] = []
    while n:
        n, group = divmod(n, 1000)
        groups.append(group)
    if len(groups) > len(_SCALES):
        raise ValueError("number too large")
    words: list[str] = []
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if not group:
            continue
        if index == 1 and group == 1:
            words.append("bin")  # "bin", never "bir bin"
            continue
        words.extend(_below_thousand(group))
        if _SCALES[index]:
            words.append(_SCALES[index])
    return words


def _tr_upper(text: str) -> str:
    return text.replace("i", "İ").replace("ı", "I").upper()


def _tr_lower(text: str) -> str:
    return text.replace("I", "ı").replace("İ", "i").lower()


def _tr_capitalize(word: str) -> str:
    if not word:
        return word
    return _tr_upper(word[0]) + _tr_lower(word[1:])


def _apply_case(words: list[str], case: Case) -> list[str]:
    if case == "upper":
        return [_tr_upper(w) for w in words]
    if case == "lower":
        return [_tr_lower(w) for w in words]
    return [_tr_capitalize(w) for w in words]


def number_to_words(n: int, *, case: Case = "lower", compact: bool = False) -> str:
    """Spell a non-negative integer in Turkish.

    >>> number_to_words(1984)
    'bin dokuz yüz seksen dört'
    >>> number_to_words(1_001_000, case="title", compact=True)
    'BirMilyonBin'
    """
    words = _apply_case(_number_words(n), case)
    return ("" if compact else " ").join(words)


def amount_in_words(
    amount: Decimal | int | str,
    currency: str = "TRY",
    *,
    case: Case = "title",
    compact: bool = False,
    unit_names: tuple[str, str] | None = None,
) -> str:
    """Spell a monetary amount in Turkish.

    >>> amount_in_words(Decimal("12325.50"))
    'On İki Bin Üç Yüz Yirmi Beş Türk Lirası Elli Kuruş'
    >>> amount_in_words("1000", "USD")
    'Bin ABD Doları'

    :param compact: join the digits' words without spaces (``"OnİkiBin..."``), a style many
        Turkish invoices use to make the text harder to tamper with.
    :param unit_names: override ``(main unit, sub unit)`` names, e.g. ``("Kuveyt Dinarı", "Fils")``.
    """
    value = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount
    if value.is_nan() or value.is_infinite():
        raise ValueError("amount must be a finite number")
    value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if value < 0:
        raise ValueError("amount must not be negative")
    main_name, sub_name = unit_names or CURRENCY_NAMES.get(currency.upper(), (currency, "Sent"))
    whole = int(value)
    cents = int((value - whole) * 100)
    sep = "" if compact else " "

    def fmt_name(name: str) -> str:
        if case == "upper":
            return _tr_upper(name)
        if case == "lower":
            return _tr_lower(name)
        return name

    parts: list[str] = []
    if whole or not cents:
        parts.append(sep.join(_apply_case(_number_words(whole), case)) + " " + fmt_name(main_name))
    if cents:
        parts.append(sep.join(_apply_case(_number_words(cents), case)) + " " + fmt_name(sub_name))
    return " ".join(parts)


def yalniz_note(
    amount: Decimal | int | str,
    currency: str = "TRY",
    *,
    case: Case = "title",
    compact: bool = False,
    prefix: str = "Yalnız:",
) -> str:
    """Return the classic invoice note, e.g. ``"Yalnız: Yüz Yirmi Türk Lirası"``."""
    return f"{prefix} {amount_in_words(amount, currency, case=case, compact=compact)}"
