"""Validation against GİB's real XSD + schematron.

These tests need GİB's packages in the local cache. CI downloads them first
(``efatura schemas fetch``); if GİB's site is unreachable the tests are skipped.
Set ``EFATURA_REQUIRE_GIB=1`` to turn a missing package into a failure.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from lxml import etree

from efatura_ubl_tr import InvoiceLine, load_invoice
from efatura_ubl_tr.validation import SchemaPackage, find_package, validate_xml
from efatura_ubl_tr.xml_builder import NS

from .conftest import EXAMPLE_FILES, make_invoice

_PACKAGE = find_package()


@pytest.fixture(scope="module")
def package() -> SchemaPackage:
    if _PACKAGE is None:
        if os.environ.get("EFATURA_REQUIRE_GIB") == "1":
            pytest.fail("GİB schema package is required but not cached")
        pytest.skip("GİB schema package not cached (run `efatura schemas fetch`)")
    return _PACKAGE


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda p: Path(p).stem)
def test_examples_pass_gib_xsd_and_schematron(package: SchemaPackage, path: Path) -> None:
    result = validate_xml(load_invoice(path).to_xml(), package=package)
    assert result.schematron_checked
    assert result.valid, result.summary()


def test_unsigned_document_needs_allow_unsigned(package: SchemaPackage) -> None:
    xml = make_invoice().to_xml()
    strict = validate_xml(xml, package=package, allow_unsigned=False, schematron=False)
    assert not strict.valid
    assert "ExtensionContent" in strict.xsd_errors[0].message
    relaxed = validate_xml(xml, package=package, schematron=False)
    assert relaxed.valid
    assert any("unsigned" in note for note in relaxed.notes)


def test_xsd_catches_wrong_element_order(package: SchemaPackage) -> None:
    root = etree.fromstring(make_invoice().to_xml())
    profile = root.find("cbc:ProfileID", NS)
    customization = root.find("cbc:CustomizationID", NS)
    assert profile is not None and customization is not None
    customization.addprevious(profile)  # ProfileID before CustomizationID is invalid
    result = validate_xml(etree.tostring(root), package=package, schematron=False)
    assert not result.valid
    assert result.xsd_errors


def test_schematron_catches_business_rule(package: SchemaPackage) -> None:
    root = etree.fromstring(make_invoice().to_xml())
    number = root.find("cbc:ID", NS)
    assert number is not None
    number.text = "INVALID-NUMBER"
    qty = root.find("cac:InvoiceLine/cbc:InvoicedQuantity", NS)
    assert qty is not None
    del qty.attrib["unitCode"]
    result = validate_xml(etree.tostring(root), package=package)
    messages = " | ".join(i.message for i in result.schematron_errors)
    assert "ABC2009123456789" in messages  # GİB's invoice number rule
    assert "unitCode" in messages


def test_schematron_catches_bad_withholding_percent(package: SchemaPackage) -> None:
    path = next(p for p in EXAMPLE_FILES if "tevkifat" in p.name)
    root = etree.fromstring(load_invoice(path).to_xml())
    for percent in root.iterfind(".//cac:WithholdingTaxTotal/cac:TaxSubtotal/cbc:Percent", NS):
        percent.text = "45"
    result = validate_xml(etree.tostring(root), package=package)
    assert any("yüzdesi" in i.message for i in result.schematron_errors)


def test_malformed_xml(package: SchemaPackage) -> None:
    result = validate_xml(b"<Invoice><unclosed></Invoice>", package=package)
    assert not result.valid
    assert result.issues[0].layer == "xml"


def test_validate_from_file(package: SchemaPackage, tmp_path: Path) -> None:
    target = tmp_path / "fatura.xml"
    target.write_bytes(make_invoice([InvoiceLine(name="Ürün", quantity=2, unit_price=50)]).to_xml())
    assert validate_xml(target, package=package).valid
    assert validate_xml(str(target), package=package).valid


GIB_RECENT_SAMPLES = ["TicariFaturaOrnegi.xml", "YTB_Satıs_Efatura.xml", "YTB_Satıs_EArşiv.xml"]


@pytest.mark.parametrize("name", GIB_RECENT_SAMPLES)
def test_gib_own_samples_pass_schematron_runner(package: SchemaPackage, name: str) -> None:
    """Sanity check of the schematron interpreter against GİB's own sample invoices."""
    samples = package.samples_dir
    if samples is None or not (samples / name).is_file():
        pytest.skip(f"{name} not present in the cached package")
    result = validate_xml(samples / name, package=package)
    assert result.valid, result.summary()
