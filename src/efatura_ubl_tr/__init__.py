"""e-fatura-ubl-tr: build and validate Turkish e-Fatura / e-Arşiv invoices (UBL-TR 1.2).

Unofficial. Not affiliated with or certified by Gelir İdaresi Başkanlığı (GİB).
Signing (mali mühür / e-imza) and sending through an özel entegratör or the GİB
portal are out of scope. Verify with your accountant / integrator before
production use.
"""

from .calc import InvoiceCalculation, calculate, round_money
from .codes import InvoiceType, Profile, SupportLevel
from .identifiers import (
    is_valid_invoice_number,
    is_valid_tckn,
    is_valid_vkn,
    make_invoice_number,
    new_uuid,
    next_invoice_number,
)
from .models import (
    Address,
    AllowanceCharge,
    DespatchReference,
    DocumentReference,
    Invoice,
    InvoiceLine,
    LineTax,
    OrderReference,
    OzelMatrah,
    Party,
    PaymentMeans,
    PaymentTerms,
    ReturnReference,
    TaxExemption,
    Withholding,
    load_invoice,
)
from .preview import render_html, render_invoice_html
from .validation import ValidationResult, validate_xml
from .words import amount_in_words, yalniz_note
from .xml_builder import build_xml

__version__ = "0.1.0"

__all__ = [
    "Address",
    "AllowanceCharge",
    "DespatchReference",
    "DocumentReference",
    "Invoice",
    "InvoiceCalculation",
    "InvoiceLine",
    "InvoiceType",
    "LineTax",
    "OrderReference",
    "OzelMatrah",
    "Party",
    "PaymentMeans",
    "PaymentTerms",
    "Profile",
    "ReturnReference",
    "SupportLevel",
    "TaxExemption",
    "ValidationResult",
    "Withholding",
    "__version__",
    "amount_in_words",
    "build_xml",
    "calculate",
    "is_valid_invoice_number",
    "is_valid_tckn",
    "is_valid_vkn",
    "load_invoice",
    "make_invoice_number",
    "new_uuid",
    "next_invoice_number",
    "render_html",
    "render_invoice_html",
    "round_money",
    "validate_xml",
    "yalniz_note",
]
