from __future__ import annotations

from pathlib import Path

import pytest

from efatura_ubl_tr import load_invoice
from efatura_ubl_tr.preview import _num, render_html, render_invoice_html

from .conftest import EXAMPLE_FILES, make_invoice


def test_turkish_number_format() -> None:
    from decimal import Decimal

    assert _num(Decimal("1234567.5")) == "1.234.567,50"
    assert _num(Decimal("0")) == "0,00"
    assert _num(Decimal("-1234.5")) == "-1.234,50"
    assert _num(Decimal("12.500"), None) == "12,5"
    assert _num(Decimal("20"), None) == "20"
    assert _num(None) == ""


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda p: Path(p).stem)
def test_every_example_renders(path: Path) -> None:
    invoice = load_invoice(path)
    page = render_invoice_html(invoice)
    assert page.startswith("<!doctype html>")
    assert invoice.number in page
    assert invoice.uuid in page
    assert "resmî fatura görüntüsü değildir" in page


def test_content_of_tevkifat_preview() -> None:
    path = next(p for p in EXAMPLE_FILES if "tevkifat" in p.name)
    page = render_html(load_invoice(path).to_xml())
    assert "e-FATURA" in page
    assert "Ege Temizlik Hizmetleri Örnek A.Ş." in page
    assert "Tevkif Edilen KDV (%90)" in page
    assert "8.100,00 TRY" in page
    assert "47.878,56 TRY" in page  # payable
    assert "Tevkifat</th>" in page  # optional column is shown


def test_optional_columns_hidden_when_empty() -> None:
    page = render_html(make_invoice().to_xml())
    assert "Tevkifat</th>" not in page
    assert "Diğer Vergiler</th>" not in page
    assert "İskonto</th>" not in page


def test_earsiv_title_and_person() -> None:
    path = next(p for p in EXAMPLE_FILES if "earsiv" in p.name)
    page = render_html(load_invoice(path).to_xml())
    assert "e-ARŞİV FATURA" in page
    assert "Elif Örnek" in page
    assert "TCKN:</span> 12345678950" in page


def test_foreign_currency_shows_try_equivalent() -> None:
    path = next(p for p in EXAMPLE_FILES if "doviz" in p.name)
    page = render_html(load_invoice(path).to_xml())
    assert "TRY karşılığı" in page
    assert "1 USD = 41,8523 TRY" in page
    assert "181.294,12 TRY" in page  # 4331.76 * 41.8523


def test_exemption_listed() -> None:
    path = next(p for p in EXAMPLE_FILES if "istisna" in p.name)
    page = render_html(load_invoice(path).to_xml())
    assert "Vergi İstisna / Muafiyet Sebebi" in page
    assert "<b>317</b>" in page


def test_html_is_escaped() -> None:
    from efatura_ubl_tr import InvoiceLine

    inv = make_invoice([InvoiceLine(name="<script>alert(1)</script>", quantity=1, unit_price=1)])
    page = render_html(inv.to_xml())
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page


def test_render_from_file_and_string(tmp_path: Path) -> None:
    xml = make_invoice().to_xml()
    target = tmp_path / "f.xml"
    target.write_bytes(xml)
    assert "ABC2026000000001" in render_html(target)
    assert "ABC2026000000001" in render_html(str(target))
    assert "ABC2026000000001" in render_html(xml.decode("utf-8").split("?>", 1)[1])
