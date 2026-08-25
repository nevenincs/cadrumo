"""End-to-end tests for :mod:`dev.sanitizer._pipeline`.

These tests exercise the orchestrator on synthesised PDFs and
assert:

* The happy path produces deterministic output and an audit log
  with the expected ``Replacement`` and ``ScrubbedSurface`` rows.
* The signed-PDF refuse guard fires.
* The already-sanitised refuse guard fires when the source SHA
  is in :data:`SANITIZED_SHAS`, and can be opted out per-call.
* Public re-exports import cleanly from :mod:`dev.sanitizer`.
"""

from __future__ import annotations

import hashlib
import io
import logging
from importlib import import_module

import pikepdf
import pytest
from pydantic import SecretStr

from cadrumo.tests import FIXTURES_DIR

from .. import fixtures, sanitize_pdf
from .._records import NameReplacement, NifReplacement, TokenMap
from ..errors import AlreadySanitizedError, SanitizerSourceParseError, SignaturePresentError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# A committed justificante whose SHA-256 is catalogued in
# fixtures.SANITIZED_SHAS, so the already-sanitised refuse guard fires against
# it without any test-side patching of the known-SHA set.
#
# HONEST NOTE ON WHAT THIS NOW EXERCISES. The guard's purpose is "refuse a file
# that has already been through the pipeline", and this pointer used to name a
# genuine sanitiser OUTPUT. Every real sanitised render has since been withdrawn
# (each carried identity the pipeline never wrote), so no such file remains in
# the tree. What is left tests the MECHANISM -- a catalogued SHA is refused, and
# the refusal can be opted out of per call -- against a catalogued file that the
# pipeline never produced. The mechanism is the part with a regression risk; the
# provenance of the input is not something the guard reads.
#
# The coverage that withdrawal DID cost -- an end-to-end run over a document the
# sanitiser really processed -- was restored rather than accepted, in
# `test_residual_identity_absence.test_the_gate_and_the_sanitiser_agree_end_to_end`.
# It builds a pre-sanitisation specimen in memory, requires the residual gate to
# flag it, runs this pipeline over it, and requires the gate to find the output
# clean against the manifest this pipeline emitted. That is the seam no test
# covered before: every other proof supplies a hand-written sidecar.
_SANITISED_FIXTURE_PDF = FIXTURES_DIR / "justificantes" / "100" / "2022-0A.pdf"
_REAL_NIE_CANARY = "Y1234567X"
_REAL_NAME_CANARY = "PERSONA PRUEBA UNO"
_SYNTHETIC_NIE = "Y0000001S"
_SYNTHETIC_NAME = "APELLIDO APELLIDO NOMBRE"
_SENSITIVE_SOURCE_BASENAME = "12345678Z-sanitizer-source.pdf"


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
        b"BT /F1 12 Tf 100 700 Td (Y1234567X) Tj ET\nBT /F1 12 Tf 100 680 Td (PERSONA PRUEBA UNO) Tj ET\n",
    )
    pdf.docinfo["/Title"] = pikepdf.String(f"Justificante AEAT {_REAL_NIE_CANARY}")
    pdf.docinfo["/Author"] = pikepdf.String(_REAL_NAME_CANARY)
    with pdf.open_metadata(set_pikepdf_as_editor=False) as metadata:
        metadata["dc:title"] = f"Justificante AEAT {_REAL_NIE_CANARY}"
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
                    real=SecretStr(_REAL_NIE_CANARY),
                    synthetic=_SYNTHETIC_NIE,
                    surface_label="taxpayer NIE",
                ),
            ),
            name=(
                NameReplacement(
                    real=SecretStr(_REAL_NAME_CANARY),
                    synthetic=_SYNTHETIC_NAME,
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
        assert _REAL_NIE_CANARY.encode("utf-8") not in decompressed
        assert _REAL_NAME_CANARY.encode("utf-8") not in decompressed
        assert _SYNTHETIC_NIE.encode("utf-8") in decompressed
        assert _SYNTHETIC_NAME.encode("utf-8") in decompressed
        # Non-stream PDF bytes (DocInfo, XMP, trailer) must also be
        # cleartext-free.
        assert _REAL_NIE_CANARY.encode("utf-8") not in result_a.output_bytes
        assert _REAL_NAME_CANARY.encode("utf-8") not in result_a.output_bytes

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


class TestSourceParseErrorHygiene:
    """Source-open failures do not expose paths or raw parser diagnostics."""

    def test_source_open_failures_use_redacted_source_label(
        self,
        caplog: pytest.LogCaptureFixture,
        tmp_path,
    ) -> None:
        missing_pdf = tmp_path / _SENSITIVE_SOURCE_BASENAME
        parser_payload = b"not a pdf for 12345678Z-sanitizer-source.pdf"

        caplog.set_level(logging.DEBUG, logger=sanitize_pdf.__module__)
        cases = (
            (
                "missing-path",
                missing_pdf,
                ("FileNotFoundError",),
                (_SENSITIVE_SOURCE_BASENAME, str(missing_pdf)),
            ),
            (
                "invalid-bytes",
                parser_payload,
                ("PdfError",),
                (parser_payload.decode("utf-8"), "12345678Z"),
            ),
        )
        for case_id, source, (failure,), forbidden_fragments in cases:
            caplog.clear()
            with pytest.raises(SanitizerSourceParseError) as exc_info:
                sanitize_pdf(source, TokenMap())

            rendered = str(exc_info.value)
            for fragment in forbidden_fragments:
                assert fragment not in rendered, case_id
            assert rendered == "source PDF could not be opened for sanitization: <input-pdf>", case_id
            assert exc_info.value.context == {"source": "<input-pdf>", "failure": failure}, case_id
            assert exc_info.value.__cause__ is None, case_id
            assert exc_info.value.__context__ is None, case_id

            log_text = "\n".join(record.getMessage() for record in caplog.records)
            for fragment in forbidden_fragments:
                assert fragment not in log_text, case_id
            assert "source=<input-pdf>" in log_text, case_id
            assert f"failure={failure}" in log_text, case_id


class TestRefuseIfSigned:
    """The orchestrator refuses to modify signed PDFs."""

    def test_raises_when_signature_surface_present(self) -> None:
        for case_id in ("sigflags", "signature-field"):
            pdf = pikepdf.Pdf.new()
            pdf.add_blank_page(page_size=(612, 792))
            if case_id == "sigflags":
                pdf.Root["/AcroForm"] = pikepdf.Dictionary(
                    Fields=pikepdf.Array(),
                    SigFlags=3,
                )
            else:
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
    """Every public symbol is importable from :mod:`dev.sanitizer`."""

    def test_all_public_names_are_importable(self) -> None:
        sanitizer = import_module("dev.sanitizer")

        assert sanitizer.__all__, "package must declare a non-empty __all__"
        for name in sanitizer.__all__:
            attr = getattr(sanitizer, name, None)
            assert attr is not None, f"missing public re-export: {name}"
            # Hardening: empty __all__ would silently make the loop a no-op
            # and the test would still pass; pinning len > 0 above + the
            # per-symbol assert below makes both regressions detectable.
        assert len(sanitizer.__all__) >= 1
