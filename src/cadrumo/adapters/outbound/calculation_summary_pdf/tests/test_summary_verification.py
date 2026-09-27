"""The document layer of summary verification, against every tamper it must name.

Each case starts from a genuine summary, changes exactly one thing the way an
editor, a forger or a viewer's re-save would, and asserts the reason the verifier
gives. The reader is the real one and the file is re-opened from its bytes, so a
check that only passed on in-memory objects would fail here.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pikepdf
import pytest
from pikepdf import Dictionary, Name

from .....application.modelo.calculation_report_certification import (
    CALCULATION_REPORT_SIGNING_CONTEXT,
    certification_signing_digest_hex,
)
from .....application.modelo.calculation_report_verification import (
    CalculationSummaryVerification,
    CalculationSummaryVerificationOutcome,
    CalculationSummaryVerificationReason,
    verify_calculation_summary,
)
from .....application.modelo.calculation_summary_pdf_ports import (
    CSV_ATTACHMENT_NAME,
    REPORT_ATTACHMENT_NAME,
    SIGNATURE_ATTACHMENT_NAME,
    STATEMENT_ATTACHMENT_NAME,
)
from .....core.ed25519_signing import sign_digest_hex
from .....core.external_constants import OutputLanguage
from .....core.hashing import sha256_hex
from .....tests.audited_process import run_audited_process
from ..summary_reading import read_calculation_summary_pdf
from .summary_report_support import MEASURED_VALUE, render_summary, synthetic_keypair, synthetic_report

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

Reason = CalculationSummaryVerificationReason
Outcome = CalculationSummaryVerificationOutcome

_KEY = synthetic_keypair()
_ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")


@pytest.fixture(scope="module")
def genuine() -> bytes:
    return render_summary(synthetic_report(OutputLanguage.ES), keypair=_KEY).payload


def _verify(payload: bytes, *, trusted: str | None = _KEY.public_key_hex) -> CalculationSummaryVerification:
    return verify_calculation_summary(payload, reader=read_calculation_summary_pdf, trusted_public_key_hex=trusted)


def _mutated(
    payload: bytes,
    change: Callable[[pikepdf.Pdf], None],
    *,
    linearize: bool = False,
    object_stream_mode: pikepdf.ObjectStreamMode = pikepdf.ObjectStreamMode.preserve,
) -> bytes:
    with pikepdf.open(io.BytesIO(payload)) as pdf:
        change(pdf)
        output = io.BytesIO()
        pdf.save(output, linearize=linearize, object_stream_mode=object_stream_mode)
    return output.getvalue()


def _attachment(pdf: pikepdf.Pdf, name: str) -> bytes:
    return pdf.attachments[name].get_file().read_bytes()


def _replace_attachment(pdf: pikepdf.Pdf, name: str, data: bytes) -> None:
    pdf.attachments[name].obj.EF.F.write(data)


def _replace_in_metadata(pdf: pikepdf.Pdf, old: bytes, new: bytes) -> None:
    packet = pdf.Root.Metadata.read_bytes()
    assert old in packet
    pdf.Root.Metadata.write(packet.replace(old, new))


def test_a_genuine_summary_verifies_against_its_pinned_key(genuine: bytes) -> None:
    verification = _verify(genuine)

    assert verification.outcome is Outcome.VERIFIED
    assert verification.reasons == ()
    assert verification.store_checked is False


def test_without_a_pinned_key_a_genuine_summary_is_only_valid_unpinned(genuine: bytes) -> None:
    assert _verify(genuine, trusted=None).outcome is Outcome.VALID_UNPINNED


def test_an_edited_csv_is_refused(genuine: bytes) -> None:
    def edit(pdf: pikepdf.Pdf) -> None:
        csv_bytes = _attachment(pdf, CSV_ATTACHMENT_NAME)
        _replace_attachment(pdf, CSV_ATTACHMENT_NAME, csv_bytes.replace(str(MEASURED_VALUE).encode(), b"1.00"))

    verification = _verify(_mutated(genuine, edit))

    assert verification.outcome is Outcome.REFUSED
    assert set(verification.reasons) == {Reason.CSV_DIGEST_MISMATCH, Reason.CSV_NOT_DERIVED_FROM_REPORT}


def test_an_edited_report_is_refused_even_with_its_metadata_digest_updated(genuine: bytes) -> None:
    def edit(pdf: pikepdf.Pdf) -> None:
        original = _attachment(pdf, REPORT_ATTACHMENT_NAME)
        edited = original.replace(f'"{MEASURED_VALUE}"'.encode(), b'"1.00"')
        assert edited != original
        _replace_attachment(pdf, REPORT_ATTACHMENT_NAME, edited)
        _replace_in_metadata(pdf, sha256_hex(original).encode(), sha256_hex(edited).encode())

    verification = _verify(_mutated(genuine, edit))

    assert verification.outcome is Outcome.REFUSED
    assert Reason.REPORT_DIGEST_MISMATCH in verification.reasons
    assert Reason.METADATA_MISMATCH in verification.reasons


def test_an_edited_metadata_identifier_is_refused(genuine: bytes) -> None:
    def edit(pdf: pikepdf.Pdf) -> None:
        statement = json.loads(_attachment(pdf, STATEMENT_ATTACHMENT_NAME))
        revision = statement["calculation_revision_id"].encode()
        _replace_in_metadata(pdf, revision, b"f" * len(revision))

    verification = _verify(_mutated(genuine, edit))

    assert verification.reasons == (Reason.METADATA_MISMATCH,)
    assert [check.detail for check in verification.checks if check.reason] == ["CalculationRevisionId"]


def test_two_figures_swapped_on_the_page_are_refused(genuine: bytes) -> None:
    def swap(pdf: pikepdf.Pdf) -> None:
        page = pdf.pages[0]
        instructions = list(pikepdf.parse_content_stream(page))
        shows = [index for index, item in enumerate(instructions) if str(item.operator) == "Tj"]
        first, second = next(
            (left, right)
            for left in shows
            for right in shows
            if left < right and bytes(instructions[left].operands[0]) != bytes(instructions[right].operands[0])
        )
        instructions[first], instructions[second] = (
            pikepdf.ContentStreamInstruction([instructions[second].operands[0]], pikepdf.Operator("Tj")),
            pikepdf.ContentStreamInstruction([instructions[first].operands[0]], pikepdf.Operator("Tj")),
        )
        page.obj.Contents = pdf.make_stream(pikepdf.unparse_content_stream(instructions))

    verification = _verify(_mutated(genuine, swap))

    assert verification.outcome is Outcome.REFUSED
    assert Reason.VISIBLE_LAYER_MISMATCH in verification.reasons


def test_an_annotation_laid_over_a_figure_is_refused(genuine: bytes) -> None:
    def overlay(pdf: pikepdf.Pdf) -> None:
        annotation = pdf.make_indirect(
            Dictionary(
                Type=Name.Annot,
                Subtype=Name.FreeText,
                Rect=[380, 300, 545, 320],
                Contents=pikepdf.String("9.999,00"),
                DA=pikepdf.String("/Helv 9 Tf 0 g"),
                F=4,
            ),
        )
        pdf.pages[0].obj.Annots = pdf.make_indirect(pikepdf.Array([annotation]))

    verification = _verify(_mutated(genuine, overlay))

    assert verification.reasons == (Reason.VISIBLE_LAYER_OVERLAY,)


def test_a_flipped_signature_byte_is_refused(genuine: bytes) -> None:
    def flip(pdf: pikepdf.Pdf) -> None:
        signature = bytearray(_attachment(pdf, SIGNATURE_ATTACHMENT_NAME))
        signature[0] ^= 0x01
        _replace_attachment(pdf, SIGNATURE_ATTACHMENT_NAME, bytes(signature))

    assert _verify(_mutated(genuine, flip)).reasons == (Reason.SIGNATURE_INVALID,)


def test_a_consistent_forgery_under_another_key_needs_a_pinned_key_to_refuse() -> None:
    """A forger with their own key produces a self-consistent file; only pinning refuses it."""
    forged = render_summary(synthetic_report(OutputLanguage.ES), keypair=synthetic_keypair("someone-else")).payload

    assert _verify(forged, trusted=None).outcome is Outcome.VALID_UNPINNED
    pinned = _verify(forged)
    assert pinned.outcome is Outcome.REFUSED
    assert pinned.reasons == (Reason.SIGNING_KEY_UNTRUSTED,)


def test_a_linearised_resave_changes_every_byte_and_still_verifies(genuine: bytes) -> None:
    resaved = _mutated(
        genuine,
        lambda _pdf: None,
        linearize=True,
        object_stream_mode=pikepdf.ObjectStreamMode.generate,
    )

    assert resaved != genuine
    assert _verify(resaved).outcome is Outcome.VERIFIED


def test_a_removed_attachment_is_named(genuine: bytes) -> None:
    def remove(pdf: pikepdf.Pdf) -> None:
        del pdf.attachments[CSV_ATTACHMENT_NAME]

    verification = _verify(_mutated(genuine, remove))

    assert verification.reasons == (Reason.ATTACHMENT_MISSING,)
    assert [check.detail for check in verification.checks if check.reason] == [CSV_ATTACHMENT_NAME]


def test_a_statement_re_encoded_and_re_signed_is_refused_as_not_canonical(genuine: bytes) -> None:
    def reencode(pdf: pikepdf.Pdf) -> None:
        statement = json.loads(_attachment(pdf, STATEMENT_ATTACHMENT_NAME))
        loose = json.dumps(statement, indent=2).encode("utf-8")
        signature = sign_digest_hex(
            private_key_hex=_KEY.private_key_hex, digest_hex=certification_signing_digest_hex(loose)
        )
        _replace_attachment(pdf, STATEMENT_ATTACHMENT_NAME, loose)
        _replace_attachment(pdf, SIGNATURE_ATTACHMENT_NAME, bytes.fromhex(signature))

    assert _verify(_mutated(genuine, reencode)).reasons == (Reason.STATEMENT_NOT_CANONICAL,)


def test_a_statement_of_another_schema_is_refused_as_unsupported(genuine: bytes) -> None:
    def rename(pdf: pikepdf.Pdf) -> None:
        statement = _attachment(pdf, STATEMENT_ATTACHMENT_NAME)
        _replace_attachment(
            pdf,
            STATEMENT_ATTACHMENT_NAME,
            statement.replace(b"certification/1", b"certification/9"),
        )

    assert _verify(_mutated(genuine, rename)).reasons == (Reason.UNSUPPORTED_STATEMENT_SCHEMA,)


def test_bytes_that_are_not_a_pdf_are_refused_as_unreadable() -> None:
    assert _verify(b"%PDF-1.7 truncated").reasons == (Reason.PDF_UNREADABLE,)


def test_a_pdf_without_the_product_metadata_is_not_a_cadrumo_report() -> None:
    plain = pikepdf.new()
    plain.add_blank_page()
    output = io.BytesIO()
    plain.save(output)

    assert _verify(output.getvalue()).reasons == (Reason.NOT_A_CADRUMO_REPORT,)


def _openssl_verifies(payload: bytes, workdir: Path) -> subprocess.CompletedProcess[str | bytes]:
    """Verify the signature with stock OpenSSL: the recipe a recipient without Cadrumo follows."""
    with pikepdf.open(io.BytesIO(payload)) as pdf:
        statement = _attachment(pdf, STATEMENT_ATTACHMENT_NAME)
        signature = _attachment(pdf, SIGNATURE_ATTACHMENT_NAME)
    public_key = bytes.fromhex(json.loads(statement)["signing_key"]["public_key_hex"])
    (workdir / "signed-input.bin").write_bytes(CALCULATION_REPORT_SIGNING_CONTEXT + statement)
    (workdir / "signature.bin").write_bytes(signature)
    (workdir / "public.der").write_bytes(_ED25519_SPKI_PREFIX + public_key)
    digest = workdir / "digest.bin"
    openssl = shutil.which("openssl")
    assert openssl is not None, "openssl is not on PATH"
    run_audited_process(
        [openssl, "dgst", "-sha256", "-binary", "-out", digest, workdir / "signed-input.bin"],
        check=True,
        capture_output=True,
    )
    return run_audited_process(
        [
            openssl,
            "pkeyutl",
            "-verify",
            "-pubin",
            "-keyform",
            "DER",
            "-inkey",
            workdir / "public.der",
            "-rawin",
            "-in",
            digest,
            "-sigfile",
            workdir / "signature.bin",
        ],
        capture_output=True,
    )


@pytest.mark.external_tool
def test_stock_openssl_verifies_the_signature_and_refuses_a_flipped_byte(genuine: bytes, tmp_path: Path) -> None:
    """The documented recipient recipe works with OpenSSL 3 alone."""
    assert _openssl_verifies(genuine, tmp_path).returncode == 0

    def flip(pdf: pikepdf.Pdf) -> None:
        signature = bytearray(_attachment(pdf, SIGNATURE_ATTACHMENT_NAME))
        signature[-1] ^= 0x80
        _replace_attachment(pdf, SIGNATURE_ATTACHMENT_NAME, bytes(signature))

    assert _openssl_verifies(_mutated(genuine, flip), tmp_path).returncode != 0
