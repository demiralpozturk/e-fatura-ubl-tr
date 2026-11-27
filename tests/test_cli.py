from __future__ import annotations

import json
from pathlib import Path

import pytest
from lxml import etree

from efatura_ubl_tr import __version__
from efatura_ubl_tr.cli import EXIT_ERROR, EXIT_INVALID, EXIT_OK, main
from efatura_ubl_tr.validation import find_package

from .conftest import EXAMPLE_FILES

EXAMPLE = next(p for p in EXAMPLE_FILES if p.name.startswith("01-"))


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_build_to_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "fatura.xml"
    assert main(["build", str(EXAMPLE), "-o", str(out), "--summary"]) == EXIT_OK
    root = etree.parse(str(out)).getroot()
    assert etree.QName(root).localname == "Invoice"
    err = capsys.readouterr().err
    assert "ödenecek 21387.50 TRY" in err


def test_build_to_stdout(capfdbinary: pytest.CaptureFixture[bytes]) -> None:
    assert main(["build", str(EXAMPLE), "--compact"]) == EXIT_OK
    out = capfdbinary.readouterr().out
    assert out.startswith(b"<?xml")


def test_build_reports_invalid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["supplier"]["vkn"] = "1234567891"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    assert main(["build", str(bad)]) == EXIT_INVALID
    assert "invalid VKN" in capsys.readouterr().err

    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["number"] = "BAD"
    bad.write_text(json.dumps(data), encoding="utf-8")
    assert main(["build", str(bad)]) == EXIT_INVALID
    assert "GİB format" in capsys.readouterr().err


def test_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["preview", "does-not-exist.xml"]) == EXIT_ERROR
    assert "file not found" in capsys.readouterr().err


def test_preview_from_xml_and_json(tmp_path: Path) -> None:
    xml = tmp_path / "f.xml"
    assert main(["build", str(EXAMPLE), "-o", str(xml)]) == EXIT_OK
    assert main(["preview", str(xml)]) == EXIT_OK
    assert "<!doctype html>" in (tmp_path / "f.html").read_text(encoding="utf-8")
    html_out = tmp_path / "direct.html"
    assert main(["preview", str(EXAMPLE), "-o", str(html_out)]) == EXIT_OK
    assert "AOY2026000000001" in html_out.read_text(encoding="utf-8")


def test_words(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["words", "1500,25", "--currency", "usd"]) == EXIT_OK
    assert capsys.readouterr().out.strip() == "Bin Beş Yüz ABD Doları Yirmi Beş Sent"
    assert main(["words", "abc"]) == EXIT_ERROR


def test_check_id(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check-id", "1234567890"]) == EXIT_OK
    assert main(["check-id", "12345678950"]) == EXIT_OK
    assert main(["check-id", "11111111111"]) == EXIT_OK
    assert main(["check-id", "1234567891"]) == EXIT_INVALID
    out = capsys.readouterr().out
    assert "valid VKN" in out and "valid TCKN" in out and "nihai tüketici" in out


def test_validate_without_package(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    xml = tmp_path / "f.xml"
    main(["build", str(EXAMPLE), "-o", str(xml)])
    code = main(["validate", str(xml), "--no-download", "--cache-dir", str(tmp_path / "empty")])
    assert code == EXIT_ERROR
    assert "efatura schemas fetch" in capsys.readouterr().err


def test_schemas_info_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["schemas", "info", "--cache-dir", str(tmp_path)]) == EXIT_INVALID
    assert "no GİB package cached" in capsys.readouterr().out


def test_schemas_fetch_requires_both_zips(tmp_path: Path) -> None:
    assert main(["schemas", "fetch", "--ubltr-zip", "x.zip", "--cache-dir", str(tmp_path)]) == (
        EXIT_ERROR
    )


@pytest.mark.skipif(find_package() is None, reason="GİB schema package not cached")
def test_validate_with_gib_package(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    xml = tmp_path / "f.xml"
    main(["build", str(EXAMPLE), "-o", str(xml)])
    assert main(["validate", str(xml), "--no-download"]) == EXIT_OK
    assert "VALID" in capsys.readouterr().out
    assert main(["validate", str(xml), "--no-download", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True and payload["schematron_checked"] is True
    assert main(["validate", str(xml), "--no-download", "--require-signature"]) == EXIT_INVALID
