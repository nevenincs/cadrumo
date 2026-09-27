"""CLI surface tests for ``aeat app modelo work report``.

Every case drives the live parser against a real encrypted profile, a real work
unit and a real sealed revision, so the subject, the document-format choice, the
destination and each refusal are the ones an operator meets.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....application.modelo.calculation_report import local_calculation_report_notice
from ....application.modelo.calculation_report_document import CALCULATION_REPORT_CSV_PREAMBLE_PREFIX
from ....core.calculation_report_format import CalculationReportDocumentFormat
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.repository import upsert_work_unit
from ....tests.cli_envelope import require_error_document
from ....tests.cli_envelope import unwrap_envelope_notices as _notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ._modelo_review_package_support import seed_exportable_modelo_revision
from ._strict_cli_fixture_support import binding_isolated_backend
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

__all__ = ["binding_isolated_backend"]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _seed_current_sealed_revision(*, operation: PinnedAuthorityOperation) -> tuple[str, str]:
    """Seed a sealed Modelo 111 revision and make it the work unit's current one.

    The work target's *current* revision is what the report addresses, exactly as
    ``work review`` does, so the pointer is advanced here the way calculating the
    revision would have advanced it.
    """
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
                update={
                    "current_calculation_revision_id": calculation_revision_id,
                    "updated_at": datetime.now(UTC),
                },
            ),
        ),
    )
    return work_unit_id, calculation_revision_id


def _report(work_unit_id: str, output: Path, *extra: str) -> Result:
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
            CalculationReportDocumentFormat.CSV.value,
            "--output",
            str(output),
            *extra,
        ),
    )


def _table_rows(payload: str) -> tuple[dict[str, str], ...]:
    table = "\n".join(
        line for line in payload.splitlines() if not line.startswith(CALCULATION_REPORT_CSV_PREAMBLE_PREFIX)
    )
    return tuple({str(column): str(cell) for column, cell in row.items()} for row in csv.DictReader(io.StringIO(table)))


def test_the_report_lands_at_the_chosen_path_described_by_its_own_facts(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The JSON result names the revision, the file and the report content digest."""
    work_unit_id, calculation_revision_id = _seed_current_sealed_revision(operation=operation)
    output = tmp_path / "modelo-111-2026-1T-report.csv"

    result = _report(work_unit_id, output)

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    landed = output.read_bytes()
    assert payload["operation"] == "modelo.work.report"
    assert payload["modelo"] == "111"
    assert payload["filing_year"] == 2026
    assert payload["work_unit_id"] == work_unit_id
    assert payload["calculation_revision_id"] == calculation_revision_id
    assert payload["document_format"] == CalculationReportDocumentFormat.CSV.value
    assert payload["output_path"] == str(output)
    assert payload["byte_size"] == len(landed)
    assert payload["file_sha256"] == hashlib.sha256(landed).hexdigest()
    assert len(payload["report_sha256"]) == 64
    assert payload["report_sha256"] != payload["file_sha256"]
    assert payload["row_count"] == len(_table_rows(landed.decode("utf-8")))
    assert payload["report_language"] == OutputLanguage.ES.value
    assert payload["local_calculation_notice"] == local_calculation_report_notice(OutputLanguage.ES)
    # The isolated backend keeps its encrypted store under the same temporary
    # root, so the assertion is that no SECOND report-shaped file appeared.
    assert [path.name for path in tmp_path.glob("*.csv")] == [output.name]


def test_the_result_says_the_artefact_is_not_official_aeat_evidence(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The notice channel carries the local-calculation warning, and the file states it."""
    work_unit_id, _ = _seed_current_sealed_revision(operation=operation)
    output = tmp_path / "modelo-111-report.csv"

    result = _report(work_unit_id, output)

    assert result.exit_code == 0, result.output
    codes = {notice["code"] for notice in _notices(result.output)}
    assert "modelo.work.report.local_calculation_not_official_evidence" in codes
    assert local_calculation_report_notice(OutputLanguage.ES) in output.read_text(encoding="utf-8")


def test_an_existing_file_is_refused_untouched_and_replaced_only_on_explicit_choice(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A path that already holds a file is refused, and --replace is the way past it."""
    work_unit_id, _ = _seed_current_sealed_revision(operation=operation)
    output = tmp_path / "modelo-111-report.csv"
    output.write_bytes(b"an earlier report")

    refused = _report(work_unit_id, output)

    assert refused.exit_code != 0
    assert "existing file" in str(require_error_document(refused.output)["error"]["message"])
    assert output.read_bytes() == b"an earlier report"

    replaced = _report(work_unit_id, output, "--replace")

    assert replaced.exit_code == 0, replaced.output
    assert _payload(replaced.output)["file_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


def test_a_missing_parent_directory_is_refused_before_any_file_is_written(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The destination is checked before the report is assembled."""
    work_unit_id, _ = _seed_current_sealed_revision(operation=operation)
    output = tmp_path / "absent" / "modelo-111-report.csv"

    refused = _report(work_unit_id, output)

    assert refused.exit_code != 0
    assert "parent directory does not exist" in str(require_error_document(refused.output)["error"]["message"])
    assert not output.parent.exists()
    assert list(tmp_path.rglob("*.csv")) == []


def test_a_draft_revision_is_refused_and_writes_nothing(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A revision still in borrador states nothing settled, so no report is written."""
    work_unit_id, calculation_revision_id = _seed_current_sealed_revision(operation=operation)
    revisions = CalculationRevisionCatalogueRepository()
    catalogue = revisions.load()
    sealed = catalogue.revisions[calculation_revision_id]
    revisions.save(
        upsert_calculation_revision(
            catalogue,
            sealed.model_copy(
                update={
                    "state": CalculationRevisionState.BORRADOR,
                    "verified_at": None,
                    "verified_by": None,
                },
            ),
        ),
    )
    output = tmp_path / "modelo-111-draft-report.csv"

    refused = _report(work_unit_id, output)

    assert refused.exit_code != 0
    assert not output.exists()


def test_a_work_target_without_a_calculation_is_refused_with_its_address(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A work unit that was never calculated has nothing to report."""
    work_unit_id, _ = seed_exportable_modelo_revision(
        input_values_by_casilla_id={},
        operation=operation,
    )
    output = tmp_path / "modelo-111-report.csv"

    refused = _report(work_unit_id, output)

    assert refused.exit_code != 0
    message = str(require_error_document(refused.output)["error"]["message"])
    assert work_unit_id in message
    assert "111" in message
    assert not output.exists()


def test_the_requested_output_language_is_the_report_language(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The artefact and the messages about it are in one language, the operator's."""
    work_unit_id, _ = _seed_current_sealed_revision(operation=operation)
    spanish_out = tmp_path / "modelo-111-es.csv"
    english_out = tmp_path / "modelo-111-en.csv"

    spanish = _report(work_unit_id, spanish_out)
    english = _report(work_unit_id, english_out, "--output-language", OutputLanguage.EN.value)

    assert spanish.exit_code == 0, spanish.output
    assert english.exit_code == 0, english.output
    spanish_payload = _payload(spanish.output)
    english_payload = _payload(english.output)
    assert spanish_payload["report_language"] == OutputLanguage.ES.value
    assert english_payload["report_language"] == OutputLanguage.EN.value
    assert english_payload["local_calculation_notice"] == local_calculation_report_notice(OutputLanguage.EN)
    assert english_payload["local_calculation_notice"] != spanish_payload["local_calculation_notice"]
    assert english_payload["local_calculation_notice"] in english_out.read_text(encoding="utf-8")
    # The language is a header fact the digest covers, so two languages of one
    # revision are two different reports rather than one report shown twice.
    assert english_payload["report_sha256"] != spanish_payload["report_sha256"]


def test_the_document_format_choice_is_the_closed_declared_set(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A format the product does not serialise is refused by the parser, not at the sink."""
    work_unit_id, _ = _seed_current_sealed_revision(operation=operation)
    output = tmp_path / "modelo-111-report.pdf"

    refused = _invoke(
        (
            "app",
            "modelo",
            "work",
            "report",
            work_unit_id,
            "--document-format",
            "pdf",
            "--output",
            str(output),
        ),
    )

    assert refused.exit_code != 0
    assert not output.exists()
