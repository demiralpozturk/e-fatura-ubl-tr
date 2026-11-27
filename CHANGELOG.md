# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-27 (not published to PyPI yet)

### Added

- Typed invoice models (pydantic v2) for parties, lines, discounts/surcharges, KDV, ÖTV-style
  line taxes, KDV withholding (tevkifat), exemptions, özel matrah, references, payment means/terms,
  multi-currency with exchange rate.
- Profiles `TEMELFATURA`, `TICARIFATURA`, `EARSIVFATURA`; invoice types `SATIS`, `IADE`,
  `TEVKIFAT`, `ISTISNA` (full) and `IHRACKAYITLI`, `OZELMATRAH` (experimental).
- `Decimal` calculations with documented per-line `ROUND_HALF_UP` rounding.
- Turkish amount in words ("Yalnız: … Türk Lirası … Kuruş").
- VKN / TCKN checksum validation, invoice number and ETTN helpers.
- UBL-TR 1.2 XML builder following GİB's UBL-TR 1.2.1 element order.
- Validation against GİB's official XSD + schematron, downloaded at runtime into a local cache,
  with a built-in XPath 2.0 schematron interpreter.
- Self-written HTML preview renderer.
- `efatura` CLI: `build`, `validate`, `preview`, `schemas`, `words`, `check-id`.
- Nine fictional example invoices; GitHub Actions CI on Ubuntu and Windows.
