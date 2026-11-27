"""Typed invoice models (pydantic v2).

The models double as the JSON input format of the ``efatura build`` command:
every field name below is a JSON key. Amounts are :class:`decimal.Decimal`;
in JSON prefer strings (``"1250.50"``) over floats to avoid binary rounding.
"""

from __future__ import annotations

import re
from datetime import date, time
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .codes import (
    IHRACKAYITLI_EXEMPTION_CODES,
    ISTISNA_EXEMPTION_CODES,
    OTHER_ZERO_KDV_CODES,
    OZELMATRAH_CODES,
    TAX_TYPES,
    WITHHOLDING_CODES,
    InvoiceType,
    Profile,
    exemption_reason_name,
)
from .identifiers import (
    NIHAI_TUKETICI_TCKN,
    is_valid_invoice_number,
    is_valid_tckn,
    is_valid_uuid,
    is_valid_vkn,
    new_uuid,
)

if TYPE_CHECKING:
    from .calc import InvoiceCalculation

__all__ = [
    "Address",
    "AllowanceCharge",
    "DespatchReference",
    "DocumentReference",
    "Invoice",
    "InvoiceLine",
    "LineTax",
    "OrderReference",
    "OzelMatrah",
    "Party",
    "PaymentMeans",
    "PaymentTerms",
    "ReturnReference",
    "TaxExemption",
    "Withholding",
    "load_invoice",
]

#: Extra ``PartyIdentification/@schemeID`` values accepted by GİB (besides VKN/TCKN).
EXTRA_PARTY_ID_SCHEMES = frozenset(
    {
        "HIZMETNO",
        "MUSTERINO",
        "TESISATNO",
        "TELEFONNO",
        "DISTRIBUTORNO",
        "TICARETSICILNO",
        "TAPDKNO",
        "BAYINO",
        "ABONENO",
        "SAYACNO",
        "EPDKNO",
        "SUBENO",
        "PASAPORTNO",
        "URETICINO",
        "CIFTCINO",
        "IMALATCINO",
        "DOSYANO",
        "HASTANO",
        "MERSISNO",
    }
)

_HUNDRED = Decimal(100)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=False)


def _check_percent(value: Decimal | None, field: str) -> Decimal | None:
    if value is not None and not (Decimal(0) <= value <= _HUNDRED):
        raise ValueError(f"{field} must be between 0 and 100 (percent)")
    return value


class Address(_Model):
    """Postal address (``cac:PostalAddress``).

    ``city_subdivision`` (ilçe) and ``city`` (il) are mandatory in UBL-TR.
    """

    street: str | None = Field(None, description="Cadde / sokak (cbc:StreetName)")
    building_number: str | None = Field(None, description="Bina no (cbc:BuildingNumber)")
    building_name: str | None = Field(None, description="Bina adı (cbc:BuildingName)")
    room: str | None = Field(None, description="Daire / kapı no (cbc:Room)")
    district: str | None = Field(None, description="Mahalle / semt (cbc:District)")
    city_subdivision: str = Field(description="İlçe (cbc:CitySubdivisionName)", min_length=1)
    city: str = Field(description="İl (cbc:CityName)", min_length=1)
    postal_code: str | None = Field(None, description="Posta kodu (cbc:PostalZone)")
    country: str = Field("Türkiye", description="Ülke adı (cbc:Country/cbc:Name)")
    country_code: str | None = Field("TR", description="ISO 3166-1 alpha-2 ülke kodu")

    @field_validator("country_code")
    @classmethod
    def _country_code(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"[A-Z]{2}", v):
            raise ValueError("country_code must be an ISO 3166-1 alpha-2 code such as 'TR'")
        return v


class Party(_Model):
    """Supplier or customer (``cac:Party``).

    Give **either** ``vkn`` (companies, 10 digits) **or** ``tckn`` (persons, 11 digits).
    Companies need ``name`` (ünvan); persons need ``first_name`` and ``family_name``.
    """

    vkn: str | None = Field(None, description="Vergi Kimlik Numarası (10 hane)")
    tckn: str | None = Field(None, description="T.C. Kimlik Numarası (11 hane)")
    name: str | None = Field(None, description="Ünvan (cac:PartyName)")
    first_name: str | None = None
    family_name: str | None = None
    tax_office: str | None = Field(None, description="Vergi dairesi")
    address: Address
    email: str | None = None
    phone: str | None = None
    fax: str | None = None
    website: str | None = None
    identifiers: dict[str, str] = Field(
        default_factory=dict,
        description="Ek kimlikler, ör. {'MERSISNO': '...', 'TICARETSICILNO': '...'}",
    )
    skip_id_checksum: bool = Field(
        False, description="VKN/TCKN checksum kontrolünü atla (yalnızca test için)"
    )

    @model_validator(mode="after")
    def _check_identity(self) -> Party:
        if bool(self.vkn) == bool(self.tckn):
            raise ValueError("exactly one of 'vkn' or 'tckn' must be given")
        if self.vkn:
            if not self.skip_id_checksum and not is_valid_vkn(self.vkn):
                raise ValueError(f"invalid VKN {self.vkn!r} (10 digits, checksum failed)")
            if not self.name:
                raise ValueError("'name' (ünvan) is required when 'vkn' is given")
        if self.tckn:
            if (
                not self.skip_id_checksum
                and self.tckn != NIHAI_TUKETICI_TCKN
                and not is_valid_tckn(self.tckn)
            ):
                raise ValueError(f"invalid TCKN {self.tckn!r} (11 digits, checksum failed)")
            if not (self.first_name and self.family_name):
                raise ValueError("'first_name' and 'family_name' are required with 'tckn'")
        for scheme in self.identifiers:
            if scheme not in EXTRA_PARTY_ID_SCHEMES:
                raise ValueError(
                    f"unsupported identifier scheme {scheme!r}; "
                    f"allowed: {', '.join(sorted(EXTRA_PARTY_ID_SCHEMES))}"
                )
        return self

    @property
    def tax_id(self) -> str:
        return self.vkn or self.tckn or ""

    @property
    def tax_id_scheme(self) -> str:
        return "VKN" if self.vkn else "TCKN"

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        return f"{self.first_name or ''} {self.family_name or ''}".strip()


class AllowanceCharge(_Model):
    """Line discount (iskonto) or surcharge (artırım).

    Give either ``rate`` (percent, e.g. ``10`` for %10) or a fixed ``amount``.
    """

    is_charge: bool = Field(False, description="True: artırım, False: iskonto")
    rate: Decimal | None = Field(None, description="Yüzde oran, ör. 10 = %10")
    amount: Decimal | None = Field(None, description="Sabit tutar")
    reason: str | None = None

    @model_validator(mode="after")
    def _one_of(self) -> AllowanceCharge:
        if (self.rate is None) == (self.amount is None):
            raise ValueError("give exactly one of 'rate' or 'amount'")
        _check_percent(self.rate, "rate")
        if self.amount is not None and self.amount < 0:
            raise ValueError("amount must not be negative")
        return self


class LineTax(_Model):
    """An additional tax on a line besides KDV, e.g. ÖTV (``0074``) or ÖİV (``4080``).

    Percentage taxes use ``rate``; fixed (maktu) taxes use ``amount`` for the line.
    """

    code: str = Field(description="Vergi kodu, ör. 0074 (ÖTV 4. liste)")
    rate: Decimal | None = None
    amount: Decimal | None = None
    name: str | None = Field(None, description="Varsayılan: kod listesindeki kısa ad")
    include_in_kdv_base: bool = Field(True, description="KDV matrahına dahil mi (ÖTV için evet)")

    @model_validator(mode="after")
    def _validate(self) -> LineTax:
        info = TAX_TYPES.get(self.code)
        if info is None:
            raise ValueError(f"unknown tax code {self.code!r}")
        if not info.supported:
            raise ValueError(
                f"tax code {self.code} ({info.short_name}) is not supported as a line tax in "
                "v0.1 (KDV uses 'kdv_rate'; stopaj and tevkifat-type codes are out of scope)"
            )
        if (self.rate is None) == (self.amount is None):
            raise ValueError("give exactly one of 'rate' or 'amount'")
        _check_percent(self.rate, "rate")
        if self.amount is not None and self.amount < 0:
            raise ValueError("amount must not be negative")
        if not self.name:
            self.name = info.short_name
        return self


class Withholding(_Model):
    """KDV tevkifatı (withholding) on a line, e.g. ``{"code": "612"}`` for cleaning (9/10)."""

    code: str = Field(description="Tevkifat kodu, ör. 612")
    rate: Decimal | None = Field(None, description="Yüzde; boşsa koda ait varsayılan oran")

    @model_validator(mode="after")
    def _validate(self) -> Withholding:
        info = WITHHOLDING_CODES.get(self.code)
        if info is None:
            raise ValueError(f"unknown withholding (tevkifat) code {self.code!r}")
        if self.rate is None:
            self.rate = info.default_rate
        if self.rate not in info.allowed_rates:
            allowed = ", ".join(str(r) for r in info.allowed_rates)
            raise ValueError(f"rate {self.rate} is not allowed for code {self.code} ({allowed})")
        return self

    @property
    def name(self) -> str:
        return WITHHOLDING_CODES[self.code].name


class TaxExemption(_Model):
    """KDV exemption (istisna) on a line: ``TaxExemptionReasonCode`` + reason text."""

    code: str
    reason: str | None = Field(None, description="Varsayılan: GİB kod listesindeki ad")

    @model_validator(mode="after")
    def _validate(self) -> TaxExemption:
        known = exemption_reason_name(self.code)
        if known is None or self.code in OZELMATRAH_CODES:
            raise ValueError(f"unknown or unsupported exemption code {self.code!r}")
        if not self.reason:
            self.reason = known
        return self


class OzelMatrah(_Model):
    """Özel matrah (special tax base) for OZELMATRAH invoices (experimental)."""

    code: str = Field(description="801-812")
    base: Decimal = Field(description="KDV'nin hesaplanacağı özel matrah tutarı", ge=0)
    reason: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> OzelMatrah:
        if self.code not in OZELMATRAH_CODES:
            raise ValueError(f"unknown özel matrah code {self.code!r} (801-812)")
        if not self.reason:
            self.reason = OZELMATRAH_CODES[self.code]
        return self


class InvoiceLine(_Model):
    """One invoice line (``cac:InvoiceLine``)."""

    name: str = Field(min_length=1, description="Mal / hizmet adı")
    quantity: Decimal = Field(gt=0)
    unit_code: str = Field("C62", description="UN/ECE Rec 20 birim kodu (C62 = adet)")
    unit_price: Decimal = Field(ge=0, description="Birim fiyat (KDV hariç)")
    kdv_rate: Decimal = Field(Decimal(20), description="KDV oranı (yüzde)")
    allowances: list[AllowanceCharge] = Field(default_factory=list)
    taxes: list[LineTax] = Field(default_factory=list, description="KDV dışı vergiler (ÖTV vb.)")
    withholding: Withholding | None = None
    exemption: TaxExemption | None = None
    ozel_matrah: OzelMatrah | None = None
    description: str | None = None
    note: str | None = None
    seller_item_id: str | None = Field(None, description="Satıcı ürün kodu")
    buyer_item_id: str | None = Field(None, description="Alıcı ürün kodu")
    brand: str | None = None
    model: str | None = None

    @field_validator("kdv_rate")
    @classmethod
    def _kdv_rate(cls, v: Decimal) -> Decimal:
        result = _check_percent(v, "kdv_rate")
        assert result is not None
        return result

    @field_validator("unit_code")
    @classmethod
    def _unit_code(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Z0-9]{1,3}", v):
            raise ValueError("unit_code must be a UN/ECE Rec 20 code such as C62, KGM, LTR")
        return v


class DocumentReference(_Model):
    """Generic ``cac:AdditionalDocumentReference`` (optionally with an embedded file)."""

    id: str
    issue_date: date
    document_type_code: str | None = None
    document_type: str | None = None
    description: str | None = None
    attachment_base64: str | None = None
    attachment_filename: str | None = None
    attachment_mime_code: str | None = None


class OrderReference(_Model):
    """Sipariş bilgisi (``cac:OrderReference``)."""

    id: str
    issue_date: date


class DespatchReference(_Model):
    """İrsaliye bilgisi (``cac:DespatchDocumentReference``)."""

    id: str
    issue_date: date


class ReturnReference(_Model):
    """The original invoice being returned (IADE) – ``cac:BillingReference``."""

    invoice_number: str
    issue_date: date

    @field_validator("invoice_number")
    @classmethod
    def _number(cls, v: str) -> str:
        if len(v) != 16:
            raise ValueError("invoice_number of the returned invoice must be 16 characters")
        return v


class PaymentMeans(_Model):
    """Ödeme şekli (``cac:PaymentMeans``). ``code`` is a UN/EDIFACT 4461 code."""

    code: str = Field("1", description="1 belirtilmemiş, 10 nakit, 42 havale/EFT, 48 kart")
    due_date: date | None = None
    iban: str | None = None
    bank_name: str | None = None
    account_currency: str | None = None
    note: str | None = None

    @field_validator("iban")
    @classmethod
    def _iban(cls, v: str | None) -> str | None:
        if v is None:
            return v
        compact = v.replace(" ", "").upper()
        if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}", compact):
            raise ValueError("iban looks malformed")
        return compact


class PaymentTerms(_Model):
    """Ödeme koşulları (``cac:PaymentTerms``)."""

    note: str | None = None
    due_date: date | None = None
    penalty_rate: Decimal | None = Field(None, description="Gecikme cezası yüzdesi")


class Invoice(_Model):
    """A UBL-TR invoice (``Invoice``).

    Build the XML with :meth:`to_xml` and inspect the computed amounts with :meth:`calculate`.
    """

    number: str = Field(description="Fatura no, ör. ABC2026000000001")
    uuid: str = Field(default_factory=new_uuid, description="ETTN (UUID)")
    issue_date: date
    issue_time: time | None = None
    profile: Profile = Profile.TEMELFATURA
    type: InvoiceType = InvoiceType.SATIS
    currency: str = Field("TRY", description="ISO 4217 belge para birimi")
    exchange_rate: Decimal | None = Field(
        None, description="1 birim döviz = ? TRY (döviz faturalarında zorunlu)", gt=0
    )
    exchange_rate_date: date | None = None
    supplier: Party
    customer: Party
    lines: list[InvoiceLine] = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)
    amount_in_words_note: bool = Field(True, description="'Yalnız: ...' notunu ekle")
    order_reference: OrderReference | None = None
    despatch_references: list[DespatchReference] = Field(default_factory=list)
    return_references: list[ReturnReference] = Field(default_factory=list)
    additional_documents: list[DocumentReference] = Field(default_factory=list)
    payment_means: list[PaymentMeans] = Field(default_factory=list)
    payment_terms: PaymentTerms | None = None

    @field_validator("currency")
    @classmethod
    def _currency(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Z]{3}", v):
            raise ValueError("currency must be an ISO 4217 code such as TRY, USD, EUR")
        return v

    @field_validator("uuid")
    @classmethod
    def _uuid(cls, v: str) -> str:
        if not is_valid_uuid(v):
            raise ValueError("uuid (ETTN) must look like 8-4-4-4-12 hexadecimal characters")
        return v.upper()

    @field_validator("exchange_rate")
    @classmethod
    def _rate_precision(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v.as_tuple().exponent < -6:  # type: ignore[operator]
            raise ValueError("exchange_rate may have at most 6 decimal places")
        return v

    @model_validator(mode="after")
    def _business_rules(self) -> Invoice:
        _validate_invoice(self)
        return self

    # -- convenience -------------------------------------------------------------------

    def calculate(self) -> InvoiceCalculation:
        """Compute line, tax and document totals (see :mod:`efatura_ubl_tr.calc`)."""
        from .calc import calculate

        return calculate(self)

    def to_xml(self, *, pretty: bool = True) -> bytes:
        """Serialize to UBL-TR 1.2 XML (UTF-8 bytes, unsigned)."""
        from .xml_builder import build_xml

        return build_xml(self, pretty=pretty)

    @classmethod
    def from_json(cls, data: str | bytes) -> Invoice:
        return cls.model_validate_json(data)


def load_invoice(path: str | Path) -> Invoice:
    """Load an :class:`Invoice` from a JSON file (UTF-8)."""
    return Invoice.model_validate_json(Path(path).read_bytes())


def _validate_invoice(inv: Invoice) -> None:
    errors: list[str] = []
    t = inv.type

    if not is_valid_invoice_number(inv.number):
        errors.append(
            f"number {inv.number!r} must match GİB format ABC2026000000001 "
            "(3 chars + year + 9 digit sequence)"
        )
    elif int(inv.number[3:7]) != inv.issue_date.year:
        errors.append(
            f"year in invoice number ({inv.number[3:7]}) differs from issue_date year "
            f"({inv.issue_date.year})"
        )

    if inv.currency == "TRY":
        if inv.exchange_rate is not None:
            errors.append("exchange_rate must not be set for TRY invoices")
    elif inv.exchange_rate is None:
        errors.append(f"exchange_rate is required for {inv.currency} invoices")

    if t is InvoiceType.IADE:
        if inv.profile is Profile.TICARIFATURA:
            errors.append("IADE invoices are only allowed with TEMELFATURA or EARSIVFATURA")
        if not inv.return_references:
            errors.append("IADE invoices need at least one entry in 'return_references'")
    elif inv.return_references:
        errors.append("'return_references' is only used with the IADE invoice type")

    has_withholding = any(line.withholding for line in inv.lines)
    if t is InvoiceType.TEVKIFAT and not has_withholding:
        errors.append("TEVKIFAT invoices need at least one line with 'withholding'")
    if has_withholding and t not in (InvoiceType.TEVKIFAT, InvoiceType.IADE):
        errors.append("line 'withholding' is only allowed on TEVKIFAT (or IADE) invoices")

    has_ozel = any(line.ozel_matrah for line in inv.lines)
    if t is InvoiceType.OZELMATRAH and not has_ozel:
        errors.append("OZELMATRAH invoices need at least one line with 'ozel_matrah'")
    if has_ozel and t is not InvoiceType.OZELMATRAH:
        errors.append("'ozel_matrah' is only allowed on OZELMATRAH invoices")

    for index, line in enumerate(inv.lines, start=1):
        where = f"line {index}"
        ex = line.exemption
        if line.ozel_matrah and (ex or line.withholding):
            errors.append(f"{where}: 'ozel_matrah' cannot be combined with exemption/withholding")
        if line.withholding and line.kdv_rate == 0:
            errors.append(f"{where}: withholding needs a KDV rate above 0")
        if ex is None:
            if line.kdv_rate == 0 and not line.ozel_matrah and t is not InvoiceType.IADE:
                errors.append(
                    f"{where}: 0% KDV needs an 'exemption' (e.g. code 351 'KDV - İstisna "
                    "Olmayan Diğer' for SATIS, or an istisna code with the ISTISNA type)"
                )
            if t is InvoiceType.IHRACKAYITLI:
                errors.append(f"{where}: IHRACKAYITLI lines need an exemption code 701/703/704")
            continue
        code = ex.code
        if t is InvoiceType.IHRACKAYITLI:
            if code not in IHRACKAYITLI_EXEMPTION_CODES:
                errors.append(f"{where}: IHRACKAYITLI lines need exemption code 701-704")
            elif code == "702":
                errors.append(
                    f"{where}: code 702 (DİİB / geçici kabul) needs GTİP and alıcı satır kodu "
                    "fields which are not supported in v0.1"
                )
            if line.kdv_rate == 0:
                errors.append(f"{where}: ihraç kayıtlı lines keep their normal KDV rate (> 0)")
            continue
        if code in IHRACKAYITLI_EXEMPTION_CODES:
            errors.append(f"{where}: exemption {code} requires the IHRACKAYITLI invoice type")
            continue
        if line.kdv_rate != 0:
            errors.append(f"{where}: an exemption ({code}) requires kdv_rate 0")
        if code in ISTISNA_EXEMPTION_CODES and t not in (InvoiceType.ISTISNA, InvoiceType.IADE):
            errors.append(
                f"{where}: istisna code {code} requires the ISTISNA (or IADE) invoice type; "
                "use 351 for other 0% KDV sales"
            )
        if code in OTHER_ZERO_KDV_CODES and t is InvoiceType.ISTISNA:
            errors.append(f"{where}: ISTISNA invoices need an istisna code, not {code}")

    if t is InvoiceType.ISTISNA and not any(
        line.exemption and line.exemption.code in ISTISNA_EXEMPTION_CODES for line in inv.lines
    ):
        errors.append("ISTISNA invoices need at least one line with an istisna exemption code")

    if errors:
        raise ValueError("; ".join(errors))
