import pytest

from efatura_ubl_tr.identifiers import (
    NIHAI_TUKETICI_TCKN,
    identify_tax_id,
    is_valid_invoice_number,
    is_valid_tckn,
    is_valid_uuid,
    is_valid_vkn,
    make_invoice_number,
    new_uuid,
    next_invoice_number,
    parse_invoice_number,
    tckn_check_digits,
    vkn_check_digit,
)


@pytest.mark.parametrize(
    "vkn",
    [
        "3900892152",  # public institution VKNs referenced in GİB's own schematron
        "1460415308",
        "1234567890",  # synthetic numbers used in the examples
        "9876543217",
    ],
)
def test_valid_vkn(vkn: str) -> None:
    assert is_valid_vkn(vkn)
    assert identify_tax_id(vkn) == "VKN"


@pytest.mark.parametrize(
    "vkn",
    ["1234567891", "123456789", "12345678901", "abcdefghij", "", "１２３４５６７８９０"],
)
def test_invalid_vkn(vkn: str) -> None:
    assert not is_valid_vkn(vkn)


def test_vkn_check_digit_roundtrip() -> None:
    for base in ("000000000", "999999999", "555666777", "100000000"):
        assert is_valid_vkn(base + vkn_check_digit(base))


def test_vkn_check_digit_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        vkn_check_digit("12345")


@pytest.mark.parametrize("tckn", ["10000000146", "12345678950"])
def test_valid_tckn(tckn: str) -> None:
    assert is_valid_tckn(tckn)
    assert identify_tax_id(tckn) == "TCKN"


@pytest.mark.parametrize(
    "tckn",
    [
        "12345678951",  # wrong 11th digit
        "12345678940",  # wrong 10th digit
        "02345678950",  # leading zero
        "1234567895",  # too short
        NIHAI_TUKETICI_TCKN,  # placeholder does not pass the checksum
    ],
)
def test_invalid_tckn(tckn: str) -> None:
    assert not is_valid_tckn(tckn)


def test_tckn_check_digits() -> None:
    assert tckn_check_digits("123456789") == "50"
    with pytest.raises(ValueError):
        tckn_check_digits("012345678")


def test_identify_unknown() -> None:
    assert identify_tax_id("12") is None


def test_invoice_number_helpers() -> None:
    number = make_invoice_number("abc", 2026, 1)
    assert number == "ABC2026000000001"
    assert is_valid_invoice_number(number)
    assert parse_invoice_number(number) == ("ABC", 2026, 1)
    assert next_invoice_number(number) == "ABC2026000000002"
    assert next_invoice_number("ABC2026000000042", year=2027) == "ABC2027000000001"


@pytest.mark.parametrize(
    "number",
    [
        "AB2026000000001",
        "ABC1999000000001",
        "abc2026000000001",
        "ABC20260000001",
        "ABC-026000000001",
    ],
)
def test_invalid_invoice_numbers(number: str) -> None:
    assert not is_valid_invoice_number(number)
    with pytest.raises(ValueError):
        parse_invoice_number(number)


@pytest.mark.parametrize(
    ("prefix", "year", "seq"),
    [("AB", 2026, 1), ("ABC", 1999, 1), ("ABC", 2026, 0), ("ABC", 2026, 10**9), ("A_C", 2026, 1)],
)
def test_make_invoice_number_rejects(prefix: str, year: int, seq: int) -> None:
    with pytest.raises(ValueError):
        make_invoice_number(prefix, year, seq)


def test_uuid_helpers() -> None:
    value = new_uuid()
    assert is_valid_uuid(value)
    assert value == value.upper()
    assert not is_valid_uuid("not-a-uuid")
