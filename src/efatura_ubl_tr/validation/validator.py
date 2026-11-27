"""Validate UBL-TR invoices against GİB's official XSD and schematron rules."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from lxml import etree

from .gib_package import SchemaPackage, fetch_package, find_package
from .schematron import Schematron

__all__ = ["ValidationIssue", "ValidationResult", "validate_xml"]

_EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
_PLACEHOLDER = "{urn:e-fatura-ubl-tr:unsigned}SignaturePlaceholder"


@dataclass(frozen=True)
class ValidationIssue:
    layer: Literal["xml", "xsd", "schematron"]
    message: str
    location: str = ""
    rule: str | None = None

    def __str__(self) -> str:
        where = f" [{self.location}]" if self.location else ""
        rule = f" ({self.rule})" if self.rule else ""
        return f"{self.layer.upper()}{rule}{where}: {self.message}"


@dataclass
class ValidationResult:
    """Outcome of :func:`validate_xml`."""

    issues: list[ValidationIssue] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    schematron_checked: bool = False
    package: SchemaPackage | None = None

    @property
    def valid(self) -> bool:
        return not self.issues

    @property
    def xsd_errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.layer in ("xml", "xsd")]

    @property
    def schematron_errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.layer == "schematron"]

    def summary(self) -> str:
        layers = "XSD + schematron" if self.schematron_checked else "XSD"
        if self.valid:
            head = f"VALID ({layers} - GİB UBL-TR 1.2.1)"
        else:
            head = f"INVALID: {len(self.issues)} issue(s) ({layers})"
        lines = [head, *(f"  - {issue}" for issue in self.issues)]
        lines += [f"  note: {note}" for note in self.notes]
        return "\n".join(lines)


@lru_cache(maxsize=4)
def _xml_schema(path: str) -> etree.XMLSchema:
    parser = etree.XMLParser(no_network=True, resolve_entities=False)
    return etree.XMLSchema(etree.parse(path, parser))


@lru_cache(maxsize=8)
def _schematron(path: str, doc_type: str) -> Schematron:
    return Schematron(path, parameters={"type": doc_type})


def _parse(source: bytes | str | Path | etree._ElementTree) -> etree._ElementTree:
    if isinstance(source, etree._ElementTree):
        return source
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    if isinstance(source, Path) or (
        isinstance(source, str) and not source.lstrip().startswith("<")
    ):
        return etree.parse(str(source), parser)
    data = source.encode("utf-8") if isinstance(source, str) else source
    return etree.fromstring(data, parser).getroottree()


def validate_xml(
    source: bytes | str | Path | etree._ElementTree,
    *,
    package: SchemaPackage | None = None,
    cache_dir: str | Path | None = None,
    download: bool = True,
    schematron: bool = True,
    allow_unsigned: bool = True,
) -> ValidationResult:
    """Validate an invoice against GİB's XSD and (optionally) schematron rules.

    :param source: XML bytes/str, a file path, or an lxml tree.
    :param package: an already loaded :class:`SchemaPackage`; otherwise the cache is used and,
        if empty and ``download`` is true, GİB's packages are downloaded first.
    :param allow_unsigned: UBL-TR's XSD requires an element inside ``ext:ExtensionContent``
        (normally the XAdES signature). When true, an *empty* ExtensionContent is accepted
        by inserting a temporary placeholder before XSD validation.
    :raises SchemaPackageError: if no package is cached and it cannot be downloaded.
    """
    if package is None:
        package = find_package(cache_dir) if not download else fetch_package(cache_dir)
        if package is None:
            from .gib_package import SchemaPackageError

            raise SchemaPackageError(
                "GİB schema package not found in cache; run `efatura schemas fetch` first"
            )
    result = ValidationResult(package=package)

    try:
        tree = _parse(source)
    except (etree.XMLSyntaxError, OSError) as exc:
        result.issues.append(ValidationIssue("xml", str(exc)))
        return result

    xsd_tree = copy.deepcopy(tree)
    if allow_unsigned:
        empty = [
            el for el in xsd_tree.getroot().iter(f"{{{_EXT}}}ExtensionContent") if len(el) == 0
        ]
        for el in empty:
            etree.SubElement(el, _PLACEHOLDER)
        if empty:
            result.notes.append(
                "document is unsigned (empty ext:ExtensionContent); the XAdES signature "
                "(mali mühür / e-imza) must be added by your signer or özel entegratör"
            )

    schema = _xml_schema(str(package.invoice_xsd))
    if not schema.validate(xsd_tree):
        for error in schema.error_log:
            result.issues.append(
                ValidationIssue("xsd", error.message, location=f"line {error.line}")
            )

    if schematron:
        profile = tree.getroot().findtext(f"{{{_CBC}}}ProfileID") or ""
        doc_type = "earchive" if profile.strip() == "EARSIVFATURA" else "efatura"
        rules = _schematron(str(package.schematron), doc_type)
        for failure in rules.validate(tree):
            result.issues.append(
                ValidationIssue(
                    "schematron",
                    failure.message,
                    location=failure.location,
                    rule=failure.rule_id,
                )
            )
        result.schematron_checked = True
        if doc_type == "earchive":
            result.notes.append("schematron run with type='earchive' (EARSIVFATURA profile)")
    return result
