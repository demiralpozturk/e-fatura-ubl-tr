"""Unit tests for the schematron interpreter using small synthetic rule files."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from efatura_ubl_tr.validation.schematron import Schematron

MAIN = """<?xml version="1.0" encoding="UTF-8"?>
<sch:schema xmlns="http://purl.oclc.org/dsdl/schematron"
            xmlns:sch="http://purl.oclc.org/dsdl/schematron">
  <sch:include href="lists.xml#codes"/>
  <sch:include href="abstract.xml#abstracts"/>
  <sch:ns prefix="d" uri="urn:test"/>
  <let name="type" value="'efatura'"/>
  <let name="rootName" value="local-name(/*)"/>

  <sch:rule context="//@unit">
    <sch:extends rule="UnitCheck"/>
  </sch:rule>

  <sch:pattern id="doc">
    <sch:rule context="d:Doc/d:Item[@special]">
      <sch:assert test="d:Price &gt; 100">special <sch:name/> needs a high price</sch:assert>
    </sch:rule>
    <sch:rule context="d:Doc/d:Item">
      <sch:extends rule="ItemCheck"/>
    </sch:rule>
    <sch:rule context="d:Doc">
      <sch:assert test="$type = 'efatura'">type is <sch:value-of select="$type"/></sch:assert>
      <sch:report test="count(d:Item) &gt; 2">too many items in <sch:value-of select="$rootName"/></sch:report>
      <sch:assert test="xs:date(d:Date) le xs:date('2030-01-01')">date too late</sch:assert>
    </sch:rule>
  </sch:pattern>
</sch:schema>
"""

LISTS = """<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron">
  <sch:pattern id="codes">
    <sch:let name="Units" value="',C62,KGM,'"/>
  </sch:pattern>
</sch:schema>
"""

ABSTRACT = """<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron">
  <sch:pattern id="abstracts">
    <sch:rule abstract="true" id="ItemCheck">
      <sch:assert test="matches(d:Code, '^[A-Z]{3}$')">bad code '<sch:value-of select="d:Code"/>'</sch:assert>
      <sch:assert test="d:Price castable as xs:decimal">price must be numeric</sch:assert>
    </sch:rule>
    <sch:rule abstract="true" id="UnitCheck">
      <sch:assert test="contains($Units, concat(',', ., ','))">unknown unit <sch:value-of select="."/></sch:assert>
    </sch:rule>
  </sch:pattern>
</sch:schema>
"""


@pytest.fixture
def schema_dir(tmp_path: Path) -> Path:
    (tmp_path / "main.xml").write_text(MAIN, encoding="utf-8")
    (tmp_path / "lists.xml").write_text(LISTS, encoding="utf-8")
    (tmp_path / "abstract.xml").write_text(ABSTRACT, encoding="utf-8")
    return tmp_path


def _doc(body: str) -> etree._ElementTree:
    return etree.fromstring(f'<Doc xmlns="urn:test">{body}</Doc>').getroottree()


GOOD = (
    '<Date>2026-11-20</Date><Item unit="C62"><Code>ABC</Code><Price>10</Price></Item>'
    '<Item special="1"><Code>x</Code><Price>500</Price></Item>'
)


def test_valid_document(schema_dir: Path) -> None:
    sch = Schematron(schema_dir / "main.xml")
    assert sch.rule_count == 4
    assert sch.validate(_doc(GOOD)) == []


def test_assert_messages_and_locations(schema_dir: Path) -> None:
    sch = Schematron(schema_dir / "main.xml")
    failures = sch.validate(
        _doc('<Date>2026-11-20</Date><Item unit="BAD"><Code>abcd</Code><Price>x</Price></Item>')
    )
    messages = sorted(f.message for f in failures)
    assert messages == ["bad code 'abcd'", "price must be numeric", "unknown unit BAD"]
    by_message = {f.message: f for f in failures}
    assert by_message["unknown unit BAD"].location.endswith("/@unit")
    assert by_message["bad code 'abcd'"].rule_id == "ItemCheck"
    assert by_message["bad code 'abcd'"].location == "/*/*[2]"


def test_first_matching_rule_wins(schema_dir: Path) -> None:
    # The special item has a lowercase code; ItemCheck must not run on it because
    # the more specific rule earlier in the same pattern already handled the node.
    failures = Schematron(schema_dir / "main.xml").validate(
        _doc('<Date>2026-11-20</Date><Item special="1"><Code>x</Code><Price>5</Price></Item>')
    )
    assert [f.message for f in failures] == ["special Item needs a high price"]


def test_report_and_xpath2_functions(schema_dir: Path) -> None:
    item = "<Item><Code>ABC</Code><Price>1</Price></Item>"
    failures = Schematron(schema_dir / "main.xml").validate(
        _doc(f"<Date>2031-05-05</Date>{item * 3}")
    )
    assert sorted(f.message for f in failures) == ["date too late", "too many items in Doc"]
    assert {f.kind for f in failures} == {"assert", "report"}


def test_parameter_override(schema_dir: Path) -> None:
    sch = Schematron(schema_dir / "main.xml", parameters={"type": "earchive"})
    failures = sch.validate(_doc(GOOD))
    assert [f.message for f in failures] == ["type is earchive"]


def test_xpath_error_is_reported(schema_dir: Path) -> None:
    failures = Schematron(schema_dir / "main.xml").validate(
        _doc("<Date>not-a-date</Date><Item><Code>ABC</Code><Price>1</Price></Item>")
    )
    assert len(failures) == 1
    assert failures[0].message.startswith("XPath error")


def test_missing_include_target(tmp_path: Path) -> None:
    (tmp_path / "main.xml").write_text(
        '<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron">'
        '<sch:include href="other.xml#nope"/></sch:schema>',
        encoding="utf-8",
    )
    (tmp_path / "other.xml").write_text(LISTS, encoding="utf-8")
    with pytest.raises(ValueError, match="include target not found"):
        Schematron(tmp_path / "main.xml")


def test_unknown_abstract_rule(tmp_path: Path) -> None:
    (tmp_path / "main.xml").write_text(
        '<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron"><sch:pattern>'
        '<sch:rule context="a"><sch:extends rule="Missing"/></sch:rule>'
        "</sch:pattern></sch:schema>",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="abstract rule 'Missing' not found"):
        Schematron(tmp_path / "main.xml")
