"""A simple, self-contained HTML preview for UBL-TR invoices.

This renderer is written from scratch for this project; it does **not** use or
copy GİB's default XSLT. The output is a developer preview, not the official
invoice representation (no QR code, no signature information).

It reads the XML itself, so it works for any UBL-TR invoice, not only for those
built with this library.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lxml import etree

from .calc import round_money
from .codes import PAYMENT_MEANS_CODES, UNIT_CODES
from .models import Invoice

__all__ = ["render_html", "render_invoice_html"]

_NS = {
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}

_TYPE_LABELS = {
    "SATIS": "Satış",
    "IADE": "İade",
    "TEVKIFAT": "Tevkifat",
    "ISTISNA": "İstisna",
    "IHRACKAYITLI": "İhraç Kayıtlı",
    "OZELMATRAH": "Özel Matrah",
}
_PROFILE_LABELS = {
    "TEMELFATURA": "Temel Fatura",
    "TICARIFATURA": "Ticari Fatura",
    "EARSIVFATURA": "e-Arşiv Fatura",
}


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _dec(text: str | None) -> Decimal | None:
    if text is None or not text.strip():
        return None
    try:
        return Decimal(text.strip())
    except InvalidOperation:
        return None


def _num(value: Decimal | None, places: int | None = 2) -> str:
    """Turkish number format: 1.234,56"""
    if value is None:
        return ""
    if places is None:
        text = format(value.normalize(), "f")
        whole, _, frac = text.partition(".")
    else:
        text = f"{value:.{places}f}"
        whole, _, frac = text.partition(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    groups: list[str] = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    result = sign + ".".join(groups)
    return f"{result},{frac}" if frac else result


def _date(text: str | None) -> str:
    if not text or len(text) < 10:
        return text or ""
    return f"{text[8:10]}.{text[5:7]}.{text[0:4]}"


@dataclass
class _X:
    el: etree._Element

    def text(self, path: str) -> str | None:
        value = self.el.findtext(path, namespaces=_NS)
        return value.strip() if value is not None else None

    def all(self, path: str) -> list[_X]:
        return [_X(e) for e in self.el.iterfind(path, namespaces=_NS)]

    def one(self, path: str) -> _X | None:
        found = self.el.find(path, namespaces=_NS)
        return _X(found) if found is not None else None

    def amount(self, path: str) -> Decimal | None:
        return _dec(self.text(path))


def _party_html(party: _X | None, title: str) -> str:
    if party is None:
        return ""
    name = party.text("cac:PartyName/cbc:Name")
    person = " ".join(
        p
        for p in (party.text("cac:Person/cbc:FirstName"), party.text("cac:Person/cbc:FamilyName"))
        if p
    )
    rows = [f'<div class="party-title">{_e(title)}</div>']
    rows.append(f'<div class="party-name">{_e(name or person)}</div>')
    if name and person:
        rows.append(f"<div>{_e(person)}</div>")
    addr = party.one("cac:PostalAddress")
    if addr is not None:
        street = " ".join(
            x
            for x in (
                addr.text("cbc:District"),
                addr.text("cbc:StreetName"),
                f"No: {addr.text('cbc:BuildingNumber')}"
                if addr.text("cbc:BuildingNumber")
                else None,
                f"D: {addr.text('cbc:Room')}" if addr.text("cbc:Room") else None,
            )
            if x
        )
        if street:
            rows.append(f"<div>{_e(street)}</div>")
        city = " ".join(
            x
            for x in (
                addr.text("cbc:PostalZone"),
                addr.text("cbc:CitySubdivisionName"),
                "/",
                addr.text("cbc:CityName"),
                addr.text("cac:Country/cbc:Name"),
            )
            if x
        )
        rows.append(f"<div>{_e(city)}</div>")
    for label, path in (
        ("Tel", "cac:Contact/cbc:Telephone"),
        ("E-posta", "cac:Contact/cbc:ElectronicMail"),
        ("Web", "cbc:WebsiteURI"),
        ("Vergi Dairesi", "cac:PartyTaxScheme/cac:TaxScheme/cbc:Name"),
    ):
        value = party.text(path)
        if value:
            rows.append(f'<div><span class="k">{_e(label)}:</span> {_e(value)}</div>')
    for pid in party.all("cac:PartyIdentification/cbc:ID"):
        scheme = pid.el.get("schemeID", "ID")
        rows.append(f'<div><span class="k">{_e(scheme)}:</span> {_e(pid.el.text)}</div>')
    return "\n".join(rows)


def render_html(source: bytes | str | Path) -> str:
    """Render UBL-TR invoice XML (bytes, string or file path) as a standalone HTML page."""
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    if isinstance(source, Path) or (
        isinstance(source, str) and not source.lstrip().startswith("<")
    ):
        root = etree.parse(str(source), parser).getroot()
    else:
        data = source.encode("utf-8") if isinstance(source, str) else source
        root = etree.fromstring(data, parser)
    inv = _X(root)

    currency = inv.text("cbc:DocumentCurrencyCode") or "TRY"
    profile = inv.text("cbc:ProfileID") or ""
    inv_type = inv.text("cbc:InvoiceTypeCode") or ""
    title = "e-ARŞİV FATURA" if profile == "EARSIVFATURA" else "e-FATURA"
    rate = inv.amount("cac:PricingExchangeRate/cbc:CalculationRate")

    def money(value: Decimal | None) -> str:
        return f"{_num(value)} {_e(currency)}" if value is not None else ""

    info_rows: list[tuple[str, str]] = [
        ("Özelleştirme No", inv.text("cbc:CustomizationID") or ""),
        ("Senaryo", _PROFILE_LABELS.get(profile, profile)),
        ("Fatura Tipi", _TYPE_LABELS.get(inv_type, inv_type)),
        ("Fatura No", inv.text("cbc:ID") or ""),
        ("Fatura Tarihi", _date(inv.text("cbc:IssueDate"))),
    ]
    if inv.text("cbc:IssueTime"):
        info_rows.append(("Fatura Saati", inv.text("cbc:IssueTime") or ""))
    order = inv.one("cac:OrderReference")
    if order is not None:
        info_rows.append(("Sipariş No", order.text("cbc:ID") or ""))
        info_rows.append(("Sipariş Tarihi", _date(order.text("cbc:IssueDate"))))
    for desp in inv.all("cac:DespatchDocumentReference"):
        info_rows.append(
            ("İrsaliye", f"{desp.text('cbc:ID') or ''} / {_date(desp.text('cbc:IssueDate'))}")
        )
    for ref in inv.all("cac:BillingReference/cac:InvoiceDocumentReference"):
        info_rows.append(
            (
                "İade Edilen Fatura",
                f"{ref.text('cbc:ID') or ''} / {_date(ref.text('cbc:IssueDate'))}",
            )
        )
    if currency != "TRY":
        info_rows.append(("Döviz", currency))
        if rate is not None:
            info_rows.append(("Döviz Kuru", f"1 {currency} = {_num(rate, None)} TRY"))

    info_html = "\n".join(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in info_rows if v)

    # -- lines ------------------------------------------------------------------------
    # (header, css class, optional) - optional columns are hidden when empty on every line
    columns = [
        ("Sıra", "c", False),
        ("Mal / Hizmet", "name", False),
        ("Miktar", "r", False),
        ("Birim Fiyat", "r", False),
        ("İskonto", "r", True),
        ("KDV %", "c", False),
        ("KDV Tutarı", "r", False),
        ("Diğer Vergiler", "r small", True),
        ("Tevkifat", "r small", True),
        ("Tutar", "r", False),
    ]
    cells_per_line: list[list[str]] = []
    exemptions: dict[str, str] = {}
    for line in inv.all("cac:InvoiceLine"):
        qty_el = line.one("cbc:InvoicedQuantity")
        unit = qty_el.el.get("unitCode", "") if qty_el is not None else ""
        qty = _dec(qty_el.el.text) if qty_el is not None else None
        discounts = [
            ac
            for ac in line.all("cac:AllowanceCharge")
            if (ac.text("cbc:ChargeIndicator") or "false") == "false"
        ]
        discount_total = sum(
            (ac.amount("cbc:Amount") or Decimal(0) for ac in discounts), Decimal(0)
        )
        subtotals = line.all("cac:TaxTotal/cac:TaxSubtotal")
        kdv = [
            s
            for s in subtotals
            if s.text("cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode") == "0015"
        ]
        others = [s for s in subtotals if s not in kdv]
        for sub in subtotals:
            code = sub.text("cac:TaxCategory/cbc:TaxExemptionReasonCode")
            if code:
                exemptions[code] = sub.text("cac:TaxCategory/cbc:TaxExemptionReason") or ""
        kdv_rate = ", ".join(f"%{_num(_dec(s.text('cbc:Percent')), None)}" for s in kdv)
        kdv_amount = sum((s.amount("cbc:TaxAmount") or Decimal(0) for s in kdv), Decimal(0))
        other_text = "<br>".join(
            f"{_e(s.text('cac:TaxCategory/cac:TaxScheme/cbc:Name'))}"
            + (f" (%{_num(_dec(s.text('cbc:Percent')), None)})" if s.text("cbc:Percent") else "")
            + f": {money(s.amount('cbc:TaxAmount'))}"
            for s in others
        )
        withholding = "<br>".join(
            f"{_e(s.text('cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode'))} "
            f"(%{_num(_dec(s.text('cbc:Percent')), None)}): {money(s.amount('cbc:TaxAmount'))}"
            for s in line.all("cac:WithholdingTaxTotal/cac:TaxSubtotal")
        )
        name_html = _e(line.text("cac:Item/cbc:Name"))
        for extra in (line.text("cac:Item/cbc:Description"), line.text("cbc:Note")):
            if extra:
                name_html += f'<div class="muted">{_e(extra)}</div>'
        cells_per_line.append(
            [
                _e(line.text("cbc:ID")),
                name_html,
                f"{_num(qty, None)} {_e(UNIT_CODES.get(unit, unit))}",
                money(line.amount("cac:Price/cbc:PriceAmount")),
                money(discount_total) if discounts and discount_total else "",
                _e(kdv_rate),
                money(kdv_amount) if kdv else "",
                other_text,
                withholding,
                money(line.amount("cbc:LineExtensionAmount")),
            ]
        )
    visible = [
        i
        for i, (_, _, optional) in enumerate(columns)
        if not optional or any(cells[i] for cells in cells_per_line)
    ]
    line_head = "".join(f'<th class="{columns[i][1]}">{_e(columns[i][0])}</th>' for i in visible)
    line_rows = [
        "<tr>" + "".join(f'<td class="{columns[i][1]}">{cells[i]}</td>' for i in visible) + "</tr>"
        for cells in cells_per_line
    ]

    # -- totals -----------------------------------------------------------------------
    total = inv.one("cac:LegalMonetaryTotal")
    totals: list[tuple[str, Decimal | None, bool]] = []
    if total is not None:
        totals.append(("Mal Hizmet Toplam Tutarı", total.amount("cbc:LineExtensionAmount"), False))
        allowance = total.amount("cbc:AllowanceTotalAmount")
        if allowance:
            totals.append(("Toplam İskonto", allowance, False))
        charge = total.amount("cbc:ChargeTotalAmount")
        if charge:
            totals.append(("Toplam Artırım", charge, False))
        totals.append(("Vergi Hariç Tutar", total.amount("cbc:TaxExclusiveAmount"), False))
    for sub in inv.all("cac:TaxTotal/cac:TaxSubtotal"):
        name = sub.text("cac:TaxCategory/cac:TaxScheme/cbc:Name") or "Vergi"
        percent = sub.text("cbc:Percent")
        label = f"Hesaplanan {name}" + (f" (%{_num(_dec(percent), None)})" if percent else "")
        code = sub.text("cac:TaxCategory/cbc:TaxExemptionReasonCode")
        if code:
            exemptions[code] = sub.text("cac:TaxCategory/cbc:TaxExemptionReason") or ""
        totals.append((label, sub.amount("cbc:TaxAmount"), False))
    for sub in inv.all("cac:WithholdingTaxTotal/cac:TaxSubtotal"):
        code = sub.text("cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode") or ""
        percent = _num(_dec(sub.text("cbc:Percent")), None)
        totals.append((f"Tevkifata Tabi KDV ({code})", sub.amount("cbc:TaxableAmount"), False))
        totals.append((f"Tevkif Edilen KDV (%{percent})", sub.amount("cbc:TaxAmount"), False))
    if total is not None:
        totals.append(
            ("Vergiler Dahil Toplam Tutar", total.amount("cbc:TaxInclusiveAmount"), False)
        )
        totals.append(("Ödenecek Tutar", total.amount("cbc:PayableAmount"), True))

    def total_row(label: str, value: Decimal | None, strong: bool) -> str:
        cls = ' class="grand"' if strong else ""
        try_col = ""
        if currency != "TRY" and rate is not None:
            converted = round_money(value * rate) if value is not None else None
            try_col = f"<td class='r'>{_num(converted)} TRY</td>"
        return f"<tr{cls}><th>{_e(label)}</th><td class='r'>{money(value)}</td>{try_col}</tr>"

    totals_html = "\n".join(total_row(*row) for row in totals)
    try_head = (
        f"<thead><tr><th></th><th class='r'>{_e(currency)}</th><th class='r'>TRY karşılığı</th>"
        "</tr></thead>"
        if currency != "TRY" and rate is not None
        else ""
    )

    notes_html = "".join(f"<li>{_e(n.el.text)}</li>" for n in inv.all("cbc:Note") if n.el.text)
    exemption_html = "".join(
        f"<li><b>{_e(code)}</b> - {_e(reason)}</li>" for code, reason in exemptions.items()
    )
    payment_html = ""
    for pm in inv.all("cac:PaymentMeans"):
        code = pm.text("cbc:PaymentMeansCode") or ""
        parts = [PAYMENT_MEANS_CODES.get(code, code)]
        if pm.text("cbc:PaymentDueDate"):
            parts.append(f"Vade: {_date(pm.text('cbc:PaymentDueDate'))}")
        iban = pm.text("cac:PayeeFinancialAccount/cbc:ID")
        if iban:
            parts.append("IBAN: " + " ".join(iban[i : i + 4] for i in range(0, len(iban), 4)))
        bank = pm.text("cac:PayeeFinancialAccount/cac:FinancialInstitutionBranch/cbc:Name")
        if bank:
            parts.append(bank)
        if pm.text("cbc:InstructionNote"):
            parts.append(pm.text("cbc:InstructionNote") or "")
        payment_html += f"<li>{_e(' · '.join(parts))}</li>"
    terms = inv.one("cac:PaymentTerms")
    if terms is not None and (terms.text("cbc:Note") or terms.text("cbc:PaymentDueDate")):
        due = terms.text("cbc:PaymentDueDate")
        text = " · ".join(
            x for x in (terms.text("cbc:Note"), f"Vade: {_date(due)}" if due else None) if x
        )
        payment_html += f"<li>{_e(text)}</li>"

    def section(heading: str, items: str) -> str:
        return (
            f'<section class="box"><h3>{_e(heading)}</h3><ul>{items}</ul></section>'
            if items
            else ""
        )

    supplier = _party_html(inv.one("cac:AccountingSupplierParty/cac:Party"), "Satıcı")
    customer = _party_html(inv.one("cac:AccountingCustomerParty/cac:Party"), "Sayın")

    return _TEMPLATE.format(
        title=_e(f"{title} {inv.text('cbc:ID') or ''}"),
        doc_title=_e(title),
        supplier=supplier,
        customer=customer,
        info=info_html,
        ettn=_e(inv.text("cbc:UUID")),
        line_head=line_head,
        lines="\n".join(line_rows),
        totals=totals_html,
        try_head=try_head,
        notes=section("Notlar", notes_html),
        exemptions=section("Vergi İstisna / Muafiyet Sebebi", exemption_html),
        payment=section("Ödeme Bilgileri", payment_html),
    )


def render_invoice_html(invoice: Invoice) -> str:
    """Render an :class:`~efatura_ubl_tr.models.Invoice` (builds the XML first)."""
    return render_html(invoice.to_xml())


_TEMPLATE = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --ink:#1d2433; --muted:#5b6475; --line:#d9dee7; --accent:#1f4e8c; --bg:#f3f5f9; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font: 13px/1.45 "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
  .page {{ max-width: 210mm; margin: 24px auto; background:#fff; padding: 28px 32px;
           box-shadow: 0 2px 12px rgba(20,30,50,.08); border-radius: 6px; }}
  .preview-banner {{ font-size:11px; color:var(--muted); text-align:center; margin-bottom:14px;
           border:1px dashed var(--line); padding:6px; border-radius:4px; }}
  header {{ display:grid; grid-template-columns: 1fr auto; gap: 24px; align-items:start; }}
  .doc-title {{ text-align:right; }}
  .doc-title .badge {{ display:inline-block; font-weight:700; letter-spacing:.08em; font-size:20px;
           color:var(--accent); border:2px solid var(--accent); padding:6px 14px; border-radius:6px; }}
  .party-title {{ font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }}
  .party-name {{ font-weight:700; font-size:15px; margin:2px 0 4px; }}
  .k {{ color:var(--muted); }}
  .row2 {{ display:grid; grid-template-columns: 1fr 300px; gap:24px; margin-top:20px; align-items:start; }}
  table {{ border-collapse:collapse; width:100%; }}
  .info th, .info td, .totals th, .totals td {{ border:1px solid var(--line); padding:4px 8px; }}
  .info th, .totals th {{ text-align:left; background:#f7f9fc; font-weight:600; width:48%; }}
  .ettn {{ margin-top:12px; font-size:12px; color:var(--muted); word-break:break-all; }}
  .lines {{ margin-top:18px; }}
  .lines th {{ background:var(--accent); color:#fff; font-weight:600; padding:6px; font-size:12px; }}
  .lines td {{ border-bottom:1px solid var(--line); padding:6px; vertical-align:top; }}
  .lines .name {{ min-width: 180px; text-align:left; }}
  .lines tr:nth-child(even) td {{ background:#fafbfd; }}
  .r {{ text-align:right; white-space:nowrap; }}
  .c {{ text-align:center; }}
  .small {{ font-size:11px; }}
  .muted {{ color:var(--muted); font-size:11px; }}
  .bottom {{ display:grid; grid-template-columns: 1fr minmax(360px, 45%); gap:24px; margin-top:18px; align-items:start; }}
  .totals .grand th, .totals .grand td {{ background:#eaf1fb; font-weight:700; font-size:14px; }}
  .box {{ border:1px solid var(--line); border-radius:4px; padding:8px 12px; margin-bottom:10px; }}
  .box h3 {{ margin:0 0 4px; font-size:12px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }}
  .box ul {{ margin:0; padding-left:18px; }}
  footer {{ margin-top:22px; font-size:10.5px; color:var(--muted); text-align:center; }}
  @media (max-width: 720px) {{
    .page {{ margin:0; border-radius:0; padding:16px; }}
    header, .row2, .bottom {{ grid-template-columns: 1fr; }}
    .doc-title {{ text-align:left; }}
    .lines-wrap {{ overflow-x:auto; }}
  }}
  @media print {{
    body {{ background:#fff; }}
    .page {{ box-shadow:none; margin:0; max-width:none; }}
    .preview-banner {{ display:none; }}
  }}
</style>
</head>
<body>
<main class="page">
  <div class="preview-banner">Önizleme / Preview &middot; e-fatura-ubl-tr &middot;
    resmî fatura görüntüsü değildir &middot; not an official representation</div>
  <header>
    <div>{supplier}</div>
    <div class="doc-title"><span class="badge">{doc_title}</span></div>
  </header>
  <div class="row2">
    <div>{customer}</div>
    <table class="info">{info}</table>
  </div>
  <div class="ettn"><b>ETTN:</b> {ettn}</div>
  <div class="lines-wrap">
  <table class="lines">
    <thead><tr>{line_head}</tr></thead>
    <tbody>
{lines}
    </tbody>
  </table>
  </div>
  <div class="bottom">
    <div>{notes}{exemptions}{payment}</div>
    <table class="totals">
      {try_head}
      <tbody>
{totals}
      </tbody>
    </table>
  </div>
  <footer>Bu sayfa e-fatura-ubl-tr ile üretilmiş bir önizlemedir. Gelir İdaresi Başkanlığı (GİB) ile
    bağlantılı değildir. Generated by e-fatura-ubl-tr (unofficial, not affiliated with GİB).</footer>
</main>
</body>
</html>
"""
