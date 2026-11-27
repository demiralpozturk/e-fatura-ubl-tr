from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from efatura_ubl_tr import Address, Invoice, InvoiceLine, Party

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("*.json"))


def make_supplier(**overrides: Any) -> Party:
    data: dict[str, Any] = {
        "vkn": "1234567890",
        "name": "Anadolu Örnek Yazılım A.Ş.",
        "tax_office": "Kozyatağı",
        "address": Address(city_subdivision="Kadıköy", city="İstanbul", street="Örnek Cd."),
    }
    data.update(overrides)
    return Party(**data)


def make_customer(**overrides: Any) -> Party:
    data: dict[str, Any] = {
        "vkn": "9876543217",
        "name": "Boğaziçi Deneme Ticaret Ltd. Şti.",
        "tax_office": "Beşiktaş",
        "address": Address(city_subdivision="Beşiktaş", city="İstanbul"),
    }
    data.update(overrides)
    return Party(**data)


def make_invoice(lines: list[InvoiceLine] | None = None, **overrides: Any) -> Invoice:
    data: dict[str, Any] = {
        "number": "ABC2026000000001",
        "uuid": "4E8F2C1A-7B3D-4F6E-9A21-5C0D8E7F6A10",
        "issue_date": date(2026, 11, 20),
        "supplier": make_supplier(),
        "customer": make_customer(),
        "lines": lines or [InvoiceLine(name="Ürün", quantity=1, unit_price=100)],
    }
    data.update(overrides)
    return Invoice(**data)


@pytest.fixture
def invoice_factory() -> Any:
    return make_invoice
