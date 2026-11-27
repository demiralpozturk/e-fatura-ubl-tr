from decimal import Decimal

import pytest

from efatura_ubl_tr.words import amount_in_words, number_to_words, yalniz_note


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (0, "sıfır"),
        (1, "bir"),
        (10, "on"),
        (11, "on bir"),
        (100, "yüz"),
        (101, "yüz bir"),
        (200, "iki yüz"),
        (999, "dokuz yüz doksan dokuz"),
        (1000, "bin"),
        (1001, "bin bir"),
        (1100, "bin yüz"),
        (2000, "iki bin"),
        (10_000, "on bin"),
        (11_000, "on bir bin"),
        (100_000, "yüz bin"),
        (101_000, "yüz bir bin"),
        (1_000_000, "bir milyon"),
        (1_001_000, "bir milyon bin"),
        (2_500_000_000, "iki milyar beş yüz milyon"),
        (1_000_000_000_000, "bir trilyon"),
    ],
)
def test_number_to_words(number: int, expected: str) -> None:
    assert number_to_words(number) == expected


def test_number_to_words_negative() -> None:
    with pytest.raises(ValueError):
        number_to_words(-1)


def test_amount_in_words_try() -> None:
    assert (
        amount_in_words(Decimal("12325.50")) == "On İki Bin Üç Yüz Yirmi Beş Türk Lirası Elli Kuruş"
    )


def test_amount_in_words_rounding_half_up() -> None:
    # 0.005 rounds up to 0.01
    assert amount_in_words("1.005") == "Bir Türk Lirası Bir Kuruş"
    assert amount_in_words("0.994") == "Doksan Dokuz Kuruş"


def test_amount_in_words_only_kurus_and_zero() -> None:
    assert amount_in_words("0.50") == "Elli Kuruş"
    assert amount_in_words(0) == "Sıfır Türk Lirası"


def test_amount_in_words_no_kurus() -> None:
    assert amount_in_words("1000.00") == "Bin Türk Lirası"


def test_amount_in_words_foreign_currency() -> None:
    assert amount_in_words("1500.25", "USD") == "Bin Beş Yüz ABD Doları Yirmi Beş Sent"
    assert amount_in_words("3", "EUR") == "Üç Euro"


def test_amount_in_words_unknown_currency_and_override() -> None:
    assert amount_in_words("2", "KWD") == "İki KWD"
    assert amount_in_words("2.5", "KWD", unit_names=("Kuveyt Dinarı", "Fils")) == (
        "İki Kuveyt Dinarı Elli Fils"
    )


def test_amount_in_words_cases_and_compact() -> None:
    assert amount_in_words("41.10", case="upper") == "KIRK BİR TÜRK LİRASI ON KURUŞ"
    assert amount_in_words("41.10", case="lower") == "kırk bir türk lirası on kuruş"
    assert amount_in_words("12325.50", compact=True) == (
        "OnİkiBinÜçYüzYirmiBeş Türk Lirası Elli Kuruş"
    )


def test_amount_in_words_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        amount_in_words("-1")
    with pytest.raises(ValueError):
        amount_in_words(Decimal("NaN"))


def test_yalniz_note() -> None:
    assert yalniz_note("120") == "Yalnız: Yüz Yirmi Türk Lirası"
