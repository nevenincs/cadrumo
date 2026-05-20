"""End-to-end tests for :mod:`aeat.adapters.inbound.sanitizer._pipeline`.

These tests exercise the orchestrator on synthesised PDFs and
assert:

* The happy path produces deterministic output and an audit log
  with the expected ``Replacement`` and ``ScrubbedSurface`` rows.
* The signed-PDF refuse guard fires.
* The already-sanitised refuse guard fires when the source SHA
  is in :data:`SANITIZED_SHAS`, and can be opted out per-call.
* Public re-exports import cleanly from :mod:`aeat.adapters.inbound.sanitizer`.
"""

from __future__ import annotations

import hashlib
import io
from importlib import import_module

import pikepdf
import pytest
from pydantic import SecretStr

from aeat.tests import FIXTURES_DIR

from . import fixtures, sanitize_pdf
from ._errors import AlreadySanitizedError, SignaturePresentError
from ._records import NameReplacement, NifReplacement, TokenMap

pytestmark = [pytest.mark.unit, pytest.mark.domain_inbound]

# A real committed sanitised justificante; its SHA-256 is catalogued in
# fixtures.SANITIZED_SHAS, so the already-sanitised refuse guard fires
# against it without any test-side patching of the known-SHA set.
_SANITISED_FIXTURE_PDF = FIXTURES_DIR / "justificantes" / "100" / "2021-0A.pdf"


def _decompressed_content_bytes(pdf_bytes: bytes) -> bytes:
    """Returns the concatenated decompressed content streams of every page.

    pikepdf round-trips the source through FlateDecode by default,
    so cleartext lives in the *decompressed* stream — the
    representation an attacker running ``pdftotext`` / ``pdfgrep``
    sees. The adversarial-absence test must operate on this view.
    """
    pdf = pikepdf.Pdf.open(io.BytesIO(pdf_bytes))
    chunks: list[bytes] = []
    for page in pdf.pages:
        contents = page.obj.get("/Contents")
        if contents is None:
            continue
        if isinstance(contents, pikepdf.Array):
            for index in range(len(contents)):
                chunks.append(bytes(contents[index].read_bytes()))
        else:
            chunks.append(bytes(contents.read_bytes()))
    return b"\n".join(chunks)


def _build_real_world_like_pdf() -> bytes:
    """Builds a single-page PDF that mimics the AEAT capture shape.

    Carries:
      * A literal-string Tj operand with a real-style NIF.
      * A populated DocInfo dictionary including the NIF in Title.
      * An XMP packet with PDF/A-1B claim + dc:title bearing the NIF.
      * One embedded JS OpenAction (defensive scrub).
      * An OCG layer dictionary (defensive scrub).
    """
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    pdf.pages[0].contents_add(
        b"BT /F1 12 Tf 100 700 Td (Y4113523X) Tj ET\nBT /F1 12 Tf 100 680 Td (WOOTSCH GERGELY DOMOKOS) Tj ET\n",
    )
    pdf.docinfo["/Title"] = pikepdf.String("Justificante AEAT Y4113523X")
    pdf.docinfo["/Author"] = pikepdf.String("WOOTSCH GERGELY DOMOKOS")
    with pdf.open_metadata(set_pikepdf_as_editor=False) as metadata:
        metadata["dc:title"] = "Justificante AEAT Y4113523X"
        metadata["pdfaid:part"] = "1"
        metadata["pdfaid:conformance"] = "B"
    pdf.Root["/OpenAction"] = pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS="alert();")
    pdf.Root["/OCProperties"] = pikepdf.Dictionary(OCGs=pikepdf.Array(), D=pikepdf.Dictionary())

    buffer = io.BytesIO()
    pdf.save(buffer)
    return buffer.getvalue()


class TestSanitizePdfHappyPath:
    """Happy-path: one input, two cleartext values, every surface scrubbed."""

    def test_scrubs_all_surfaces_and_runs_deterministically(self) -> None:
        source = _build_real_world_like_pdf()
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr("Y4113523X"),
                    synthetic="Y0000001S",
                    surface_label="taxpayer NIE",
                ),
            ),
            name=(
                NameReplacement(
                    real=SecretStr("WOOTSCH GERGELY DOMOKOS"),
                    synthetic="APELLIDO APELLIDO NOMBRE",
                    surface_label="taxpayer name",
                ),
            ),
        )

        result_a = sanitize_pdf(source, mapping)
        result_b = sanitize_pdf(source, mapping)

        # Determinism: byte-equal across two runs.
        assert result_a.output_bytes == result_b.output_bytes
        assert result_a.output_sha256 == result_b.output_sha256

        # The cleartext does not leak into the decompressed content
        # streams (the view a ``pdftotext`` / ``pdfgrep`` attacker
        # sees) and the synthetic landed in its place.
        decompressed = _decompressed_content_bytes(result_a.output_bytes)
        assert b"Y4113523X" not in decompressed
        assert b"WOOTSCH GERGELY DOMOKOS" not in decompressed
        assert b"Y0000001S" in decompressed
        assert b"APELLIDO APELLIDO NOMBRE" in decompressed
        # Non-stream PDF bytes (DocInfo, XMP, trailer) must also be
        # cleartext-free.
        assert b"Y4113523X" not in result_a.output_bytes
        assert b"WOOTSCH GERGELY DOMOKOS" not in result_a.output_bytes

        # Every audit-log surface is recorded (presence or absence).
        scrubbed_surfaces = {row.surface for row in result_a.surfaces_scrubbed}
        for required in (
            "attachments",
            "javascript",
            "open_action",
            "annotation_drop",
            "optional_content_groups",
            "acroform_field_value",
            "page_thumbnail",
            "outlines",
            "page_labels",
            "structtree_dropped",
            "docinfo_other",
            "xmp_packet",
        ):
            assert required in scrubbed_surfaces, f"missing surface: {required}"

        # Replacement rows reference the cleartext via SHA only.
        assert all(row.real_sha256 != "" for row in result_a.replacements_applied)
        assert any(row.synthetic == "Y0000001S" for row in result_a.replacements_applied)

        # The output round-trips through pikepdf.
        re_opened = pikepdf.Pdf.open(io.BytesIO(result_a.output_bytes))
        assert len(re_opened.pages) == 1


class TestRefuseIfSigned:
    """The orchestrator refuses to modify signed PDFs."""

    def test_raises_when_sigflags_set(self) -> None:
        pdf = pikepdf.Pdf.new()
        pdf.add_blank_page(page_size=(612, 792))
        pdf.Root["/AcroForm"] = pikepdf.Dictionary(
            Fields=pikepdf.Array(),
            SigFlags=3,
        )
        buffer = io.BytesIO()
        pdf.save(buffer)

        with pytest.raises(SignaturePresentError, match=r"signature|SigFlags|signed|AcroForm"):
            sanitize_pdf(buffer.getvalue(), TokenMap())

    def test_raises_when_signature_field_present(self) -> None:
        pdf = pikepdf.Pdf.new()
        pdf.add_blank_page(page_size=(612, 792))
        sig_field = pikepdf.Dictionary(FT=pikepdf.Name.Sig, T="signature")
        pdf.Root["/AcroForm"] = pikepdf.Dictionary(Fields=pikepdf.Array([sig_field]))
        buffer = io.BytesIO()
        pdf.save(buffer)

        with pytest.raises(SignaturePresentError, match=r"signature|SigFlags|signed|AcroForm"):
            sanitize_pdf(buffer.getvalue(), TokenMap())


class TestRefuseIfAlreadySanitized:
    """The orchestrator refuses re-sanitising a known-sanitised SHA.

    Both tests feed a real committed sanitised fixture whose SHA-256 is
    genuinely a member of :data:`SANITIZED_SHAS` -- the guard is
    exercised against the real catalogue, with no monkeypatching of the
    known-SHA set.
    """

    def test_raises_when_source_sha_in_known_set(self) -> None:
        source = _SANITISED_FIXTURE_PDF.read_bytes()
        sha = hashlib.sha256(source).hexdigest()
        assert sha in fixtures.SANITIZED_SHAS, "fixture SHA must already be catalogued"

        with pytest.raises(AlreadySanitizedError, match=r"already|sanitized") as exc:
            sanitize_pdf(source, TokenMap())
        assert exc.value.source_sha256 == sha

    def test_can_opt_out_via_flag(self) -> None:
        source = _SANITISED_FIXTURE_PDF.read_bytes()
        sha = hashlib.sha256(source).hexdigest()
        assert sha in fixtures.SANITIZED_SHAS, "fixture SHA must already be catalogued"

        result = sanitize_pdf(source, TokenMap(), refuse_if_already_sanitized=False)
        assert result.source_sha256 == sha


class TestPublicReexports:
    """Every public symbol is importable from :mod:`aeat.adapters.inbound.sanitizer`."""

    def test_all_public_names_are_importable(self) -> None:
        sanitizer = import_module(__package__ or "aeat.adapters.inbound.sanitizer")

        assert sanitizer.__all__, "package must declare a non-empty __all__"
        for name in sanitizer.__all__:
            attr = getattr(sanitizer, name, None)
            assert attr is not None, f"missing public re-export: {name}"
            # Hardening: empty __all__ would silently make the loop a no-op
            # and the test would still pass; pinning len > 0 above + the
            # per-symbol assert below makes both regressions detectable.
        assert len(sanitizer.__all__) >= 1
