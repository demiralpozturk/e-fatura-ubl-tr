from __future__ import annotations

from decimal import Decimal

import pytest

from efatura_ubl_tr import AllowanceCharge, InvoiceLine, InvoiceType, LineTax, Profile
from efatura_ubl_tr.calc import round_money
from efatura_ubl_tr.models import OzelMatrah, TaxExemption, Withholding

from .conftest import make_invoice

D = Decimal


def test_round_money_half_up() -> None:
    assert round_money(D("0.005")) == D("0.01")
    assert round_money(D("0.004999")) == D("0.00")
    assert round_money(D("2.675")) == D("2.68")  # float would give 2.67
    assert round_money(D("-1.005")) == D("-1.01")


def test_simple_line_totals() -> None:
    inv = make_invoice([InvoiceLine(name="A", quantity=3, unit_price=D("4500"), kdv_rate=20)])
    calc = inv.calculate()
    assert calc.line_extension_total == D("13500.00")
    assert calc.tax_exclusive == D("13500.00")
    assert calc.tax_total == D("2700.00")
    assert calc.tax_inclusive == D("16200.00")
    assert calc.payable == D("16200.00")
    assert calc.allowance_total == D("0.00")


def test_rounding_happens_per_line() -> None:
    # three lines of 0.105 KDV each: per-line rounding gives 0.11 x 3 = 0.33,
    # rounding the total once would give round(0.315) = 0.32
    lines = [
        InvoiceLine(name=f"L{i}", quantity=1, unit_price=D("1.05"), kdv_rate=10) for i in range(3)
    ]
    calc = make_invoice(lines).calculate()
    assert [ln.kdv.amount for ln in calc.lines] == [D("0.11")] * 3
    assert calc.tax_total == D("0.33")
    (subtotal,) = calc.tax_subtotals
    assert subtotal.taxable == D("3.15")
    assert subtotal.amount == D("0.33")


def test_quantity_times_price_rounding() -> None:
    line = InvoiceLine(name="Fındık", quantity=D("2.333"), unit_price=D("10.555"), kdv_rate=1)
    calc = make_invoice([line]).calculate()
    # 2.333 * 10.555 = 24.624815 -> 24.62
    assert calc.lines[0].gross == D("24.62")
    assert calc.lines[0].kdv.amount == D("0.25")  # 0.2462 -> 0.25


def test_cascading_discounts_and_charges() -> None:
    line = InvoiceLine(
        name="Abonelik",
        quantity=25,
        unit_price=D("119.99"),
        kdv_rate=20,
        allowances=[
            AllowanceCharge(rate=15, reason="Hacim"),
            AllowanceCharge(rate=5, reason="Erken ödeme"),
            AllowanceCharge(is_charge=True, amount=D("10"), reason="Kargo"),
        ],
    )
    calc = make_invoice([line]).calculate()
    ln = calc.lines[0]
    assert ln.gross == D("2999.75")
    assert [a.amount for a in ln.allowances] == [D("449.96"), D("127.49"), D("10.00")]
    assert [a.base for a in ln.allowances] == [D("2999.75"), D("2549.79"), D("2422.30")]
    assert ln.allowance_total == D("577.45")
    assert ln.charge_total == D("10.00")
    assert ln.line_extension == D("2432.30")
    assert calc.tax_exclusive == D("2432.30")
    assert calc.line_extension_total == D("2999.75")
    assert ln.kdv.amount == D("486.46")


def test_discount_larger_than_line_is_rejected() -> None:
    line = InvoiceLine(name="X", quantity=1, unit_price=10, allowances=[AllowanceCharge(amount=11)])
    with pytest.raises(ValueError, match="discounts exceed"):
        make_invoice([line]).calculate()


def test_multiple_kdv_rates_grouped() -> None:
    lines = [
        InvoiceLine(name="A", quantity=1, unit_price=100, kdv_rate=20),
        InvoiceLine(name="B", quantity=1, unit_price=200, kdv_rate=10),
        InvoiceLine(name="C", quantity=2, unit_price=50, kdv_rate=20),
    ]
    calc = make_invoice(lines).calculate()
    by_rate = {t.rate: t for t in calc.tax_subtotals}
    assert by_rate[D(20)].taxable == D("200.00")
    assert by_rate[D(20)].amount == D("40.00")
    assert by_rate[D(10)].amount == D("20.00")
    assert calc.payable == D("460.00")


def test_tevkifat_amounts() -> None:
    lines = [
        InvoiceLine(
            name="Temizlik",
            quantity=1,
            unit_price=D("45000"),
            kdv_rate=20,
            withholding=Withholding(code="612"),
        ),
        InvoiceLine(name="Malzeme", quantity=12, unit_price=D("137.40"), kdv_rate=20),
    ]
    inv = make_invoice(lines, type=InvoiceType.TEVKIFAT, profile=Profile.TICARIFATURA)
    calc = inv.calculate()
    w = calc.lines[0].withholding
    assert w is not None
    assert (w.code, w.rate, w.taxable, w.amount) == ("612", D(90), D("9000.00"), D("8100.00"))
    assert calc.withholding_total == D("8100.00")
    assert calc.tax_total == D("9329.76")
    assert calc.tax_total_after_withholding == D("1229.76")
    assert calc.tax_inclusive == D("55978.56")
    assert calc.payable == D("47878.56")


def test_tevkifat_odd_rounding() -> None:
    line = InvoiceLine(
        name="Yemek",
        quantity=1,
        unit_price=D("333.33"),
        kdv_rate=10,
        withholding=Withholding(code="604"),  # 5/10
    )
    calc = make_invoice([line], type=InvoiceType.TEVKIFAT).calculate()
    # KDV 33.333 -> 33.33, withholding 16.665 -> 16.67
    assert calc.lines[0].kdv.amount == D("33.33")
    assert calc.withholding_total == D("16.67")
    assert calc.payable == D("333.33") + D("33.33") - D("16.67")


def test_full_withholding_and_custom_rate() -> None:
    full = InvoiceLine(
        name="Servis",
        quantity=1,
        unit_price=1000,
        withholding=Withholding(code="814"),
    )
    alt = InvoiceLine(
        name="Yapım", quantity=1, unit_price=1000, withholding=Withholding(code="601", rate=30)
    )
    calc = make_invoice([full, alt], type=InvoiceType.TEVKIFAT).calculate()
    rates = {w.code: (w.rate, w.amount) for w in calc.withholding_subtotals}
    assert rates == {"814": (D(100), D("200.00")), "601": (D(30), D("60.00"))}


def test_otv_is_added_to_kdv_base() -> None:
    line = InvoiceLine(
        name="Klima",
        quantity=4,
        unit_price=D("21500"),
        kdv_rate=20,
        taxes=[LineTax(code="0074", rate=20)],
    )
    calc = make_invoice([line]).calculate()
    otv, kdv = calc.lines[0].taxes
    assert (otv.code, otv.amount) == ("0074", D("17200.00"))
    assert kdv.taxable == D("103200.00")
    assert kdv.amount == D("20640.00")
    assert calc.tax_inclusive == D("123840.00")
    assert [t.code for t in calc.tax_subtotals] == ["0074", "0015"]


def test_fixed_amount_tax_not_in_kdv_base() -> None:
    line = InvoiceLine(
        name="Hizmet",
        quantity=1,
        unit_price=100,
        taxes=[LineTax(code="4080", amount=D("7.5"), include_in_kdv_base=False)],
    )
    calc = make_invoice([line]).calculate()
    assert calc.lines[0].kdv.taxable == D("100.00")
    assert calc.tax_total == D("27.50")


def test_istisna_zero_kdv() -> None:
    line = InvoiceLine(
        name="Yazılım", quantity=10, unit_price=1750, kdv_rate=0, exemption=TaxExemption(code="317")
    )
    calc = make_invoice([line], type=InvoiceType.ISTISNA).calculate()
    (sub,) = calc.tax_subtotals
    assert sub.amount == D("0.00")
    assert sub.exemption_code == "317"
    assert sub.exemption_reason and sub.exemption_reason.startswith("17/4-s")
    assert calc.payable == D("17500.00")


def test_ihrackayitli_kdv_shown_not_collected() -> None:
    line = InvoiceLine(
        name="Kart", quantity=500, unit_price=385, kdv_rate=20, exemption=TaxExemption(code="701")
    )
    calc = make_invoice([line], type=InvoiceType.IHRACKAYITLI).calculate()
    (sub,) = calc.tax_subtotals
    assert sub.amount == D("38500.00") and not sub.collected
    assert calc.tax_total == D("38500.00")
    assert calc.tax_inclusive == calc.payable == D("192500.00")


def test_ozelmatrah_uses_special_base() -> None:
    line = InvoiceLine(
        name="Bilezik",
        quantity=D("15.2"),
        unit_price=D("4850"),
        kdv_rate=20,
        ozel_matrah=OzelMatrah(code="805", base=D("6080")),
    )
    calc = make_invoice([line], type=InvoiceType.OZELMATRAH).calculate()
    (sub,) = calc.tax_subtotals
    assert (sub.taxable, sub.amount, sub.exemption_code) == (D("6080.00"), D("1216.00"), "805")
    assert calc.payable == D("73720.00")


def test_multi_currency_and_try_conversion() -> None:
    inv = make_invoice(
        [InvoiceLine(name="Danışmanlık", quantity=D("12.5"), unit_price=95, kdv_rate=20)],
        currency="USD",
        exchange_rate=D("41.8523"),
    )
    calc = inv.calculate()
    assert calc.payable == D("1425.00")
    assert calc.in_try(calc.payable) == D("59639.53")  # 1425 * 41.8523 = 59639.5275


def test_try_invoice_in_try_is_identity() -> None:
    calc = make_invoice().calculate()
    assert calc.in_try(D("12.34")) == D("12.34")
