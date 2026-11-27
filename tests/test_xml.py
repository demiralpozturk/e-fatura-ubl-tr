from __future__ import annotations

from datetime import time
from decimal import Decimal
from pathlib import Path

import pytest
from lxml import etree

from efatura_ubl_tr import InvoiceLine, InvoiceType, Profile, build_xml, load_invoice
from efatura_ubl_tr.models import DocumentReference, Withholding
from efatura_ubl_tr.xml_builder import NS

from .conftest import EXAMPLE_FILES, make_invoice

# Element order of Invoice children as defined by GİB's UBL-Invoice-2.1.xsd
INVOICE_ORDER = [
    "UBLExtensions", "UBLVersionID", "CustomizationID", "ProfileID", "ID", "CopyIndicator",
    "UUID", "IssueDate", "IssueTime", "InvoiceTypeCode", "Note", "DocumentCurrencyCode",
    "TaxCurrencyCode", "PricingCurrencyCode", "PaymentCurrencyCode",
    "PaymentAlternativeCurrencyCode", "AccountingCost", "LineCountNumeric", "InvoicePeriod",
    "OrderReference", "BillingReference", "DespatchDocumentReference",
    "ReceiptDocumentReference", "OriginatorDocumentReference", "ContractDocumentReference",
    "AdditionalDocumentReference", "Signature", "AccountingSupplierParty",
    "AccountingCustomerParty", "BuyerCustomerParty", "SellerSupplierParty",
    "TaxRepresentativeParty", "Delivery", "PaymentMeans", "PaymentTerms", "AllowanceCharge",
    "TaxExchangeRate", "PricingExchangeRate", "PaymentExchangeRate",
    "PaymentAlternativeExchangeRate", "TaxTotal", "WithholdingTaxTotal", "LegalMonetaryTotal",
    "InvoiceLine",
]  # fmt: skip
LINE_ORDER = [
    "ID", "Note", "InvoicedQuantity", "LineExtensionAmount", "OrderLineReference",
    "DespatchLineReference", "ReceiptLineReference", "Delivery", "AllowanceCharge", "TaxTotal",
    "WithholdingTaxTotal", "Item", "Price", "SubInvoiceLine",
]  # fmt: skip
PARTY_ORDER = [
    "WebsiteURI", "EndpointID", "IndustryClassificationCode", "PartyIdentification",
    "PartyName", "PostalAddress", "PhysicalLocation", "PartyTaxScheme", "PartyLegalEntity",
    "Contact", "Person", "AgentParty",
]  # fmt: skip
ADDRESS_ORDER = [
    "ID", "Postbox", "Room", "StreetName", "BlockName", "BuildingName", "BuildingNumber",
    "CitySubdivisionName", "CityName", "PostalZone", "Region", "District", "Country",
]  # fmt: skip


def _children(el: etree._Element) -> list[str]:
    return [etree.QName(child).localname for child in el]


def _assert_ordered(names: list[str], order: list[str]) -> None:
    positions = [order.index(n) for n in names]
    assert positions == sorted(positions), names


def _parse(xml: bytes) -> etree._Element:
    return etree.fromstring(xml)


def _text(root: etree._Element, path: str) -> str:
    result = root.findtext(path, namespaces=NS)
    assert result is not None, path
    return result


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda p: Path(p).stem)
def test_examples_element_order(path: Path) -> None:
    root = _parse(load_invoice(path).to_xml())
    assert etree.QName(root).namespace == NS["inv"]
    _assert_ordered(_children(root), INVOICE_ORDER)
    for line in root.iterfind("cac:InvoiceLine", NS):
        _assert_ordered(_children(line), LINE_ORDER)
    for party in root.iterfind(".//cac:Party", NS):
        _assert_ordered(_children(party), PARTY_ORDER)
    for addr in root.iterfind(".//cac:PostalAddress", NS):
        _assert_ordered(_children(addr), ADDRESS_ORDER)


def test_header_values() -> None:
    inv = make_invoice(issue_time=time(9, 5, 7, 123), notes=["Teşekkürler"])
    root = _parse(inv.to_xml())
    assert _text(root, "cbc:UBLVersionID") == "2.1"
    assert _text(root, "cbc:CustomizationID") == "TR1.2"
    assert _text(root, "cbc:ProfileID") == "TEMELFATURA"
    assert _text(root, "cbc:ID") == "ABC2026000000001"
    assert _text(root, "cbc:CopyIndicator") == "false"
    assert _text(root, "cbc:IssueDate") == "2026-11-20"
    assert _text(root, "cbc:IssueTime") == "09:05:07"
    assert _text(root, "cbc:InvoiceTypeCode") == "SATIS"
    assert _text(root, "cbc:LineCountNumeric") == "1"
    notes = [n.text for n in root.iterfind("cbc:Note", NS)]
    assert notes == ["Teşekkürler", "Yalnız: Yüz Yirmi Türk Lirası"]
    # unsigned placeholder for the XAdES signature
    content = root.find("ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent", NS)
    assert content is not None and len(content) == 0


def test_amount_in_words_note_can_be_disabled() -> None:
    root = _parse(make_invoice(amount_in_words_note=False).to_xml())
    assert root.find("cbc:Note", NS) is None


def test_signature_and_parties() -> None:
    root = _parse(make_invoice().to_xml())
    sig = root.find("cac:Signature", NS)
    assert sig is not None
    sig_id = sig.find("cbc:ID", NS)
    assert sig_id is not None and sig_id.get("schemeID") == "VKN_TCKN"
    assert sig_id.text == "1234567890"
    assert _text(sig, "cac:DigitalSignatureAttachment/cac:ExternalReference/cbc:URI") == (
        "#Signature_ABC2026000000001"
    )
    sup = root.find("cac:AccountingSupplierParty/cac:Party", NS)
    assert sup is not None
    pid = sup.find("cac:PartyIdentification/cbc:ID", NS)
    assert pid is not None and pid.get("schemeID") == "VKN"
    assert _text(sup, "cac:PartyName/cbc:Name") == "Anadolu Örnek Yazılım A.Ş."
    assert _text(sup, "cac:PartyTaxScheme/cac:TaxScheme/cbc:Name") == "Kozyatağı"
    assert _text(sup, "cac:PostalAddress/cac:Country/cbc:IdentificationCode") == "TR"


def test_person_customer_has_person_element() -> None:
    path = next(p for p in EXAMPLE_FILES if "earsiv" in p.name)
    root = _parse(load_invoice(path).to_xml())
    cust = root.find("cac:AccountingCustomerParty/cac:Party", NS)
    assert cust is not None
    pid = cust.find("cac:PartyIdentification/cbc:ID", NS)
    assert pid is not None and pid.get("schemeID") == "TCKN"
    assert _text(cust, "cac:Person/cbc:FirstName") == "Elif"
    assert _text(root, "cbc:ProfileID") == "EARSIVFATURA"


def test_monetary_totals_and_currency_attributes() -> None:
    inv = make_invoice(
        [InvoiceLine(name="A", quantity=2, unit_price=Decimal("10.5"), kdv_rate=20)],
        currency="EUR",
        exchange_rate=Decimal("48.25"),
    )
    root = _parse(inv.to_xml())
    total = root.find("cac:LegalMonetaryTotal", NS)
    assert total is not None
    values = {etree.QName(e).localname: e.text for e in total}
    assert values == {
        "LineExtensionAmount": "21.00",
        "TaxExclusiveAmount": "21.00",
        "TaxInclusiveAmount": "25.20",
        "AllowanceTotalAmount": "0.00",
        "PayableAmount": "25.20",
    }
    currencies = {el.get("currencyID") for el in root.iter() if el.get("currencyID")}
    assert currencies == {"EUR"}
    rate = root.find("cac:PricingExchangeRate", NS)
    assert rate is not None
    assert _children(rate) == [
        "SourceCurrencyCode",
        "TargetCurrencyCode",
        "CalculationRate",
        "Date",
    ]
    assert _text(rate, "cbc:CalculationRate") == "48.25"
    assert _text(root, "cbc:Note").endswith("Yirmi Beş Euro Yirmi Sent")


def test_tevkifat_xml() -> None:
    line = InvoiceLine(
        name="Temizlik",
        quantity=1,
        unit_price=1000,
        kdv_rate=20,
        withholding=Withholding(code="612"),
    )
    inv = make_invoice([line], type=InvoiceType.TEVKIFAT, profile=Profile.TICARIFATURA)
    root = _parse(inv.to_xml())
    # invoice-level TaxTotal holds KDV minus withholding, subtotal holds full KDV
    assert _text(root, "cac:TaxTotal/cbc:TaxAmount") == "20.00"
    assert _text(root, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount") == "200.00"
    wht = root.find("cac:WithholdingTaxTotal", NS)
    assert wht is not None
    assert _text(wht, "cbc:TaxAmount") == "180.00"
    assert _text(wht, "cac:TaxSubtotal/cbc:TaxableAmount") == "200.00"
    assert _text(wht, "cac:TaxSubtotal/cbc:Percent") == "90"
    assert _text(wht, "cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode") == "612"
    assert _text(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount") == "1200.00"
    assert _text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount") == "1020.00"
    line_el = root.find("cac:InvoiceLine", NS)
    assert line_el is not None
    assert line_el.find("cac:WithholdingTaxTotal", NS) is not None


def test_iade_billing_reference() -> None:
    path = next(p for p in EXAMPLE_FILES if "iade" in p.name)
    root = _parse(load_invoice(path).to_xml())
    ref = root.find("cac:BillingReference/cac:InvoiceDocumentReference", NS)
    assert ref is not None
    assert _text(ref, "cbc:ID") == "AOY2026000000001"
    assert _text(ref, "cbc:DocumentTypeCode") == "IADE"


def test_line_details() -> None:
    path = next(p for p in EXAMPLE_FILES if p.name.startswith("01-"))
    root = _parse(load_invoice(path).to_xml())
    line = root.find("cac:InvoiceLine", NS)
    assert line is not None
    qty = line.find("cbc:InvoicedQuantity", NS)
    assert qty is not None and qty.get("unitCode") == "C62" and qty.text == "3"
    assert _text(line, "cbc:LineExtensionAmount") == "12150.00"
    ac = line.find("cac:AllowanceCharge", NS)
    assert ac is not None
    assert _children(ac) == [
        "ChargeIndicator",
        "AllowanceChargeReason",
        "MultiplierFactorNumeric",
        "Amount",
        "BaseAmount",
    ]
    assert _text(ac, "cbc:MultiplierFactorNumeric") == "0.1"
    assert _text(line, "cac:Price/cbc:PriceAmount") == "4500"
    assert _text(line, "cac:Item/cac:SellersItemIdentification/cbc:ID") == "LIS-001"


def test_additional_document_with_attachment() -> None:
    doc = DocumentReference(
        id="XSLT-1",
        issue_date="2026-11-20",
        document_type="XSLT",
        attachment_base64="PGh0bWwvPg==",
        attachment_filename="sablon.xslt",
        attachment_mime_code="application/xml",
    )
    root = _parse(make_invoice(additional_documents=[doc]).to_xml())
    obj = root.find(
        "cac:AdditionalDocumentReference/cac:Attachment/cbc:EmbeddedDocumentBinaryObject", NS
    )
    assert obj is not None
    assert obj.get("filename") == "sablon.xslt"
    assert obj.get("encodingCode") == "Base64"


def test_build_xml_function_and_compact_output() -> None:
    inv = make_invoice()
    compact = build_xml(inv, pretty=False)
    assert compact.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")
    assert b"\n  <" not in compact
    parser = etree.XMLParser(remove_blank_text=True)
    pretty = etree.fromstring(inv.to_xml(pretty=True), parser)
    assert etree.tostring(etree.fromstring(compact, parser)) == etree.tostring(pretty)
