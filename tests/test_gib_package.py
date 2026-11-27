"""Tests for downloading / caching GİB packages – no network access needed."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import pytest

from efatura_ubl_tr.validation import gib_package
from efatura_ubl_tr.validation.gib_package import (
    SchemaPackageError,
    default_cache_dir,
    fetch_package,
    find_package,
    install_from_zips,
)


def _zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


UBLTR_ZIP = _zip(
    {
        "UBLTR_1.2.1_Paketi/xsdrt/maindoc/UBL-Invoice-2.1.xsd": "<xsd/>",
        "UBLTR_1.2.1_Paketi/xsdrt/common/UBL-CommonBasicComponents-2.1.xsd": "<xsd/>",
        "UBLTR_1.2.1_Paketi/xml/TemelFaturaOrnegi.xml": "<Invoice/>",
        "UBLTR_1.2.1_Paketi/xml/general.xslt": "<xsl/>",  # not extracted
    }
)
EFATURA_ZIP = _zip(
    {
        "e-FaturaPaketi/schematron/UBL-TR_Main_Schematron.xml": "<schema/>",
        "e-FaturaPaketi/schematron/UBL-TR_Codelist.xml": "<schema/>",
        "e-FaturaPaketi/wsdl/EFatura.wsdl": "<wsdl/>",  # not extracted
    }
)


def test_default_cache_dir_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EFATURA_CACHE_DIR", str(tmp_path / "x"))
    assert default_cache_dir() == tmp_path / "x"
    monkeypatch.delenv("EFATURA_CACHE_DIR")
    assert "e-fatura-ubl-tr" in str(default_cache_dir())


def test_install_from_zips_and_find(tmp_path: Path) -> None:
    (tmp_path / "u.zip").write_bytes(UBLTR_ZIP)
    (tmp_path / "e.zip").write_bytes(EFATURA_ZIP)
    cache = tmp_path / "cache"
    assert find_package(cache) is None
    package = install_from_zips(tmp_path / "u.zip", tmp_path / "e.zip", cache)
    assert package.invoice_xsd.name == "UBL-Invoice-2.1.xsd"
    assert package.schematron.name == "UBL-TR_Main_Schematron.xml"
    assert package.samples_dir is not None
    assert not list(package.root.rglob("general.xslt"))
    assert not list(package.root.rglob("*.wsdl"))
    found = find_package(cache)
    assert found is not None and found.root == package.root
    assert "sha256" in found.manifest["ubltr"]
    assert "GİB schema cache" in found.describe()


def test_install_rejects_incomplete_package(tmp_path: Path) -> None:
    (tmp_path / "u.zip").write_bytes(_zip({"readme.txt": "x"}))
    (tmp_path / "e.zip").write_bytes(EFATURA_ZIP)
    with pytest.raises(SchemaPackageError, match="xsdrt"):
        install_from_zips(tmp_path / "u.zip", tmp_path / "e.zip", tmp_path / "cache")
    # nothing half-installed is left behind
    assert find_package(tmp_path / "cache") is None


def test_zip_slip_is_blocked(tmp_path: Path) -> None:
    evil = _zip({"../xsdrt/evil.xsd": "<x/>"})
    with pytest.raises(SchemaPackageError, match="unsafe path"):
        gib_package._extract(evil, tmp_path / "out", gib_package._UBLTR_MEMBERS)
    assert not (tmp_path / "xsdrt").exists()


def test_not_a_zip(tmp_path: Path) -> None:
    with pytest.raises(SchemaPackageError, match="not a valid ZIP"):
        gib_package._extract(b"<html>blocked</html>", tmp_path, gib_package._UBLTR_MEMBERS)


def test_fetch_package_uses_discovered_link(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = '<a href="/dosyalar/kilavuzlar/e-FaturaPaketi (31).zip">e-Fatura Paketi</a>'
    requested: list[str] = []

    def fake_download(url: str, timeout: float) -> tuple[bytes, dict[str, Any]]:
        requested.append(url)
        if url == gib_package.GIB_PAGE_URL:
            return page.encode("cp1254"), {}
        if url == gib_package.UBLTR_PACKAGE_URL:
            return UBLTR_ZIP, {"last-modified": "Mon, 12 Jan 2026 08:48:25 GMT"}
        return EFATURA_ZIP, {}

    monkeypatch.delenv("EFATURA_UBLTR_URL", raising=False)
    monkeypatch.delenv("EFATURA_PAKET_URL", raising=False)
    monkeypatch.setattr(gib_package, "_download", fake_download)
    package = fetch_package(tmp_path)
    assert (
        requested[-1]
        == "https://ebelge.gib.gov.tr/dosyalar/kilavuzlar/e-FaturaPaketi%20%2831%29.zip"
    )
    assert package.manifest["ubltr"]["last_modified"] == "Mon, 12 Jan 2026 08:48:25 GMT"

    # second call is served from the cache without network access
    monkeypatch.setattr(gib_package, "_download", None)
    assert fetch_package(tmp_path).root == package.root


def test_discovery_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(url: str, timeout: float) -> tuple[bytes, dict[str, Any]]:
        raise SchemaPackageError("offline")

    monkeypatch.setattr(gib_package, "_download", failing)
    assert gib_package._discover_efatura_url(1) == gib_package.EFATURA_PACKAGE_FALLBACK_URL


def test_download_error_is_wrapped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def failing(url: str, timeout: float) -> tuple[bytes, dict[str, Any]]:
        raise SchemaPackageError(f"could not download {url}")

    monkeypatch.setattr(gib_package, "_download", failing)
    with pytest.raises(SchemaPackageError, match="could not download"):
        fetch_package(tmp_path, efatura_url="https://example.invalid/e.zip")
