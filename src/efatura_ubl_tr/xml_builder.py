"""UBL-TR 1.2 XML generation.

Element order follows GİB's UBL-TR 1.2.1 schemas (``UBL-Invoice-2.1.xsd`` and the
common aggregate components). The output is **unsigned**: ``ext:UBLExtensions``
contains an empty ``ext:ExtensionContent`` where your signing tool / özel
entegratör places the XAdES signature (mali mühür / e-imza).
"""

from __future__ import annotations

from decimal import Decimal

from lxml import etree

from .calc import InvoiceCalculation, LineCalculation, TaxResult, WithholdingResult, calculate
from .models import Address, Invoice, InvoiceLine, Party
from .words import yalniz_note

__all__ = ["NS", "UBL_CUSTOMIZATION_ID", "UBL_VERSION_ID", "build_tree", "build_xml"]

UBL_VERSION_ID = "2.1"
UBL_CUSTOMIZATION_ID = "TR1.2"

NS = {
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}
_NSMAP = {
    None: NS["inv"],
    "cac": NS["cac"],
    "cbc": NS["cbc"],
    "ext": NS["ext"],
    "xsi": NS["xsi"],
}
_SCHEMA_LOCATION = f"{NS['inv']} UBL-Invoice-2.1.xsd"


def _plain(value: Decimal) -> str:
    """Format a Decimal without exponent and without trailing zeros (``20``, ``0.5``)."""
    text = format(value.normalize(), "f")
    return "0" if text in ("-0", "") else text


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


class _Writer:
    def __init__(self, currency: str) -> None:
        self.currency = currency

    @staticmethod
    def cac(parent: etree._Element, name: str) -> etree._Element:
        return etree.SubElement(parent, f"{{{NS['cac']}}}{name}")

    @staticmethod
    def cbc(
        parent: etree._Element, name: str, text: str | None, **attrs: str
    ) -> etree._Element | None:
        if text is None:
            return None
        el = etree.SubElement(parent, f"{{{NS['cbc']}}}{name}", attrs)
        el.text = text
        return el

    def amount(self, parent: etree._Element, name: str, value: Decimal) -> None:
        self.cbc(parent, name, _money(value), currencyID=self.currency)

    # -- parties --------------------------------------------------------------------

    def address(self, parent: etree._Element, addr: Address, tag: str = "PostalAddress") -> None:
        el = self.cac(parent, tag)
        self.cbc(el, "Room", addr.room)
        self.cbc(el, "StreetName", addr.street)
        self.cbc(el, "BuildingName", addr.building_name)
        self.cbc(el, "BuildingNumber", addr.building_number)
        self.cbc(el, "CitySubdivisionName", addr.city_subdivision)
        self.cbc(el, "CityName", addr.city)
        self.cbc(el, "PostalZone", addr.postal_code)
        self.cbc(el, "District", addr.district)
        country = self.cac(el, "Country")
        self.cbc(country, "IdentificationCode", addr.country_code)
        self.cbc(country, "Name", addr.country)

    def party(self, parent: etree._Element, party: Party) -> None:
        el = self.cac(parent, "Party")
        self.cbc(el, "WebsiteURI", party.website)
        pid = self.cac(el, "PartyIdentification")
        self.cbc(pid, "ID", party.tax_id, schemeID=party.tax_id_scheme)
        for scheme, value in party.identifiers.items():
            extra = self.cac(el, "PartyIdentification")
            self.cbc(extra, "ID", value, schemeID=scheme)
        if party.name:
            self.cbc(self.cac(el, "PartyName"), "Name", party.name)
        self.address(el, party.address)
        if party.tax_office:
            scheme = self.cac(self.cac(el, "PartyTaxScheme"), "TaxScheme")
            self.cbc(scheme, "Name", party.tax_office)
        if party.phone or party.fax or party.email:
            contact = self.cac(el, "Contact")
            self.cbc(contact, "Telephone", party.phone)
            self.cbc(contact, "Telefax", party.fax)
            self.cbc(contact, "ElectronicMail", party.email)
        if party.tckn:
            person = self.cac(el, "Person")
            self.cbc(person, "FirstName", party.first_name)
            self.cbc(person, "FamilyName", party.family_name)

    def signature(self, parent: etree._Element, inv: Invoice) -> None:
        sig = self.cac(parent, "Signature")
        self.cbc(sig, "ID", inv.supplier.tax_id, schemeID="VKN_TCKN")
        signatory = self.cac(sig, "SignatoryParty")
        pid = self.cac(signatory, "PartyIdentification")
        self.cbc(pid, "ID", inv.supplier.tax_id, schemeID=inv.supplier.tax_id_scheme)
        self.address(signatory, inv.supplier.address)
        ref = self.cac(self.cac(sig, "DigitalSignatureAttachment"), "ExternalReference")
        self.cbc(ref, "URI", f"#Signature_{inv.number}")

    # -- taxes ----------------------------------------------------------------------

    def tax_subtotal(self, parent: etree._Element, tax: TaxResult) -> None:
        sub = self.cac(parent, "TaxSubtotal")
        self.amount(sub, "TaxableAmount", tax.taxable)
        self.amount(sub, "TaxAmount", tax.amount)
        if tax.rate is not None:
            self.cbc(sub, "Percent", _plain(tax.rate))
        category = self.cac(sub, "TaxCategory")
        self.cbc(category, "TaxExemptionReasonCode", tax.exemption_code)
        self.cbc(category, "TaxExemptionReason", tax.exemption_reason)
        scheme = self.cac(category, "TaxScheme")
        self.cbc(scheme, "Name", tax.name)
        self.cbc(scheme, "TaxTypeCode", tax.code)

    def tax_total(
        self, parent: etree._Element, total: Decimal, subtotals: tuple[TaxResult, ...]
    ) -> None:
        el = self.cac(parent, "TaxTotal")
        self.amount(el, "TaxAmount", total)
        for tax in subtotals:
            self.tax_subtotal(el, tax)

    def withholding_total(
        self, parent: etree._Element, total: Decimal, subtotals: tuple[WithholdingResult, ...]
    ) -> None:
        el = self.cac(parent, "WithholdingTaxTotal")
        self.amount(el, "TaxAmount", total)
        for w in subtotals:
            sub = self.cac(el, "TaxSubtotal")
            self.amount(sub, "TaxableAmount", w.taxable)
            self.amount(sub, "TaxAmount", w.amount)
            self.cbc(sub, "Percent", _plain(w.rate))
            scheme = self.cac(self.cac(sub, "TaxCategory"), "TaxScheme")
            self.cbc(scheme, "Name", w.name)
            self.cbc(scheme, "TaxTypeCode", w.code)

    # -- lines ----------------------------------------------------------------------

    def line(self, parent: etree._Element, line: InvoiceLine, calc: LineCalculation) -> None:
        el = self.cac(parent, "InvoiceLine")
        self.cbc(el, "ID", str(calc.index))
        self.cbc(el, "Note", line.note)
        self.cbc(el, "InvoicedQuantity", _plain(line.quantity), unitCode=line.unit_code)
        self.amount(el, "LineExtensionAmount", calc.line_extension)
        for ac in calc.allowances:
            ac_el = self.cac(el, "AllowanceCharge")
            self.cbc(ac_el, "ChargeIndicator", "true" if ac.is_charge else "false")
            self.cbc(ac_el, "AllowanceChargeReason", ac.reason)
            if ac.rate is not None:
                self.cbc(ac_el, "MultiplierFactorNumeric", _plain(ac.rate / Decimal(100)))
            self.amount(ac_el, "Amount", ac.amount)
            self.amount(ac_el, "BaseAmount", ac.base)
        self.tax_total(el, calc.tax_total - calc.withholding_amount, calc.taxes)
        if calc.withholding is not None:
            self.withholding_total(el, calc.withholding.amount, (calc.withholding,))
        item = self.cac(el, "Item")
        self.cbc(item, "Description", line.description)
        self.cbc(item, "Name", line.name)
        self.cbc(item, "BrandName", line.brand)
        self.cbc(item, "ModelName", line.model)
        if line.buyer_item_id:
            self.cbc(self.cac(item, "BuyersItemIdentification"), "ID", line.buyer_item_id)
        if line.seller_item_id:
            self.cbc(self.cac(item, "SellersItemIdentification"), "ID", line.seller_item_id)
        price = self.cac(el, "Price")
        self.cbc(price, "PriceAmount", _plain(line.unit_price), currencyID=self.currency)


def build_tree(invoice: Invoice, calc: InvoiceCalculation | None = None) -> etree._ElementTree:
    """Build the UBL-TR ``Invoice`` element tree for *invoice*."""
    calc = calc or calculate(invoice)
    w = _Writer(invoice.currency)
    root = etree.Element(f"{{{NS['inv']}}}Invoice", nsmap=_NSMAP)
    root.set(f"{{{NS['xsi']}}}schemaLocation", _SCHEMA_LOCATION)

    # Placeholder for the XAdES signature added later by the signer / integrator.
    ext = etree.SubElement(root, f"{{{NS['ext']}}}UBLExtensions")
    ext_one = etree.SubElement(ext, f"{{{NS['ext']}}}UBLExtension")
    etree.SubElement(ext_one, f"{{{NS['ext']}}}ExtensionContent")

    w.cbc(root, "UBLVersionID", UBL_VERSION_ID)
    w.cbc(root, "CustomizationID", UBL_CUSTOMIZATION_ID)
    w.cbc(root, "ProfileID", invoice.profile.value)
    w.cbc(root, "ID", invoice.number)
    w.cbc(root, "CopyIndicator", "false")
    w.cbc(root, "UUID", invoice.uuid)
    w.cbc(root, "IssueDate", invoice.issue_date.isoformat())
    if invoice.issue_time is not None:
        w.cbc(root, "IssueTime", invoice.issue_time.replace(microsecond=0).isoformat())
    w.cbc(root, "InvoiceTypeCode", invoice.type.value)

    notes = list(invoice.notes)
    if invoice.amount_in_words_note:
        notes.append(yalniz_note(calc.payable, invoice.currency))
    for note in notes:
        w.cbc(root, "Note", note)

    w.cbc(root, "DocumentCurrencyCode", invoice.currency)
    w.cbc(root, "LineCountNumeric", str(len(invoice.lines)))

    if invoice.order_reference is not None:
        order = w.cac(root, "OrderReference")
        w.cbc(order, "ID", invoice.order_reference.id)
        w.cbc(order, "IssueDate", invoice.order_reference.issue_date.isoformat())
    for ret in invoice.return_references:
        ref = w.cac(w.cac(root, "BillingReference"), "InvoiceDocumentReference")
        w.cbc(ref, "ID", ret.invoice_number)
        w.cbc(ref, "IssueDate", ret.issue_date.isoformat())
        w.cbc(ref, "DocumentTypeCode", "IADE")
    for desp in invoice.despatch_references:
        ref = w.cac(root, "DespatchDocumentReference")
        w.cbc(ref, "ID", desp.id)
        w.cbc(ref, "IssueDate", desp.issue_date.isoformat())
    for doc in invoice.additional_documents:
        ref = w.cac(root, "AdditionalDocumentReference")
        w.cbc(ref, "ID", doc.id)
        w.cbc(ref, "IssueDate", doc.issue_date.isoformat())
        w.cbc(ref, "DocumentTypeCode", doc.document_type_code)
        w.cbc(ref, "DocumentType", doc.document_type)
        w.cbc(ref, "DocumentDescription", doc.description)
        if doc.attachment_base64:
            attrs = {"encodingCode": "Base64", "characterSetCode": "UTF-8"}
            if doc.attachment_mime_code:
                attrs["mimeCode"] = doc.attachment_mime_code
            if doc.attachment_filename:
                attrs["filename"] = doc.attachment_filename
            w.cbc(
                w.cac(ref, "Attachment"),
                "EmbeddedDocumentBinaryObject",
                doc.attachment_base64,
                **attrs,
            )

    w.signature(root, invoice)
    w.party(w.cac(root, "AccountingSupplierParty"), invoice.supplier)
    w.party(w.cac(root, "AccountingCustomerParty"), invoice.customer)

    for pm in invoice.payment_means:
        el = w.cac(root, "PaymentMeans")
        w.cbc(el, "PaymentMeansCode", pm.code)
        w.cbc(el, "PaymentDueDate", pm.due_date.isoformat() if pm.due_date else None)
        w.cbc(el, "InstructionNote", pm.note)
        if pm.iban:
            account = w.cac(el, "PayeeFinancialAccount")
            w.cbc(account, "ID", pm.iban)
            w.cbc(account, "CurrencyCode", pm.account_currency)
            if pm.bank_name:
                w.cbc(w.cac(account, "FinancialInstitutionBranch"), "Name", pm.bank_name)
    if invoice.payment_terms is not None:
        terms = w.cac(root, "PaymentTerms")
        pt = invoice.payment_terms
        w.cbc(terms, "Note", pt.note)
        w.cbc(
            terms, "PenaltySurchargePercent", _plain(pt.penalty_rate) if pt.penalty_rate else None
        )
        w.cbc(terms, "PaymentDueDate", pt.due_date.isoformat() if pt.due_date else None)

    if invoice.exchange_rate is not None:
        rate = w.cac(root, "PricingExchangeRate")
        w.cbc(rate, "SourceCurrencyCode", invoice.currency)
        w.cbc(rate, "TargetCurrencyCode", "TRY")
        w.cbc(rate, "CalculationRate", _plain(invoice.exchange_rate))
        rate_date = invoice.exchange_rate_date or invoice.issue_date
        w.cbc(rate, "Date", rate_date.isoformat())

    w.tax_total(root, calc.tax_total_after_withholding, calc.tax_subtotals)
    if calc.withholding_subtotals:
        w.withholding_total(root, calc.withholding_total, calc.withholding_subtotals)

    total = w.cac(root, "LegalMonetaryTotal")
    w.amount(total, "LineExtensionAmount", calc.line_extension_total)
    w.amount(total, "TaxExclusiveAmount", calc.tax_exclusive)
    w.amount(total, "TaxInclusiveAmount", calc.tax_inclusive)
    w.amount(total, "AllowanceTotalAmount", calc.allowance_total)
    if calc.charge_total:
        w.amount(total, "ChargeTotalAmount", calc.charge_total)
    w.amount(total, "PayableAmount", calc.payable)

    for line, line_calc in zip(invoice.lines, calc.lines, strict=True):
        w.line(root, line, line_calc)

    return etree.ElementTree(root)


def build_xml(invoice: Invoice, *, pretty: bool = True) -> bytes:
    """Return the UBL-TR XML of *invoice* as UTF-8 bytes (with XML declaration)."""
    tree = build_tree(invoice)
    data: bytes = etree.tostring(tree, xml_declaration=True, encoding="UTF-8", pretty_print=pretty)
    return data
