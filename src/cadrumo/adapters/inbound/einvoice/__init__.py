"""Deterministic readers for structured electronic-invoice documents.

An e-invoice that already carries a machine-readable record is *read*, not
inferred. Parsing it is exact, model-free and costs nothing marginal: it runs on
the already-declared ``defusedxml``, needs no GPU, adds no licence exposure and
is available on a default install with no optional extra enabled.

That is why these readers sit in the deterministic core rather than behind the
inference boundary, and why they sit in ``adapters/inbound/`` beside the six
sibling packages that already parse externally-authored formats -- ``pdf``,
``financial``, ``borrador``, ``censo``, ``declaracion`` and ``justificante``.

The routing order this package enables is itself a control, and is recorded as
one so a later change optimising for latency does not discard it: **a document
carrying a structured record reaches no model at all**, which makes prompt
injection categorically impossible for that document rather than merely
mitigated. The corresponding hazard moves to the XML reader rather than
disappearing, and is bounded there -- see :mod:`._xml`.

Two properties are load-bearing and neither is an accuracy claim. The reader
**fails loudly**: a malformed document raises :class:`EInvoiceXmlParseError` and
yields no record, where a model handed the same bytes returns a confident,
plausible, wrong invoice. And it is **three to five orders of magnitude
faster** than a vision read of the same document.
"""

from __future__ import annotations

from ._parsers import FacturaeInvoiceClass, ParsedEInvoice, ParsedEInvoiceLine, parse_einvoice_document
from ._record_batch import (
    AeatParty,
    AeatRecordBatch,
    AeatRecordFamily,
    ParsedAeatRecord,
    RefusedAeatRecord,
    parse_aeat_record_batch,
)
from ._shape import EMBEDDED_XML_SUFFIXES, iter_pdf_embedded_files, probe_document_shape
from ._xml import MAX_XML_DEPTH, MAX_XML_PAYLOAD_BYTES, EInvoiceXmlParseError, parse_hardened_xml

__all__ = [
    "EMBEDDED_XML_SUFFIXES",
    "MAX_XML_DEPTH",
    "MAX_XML_PAYLOAD_BYTES",
    "AeatParty",
    "AeatRecordBatch",
    "AeatRecordFamily",
    "EInvoiceXmlParseError",
    "FacturaeInvoiceClass",
    "ParsedAeatRecord",
    "ParsedEInvoice",
    "ParsedEInvoiceLine",
    "RefusedAeatRecord",
    "iter_pdf_embedded_files",
    "parse_aeat_record_batch",
    "parse_einvoice_document",
    "parse_hardened_xml",
    "probe_document_shape",
]
