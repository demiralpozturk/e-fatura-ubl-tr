"""Invoice calculations with :class:`decimal.Decimal`.

Rounding policy (documented, deterministic):

1. Every monetary amount is rounded to 2 decimals with ``ROUND_HALF_UP``
   ("yarım yukarı"), the convention used on Turkish invoices.
2. Rounding happens **per line**: ``gross = round(quantity × unit_price)``, each
   discount/surcharge is rounded, each tax is rounded. Document totals are the
   sums of the already-rounded line values, so lines and totals always agree.
3. Multiple discounts on one line are applied **sequentially** (cascading):
   ``%10 + %5`` on 100.00 gives 10.00 then 4.50.
4. Additional line taxes (e.g. ÖTV) are computed on the line amount after
   discounts and, when ``include_in_kdv_base`` is true, added to the KDV base.
5. Tevkifat (withholding) = ``round(KDV × rate / 100)`` per line.

Monetary-total semantics follow GİB's sample invoices:

* ``LegalMonetaryTotal/LineExtensionAmount`` – sum of line gross amounts (before discounts)
* ``AllowanceTotalAmount`` / ``ChargeTotalAmount`` – sum of line discounts / surcharges
* ``TaxExclusiveAmount`` – sum of the line net amounts
* ``TaxInclusiveAmount`` – tax exclusive + taxes that are collected
* ``PayableAmount`` – tax inclusive − withheld KDV (tevkifat)
* ``TaxTotal/TaxAmount`` – total of tax subtotals − withheld KDV (as in GİB's
  ``TEVKIFAT.xml`` sample); ``TaxSubtotal/TaxAmount`` holds the full computed tax.

Taxes that are shown but *not collected* (KDV on IHRACKAYITLI lines, which is
deferred, and KDV on OZELMATRAH lines, which is included in the price) are
reported in the tax subtotals but not added to the inclusive/payable amounts.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from .codes import KDV_TAX_CODE, InvoiceType

if TYPE_CHECKING:
    from .models import Invoice, InvoiceLine

__all__ = [
    "AllowanceChargeResult",
    "InvoiceCalculation",
    "LineCalculation",
    "TaxResult",
    "WithholdingResult",
    "calculate",
    "calculate_line",
    "round_money",
]

_CENT = Decimal("0.01")
_HUNDRED = Decimal(100)
_ZERO = Decimal("0.00")


def round_money(value: Decimal) -> Decimal:
    """Round to 2 decimals using ROUND_HALF_UP."""
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _percent_of(base: Decimal, rate: Decimal) -> Decimal:
    return round_money(base * rate / _HUNDRED)


@dataclass(frozen=True)
class AllowanceChargeResult:
    is_charge: bool
    reason: str | None
    rate: Decimal | None
    base: Decimal
    amount: Decimal


@dataclass(frozen=True)
class TaxResult:
    code: str
    name: str
    rate: Decimal | None
    taxable: Decimal
    amount: Decimal
    exemption_code: str | None = None
    exemption_reason: str | None = None
    #: False when the tax is shown but not charged to the buyer (deferred / in price).
    collected: bool = True


@dataclass(frozen=True)
class WithholdingResult:
    code: str
    name: str
    rate: Decimal
    taxable: Decimal
    amount: Decimal


@dataclass(frozen=True)
class LineCalculation:
    index: int
    gross: Decimal
    allowances: tuple[AllowanceChargeResult, ...]
    allowance_total: Decimal
    charge_total: Decimal
    line_extension: Decimal
    #: Additional taxes first (ÖTV …), KDV last.
    taxes: tuple[TaxResult, ...]
    withholding: WithholdingResult | None

    @property
    def kdv(self) -> TaxResult:
        return next(t for t in self.taxes if t.code == KDV_TAX_CODE)

    @property
    def tax_total(self) -> Decimal:
        """Sum of all line tax amounts (before withholding)."""
        return sum((t.amount for t in self.taxes), _ZERO)

    @property
    def withholding_amount(self) -> Decimal:
        return self.withholding.amount if self.withholding else _ZERO


@dataclass(frozen=True)
class InvoiceCalculation:
    currency: str
    exchange_rate: Decimal | None
    lines: tuple[LineCalculation, ...]
    line_extension_total: Decimal
    allowance_total: Decimal
    charge_total: Decimal
    tax_exclusive: Decimal
    tax_subtotals: tuple[TaxResult, ...]
    tax_total: Decimal
    collected_tax_total: Decimal
    withholding_subtotals: tuple[WithholdingResult, ...]
    withholding_total: Decimal
    tax_inclusive: Decimal
    payable: Decimal

    @property
    def tax_total_after_withholding(self) -> Decimal:
        """Value written to ``cac:TaxTotal/cbc:TaxAmount``."""
        return self.tax_total - self.withholding_total

    def in_try(self, amount: Decimal) -> Decimal:
        """Convert a document-currency amount to TRY using the invoice exchange rate."""
        if self.exchange_rate is None:
            return amount
        return round_money(amount * self.exchange_rate)


def calculate_line(line: InvoiceLine, index: int, invoice_type: InvoiceType) -> LineCalculation:
    gross = round_money(line.quantity * line.unit_price)

    running = gross
    results: list[AllowanceChargeResult] = []
    allowance_total = _ZERO
    charge_total = _ZERO
    for ac in line.allowances:
        if ac.rate is not None:
            amount = _percent_of(running, ac.rate)
        else:
            assert ac.amount is not None
            amount = round_money(ac.amount)
        results.append(AllowanceChargeResult(ac.is_charge, ac.reason, ac.rate, running, amount))
        if ac.is_charge:
            charge_total += amount
            running += amount
        else:
            allowance_total += amount
            running -= amount
    if running < 0:
        raise ValueError(f"line {index}: discounts exceed the line amount")
    line_extension = running

    taxes: list[TaxResult] = []
    kdv_base = line_extension
    for tax in line.taxes:
        if tax.rate is not None:
            tax_amount = _percent_of(line_extension, tax.rate)
        else:
            assert tax.amount is not None
            tax_amount = round_money(tax.amount)
        taxes.append(
            TaxResult(
                code=tax.code,
                name=tax.name or tax.code,
                rate=tax.rate,
                taxable=line_extension,
                amount=tax_amount,
            )
        )
        if tax.include_in_kdv_base:
            kdv_base += tax_amount

    exemption_code = line.exemption.code if line.exemption else None
    exemption_reason = line.exemption.reason if line.exemption else None
    collected = True
    if line.ozel_matrah is not None:
        kdv_base = round_money(line.ozel_matrah.base)
        exemption_code = line.ozel_matrah.code
        exemption_reason = line.ozel_matrah.reason
        collected = False
    elif invoice_type is InvoiceType.IHRACKAYITLI:
        collected = False  # KDV is computed and shown but deferred (tecil)

    kdv = TaxResult(
        code=KDV_TAX_CODE,
        name="KDV",
        rate=line.kdv_rate,
        taxable=kdv_base,
        amount=_percent_of(kdv_base, line.kdv_rate),
        exemption_code=exemption_code,
        exemption_reason=exemption_reason,
        collected=collected,
    )
    taxes.append(kdv)

    withholding = None
    if line.withholding is not None:
        assert line.withholding.rate is not None
        withholding = WithholdingResult(
            code=line.withholding.code,
            name=line.withholding.name,
            rate=line.withholding.rate,
            taxable=kdv.amount,
            amount=_percent_of(kdv.amount, line.withholding.rate),
        )

    return LineCalculation(
        index=index,
        gross=gross,
        allowances=tuple(results),
        allowance_total=allowance_total,
        charge_total=charge_total,
        line_extension=line_extension,
        taxes=tuple(taxes),
        withholding=withholding,
    )


def _group_taxes(lines: tuple[LineCalculation, ...]) -> tuple[TaxResult, ...]:
    groups: dict[tuple[str, Decimal | None, str | None, bool], list[TaxResult]] = {}
    for line in lines:
        for tax in line.taxes:
            key = (tax.code, tax.rate, tax.exemption_code, tax.collected)
            groups.setdefault(key, []).append(tax)
    subtotals = []
    for (code, rate, ex_code, collected), items in groups.items():
        subtotals.append(
            TaxResult(
                code=code,
                name=items[0].name,
                rate=rate,
                taxable=sum((t.taxable for t in items), _ZERO),
                amount=sum((t.amount for t in items), _ZERO),
                exemption_code=ex_code,
                exemption_reason=items[0].exemption_reason,
                collected=collected,
            )
        )
    # KDV subtotals last, like the per-line order (additional taxes first)
    subtotals.sort(key=lambda t: t.code == KDV_TAX_CODE)
    return tuple(subtotals)


def _group_withholding(lines: tuple[LineCalculation, ...]) -> tuple[WithholdingResult, ...]:
    groups: dict[tuple[str, Decimal], list[WithholdingResult]] = {}
    for line in lines:
        if line.withholding is not None:
            w = line.withholding
            groups.setdefault((w.code, w.rate), []).append(w)
    return tuple(
        WithholdingResult(
            code=code,
            name=items[0].name,
            rate=rate,
            taxable=sum((w.taxable for w in items), _ZERO),
            amount=sum((w.amount for w in items), _ZERO),
        )
        for (code, rate), items in groups.items()
    )


def calculate(invoice: Invoice) -> InvoiceCalculation:
    """Calculate all line and document amounts of *invoice*."""
    lines = tuple(
        calculate_line(line, index, invoice.type)
        for index, line in enumerate(invoice.lines, start=1)
    )
    line_extension_total = sum((ln.gross for ln in lines), _ZERO)
    allowance_total = sum((ln.allowance_total for ln in lines), _ZERO)
    charge_total = sum((ln.charge_total for ln in lines), _ZERO)
    tax_exclusive = sum((ln.line_extension for ln in lines), _ZERO)

    tax_subtotals = _group_taxes(lines)
    tax_total = sum((t.amount for t in tax_subtotals), _ZERO)
    collected = sum((t.amount for t in tax_subtotals if t.collected), _ZERO)
    withholding_subtotals = _group_withholding(lines)
    withholding_total = sum((w.amount for w in withholding_subtotals), _ZERO)

    tax_inclusive = tax_exclusive + collected
    payable = tax_inclusive - withholding_total

    return InvoiceCalculation(
        currency=invoice.currency,
        exchange_rate=invoice.exchange_rate,
        lines=lines,
        line_extension_total=line_extension_total,
        allowance_total=allowance_total,
        charge_total=charge_total,
        tax_exclusive=tax_exclusive,
        tax_subtotals=tax_subtotals,
        tax_total=tax_total,
        collected_tax_total=collected,
        withholding_subtotals=withholding_subtotals,
        withholding_total=withholding_total,
        tax_inclusive=tax_inclusive,
        payable=payable,
    )
