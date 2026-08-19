"""Reading an embedded payload leaves the document exactly as it was.

Two places in this tree open a PDF's attachment table. The sanitiser DELETES
from it, because an embedded file is an attack surface it exists to remove; the
e-invoice probe READS from it, because a ZUGFeRD or Factur-X invoice keeps its
structured XML there and dropping it would throw away the only exact data on the
document. Opposite intentions over the same table.

They are not, however, two implementations of one walk. Both are thin uses of
``pikepdf``'s own ``Pdf.attachments`` mapping -- there is no hand-rolled
traversal in either, and so nothing to factor out into a shared reader. What
needs guarding is not duplication but the INTERACTION: that the reading side
stays read-only, so a probe can never quietly alter a document the sanitiser is
responsible for, and that the stripping side still strips.

The failure this guards is specific and would be quiet: a read that spilled the
document to a temp file to open it would return exactly the right payload while
leaving evidence bytes on disk. Every assertion about the payload would still
pass.

Deliberately NOT asserted is that the input is unchanged in memory. The probe
takes ``bytes`` and returns a tuple, and ``bytes`` is immutable, so a
before/after comparison of the input cannot fail whatever the function does.
That assertion would read as coverage of the no-mutation claim while being
incapable of failing, which is worse than leaving the claim to the signature
that actually guarantees it.
"""

from __future__ import annotations

import contextlib
from io import BytesIO

import pytest

from cadrumo.adapters.inbound.einvoice._shape import iter_pdf_embedded_files
from cadrumo.core import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_XML_PAYLOAD = b"<?xml version='1.0'?><Invoice><ID>ZUGFERD-2024-1</ID></Invoice>"
_ATTACHMENT_NAME = "factur-x.xml"


def _pdf_with_embedded_xml() -> bytes:
    """A one-page PDF carrying an embedded XML file, built the real way."""
    import pikepdf
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    page = canvas.Canvas(buf, pagesize=A4)
    page.drawString(72, 760, "Factura")
    page.save()

    with pikepdf.Pdf.open(BytesIO(buf.getvalue())) as pdf:
        # The descriptive fields are named rather than defaulted. A real
        # Factur-X attachment carries them, and pikepdf's own stub declares
        # them required even though the binding defaults them -- so supplying
        # them makes the fixture both more faithful and checkable.
        pdf.attachments[_ATTACHMENT_NAME] = pikepdf.AttachedFileSpec(
            pdf,
            _XML_PAYLOAD,
            description="Factur-X invoice data",
            filename=_ATTACHMENT_NAME,
            mime_type="text/xml",
            creation_date="D:20240101000000Z",
            mod_date="D:20240101000000Z",
        )
        out = BytesIO()
        pdf.save(out)
        return out.getvalue()


def test_the_embedded_xml_payload_is_readable() -> None:
    """The probe recovers the exact bytes that were embedded.

    The premise of everything below: if the payload could not be read at all,
    the no-mutation assertion would hold trivially and prove nothing.
    """
    embedded = iter_pdf_embedded_files(_pdf_with_embedded_xml())

    assert [name for name, _ in embedded] == [_ATTACHMENT_NAME]
    assert [payload for _, payload in embedded] == [_XML_PAYLOAD]


def test_reading_the_payload_writes_nothing_to_disk(tmp_path) -> None:
    """The read side leaves no file behind.

    The in-memory half of "does not mutate" needs no test and must not pretend
    to have one: the probe takes ``bytes`` and returns a tuple, and ``bytes`` is
    immutable, so a before/after comparison of the input cannot fail no matter
    what the function does. Asserting it would look like coverage and be worth
    nothing.

    What CAN go wrong is the filesystem. ``pikepdf`` opens documents from paths
    as readily as from buffers, and an implementation that spilled the source to
    a temp file to open it -- or saved a normalised copy -- would return exactly
    the right payload while leaving evidence bytes on disk. That is a
    secure-storage violation rather than a correctness one, which is why it is
    worth a gate even though the payload assertions would never notice.
    """
    with contextlib.chdir(tmp_path):
        before = set(scan_directory(tmp_path, pattern="*", recursive=True))

        iter_pdf_embedded_files(_pdf_with_embedded_xml())

    assert set(scan_directory(tmp_path, pattern="*", recursive=True)) == before, (
        "reading an embedded payload left a file behind; evidence bytes must never reach disk outside encrypted storage"
    )


def test_the_sanitiser_still_strips_what_the_probe_can_read() -> None:
    """The two sides keep their opposite intentions.

    The probe reading attachments must not soften the sanitiser: a document that
    goes through stripping comes out with nothing left for the probe to find.
    Both directions are asserted together because the risk is that one is
    changed to accommodate the other.
    """
    import pikepdf

    from dev.sanitizer._dynamic import strip_attachments

    source = _pdf_with_embedded_xml()
    assert iter_pdf_embedded_files(source), "precondition: the probe can see the attachment"

    with pikepdf.Pdf.open(BytesIO(source)) as pdf:
        result = strip_attachments(pdf)
        out = BytesIO()
        pdf.save(out)
        scrubbed = out.getvalue()

    assert result.surface == "attachments"
    assert result.count == 1, "the sanitiser must report the attachment it removed"
    assert iter_pdf_embedded_files(scrubbed) == (), (
        "the sanitiser no longer strips embedded files the probe can read; an attack surface survived scrubbing"
    )


def test_a_pdf_without_attachments_reads_as_empty_rather_than_raising() -> None:
    """An ordinary invoice PDF is not an error at probe time.

    The probe runs on every document to decide its shape, so the overwhelmingly
    common case -- a PDF with no attachments at all -- must be an empty result
    and not an exception routed as a broken document.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    page = canvas.Canvas(buf, pagesize=A4)
    page.drawString(72, 760, "Factura sin adjuntos")
    page.save()

    assert iter_pdf_embedded_files(buf.getvalue()) == ()
    assert iter_pdf_embedded_files(b"not a pdf at all") == ()
