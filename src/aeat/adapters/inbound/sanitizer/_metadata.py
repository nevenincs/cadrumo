"""DocInfo + XMP scrub for :mod:`aeat.adapters.inbound.sanitizer`.

Two surfaces, two scrubbers:

* :func:`scrub_docinfo` deletes the legacy DocInfo dictionary
  (``Title``, ``Subject``, ``Author``, ``Keywords``, ``Creator``,
  ``Producer``, ``CreationDate``, ``ModDate``, plus any custom
  keys). DocInfo is the original PDF metadata format; AEAT
  justificantes still write to it on every render, often with the
  CSV embedded in the ``Title`` and ``Subject`` strings.
* :func:`scrub_xmp` deletes the XMP packet (``Root.Metadata``)
  wholesale by default. Per-key deletion leaves orphan namespace
  declarations (`pikepdf/pikepdf#89`); the ``rewrite`` strategy is
  available for callers that must keep a minimal XMP packet, but
  the default is to drop it.

Both scrubbers also clear the PDF/A conformance claim — rewriting
``Tj`` operands invalidates PDF/A-1B's content/XMP alignment, so
leaving the claim intact would be dishonest.
"""

from __future__ import annotations

from typing import Literal

from pikepdf import Pdf

from ._records import SanitizationWarning, ScrubbedSurface


def scrub_docinfo(pdf: Pdf) -> ScrubbedSurface:
    """Drops the entire DocInfo dictionary from ``pdf``.

    Args:
        pdf: An open :class:`pikepdf.Pdf` instance whose DocInfo
            should be wiped. Modifies ``pdf`` in place.

    Returns:
        A :class:`ScrubbedSurface` carrying the count of DocInfo
        keys that were present before the wipe (zero when the
        document had no DocInfo dictionary).
    """
    info = pdf.trailer.get("/Info")
    if info is None:
        return ScrubbedSurface(surface="docinfo_other", count=0)
    count = len(list(info.keys()))
    # `del pdf.docinfo` is the documented pattern but pikepdf's
    # typing metadata omits the deleter; reach into the trailer
    # directly so the static checker stays happy.
    del pdf.trailer["/Info"]
    return ScrubbedSurface(surface="docinfo_other", count=count)


def scrub_xmp(
    pdf: Pdf,
    *,
    strategy: Literal["delete", "rewrite"] = "delete",
) -> tuple[ScrubbedSurface, tuple[SanitizationWarning, ...]]:
    """Drops or rewrites the XMP metadata packet on ``pdf``.

    Args:
        pdf: An open :class:`pikepdf.Pdf` instance whose XMP packet
            should be scrubbed. Modifies ``pdf`` in place.
        strategy: ``"delete"`` (default) wipes ``Root.Metadata``
            wholesale; ``"rewrite"`` clears every PII-bearing
            entry while keeping the packet intact (useful when a
            downstream consumer still asserts the packet exists).

    Returns:
        A 2-tuple of (counter, warnings). The counter is a :class:`ScrubbedSurface`
        recording how many top-level XMP entries were affected; the warning
        tuple contains :class:`SanitizationWarning` entries, including
        ``pdfa_claim_invalidated`` when the original packet declared PDF/A
        conformance.
    """
    root = pdf.Root
    if "/Metadata" not in root:
        return ScrubbedSurface(surface="xmp_packet", count=0), ()

    pdfa_claim_present = _packet_declares_pdfa(pdf)
    warnings: list[SanitizationWarning] = []
    if pdfa_claim_present:
        warnings.append(
            SanitizationWarning(
                code="pdfa_claim_invalidated",
                detail="Source PDF declared PDF/A conformance; the sanitiser's content "
                "rewrite invalidates the alignment so the claim is dropped.",
            ),
        )

    if strategy == "delete":
        del root.Metadata
        return (
            ScrubbedSurface(surface="xmp_packet", count=1),
            tuple(warnings),
        )

    cleared = _rewrite_xmp_in_place(pdf)
    return (
        ScrubbedSurface(surface="xmp_packet", count=cleared),
        tuple(warnings),
    )


# XMP namespace URIs — pikepdf returns keys in Clark-notation
# (``{namespace-uri}localname``) regardless of how callers set them.
# Match against the URI form so the scrubber catches every entry
# whose namespace-prefix the project considers PII-bearing.
_XMP_DC_NS = "{http://purl.org/dc/elements/1.1/}"
_XMP_PDF_NS = "{http://ns.adobe.com/pdf/1.3/}"
_XMP_XMP_NS = "{http://ns.adobe.com/xap/1.0/}"
_XMP_PDFAID_NS = "{http://www.aiim.org/pdfa/ns/id/}"

# Within each namespace, the local-name suffixes the scrubber wipes
# (a key matches when its Clark form starts with the namespace URI
# AND ends with one of these local names — every entry in the
# pdfaid namespace is wiped without a localname filter, since the
# entire claim is invalidated by the content rewrite).
_XMP_DC_PII_LOCALS = ("title", "description", "creator", "contributor", "subject", "rights")
_XMP_PDF_PII_LOCALS = ("Keywords", "Author", "Title", "Subject", "Creator", "Producer")
_XMP_XMP_PII_LOCALS = ("CreatorTool", "CreateDate", "ModifyDate", "MetadataDate")


def _packet_declares_pdfa(pdf: Pdf) -> bool:
    """Returns True when the XMP packet carries a ``pdfaid:*`` claim."""
    try:
        with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as metadata:
            for key in metadata:
                if key.startswith(_XMP_PDFAID_NS):
                    return True
    except (KeyError, AttributeError):
        return False
    return False


def _is_pii_xmp_key(key: str) -> bool:
    """Returns True when ``key`` (Clark notation) is in a PII surface."""
    if key.startswith(_XMP_PDFAID_NS):
        return True
    if key.startswith(_XMP_DC_NS):
        local = key[len(_XMP_DC_NS) :]
        return local in _XMP_DC_PII_LOCALS
    if key.startswith(_XMP_PDF_NS):
        local = key[len(_XMP_PDF_NS) :]
        return local in _XMP_PDF_PII_LOCALS
    if key.startswith(_XMP_XMP_NS):
        local = key[len(_XMP_XMP_NS) :]
        return local in _XMP_XMP_PII_LOCALS
    return False


def _rewrite_xmp_in_place(pdf: Pdf) -> int:
    """Clears PII-bearing keys from the XMP packet, preserves the packet.

    Args:
        pdf: An open PDF whose XMP metadata should be rewritten.

    Returns:
        The number of XMP entries that were cleared.
    """
    cleared = 0
    with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as metadata:
        keys = list(metadata)
        for key in keys:
            if _is_pii_xmp_key(key):
                del metadata[key]
                cleared += 1
    return cleared
