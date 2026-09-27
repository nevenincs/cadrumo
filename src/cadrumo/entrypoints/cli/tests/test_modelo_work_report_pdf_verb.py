"""CLI surface tests for the calculation summary PDF and ``work report-verify``.

Every case drives the live parser against a real encrypted profile and a real
sealed revision, so the document-format choice, the destination, the verdicts,
the exit status and each refusal are the ones an operator meets.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pikepdf
import pytest
from click.testing import Result

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....application.modelo.calculation_summary_pdf_ports import SIGNATURE_ATTACHMENT_NAME, STATEMENT_ATTACHMENT_NAME
from ....core.calculation_report_format import CalculationReportDocumentFormat
from ....core.optional_extras import PDF_EXTRA
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.repository import upsert_work_unit
from ....tests.cli_envelope import require_error_document
from ....tests.cli_envelope import unwrap_envelope_notices as _notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.optional_extra_absence import optional_extra_absent
from ._modelo_review_package_support import seed_exportable_modelo_revision
from ._strict_cli_fixture_support import binding_isolated_backend
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

__all__ = ["binding_isolated_backend"]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _seed_current_sealed_revision(*, operation: PinnedAuthorityOperation) -> str:
    """Seed a sealed Modelo 111 revision as its work unit's current one; return the work unit id."""
    work_unit_id, calculation_revision_id = seed_exportable_modelo_revision(
        input_values_by_casilla_id={},
        operation=operation,
    )
    repository = WorkUnitCatalogueRepository()
    catalogue = repository.load()
    work_unit = catalogue.get(work_unit_id)
    assert work_unit is not None
    repository.save(
        upsert_work_unit(
            catalogue,
            work_unit.model_copy(
                update={"current_calculation_revision_id": calculation_revision_id, "updated_at": datetime.now(UTC)},
            ),
        ),
    )
    return work_unit_id


def _summary(work_unit_id: str, output: Path, *extra: str) -> Result:
    return _invoke(
        (
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "report",
            work_unit_id,
            "--document-format",
            CalculationReportDocumentFormat.PDF.value,
            "--output",
            str(output),
            *extra,
        ),
    )


def _verify(path: Path, *extra: str) -> Result:
    return _invoke(("--format", "json", "app", "modelo", "work", "report-verify", str(path), *extra))


def _signed_by(path: Path) -> str:
    with pikepdf.open(path) as pdf:
        statement = pdf.attachments[STATEMENT_ATTACHMENT_NAME].get_file().read_bytes()
    return str(json.loads(statement)["signing_key"]["public_key_hex"])


@pytest.fixture
def summary_path(tmp_path: Path, operation: PinnedAuthorityOperation) -> Path:
    work_unit_id = _seed_current_sealed_revision(operation=operation)
    output = tmp_path / "modelo-111-summary.pdf"
    result = _summary(work_unit_id, output)
    assert result.exit_code == 0, result.output
    return output


def test_the_summary_lands_and_names_the_key_it_is_signed_with(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit_id = _seed_current_sealed_revision(operation=operation)
    output = tmp_path / "modelo-111-summary.pdf"

    result = _summary(work_unit_id, output)

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    landed = output.read_bytes()
    assert landed.startswith(b"%PDF-1.7")
    assert payload["document_format"] == CalculationReportDocumentFormat.PDF.value
    assert payload["file_sha256"] == hashlib.sha256(landed).hexdigest()
    assert payload["signing_key_fingerprint"] == hashlib.sha256(bytes.fromhex(_signed_by(output))).hexdigest()
    codes = {notice["code"] for notice in _notices(result.output)}
    assert "modelo.work.report.local_calculation_not_official_evidence" in codes


def test_an_existing_file_is_refused_and_replaced_only_on_explicit_choice(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit_id = _seed_current_sealed_revision(operation=operation)
    output = tmp_path / "modelo-111-summary.pdf"
    output.write_bytes(b"an earlier summary")

    refused = _summary(work_unit_id, output)

    assert refused.exit_code != 0
    assert "existing file" in str(require_error_document(refused.output)["error"]["message"])
    assert output.read_bytes() == b"an earlier summary"
    replaced = _summary(work_unit_id, output, "--replace")
    assert replaced.exit_code == 0, replaced.output
    assert output.read_bytes().startswith(b"%PDF")


def test_a_summary_verifies_against_the_store_and_exits_zero(summary_path: Path) -> None:
    result = _verify(summary_path)

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["operation"] == "modelo.work.report_verify"
    assert payload["outcome"] == "verified"
    assert payload["store_checked"] is True
    assert payload["reasons"] == []
    assert {check["layer"] for check in payload["checks"]} == {"document", "store"}
    assert all(check["reason"] is None for check in payload["checks"])


def test_a_document_only_check_is_unpinned_until_a_key_is_trusted(summary_path: Path) -> None:
    unpinned = _verify(summary_path, "--document-only")
    pinned = _verify(summary_path, "--document-only", "--trusted-key", _signed_by(summary_path))

    assert unpinned.exit_code == 0, unpinned.output
    assert _payload(unpinned.output)["outcome"] == "valid_unpinned"
    assert _payload(unpinned.output)["store_checked"] is False
    assert "modelo.work.report_verify.valid_unpinned" in {notice["code"] for notice in _notices(unpinned.output)}
    assert pinned.exit_code == 0, pinned.output
    assert _payload(pinned.output)["outcome"] == "verified"


def test_a_tampered_summary_is_refused_with_a_non_zero_exit(summary_path: Path, tmp_path: Path) -> None:
    tampered = tmp_path / "tampered.pdf"
    with pikepdf.open(summary_path) as pdf:
        signature = bytearray(pdf.attachments[SIGNATURE_ATTACHMENT_NAME].get_file().read_bytes())
        signature[0] ^= 0x01
        pdf.attachments[SIGNATURE_ATTACHMENT_NAME].obj.EF.F.write(bytes(signature))
        pdf.save(tampered)

    result = _verify(tampered, "--document-only")

    assert result.exit_code == 1
    payload = _payload(result.output)
    assert payload["outcome"] == "refused"
    assert payload["reasons"] == ["signature_invalid"]


def test_another_trusted_key_refuses_the_summary(summary_path: Path) -> None:
    result = _verify(summary_path, "--document-only", "--trusted-key", "ab" * 32)

    assert result.exit_code == 1
    assert _payload(result.output)["reasons"] == ["signing_key_untrusted"]


def test_a_malformed_trusted_key_and_a_missing_file_are_refused(summary_path: Path, tmp_path: Path) -> None:
    malformed = _verify(summary_path, "--trusted-key", "not-a-key")
    missing = _verify(tmp_path / "absent.pdf")

    assert malformed.exit_code != 0
    assert "64" in malformed.output
    assert missing.exit_code != 0
    assert "absent.pdf" in missing.output


@pytest.fixture
def pdf_extra_absent() -> Iterator[None]:
    """Run the production spec probe against a real absence of the ``pdf`` extra."""
    with optional_extra_absent(PDF_EXTRA):
        yield


@pytest.mark.usefixtures("pdf_extra_absent")
@pytest.mark.parametrize(
    ("language", "phrase"),
    (("es", "complemento opcional"), ("en", "optional")),
)
def test_without_the_pdf_extra_the_summary_is_refused_before_the_store_is_read(
    tmp_path: Path,
    language: str,
    phrase: str,
) -> None:
    """A work unit that does not exist proves the refusal precedes any store read."""
    output = tmp_path / "summary.pdf"

    refused = _summary("0" * 64, output, "--output-language", language)

    assert refused.exit_code != 0
    error = require_error_document(refused.output)["error"]
    assert error["code"] == "REFUSED_CALCULATION_SUMMARY_PDF_UNAVAILABLE"
    assert phrase in error["message"]
    assert "cadrumo[pdf]" in error["message"]
    assert not output.exists()


def test_verification_needs_no_pdf_extra(summary_path: Path, pdf_extra_absent: None) -> None:
    result = _verify(summary_path, "--document-only")

    assert result.exit_code == 0, result.output
    assert _payload(result.output)["outcome"] == "valid_unpinned"
