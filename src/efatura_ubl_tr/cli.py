"""Command line interface: ``efatura build | validate | preview | schemas | words | check-id``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import ValidationError

from . import __version__
from .identifiers import NIHAI_TUKETICI_TCKN, identify_tax_id
from .models import Invoice, load_invoice
from .preview import render_html
from .words import amount_in_words

__all__ = ["main"]

DISCLAIMER = (
    "Unofficial tool, not affiliated with or certified by GİB. Output is unsigned; signing and "
    "sending via an özel entegratör / GİB portal are out of scope."
)

EXIT_OK, EXIT_INVALID, EXIT_ERROR = 0, 1, 2


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if encoding == "utf8":
            continue
        isatty = getattr(stream, "isatty", lambda: False)
        if isatty():
            reconfigure(errors="replace")
        else:
            reconfigure(encoding="utf-8", errors="replace")


def _err(message: str) -> None:
    print(f"efatura: {message}", file=sys.stderr)


def _write(data: bytes, output: str | None) -> None:
    if output is None or output == "-":
        sys.stdout.buffer.write(data)
        sys.stdout.flush()
    else:
        Path(output).write_bytes(data)
        _err(f"wrote {output}")


def _load(path: str) -> Invoice | None:
    try:
        return load_invoice(path)
    except ValidationError as exc:
        _err(f"{path}: invalid invoice data")
        for error in exc.errors():
            location = ".".join(str(p) for p in error["loc"]) or "(invoice)"
            print(f"  - {location}: {error['msg']}", file=sys.stderr)
        return None


def cmd_build(args: argparse.Namespace) -> int:
    invoice = _load(args.input)
    if invoice is None:
        return EXIT_INVALID
    xml = invoice.to_xml(pretty=not args.compact)
    if args.summary:
        calc = invoice.calculate()
        cur = invoice.currency
        _err(
            f"{invoice.number} {invoice.profile.value}/{invoice.type.value}: "
            f"matrah {calc.tax_exclusive} {cur}, vergi {calc.tax_total} {cur}, "
            f"tevkifat {calc.withholding_total} {cur}, ödenecek {calc.payable} {cur}"
        )
    _write(xml, args.output)
    return EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    from .validation import SchemaPackageError, validate_xml

    try:
        result = validate_xml(
            Path(args.input),
            cache_dir=args.cache_dir,
            download=not args.no_download,
            schematron=not args.xsd_only,
            allow_unsigned=not args.require_signature,
        )
    except SchemaPackageError as exc:
        _err(str(exc))
        _err("tip: run `efatura schemas fetch`, or install ZIPs downloaded from GİB with")
        _err("     `efatura schemas fetch --ubltr-zip <UBL-TR zip> --efatura-zip <e-Fatura zip>`")
        return EXIT_ERROR
    if args.json:
        payload = {
            "file": args.input,
            "valid": result.valid,
            "schematron_checked": result.schematron_checked,
            "issues": [
                {"layer": i.layer, "message": i.message, "location": i.location, "rule": i.rule}
                for i in result.issues
            ],
            "notes": result.notes,
            "package": result.package.manifest if result.package else None,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"{args.input}: {result.summary()}")
    return EXIT_OK if result.valid else EXIT_INVALID


def cmd_preview(args: argparse.Namespace) -> int:
    source = Path(args.input)
    if source.suffix.lower() == ".json":
        invoice = _load(args.input)
        if invoice is None:
            return EXIT_INVALID
        page = render_html(invoice.to_xml())
    else:
        page = render_html(source)
    output = args.output or str(source.with_suffix(".html"))
    _write(page.encode("utf-8"), output)
    return EXIT_OK


def cmd_schemas(args: argparse.Namespace) -> int:
    from .validation import (
        SchemaPackageError,
        default_cache_dir,
        fetch_package,
        find_package,
        install_from_zips,
    )

    if args.action == "fetch":
        try:
            if args.ubltr_zip or args.efatura_zip:
                if not (args.ubltr_zip and args.efatura_zip):
                    _err("--ubltr-zip and --efatura-zip must be given together")
                    return EXIT_ERROR
                package = install_from_zips(args.ubltr_zip, args.efatura_zip, args.cache_dir)
            else:
                _err("downloading GİB UBL-TR packages from ebelge.gib.gov.tr ...")
                package = fetch_package(args.cache_dir, force=args.force)
        except (SchemaPackageError, OSError) as exc:
            _err(str(exc))
            return EXIT_ERROR
        print(package.describe())
        return EXIT_OK
    cached = find_package(args.cache_dir)
    if cached is None:
        print(f"no GİB package cached in {args.cache_dir or default_cache_dir()}")
        return EXIT_INVALID
    print(cached.describe())
    return EXIT_OK


def cmd_words(args: argparse.Namespace) -> int:
    try:
        amount = Decimal(args.amount.replace(",", "."))
        print(amount_in_words(amount, args.currency.upper(), compact=args.compact))
    except (InvalidOperation, ValueError) as exc:
        _err(f"invalid amount {args.amount!r}: {exc}")
        return EXIT_ERROR
    return EXIT_OK


def cmd_check_id(args: argparse.Namespace) -> int:
    kind = identify_tax_id(args.value)
    if kind:
        print(f"{args.value}: valid {kind} (checksum only)")
        return EXIT_OK
    if args.value == NIHAI_TUKETICI_TCKN:
        print(f"{args.value}: placeholder TCKN for final consumers (nihai tüketici)")
        return EXIT_OK
    print(f"{args.value}: not a valid VKN (10 digits) or TCKN (11 digits)")
    return EXIT_INVALID


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="efatura",
        description="Build, validate and preview Turkish e-Fatura / e-Arşiv invoices (UBL-TR 1.2).",
        epilog=DISCLAIMER,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("build", help="build UBL-TR XML from an invoice JSON file")
    p.add_argument("input", help="invoice JSON file (see examples/)")
    p.add_argument("-o", "--output", help="output XML file (default: stdout)")
    p.add_argument("--compact", action="store_true", help="no indentation")
    p.add_argument("--summary", action="store_true", help="print computed totals to stderr")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("validate", help="validate XML against GİB's XSD + schematron")
    p.add_argument("input", help="UBL-TR invoice XML file")
    p.add_argument("--xsd-only", action="store_true", help="skip schematron business rules")
    p.add_argument("--no-download", action="store_true", help="never access the network")
    p.add_argument("--cache-dir", help="GİB package cache directory")
    p.add_argument(
        "--require-signature",
        action="store_true",
        help="do not accept an empty ext:ExtensionContent (unsigned document)",
    )
    p.add_argument("--json", action="store_true", help="machine readable output")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("preview", help="render an HTML preview (XML or JSON input)")
    p.add_argument("input", help="UBL-TR invoice XML (or invoice JSON)")
    p.add_argument("-o", "--output", help="output HTML file (default: <input>.html)")
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("schemas", help="download / inspect GİB's schema package cache")
    p.add_argument("action", choices=["fetch", "info"])
    p.add_argument("--cache-dir", help="cache directory")
    p.add_argument("--force", action="store_true", help="download again even if cached")
    p.add_argument("--ubltr-zip", help="install from a local UBL-TR1.2.1_Paketi.zip")
    p.add_argument("--efatura-zip", help="install from a local e-FaturaPaketi.zip")
    p.set_defaults(func=cmd_schemas)

    p = sub.add_parser("words", help="spell an amount in Turkish (Yalnız ...)")
    p.add_argument("amount")
    p.add_argument("--currency", default="TRY")
    p.add_argument("--compact", action="store_true")
    p.set_defaults(func=cmd_words)

    p = sub.add_parser("check-id", help="check a VKN / TCKN checksum")
    p.add_argument("value")
    p.set_defaults(func=cmd_check_id)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    source = getattr(args, "input", None)
    if source is not None and not Path(source).is_file():
        _err(f"file not found: {source}")
        return EXIT_ERROR
    try:
        return int(args.func(args))
    except FileNotFoundError as exc:
        _err(f"file not found: {exc.filename}")
        return EXIT_ERROR
    except Exception as exc:  # pragma: no cover - last-resort error message
        _err(f"{type(exc).__name__}: {exc}")
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
