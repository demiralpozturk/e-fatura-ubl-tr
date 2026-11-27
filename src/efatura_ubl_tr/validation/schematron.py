"""A small ISO Schematron interpreter for GİB's UBL-TR rules.

GİB's schematron (``UBL-TR_Main_Schematron.xml`` + includes) uses XPath 2.0
functions such as ``matches()`` and ``xs:date()``. lxml's built-in
``isoschematron`` only supports XSLT 1.0, so this module evaluates the rules
directly with `elementpath <https://pypi.org/project/elementpath/>`_ (XPath 2.0).

Supported subset – everything GİB's files use:

* ``sch:ns``, global ``sch:let`` (schema- and pattern-level), ``sch:include``
  with ``file#id`` fragments, ``sch:pattern``, ``sch:rule`` (``context``,
  ``abstract``/``id``), ``sch:extends``, ``sch:assert``, ``sch:report``,
  ``sch:name`` and ``sch:value-of`` in messages.
* ISO semantics: within one pattern a node is handled only by the first rule
  whose context matches it.
* Rules placed directly under ``sch:schema`` (outside any pattern) are run as
  an implicit extra pattern.

The ``type`` variable that GİB declares as a parameter (``efatura`` /
``earchive``) can be overridden with ``parameters={"type": "earchive"}``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import elementpath
from elementpath import XPath2Parser, XPathContext
from lxml import etree

__all__ = ["Schematron", "SchematronFailure"]

SCH = "http://purl.oclc.org/dsdl/schematron"
_Q = f"{{{SCH}}}"


@dataclass(frozen=True)
class SchematronFailure:
    """A failed ``assert`` (or a fired ``report``)."""

    pattern: str
    rule_context: str
    rule_id: str | None
    test: str
    message: str
    location: str
    #: "assert" or "report"
    kind: str = "assert"


@dataclass
class _Check:
    kind: str  # "assert" | "report"
    test: str
    message_parts: list[Any]  # str | ("name", path) | ("value-of", select)
    rule_id: str | None


@dataclass
class _Rule:
    context: str
    checks: list[_Check] = field(default_factory=list)
    extends: list[str] = field(default_factory=list)


@dataclass
class _Pattern:
    id: str
    rules: list[_Rule] = field(default_factory=list)


def _load(path: Path) -> etree._Element:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_comments=True)
    return etree.parse(str(path), parser).getroot()


class Schematron:
    """Compile a schematron schema once and validate many documents with it."""

    def __init__(self, path: str | Path, *, parameters: dict[str, str] | None = None) -> None:
        self.path = Path(path)
        self.namespaces: dict[str, str] = {}
        self.patterns: list[_Pattern] = []
        self._lets: list[tuple[str, str]] = []
        self._abstract: dict[str, list[_Check]] = {}
        self._parameters = dict(parameters or {})

        loose = _Pattern(id="(rules outside patterns)")
        for child in self._expand(_load(self.path), self.path.parent):
            if child.tag == _Q + "ns":
                self.namespaces[child.get("prefix", "")] = child.get("uri", "")
            elif child.tag == _Q + "let":
                self._lets.append((child.get("name", ""), child.get("value", "")))
            elif child.tag == _Q + "pattern":
                self._read_pattern(child)
            elif child.tag == _Q + "rule":
                rule = self._read_rule(child)
                if rule is not None:
                    loose.rules.append(rule)
        if loose.rules:
            self.patterns.append(loose)
        self._resolve_extends()

        self._parser = XPath2Parser(namespaces=self.namespaces)
        self._compile_cache: dict[str, Any] = {}

    @property
    def rule_count(self) -> int:
        return sum(len(p.rules) for p in self.patterns)

    # -- loading ----------------------------------------------------------------------

    def _expand(self, root: etree._Element, base: Path) -> list[etree._Element]:
        """Children of *root* with ``sch:include`` replaced by the referenced elements."""
        out: list[etree._Element] = []
        for child in root:
            if not isinstance(child.tag, str):
                continue
            if child.tag != _Q + "include":
                out.append(child)
                continue
            href = child.get("href", "")
            file_part, _, fragment = href.partition("#")
            target = _load(base / file_part)
            if fragment:
                found = target.xpath("//*[@id=$id]", id=fragment)
                if not found:
                    raise ValueError(f"schematron include target not found: {href}")
                target = found[0]
            if target.tag == _Q + "schema":
                out.extend(self._expand(target, base))
            else:
                out.append(target)
        return out

    def _read_pattern(self, element: etree._Element) -> None:
        pattern = _Pattern(id=element.get("id") or element.get("name") or "pattern")
        for child in element:
            if child.tag == _Q + "let":
                self._lets.append((child.get("name", ""), child.get("value", "")))
            elif child.tag == _Q + "rule":
                rule = self._read_rule(child)
                if rule is not None:
                    pattern.rules.append(rule)
        if pattern.rules:
            self.patterns.append(pattern)

    def _read_rule(self, element: etree._Element) -> _Rule | None:
        rule_id = element.get("id")
        rule = _Rule(context=element.get("context", ""))
        for child in element:
            if child.tag in (_Q + "assert", _Q + "report"):
                rule.checks.append(
                    _Check(
                        kind="assert" if child.tag == _Q + "assert" else "report",
                        test=child.get("test", "true()"),
                        message_parts=self._message_parts(child),
                        rule_id=rule_id,
                    )
                )
            elif child.tag == _Q + "extends":
                rule.extends.append(child.get("rule", ""))
        if element.get("abstract") == "true":
            if rule_id:
                self._abstract[rule_id] = rule.checks
            return None
        return rule

    @staticmethod
    def _message_parts(element: etree._Element) -> list[Any]:
        parts: list[Any] = [element.text or ""]
        for child in element:
            if child.tag == _Q + "name":
                parts.append(("name", child.get("path")))
            elif child.tag == _Q + "value-of":
                parts.append(("value-of", child.get("select", ".")))
            parts.append(child.tail or "")
        return parts

    def _resolve_extends(self) -> None:
        for pattern in self.patterns:
            for rule in pattern.rules:
                for name in rule.extends:
                    if name not in self._abstract:
                        raise ValueError(f"abstract rule {name!r} not found")
                    rule.checks.extend(self._abstract[name])
                rule.extends.clear()

    # -- evaluation -------------------------------------------------------------------

    def _compiled(self, expr: str) -> Any:
        token = self._compile_cache.get(expr)
        if token is None:
            token = self._parser.parse(expr)
            self._compile_cache[expr] = token
        return token

    def validate(self, document: etree._ElementTree | etree._Element) -> list[SchematronFailure]:
        """Return the failed asserts / fired reports for *document* (empty list = valid)."""
        tree = document if isinstance(document, etree._ElementTree) else document.getroottree()
        doc_node = XPathContext(tree).root  # build elementpath's node tree only once

        def ctx(item: Any, variables: dict[str, Any]) -> XPathContext:
            return XPathContext(doc_node, item=item, variables=variables)

        variables: dict[str, Any] = {}
        for name, value in self._lets:
            if name in self._parameters:
                variables[name] = self._parameters[name]
            else:
                variables[name] = self._compiled(value).evaluate(ctx(None, dict(variables)))

        failures: list[SchematronFailure] = []
        for pattern in self.patterns:
            fired: set[int] = set()
            for rule in pattern.rules:
                expr = rule.context if rule.context.startswith("/") else "//" + rule.context
                for node in self._compiled(expr).select(ctx(None, variables)):
                    if id(node) in fired:
                        continue
                    fired.add(id(node))
                    for check in rule.checks:
                        message = self._check(check, node, ctx(node, variables))
                        if message is None:
                            continue
                        failures.append(
                            SchematronFailure(
                                pattern=pattern.id,
                                rule_context=rule.context,
                                rule_id=check.rule_id,
                                test=check.test,
                                message=" ".join(message.split()),
                                location=_location(node, tree),
                                kind=check.kind,
                            )
                        )
        return failures

    def _check(self, check: _Check, node: Any, context: XPathContext) -> str | None:
        token = self._compiled(check.test)
        try:
            result = bool(token.boolean_value(token.evaluate(context)))
        except elementpath.ElementPathError as exc:
            return f"XPath error while evaluating {check.test!r}: {exc}"
        failed = (not result) if check.kind == "assert" else result
        if not failed:
            return None
        text: list[str] = []
        for part in check.message_parts:
            if isinstance(part, str):
                text.append(part)
            elif part[0] == "name":
                text.append(_node_name(node))
            else:
                try:
                    text.append(_stringify(self._compiled(part[1]).evaluate(context)))
                except elementpath.ElementPathError:
                    text.append("?")
        return "".join(text)


def _stringify(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(_stringify(v) for v in value)
    string_value = getattr(value, "string_value", None)
    if isinstance(string_value, str):
        return string_value
    return "" if value is None else str(value)


def _node_name(node: Any) -> str:
    elem = getattr(node, "elem", None)
    if isinstance(elem, etree._Element):
        local = etree.QName(elem).localname
        return f"{elem.prefix}:{local}" if elem.prefix else local
    name = getattr(node, "name", None)
    return etree.QName(name).localname if name else "?"


def _location(node: Any, tree: etree._ElementTree) -> str:
    elem = getattr(node, "elem", None)
    if isinstance(elem, etree._Element):
        return str(tree.getpath(elem))
    parent = getattr(node, "parent", None)
    parent_elem = getattr(parent, "elem", None)
    name = getattr(node, "name", None)
    if isinstance(parent_elem, etree._Element) and name:
        return f"{tree.getpath(parent_elem)}/@{etree.QName(name).localname}"
    return "?"
