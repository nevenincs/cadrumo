"""Derive a :class:`DocumentShape` from a document's own bytes.

Never consults a declared MIME type, a filename suffix, or any caller-supplied
label. The whole point of the probe is that those three all answered
``application/pdf`` for a ZUGFeRD invoice whose embedded XML carried the
complete invoice, so the most exactly readable document in the corpus was
routed to prose extraction.

The probe is read-only and allocates nothing outside memory. XML detection runs
through the hardened parser in :mod:`._xml`, so a probe against a hostile
document cannot resolve an external entity or expand a billion-laughs payload.
"""

from __future__ import annotations

from io import BytesIO
from xml.etree.ElementTree import Element

from ....core import DocumentShape, detect_image_media_type
from ....core.errors import CoreValidationError
from ._xml import EInvoiceXmlParseError, parse_hardened_xml

__all__ = ["EMBEDDED_XML_SUFFIXES", "iter_pdf_embedded_files", "probe_document_shape"]

_PDF_MAGIC = b"%PDF-"


def _is_image(data: bytes) -> bool:
    """Return whether the bytes are an image this product can actually read.

    Delegates to :func:`~core.detect_image_media_type`, the single sniffer, so
    the probe's notion of "image" and the vision transport's cannot diverge.
    A local magic-byte tuple here diverged in BOTH directions: it omitted WebP,
    which it structurally could not express because a single-offset
    ``startswith`` cannot match a magic split across offsets 0 and 8, so a WebP
    receipt probed ``UNKNOWN`` and was refused at admission despite
    :class:`~core.ImageMediaType` carrying a member for exactly that case; and
    it admitted BMP and TIFF, which the sniffer refuses, so those passed
    admission and raised later against evidence already accepted.
    """
    try:
        detect_image_media_type(data)
    except CoreValidationError:
        return False
    return True


EMBEDDED_XML_SUFFIXES: tuple[str, ...] = (
    "factur-x.xml",
    "zugferd-invoice.xml",
    "xrechnung.xml",
    "factura.xml",
)
"""Filenames the EN16931 PDF/A-3 profiles use for the embedded invoice.

Used only to *rank* candidates when a PDF carries several attachments. A
document is never classified on the filename alone -- the payload is parsed and
its root element is what decides, so a mislabelled attachment cannot promote a
non-invoice into a structured shape.
"""

# Root-element local names, by syntax. Matched on the local name so a document
# is classified identically whichever namespace prefix it happens to use.
_CII_ROOTS = frozenset({"CrossIndustryInvoice", "CrossIndustryDocument"})
_UBL_ROOTS = frozenset({"Invoice", "CreditNote"})
_FACTURAE_ROOTS = frozenset({"Facturae"})

# AEAT record-batch payload elements, by family. These are matched ANYWHERE in
# the document rather than at the root, because AEAT submissions arrive in two
# shapes: wrapped in a SOAP `Envelope`, or as a bare payload element. Both ship
# in the wild -- the gisce SII captures are SOAP-wrapped while the josemmo
# VERI*FACTU records are bare -- so a root-only test recognises half of them
# and reports the rest as UNKNOWN.
_SII_PAYLOAD_ELEMENTS = frozenset(
    {
        "SuministroLRFacturasEmitidas",
        "SuministroLRFacturasRecibidas",
        "BajaLRFacturasEmitidas",
        "BajaLRFacturasRecibidas",
        "SuministroLRBienesInversion",
        "BajaLRBienesInversion",
        "SuministroLRAgenciasViajes",
        "BajaLRAgenciasViajes",
        "SuministroLRCobrosMetalico",
        "BajaLRCobrosMetalico",
        "SuministroLROperacionesSeguros",
        "BajaLROperacionesSeguros",
        "SuministroLRDetOperacionIntracomunitaria",
        "BajaLRDetOperacionIntracomunitaria",
        "SuministroLRCobrosEmitidas",
        "SuministroLRInmueblesAdicionales",
        "SuministroLRPagosRecibidas",
    },
)
"""Every top-level record family the SII envelope schema declares.

All seventeen, not only the two this reader claims. Recognising the SHAPE is
separate from supporting the FAMILY: a document we decline to read must still
be identified, so the refusal can name what it is instead of reporting
unrecognised bytes.
"""

_VERIFACTU_PAYLOAD_ELEMENTS = frozenset(
    {"RegFactuSistemaFacturacion", "RegistroAlta", "RegistroAnulacion"},
)
"""The VERI*FACTU envelope plus the two bare record elements.

The bare forms are listed because real captures ship a lone ``RegistroAlta``
or ``RegistroAnulacion`` with no envelope around it.
"""


def _local_name(tag: str) -> str:
    """Return an element tag's local name, dropping any ``{namespace}`` prefix."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _xml_shape(payload: bytes) -> DocumentShape | None:
    """Classify ``payload`` by its XML root element, or ``None`` when it is not one.

    Returns ``None`` for anything that does not parse as XML or whose root is
    not a recognised invoice root. A refusal from the hardened parser is
    deliberately swallowed *here* and only here: the probe's contract is to
    report a shape, and an unparseable payload simply is not a structured
    document. The parsers themselves re-parse and refuse loudly, so nothing is
    silently accepted downstream.
    """
    try:
        root = parse_hardened_xml(payload)
    except EInvoiceXmlParseError:
        return None
    name = _local_name(root.tag)
    if name in _CII_ROOTS:
        return DocumentShape.XML_CII
    if name in _FACTURAE_ROOTS:
        return DocumentShape.XML_FACTURAE
    if name in _UBL_ROOTS:
        # UBL shares the bare local name "Invoice" with nothing else in the
        # recognised set, but the namespace confirms it rather than assuming.
        return DocumentShape.XML_UBL if "urn:oasis:names" in root.tag or "}" not in root.tag else None
    return _aeat_record_batch_shape(root)


def _aeat_record_batch_shape(root: Element) -> DocumentShape | None:
    """Classify an AEAT record submission by LOCATING its payload element.

    Searched rather than read off the root, because a submission may be wrapped
    in a SOAP ``Envelope`` or arrive as a bare payload element and both forms
    ship. The search is over the payload element NAMES the two AEAT envelope
    schemas declare, so an arbitrary SOAP message carrying something else stays
    unrecognised rather than being classified as a tax record.

    Checked only after the single-invoice roots, so a document that is both --
    which none is -- would keep its more precise classification.
    """
    for node in root.iter():
        local = _local_name(node.tag)
        if local in _SII_PAYLOAD_ELEMENTS:
            return DocumentShape.XML_AEAT_SII
        if local in _VERIFACTU_PAYLOAD_ELEMENTS:
            return DocumentShape.XML_AEAT_VERIFACTU
    return None


def iter_pdf_embedded_files(pdf_bytes: bytes) -> tuple[tuple[str, bytes], ...]:
    """Return ``(filename, payload)`` for every embedded file in a PDF.

    The read half of the embedded-file walk the sanitiser already performs.
    The fixture-preparation sanitiser strips these; this
    reads them without mutating anything, so a ZUGFeRD payload is visible to
    a parser.

    Returns an empty tuple when the bytes are not a readable PDF or carry no
    attachments -- an unreadable document is not an error at probe time.
    """
    try:
        import pikepdf
    except ImportError:  # pragma: no cover - pikepdf is a declared dependency
        return ()
    try:
        with pikepdf.Pdf.open(BytesIO(pdf_bytes)) as pdf:
            found: list[tuple[str, bytes]] = []
            for name in pdf.attachments:
                attachment = pdf.attachments[name]
                stream = getattr(attachment, "get_file", None)
                data = stream().read_bytes() if callable(stream) else None
                if data:
                    found.append((str(name), bytes(data)))
            return tuple(found)
    except Exception:
        # pikepdf raises a wide family for malformed input. A document that
        # cannot be opened simply has no visible embedded files; the caller's
        # own reader refuses it loudly later.
        return ()


def _rank_embedded(entry: tuple[str, bytes]) -> int:
    """Rank an embedded file so profile-named invoice payloads are tried first."""
    name = entry[0].lower()
    for index, candidate in enumerate(EMBEDDED_XML_SUFFIXES):
        if name.endswith(candidate):
            return index
    return len(EMBEDDED_XML_SUFFIXES)


def probe_document_shape(data: bytes, *, has_text_layer: bool | None = None) -> DocumentShape:
    """Return the :class:`DocumentShape` of ``data``, derived from its bytes.

    Args:
        data: The document's full in-memory bytes.
        has_text_layer: Whether the caller has already established that a PDF
            carries extractable text. Supplied by callers that have run the
            text-layer extractor, so the probe never re-runs it. When omitted a
            PDF with no embedded structured record resolves to
            :attr:`DocumentShape.PDF_TEXT_LAYER`, the conservative answer: it
            routes to text extraction, which then reports emptiness itself
            rather than the probe pre-judging a scan.

    Returns:
        The derived shape, or :attr:`DocumentShape.UNKNOWN` when the bytes match
        nothing recognised. ``UNKNOWN`` is always refused by callers, never
        guessed into a neighbouring shape.
    """
    if not data:
        return DocumentShape.UNKNOWN
    if data.startswith(_PDF_MAGIC):
        for name, payload in sorted(iter_pdf_embedded_files(data), key=_rank_embedded):
            del name
            if _xml_shape(payload) is not None:
                return DocumentShape.PDF_EMBEDDED_XML
        if has_text_layer is False:
            return DocumentShape.PDF_SCAN
        return DocumentShape.PDF_TEXT_LAYER
    if _is_image(data):
        return DocumentShape.IMAGE
    shape = _xml_shape(data)
    return shape if shape is not None else DocumentShape.UNKNOWN
