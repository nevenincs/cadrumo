"""Hardened XML read boundary for externally-authored e-invoice documents.

Every byte parsed here arrives from outside the host: an operator's attachment,
a supplier's emailed invoice, a payload embedded in a PDF. The document is
therefore treated as hostile input, and the parse is bounded on all four axes
an XML reader can be attacked on.

* **Entity resolution and external DTD loading are disabled**, which is what
  ``defusedxml`` is for and why this module exists rather than each parser
  reaching for ``ElementTree`` directly. An XXE probe cannot read a local file
  or open a network connection.
* **Payload size is bounded** before parsing begins, so a multi-gigabyte
  document is refused rather than buffered.
* **Nesting depth is bounded** after parsing, which is the residual
  billion-laughs-adjacent risk once entity expansion is already off: a deeply
  nested document can still exhaust the recursion budget of a naive walker.

``defusedxml`` is already a declared ``[project.dependencies]`` entry, so exact
structured reading costs no new dependency, no model, no GPU and no extra --
which is what lets it live in the deterministic core rather than behind the
inference boundary.
"""

from __future__ import annotations

from xml.etree.ElementTree import Element

from defusedxml.ElementTree import ParseError as _DefusedParseError
from defusedxml.ElementTree import fromstring as _defused_fromstring

from ....core.errors import CadrumoError

__all__ = ["MAX_XML_DEPTH", "MAX_XML_PAYLOAD_BYTES", "EInvoiceXmlParseError", "parse_hardened_xml"]

MAX_XML_PAYLOAD_BYTES = 32 * 1024 * 1024
"""Largest e-invoice payload accepted. Two orders of magnitude above any real
EN16931 or Facturae document, so it refuses abuse without refusing a genuine
invoice carrying embedded attachments."""

MAX_XML_DEPTH = 100
"""Deepest element nesting accepted. EN16931 and Facturae both bottom out well
under 20; 100 leaves generous headroom while still bounding a walker."""


class EInvoiceXmlParseError(CadrumoError, ValueError):
    """Raised when an e-invoice XML payload is refused at the read boundary.

    Deliberately a refusal rather than a partial result. A structured reader
    that returned half a record on malformed input would be worse than a model:
    it would look exact while being wrong.

    Derives from BOTH bases, and each one earns its place.
    :class:`~cadrumo.core.errors.CadrumoError` binds the class to the error
    registry, so the refusal an operator meets carries a stable code and a
    translated message rather than a bare traceback -- which is what a
    read-boundary refusal of an operator-supplied file has to do.
    ``ValueError`` is kept so a pydantic validator can still absorb it, the
    same pairing the fixture-preparation sanitiser uses for the same reason
    (``SanitizerValidationError``).

    The alternative the hygiene gate offers -- declaring a
    ``__bare_base_rationale__`` and staying outside the registry -- would be a
    claim that this refusal is deliberately unregistered. That is false here:
    it is operator-facing, it names a file the operator supplied, and there is
    no reason it should reach them less legibly than every other refusal at
    this boundary.
    """


def _depth(element: Element) -> int:
    """Return the maximum nesting depth under ``element``, iteratively.

    Iterative on purpose: a recursive measurement of a hostile document would
    hit the interpreter's recursion limit before it could report the very
    condition it exists to detect.
    """
    deepest = 1
    stack: list[tuple[Element, int]] = [(element, 1)]
    while stack:
        node, level = stack.pop()
        deepest = max(deepest, level)
        if level > MAX_XML_DEPTH:
            return level
        stack.extend((child, level + 1) for child in node)
    return deepest


def parse_hardened_xml(payload: bytes) -> Element:
    """Parse ``payload`` with entity resolution and external DTDs disabled.

    Args:
        payload: Raw document bytes from outside the host.

    Returns:
        The parsed root :class:`~xml.etree.ElementTree.Element`.

    Raises:
        EInvoiceXmlParseError: If the payload is empty, exceeds
            :data:`MAX_XML_PAYLOAD_BYTES`, is not well-formed XML, resolves a
            forbidden entity, or nests deeper than :data:`MAX_XML_DEPTH`.
    """
    if not payload:
        raise EInvoiceXmlParseError("empty XML payload")
    if len(payload) > MAX_XML_PAYLOAD_BYTES:
        raise EInvoiceXmlParseError(
            f"XML payload of {len(payload)} bytes exceeds the {MAX_XML_PAYLOAD_BYTES}-byte read limit",
        )
    try:
        root = _defused_fromstring(payload)
    except _DefusedParseError as exc:
        raise EInvoiceXmlParseError(f"malformed XML: {exc}") from exc
    except Exception as exc:
        # defusedxml raises its own EntityDeclared / DTDForbidden family for a
        # hostile document. Every one of them is a refusal, and none may be
        # allowed to surface as a partially-read record.
        raise EInvoiceXmlParseError(f"refused XML payload: {type(exc).__name__}: {exc}") from exc
    depth = _depth(root)
    if depth > MAX_XML_DEPTH:
        raise EInvoiceXmlParseError(f"XML nesting depth {depth} exceeds the limit of {MAX_XML_DEPTH}")
    return root
