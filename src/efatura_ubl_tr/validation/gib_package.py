"""Download GİB's UBL-TR schema packages at runtime and keep them in a local cache.

GİB publishes the official XSD and schematron files on https://ebelge.gib.gov.tr.
Those files are **not** redistributed with this library (the site states
"© Gelir İdaresi Başkanlığı Her Hakkı Saklıdır" and the packages carry no
redistribution license). Instead they are downloaded from GİB on first use and
stored in a per-user cache directory:

* ``UBL-TR1.2.1_Paketi.zip`` – XSD schemas (``xsdrt/``) and GİB's sample XMLs
* ``e-FaturaPaketi*.zip`` – schematron rules (``schematron/``)

Cache location: ``$EFATURA_CACHE_DIR`` or the platform cache directory
(``%LOCALAPPDATA%\\e-fatura-ubl-tr`` on Windows, ``~/.cache/e-fatura-ubl-tr`` elsewhere).
You can also install the packages from ZIP files you downloaded yourself
(:func:`install_from_zips`), e.g. when GİB's site is not reachable from CI.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

__all__ = [
    "EFATURA_PACKAGE_FALLBACK_URL",
    "GIB_PAGE_URL",
    "UBLTR_PACKAGE_URL",
    "SchemaPackage",
    "SchemaPackageError",
    "default_cache_dir",
    "fetch_package",
    "find_package",
    "install_from_zips",
]

GIB_PAGE_URL = "https://ebelge.gib.gov.tr/efaturamevzuat.html"
UBLTR_PACKAGE_URL = "https://ebelge.gib.gov.tr/dosyalar/kilavuzlar/UBL-TR1.2.1_Paketi.zip"
EFATURA_PACKAGE_FALLBACK_URL = "https://ebelge.gib.gov.tr/dosyalar/kilavuzlar/e-FaturaPaketi.zip"

_PACKAGE_DIR = "gib-ubltr-1.2.1"
_MAX_DOWNLOAD = 64 * 1024 * 1024
_MANIFEST = "manifest.json"


class SchemaPackageError(RuntimeError):
    """Raised when GİB's schema package cannot be downloaded or is incomplete."""


@dataclass(frozen=True)
class SchemaPackage:
    """A locally cached copy of GİB's UBL-TR schema packages."""

    root: Path
    manifest: dict[str, Any]

    @property
    def invoice_xsd(self) -> Path:
        return self._find("ubltr", "UBL-Invoice-2.1.xsd", parent="maindoc")

    @property
    def schematron(self) -> Path:
        return self._find("efatura", "UBL-TR_Main_Schematron.xml")

    @property
    def samples_dir(self) -> Path | None:
        try:
            return self._find("ubltr", "TemelFaturaOrnegi.xml").parent
        except SchemaPackageError:
            return None

    def _find(self, part: str, name: str, parent: str | None = None) -> Path:
        for path in sorted((self.root / part).rglob(name)):
            if parent is None or path.parent.name == parent:
                return path
        raise SchemaPackageError(f"{name} not found in {self.root / part}")

    def describe(self) -> str:
        lines = [f"GİB schema cache: {self.root}"]
        for key in ("ubltr", "efatura"):
            info = self.manifest.get(key, {})
            lines.append(
                f"  {key}: {info.get('source', '?')} "
                f"(Last-Modified: {info.get('last_modified') or '?'}, "
                f"sha256: {str(info.get('sha256', '?'))[:12]}…)"
            )
        lines.append(f"  installed: {self.manifest.get('installed_at', '?')}")
        return "\n".join(lines)


def default_cache_dir() -> Path:
    """Directory where GİB packages are cached (override with ``EFATURA_CACHE_DIR``)."""
    env = os.environ.get("EFATURA_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    platform: str = sys.platform
    if platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "e-fatura-ubl-tr" / "Cache"
    if platform == "darwin":
        return Path.home() / "Library" / "Caches" / "e-fatura-ubl-tr"
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "e-fatura-ubl-tr"


def find_package(cache_dir: str | Path | None = None) -> SchemaPackage | None:
    """Return the cached package if it is complete, otherwise ``None`` (no network access)."""
    root = Path(cache_dir) if cache_dir else default_cache_dir()
    root = root / _PACKAGE_DIR
    manifest_path = root / _MANIFEST
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        package = SchemaPackage(root=root, manifest=manifest)
        package.invoice_xsd  # noqa: B018 - existence checks
        package.schematron  # noqa: B018
    except (OSError, ValueError, SchemaPackageError):
        return None
    return package


def _user_agent() -> str:
    from .. import __version__

    return f"e-fatura-ubl-tr/{__version__} (+https://github.com/demiralpozturk/e-fatura-ubl-tr)"


def _download(url: str, timeout: float) -> tuple[bytes, dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(_MAX_DOWNLOAD + 1)
            headers = {k.lower(): v for k, v in response.headers.items()}
    except OSError as exc:
        raise SchemaPackageError(f"could not download {url}: {exc}") from exc
    if len(data) > _MAX_DOWNLOAD:
        raise SchemaPackageError(f"download from {url} is unexpectedly large")
    return data, headers


def _discover_efatura_url(timeout: float) -> str:
    """Find the current e-Fatura package link on GİB's page (the file name changes)."""
    try:
        page, _ = _download(GIB_PAGE_URL, timeout)
    except SchemaPackageError:
        return EFATURA_PACKAGE_FALLBACK_URL
    text = page.decode("cp1254", errors="replace")
    match = re.search(r'href="\s*([^"]*e-FaturaPaketi[^"]*\.zip)\s*"', text, re.IGNORECASE)
    if not match:
        return EFATURA_PACKAGE_FALLBACK_URL
    absolute = urllib.parse.urljoin(GIB_PAGE_URL, match.group(1).strip())
    parts = urllib.parse.urlsplit(absolute)
    return str(
        urllib.parse.urlunsplit(parts._replace(path=urllib.parse.quote(parts.path, safe="/%")))
    )


def _extract(data: bytes, target: Path, wanted: re.Pattern[str]) -> int:
    """Safely extract matching members (no absolute paths, no ``..``)."""
    count = 0
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise SchemaPackageError("downloaded file is not a valid ZIP archive") from exc
    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if not wanted.search(name):
                continue
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts:
                raise SchemaPackageError(f"unsafe path in archive: {name!r}")
            destination = target.joinpath(*pure.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    return count


_UBLTR_MEMBERS = re.compile(r"(^|/)(xsdrt/.+\.xsd|xml/[^/]+\.xml)$", re.IGNORECASE)
_EFATURA_MEMBERS = re.compile(r"(^|/)schematron/[^/]+\.xml$", re.IGNORECASE)


def _install(
    ubltr: tuple[bytes, dict[str, Any]],
    efatura: tuple[bytes, dict[str, Any]],
    cache_dir: Path,
) -> SchemaPackage:
    cache_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="gib-", dir=cache_dir))
    try:
        if _extract(ubltr[0], staging / "ubltr", _UBLTR_MEMBERS) == 0:
            raise SchemaPackageError("UBL-TR package does not contain xsdrt/*.xsd files")
        if _extract(efatura[0], staging / "efatura", _EFATURA_MEMBERS) == 0:
            raise SchemaPackageError("e-Fatura package does not contain schematron files")
        manifest = {
            "ubltr": {**ubltr[1], "sha256": hashlib.sha256(ubltr[0]).hexdigest()},
            "efatura": {**efatura[1], "sha256": hashlib.sha256(efatura[0]).hexdigest()},
            "installed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "notice": (
                "Files in this directory were downloaded from GİB (ebelge.gib.gov.tr). "
                "They are not part of e-fatura-ubl-tr and are not redistributed by it."
            ),
        }
        (staging / _MANIFEST).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        package = SchemaPackage(root=staging, manifest=manifest)
        package.invoice_xsd  # noqa: B018 - validate the layout before activating it
        package.schematron  # noqa: B018
        final = cache_dir / _PACKAGE_DIR
        if final.exists():
            shutil.rmtree(final)
        staging.rename(final)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return SchemaPackage(root=final, manifest=manifest)


def fetch_package(
    cache_dir: str | Path | None = None,
    *,
    force: bool = False,
    timeout: float = 60.0,
    ubltr_url: str | None = None,
    efatura_url: str | None = None,
) -> SchemaPackage:
    """Return the cached package, downloading it from GİB first if needed.

    URLs can be overridden with the ``EFATURA_UBLTR_URL`` / ``EFATURA_PAKET_URL``
    environment variables (e.g. to use an internal mirror).
    """
    cache = Path(cache_dir) if cache_dir else default_cache_dir()
    if not force:
        existing = find_package(cache)
        if existing is not None:
            return existing
    ubltr_src = ubltr_url or os.environ.get("EFATURA_UBLTR_URL") or UBLTR_PACKAGE_URL
    efatura_src = (
        efatura_url or os.environ.get("EFATURA_PAKET_URL") or _discover_efatura_url(timeout)
    )
    ubltr_data, ubltr_headers = _download(ubltr_src, timeout)
    efatura_data, efatura_headers = _download(efatura_src, timeout)
    return _install(
        (ubltr_data, {"source": ubltr_src, "last_modified": ubltr_headers.get("last-modified")}),
        (
            efatura_data,
            {"source": efatura_src, "last_modified": efatura_headers.get("last-modified")},
        ),
        cache,
    )


def install_from_zips(
    ubltr_zip: str | Path, efatura_zip: str | Path, cache_dir: str | Path | None = None
) -> SchemaPackage:
    """Install the packages from ZIP files downloaded manually from ebelge.gib.gov.tr."""
    cache = Path(cache_dir) if cache_dir else default_cache_dir()
    ubltr_path, efatura_path = Path(ubltr_zip), Path(efatura_zip)
    return _install(
        (ubltr_path.read_bytes(), {"source": f"file:{ubltr_path.name}", "last_modified": None}),
        (
            efatura_path.read_bytes(),
            {"source": f"file:{efatura_path.name}", "last_modified": None},
        ),
        cache,
    )
