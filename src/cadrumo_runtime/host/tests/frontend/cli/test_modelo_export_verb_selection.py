"""CLI surface tests for revision selection and refusals of ``aeat app modelo export``."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_cli_backend
from cadrumo.application.modelo.operation_shared import MODELO_EXPORT_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_export_contracts import ModeloExportRequest
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.errors.error_codes import get_registered_error_code_by_code
from cadrumo.core.i18n.render import tr
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    EditionBelowFilingGrade,
    authored_editions_below_filing_grade,
)
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevisionState,
)
from cadrumo.entrypoints.cli.tests.modelo_review_package_support import seed_exportable_modelo_revision
from cadrumo.entrypoints.operation_composition import compose_operation_dependencies
from cadrumo.tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope

from .modelo_export_verb_support import (
    MODELO_111_INPUTS,
    clear_export_profile_surnames,
    export_operator,
    invoke,
    seed_exportable_modelo_202_pre_b2_revision,
    seed_modelo_111_revisions,
    seed_verified_revision_without_inputs,
    set_emilio_legal_entity_export_profile,
    set_export_profile_name,
)
from .modelo_profile_seed import seed_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

__all__ = ["export_operator", "isolated_cli_backend", "seed_profile"]


def _export_through_the_operation(
    *, work_unit_id: str, calculation_revision_id: str, output_path: Path, operation: PinnedAuthorityOperation
) -> tuple[OperationTerminalCondition | None, str | None]:
    """Submit the registered export operation the TUI uses and return its terminal condition and code."""

    async def run() -> tuple[OperationTerminalCondition | None, str | None]:
        services = compose_operation_dependencies(authority_operation=operation)
        try:
            submitted = await services.submission.submit(
                OperationRequest(
                    definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
                    subject_ref=work_unit_id,
                    payload=ModeloExportRequest(
                        calculation_revision_id=calculation_revision_id,
                        output_path=str(output_path),
                        actor="Emilio",
                    ),
                ),
                actor_ref="operator:export-parity",
            )
            await services.submission.start(submitted.receipt.operation_id)
            await services.submission.settled(submitted.receipt.operation_id)
            observed = await services.observation.observe(
                OperationObservationRequestV1(
                    operation_id=submitted.receipt.operation_id, after_cursor=0, page_limit=64
                )
            )
            assert isinstance(observed, OperationObservationSuccessV1)
            projection = observed.projection
            return projection.terminal_condition, projection.refusal_ref or projection.failure_error_code
        finally:
            await services.shutdown()

    return asyncio.run(run())


def test_the_export_operation_and_the_command_line_reach_the_same_gate_for_one_revision(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Both surfaces carry the same elections and product identity, so one revision meets the same gate.

    The operation once failed earlier than the command line for a Modelo 303,
    because it forwarded none of the elections the command line supplies.
    Byte parity of a successful export is proven for Modelo 303 in the
    surface-parity module; here both routes must stop at the same producer gate.
    """
    set_emilio_legal_entity_export_profile()
    work_unit_id, calculation_revision_id = seed_exportable_modelo_202_pre_b2_revision(operation=operation)
    cli_out = tmp_path / "cli.boe"
    operation_out = tmp_path / "operation.boe"

    cli = invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            work_unit_id,
            "--output",
            str(cli_out),
            "--by",
            "Emilio",
        ],
    )
    condition, operation_code = _export_through_the_operation(
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        output_path=operation_out,
        operation=operation,
    )

    cli_code = json.loads(cli.output)["error"]["code"]
    assert cli.exit_code != 0, cli.output
    assert condition is not OperationTerminalCondition.SUCCEEDED
    assert operation_code == cli_code
    assert not cli_out.exists()
    assert not operation_out.exists()


def test_export_keeps_raw_revision_and_selector_refusals_distinct(tmp_path: Path) -> None:
    """The handler preserves the shared resolver's address-versus-selector errors."""
    set_export_profile_name()
    raw_revision = invoke(
        ["app", "modelo", "export", "--output", str(tmp_path / "raw.boe"), "--revision", "not-a-revision-id"]
    )
    selector = invoke(
        ["app", "modelo", "export", "--output", str(tmp_path / "selector.boe"), "--select", "not-a-selector"]
    )

    assert raw_revision.exit_code != 0, raw_revision.output
    assert selector.exit_code != 0, selector.output
    assert "not-a-revision-id" in raw_revision.output
    assert "not-a-selector" in selector.output


def test_export_invalid_period_names_the_selected_modelo_tokens(tmp_path: Path) -> None:
    """An invalid period token is rejected with the selected modelo's valid token."""
    set_export_profile_name()

    result = invoke(
        [
            "app",
            "modelo",
            "export",
            "--modelo",
            "100",
            "--year",
            "2024",
            "--period",
            "INVALID",
            "--output",
            str(tmp_path / "invalid-period.boe"),
        ]
    )

    assert result.exit_code != 0, result.output
    assert "0A" in result.output


@pytest.mark.parametrize(
    ("output_language", "expected_notice"),
    [
        ("en", "The exported file is not an AEAT filing receipt."),
        ("es", "El fichero exportado no es un justificante de presentación de la AEAT."),
        ("ca", "El fitxer exportat no és un justificant de presentació de l'AEAT."),
        ("hu", "Az exportált fájl nem az AEAT által kiállított benyújtási igazolás."),
    ],
)
def test_export_resolves_visible_target_to_current_verified_revision(
    tmp_path: Path,
    output_language: str,
    expected_notice: str,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Natural-key export defaults to the current verified-complete revision."""

    set_export_profile_name()
    _, (calculation_revision_id,) = seed_modelo_111_revisions(
        states=(CalculationRevisionState.VERIFICADO_COMPLETO,),
        current_index=0,
        operation=operation,
    )
    out = tmp_path / "modelo-111-current.txt"

    result = invoke(
        [
            "--language",
            output_language,
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            "--modelo",
            "111",
            "--year",
            "2026",
            "--period",
            "1T",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)
    assert payload["calculation_revision_id"] == calculation_revision_id
    notices = unwrap_envelope_notices(result.output)
    notice = next(notice for notice in notices if notice["code"] == "modelo.export.local_export_not_official_evidence")
    assert notice["severity"] == "warning"
    assert notice["context"]["evidence_status"] == "local_export_not_official_aeat_filing_evidence"
    assert notice["context"]["modelo"] == "111"
    assert notice["context"]["filing_year"] == "2026"
    assert notice["context"]["period"] == "1T"
    assert notice["message"] == expected_notice
    assert notice["action"] is None
    assert out.exists()


def test_export_selects_the_filed_revision_when_asked_and_the_current_calculation_by_default(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Natural-key export takes the declaration's current calculation unless ``--select filed`` names the filed one."""

    set_export_profile_name()
    _, revision_ids = seed_modelo_111_revisions(
        states=(CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.PRESENTADO),
        current_index=0,
        filed_index=1,
        operation=operation,
    )
    target = ["--format", "json", "app", "modelo", "export", "--modelo", "111", "--year", "2026", "--period", "1T"]

    for select, index in (("filed", 1), (None, 0)):
        out = tmp_path / f"modelo-111-{select or 'default'}.txt"
        result = invoke([*target, "--output", str(out), *(("--select", select) if select else ())])

        assert result.exit_code == 0, result.output
        assert unwrap_schema_envelope(result.output)["calculation_revision_id"] == revision_ids[index]
        assert out.exists()


def test_export_refuses_a_work_unit_with_no_current_calculation_despite_stored_verified_revisions(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A withdrawn calculation stays stored but is no longer the declaration's: export opens calculate."""

    seed_modelo_111_revisions(
        states=(CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.VERIFICADO_COMPLETO),
        operation=operation,
    )
    out = tmp_path / "modelo-111-withdrawn.txt"

    result = invoke(
        [
            "--language",
            "en",
            "app",
            "modelo",
            "export",
            "--modelo",
            "111",
            "--year",
            "2026",
            "--period",
            "1T",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code != 0, result.output
    assert '"action_id":"operator.modelo.work.calculate"' in result.output, result.output
    assert not out.exists()


def test_export_modelo_111_refuses_when_profile_name_missing(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """When the active profile lacks ``identity.surnames`` the export
    must refuse with a clear error naming the missing profile fact
    rather than fabricating a placeholder name."""

    clear_export_profile_surnames()
    work_unit_id, _ = seed_exportable_modelo_revision(input_values_by_casilla_id=MODELO_111_INPUTS, operation=operation)
    out = tmp_path / "modelo-111.txt"

    result = invoke(
        ["app", "modelo", "export", work_unit_id, "--output", str(out)],
    )

    assert result.exit_code != 0, result.output
    assert "surnames" in result.output.lower(), result.output
    assert not out.exists()


def _calculation_grade_edition() -> EditionBelowFilingGrade:
    """The newest annual edition of the envelope authored for its own year and served at calculation grade.

    Editions rise to filing grade as their evidence lands, so the modelo and year come from the authority. One
    below calculation grade does not compute at all, so it is not taken. Read when the test runs, so a registry
    with no such edition fails this case alone rather than its whole module.
    """
    edition = next(
        (
            edition
            for edition in authored_editions_below_filing_grade("0A")
            if edition.grade is RegistryAuthorityGrade.CALCULATION
        ),
        None,
    )
    assert edition is not None, (
        "precondition: no annual edition of the support envelope authored for its own year is served at "
        "calculation grade, so there is no computed declaration whose export is refused on grade"
    )
    return edition


def test_export_refuses_a_calculation_grade_edition_for_filing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """An edition the authority serves at calculation grade computes but cannot satisfy a filing-grade export."""

    edition = _calculation_grade_edition()
    set_export_profile_name()
    work_unit_id, _ = seed_verified_revision_without_inputs(
        modelo=edition.modelo, filing_year=edition.filing_year, period=edition.period, operation=operation
    )
    out = tmp_path / f"modelo-{edition.modelo}.txt"

    result = invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            work_unit_id,
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    error = payload["error"]
    assert error["code"] == "ERROR_CALCULATIONS_REGISTRY_VALIDATION"
    assert error["category"] == "ERROR"
    # The runtime names the stopped operation; the refusal's facts travel in its verdict.
    assert set(error["context"]) == {"effect", "operation_id", "terminal_condition"}
    assert error["context"]["terminal_condition"] == "failed"
    assert error["action"]["failed_condition_id"] == "registry.snapshot.authority_grade.sufficient"
    assert error["action"]["no_recovery_outcome"] == "safety"
    evidence = error["action"]["evidence"]
    assert len(evidence) == 1
    assert evidence[0]["condition_id"] == "registry.snapshot.authority_grade.sufficient"
    assert evidence[0]["provenance"] == "registry_record"
    evidence_values = evidence[0]["values"]
    assert evidence_values["authority_grade_declared"] is True
    assert evidence_values["declared_authority_grade"] == "calculation"
    assert evidence_values["modelo"] == edition.modelo
    assert evidence_values["requested_authority_grade"] == "filing"
    assert evidence_values["revision_id"] == edition.revision_id
    # Free exception text never crosses the runtime; the catalogue sentence does.
    assert error["message"] == tr(get_registered_error_code_by_code(error["code"]).message_key)
    assert not out.exists()
    assert "Traceback" not in result.output


def test_export_modelo_303_cli_refuses_revision_without_filing_evidence(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    work_unit_id, _ = seed_verified_revision_without_inputs(
        modelo="303", filing_year=2026, period="1T", operation=operation
    )
    out = tmp_path / "modelo-303.txt"

    result = invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            work_unit_id,
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    error = payload["error"]
    # The producer's own registered refusal reaches the operator; the export
    # lookup does not rewrap it as a generic export failure.
    assert error["code"] == "REFUSED_MODELO_M303_FILING_EVIDENCE"
    assert error["category"] == "REFUSED"
    assert error["message"] == tr(get_registered_error_code_by_code(error["code"]).message_key)
    action = error["action"]
    assert action["failed_condition_id"] == "modelo.work.calculate.m303_filing_evidence.valid"
    evidence = action["evidence"]
    assert len(evidence) == 1
    assert evidence[0]["evidence_id"] == "modelo.work.calculate.m303_filing_evidence.missing.observation"
    assert evidence[0]["values"]["evidence_present"] is False
    assert evidence[0]["values"]["modelo"] == "303"
    assert not out.exists()
    assert not out.with_name(out.name + ".tmp").exists()
    assert "Traceback" not in result.output


def test_export_modelo_100_reaches_xml_dictionary_path_before_cross_period_gate(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    work_unit_id, _ = seed_verified_revision_without_inputs(
        modelo="100", filing_year=2025, period="0A", operation=operation
    )
    out = tmp_path / "modelo-100.xml"

    result = invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            work_unit_id,
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "REFUSED_MODELO_CROSS_PERIOD_CLEAN_STATE"
    assert payload["error"]["category"] == "REFUSED"
    assert "fixed_width" not in result.output
    assert "xml_dictionary" not in payload["error"]["message"]
    assert not out.exists()
    assert "Traceback" not in result.output
