from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from efatura_ubl_tr import (
    Address,
    AllowanceCharge,
    Invoice,
    InvoiceLine,
    InvoiceType,
    LineTax,
    Party,
    Profile,
    load_invoice,
)
from efatura_ubl_tr.identifiers import NIHAI_TUKETICI_TCKN
from efatura_ubl_tr.models import (
    OzelMatrah,
    PaymentMeans,
    ReturnReference,
    TaxExemption,
    Withholding,
)

from .conftest import EXAMPLE_FILES, make_customer, make_invoice

ADDR = Address(city_subdivision="Çankaya", city="Ankara")


def test_examples_load() -> None:
    assert len(EXAMPLE_FILES) >= 9
    for path in EXAMPLE_FILES:
        inv = load_invoice(path)
        assert inv.lines


class TestParty:
    def test_company(self) -> None:
        party = Party(vkn="1234567890", name="Örnek A.Ş.", address=ADDR)
        assert (party.tax_id, party.tax_id_scheme, party.display_name) == (
            "1234567890",
            "VKN",
            "Örnek A.Ş.",
        )

    def test_person(self) -> None:
        party = Party(tckn="12345678950", first_name="Elif", family_name="Örnek", address=ADDR)
        assert party.tax_id_scheme == "TCKN"
        assert party.display_name == "Elif Örnek"

    def test_final_consumer_placeholder(self) -> None:
        Party(tckn=NIHAI_TUKETICI_TCKN, first_name="Nihai", family_name="Tüketici", address=ADDR)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"name": "X"},  # neither id
            {"vkn": "1234567890", "tckn": "12345678950", "name": "X"},  # both
            {"vkn": "1234567891", "name": "X"},  # bad checksum
            {"vkn": "1234567890"},  # missing name
            {"tckn": "12345678951", "first_name": "A", "family_name": "B"},  # bad checksum
            {"tckn": "12345678950", "first_name": "A"},  # missing family name
            {"vkn": "1234567890", "name": "X", "identifiers": {"FOO": "1"}},
        ],
    )
    def test_invalid(self, kwargs: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            Party(address=ADDR, **kwargs)

    def test_skip_checksum(self) -> None:
        Party(vkn="1234567891", name="Test", address=ADDR, skip_id_checksum=True)

    def test_country_code(self) -> None:
        with pytest.raises(ValidationError):
            Address(city_subdivision="a", city="b", country_code="TUR")


class TestLineParts:
    def test_allowance_requires_exactly_one(self) -> None:
        with pytest.raises(ValidationError):
            AllowanceCharge()
        with pytest.raises(ValidationError):
            AllowanceCharge(rate=1, amount=1)
        with pytest.raises(ValidationError):
            AllowanceCharge(rate=101)

    def test_line_tax(self) -> None:
        assert LineTax(code="0074", rate=20).name == "ÖTV 4.LİSTE"
        with pytest.raises(ValidationError, match="not supported"):
            LineTax(code="0015", rate=20)
        with pytest.raises(ValidationError, match="unknown tax code"):
            LineTax(code="9999", rate=1)

    def test_withholding_default_and_allowed_rates(self) -> None:
        assert Withholding(code="612").rate == Decimal(90)
        assert Withholding(code="612", rate=70).rate == Decimal(70)
        assert Withholding(code="825").rate == Decimal(100)
        with pytest.raises(ValidationError, match="not allowed"):
            Withholding(code="612", rate=50)
        with pytest.raises(ValidationError, match="unknown"):
            Withholding(code="699")

    def test_exemption_default_reason(self) -> None:
        assert TaxExemption(code="301").reason == "11/1-a Mal İhracatı"
        with pytest.raises(ValidationError):
            TaxExemption(code="999")

    def test_line_validation(self) -> None:
        with pytest.raises(ValidationError):
            InvoiceLine(name="X", quantity=0, unit_price=1)
        with pytest.raises(ValidationError):
            InvoiceLine(name="X", quantity=1, unit_price=-1)
        with pytest.raises(ValidationError):
            InvoiceLine(name="X", quantity=1, unit_price=1, kdv_rate=120)
        with pytest.raises(ValidationError):
            InvoiceLine(name="X", quantity=1, unit_price=1, unit_code="adet")

    def test_payment_means_iban_normalized(self) -> None:
        pm = PaymentMeans(code="42", iban="tr29 9999 9000 0000 0000 0012 3456")
        assert pm.iban == "TR29999990000000000000123456"
        with pytest.raises(ValidationError):
            PaymentMeans(iban="123")


class TestInvoiceRules:
    def test_number_format_and_year(self) -> None:
        with pytest.raises(ValidationError, match="GİB format"):
            make_invoice(number="ABC-1")
        with pytest.raises(ValidationError, match="differs from issue_date"):
            make_invoice(number="ABC2025000000001")

    def test_currency_and_rate(self) -> None:
        with pytest.raises(ValidationError, match="exchange_rate is required"):
            make_invoice(currency="USD")
        with pytest.raises(ValidationError, match="must not be set"):
            make_invoice(exchange_rate=Decimal("1.5"))
        with pytest.raises(ValidationError, match="6 decimal"):
            make_invoice(currency="EUR", exchange_rate=Decimal("45.1234567"))
        with pytest.raises(ValidationError):
            make_invoice(currency="usd", exchange_rate=1)

    def test_uuid_validation(self) -> None:
        assert make_invoice(uuid="4e8f2c1a-7b3d-4f6e-9a21-5c0d8e7f6a10").uuid.isupper()
        with pytest.raises(ValidationError):
            make_invoice(uuid="nope")

    def test_iade_rules(self) -> None:
        ref = ReturnReference(invoice_number="ABC2026000000001", issue_date="2026-11-01")
        make_invoice(type=InvoiceType.IADE, return_references=[ref])
        with pytest.raises(ValidationError, match="TEMELFATURA or EARSIVFATURA"):
            make_invoice(
                type=InvoiceType.IADE, profile=Profile.TICARIFATURA, return_references=[ref]
            )
        with pytest.raises(ValidationError, match="return_references"):
            make_invoice(type=InvoiceType.IADE)
        with pytest.raises(ValidationError, match="only used with the IADE"):
            make_invoice(return_references=[ref])
        with pytest.raises(ValidationError):
            ReturnReference(invoice_number="SHORT", issue_date="2026-11-01")

    def test_tevkifat_rules(self) -> None:
        with pytest.raises(ValidationError, match="TEVKIFAT invoices need"):
            make_invoice(type=InvoiceType.TEVKIFAT)
        wline = InvoiceLine(name="T", quantity=1, unit_price=1, withholding=Withholding(code="612"))
        with pytest.raises(ValidationError, match="only allowed on TEVKIFAT"):
            make_invoice([wline])
        zero = InvoiceLine(
            name="T",
            quantity=1,
            unit_price=1,
            kdv_rate=0,
            withholding=Withholding(code="612"),
            exemption=TaxExemption(code="351"),
        )
        with pytest.raises(ValidationError, match="KDV rate above 0"):
            make_invoice([zero], type=InvoiceType.TEVKIFAT)

    def test_zero_kdv_requires_exemption(self) -> None:
        line = InvoiceLine(name="X", quantity=1, unit_price=1, kdv_rate=0)
        with pytest.raises(ValidationError, match="needs an 'exemption'"):
            make_invoice([line])
        ok = InvoiceLine(
            name="X", quantity=1, unit_price=1, kdv_rate=0, exemption=TaxExemption(code="351")
        )
        make_invoice([ok])

    def test_istisna_rules(self) -> None:
        istisna = InvoiceLine(
            name="X", quantity=1, unit_price=1, kdv_rate=0, exemption=TaxExemption(code="301")
        )
        with pytest.raises(ValidationError, match="requires the ISTISNA"):
            make_invoice([istisna])
        make_invoice([istisna], type=InvoiceType.ISTISNA)
        other = InvoiceLine(
            name="X", quantity=1, unit_price=1, kdv_rate=0, exemption=TaxExemption(code="351")
        )
        with pytest.raises(ValidationError, match="need an istisna code"):
            make_invoice([other], type=InvoiceType.ISTISNA)
        with pytest.raises(ValidationError, match="ISTISNA invoices need"):
            make_invoice(type=InvoiceType.ISTISNA)
        positive = InvoiceLine(
            name="X", quantity=1, unit_price=1, exemption=TaxExemption(code="301")
        )
        with pytest.raises(ValidationError, match="requires kdv_rate 0"):
            make_invoice([positive], type=InvoiceType.ISTISNA)

    def test_ihrackayitli_rules(self) -> None:
        def line(code: str | None, rate: int = 20) -> InvoiceLine:
            ex = TaxExemption(code=code) if code else None
            return InvoiceLine(name="X", quantity=1, unit_price=1, kdv_rate=rate, exemption=ex)

        make_invoice([line("701")], type=InvoiceType.IHRACKAYITLI)
        with pytest.raises(ValidationError, match="701/703/704"):
            make_invoice([line(None)], type=InvoiceType.IHRACKAYITLI)
        with pytest.raises(ValidationError, match="not supported in v0.1"):
            make_invoice([line("702")], type=InvoiceType.IHRACKAYITLI)
        with pytest.raises(ValidationError, match="normal KDV rate"):
            make_invoice([line("701", 0)], type=InvoiceType.IHRACKAYITLI)
        with pytest.raises(ValidationError, match="requires the IHRACKAYITLI"):
            make_invoice([line("701")])

    def test_ozelmatrah_rules(self) -> None:
        om = InvoiceLine(
            name="X", quantity=1, unit_price=100, ozel_matrah=OzelMatrah(code="806", base=50)
        )
        make_invoice([om], type=InvoiceType.OZELMATRAH)
        with pytest.raises(ValidationError, match="only allowed on OZELMATRAH"):
            make_invoice([om])
        with pytest.raises(ValidationError, match="OZELMATRAH invoices need"):
            make_invoice(type=InvoiceType.OZELMATRAH)
        with pytest.raises(ValidationError):
            OzelMatrah(code="701", base=1)

    def test_json_roundtrip(self) -> None:
        inv = make_invoice(
            customer=make_customer(email="a@b.example"),
            notes=["Not 1"],
        )
        again = Invoice.from_json(inv.model_dump_json())
        assert again == inv

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            InvoiceLine(name="X", quantity=1, unit_price=1, colour="red")  # type: ignore[call-arg]
