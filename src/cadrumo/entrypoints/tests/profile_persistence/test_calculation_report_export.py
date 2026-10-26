"""Calculation report assembly, CSV serialisation and publication over real state.

Every assertion here runs against the published registry authority, encrypted
SQLite storage and the real formula engine: the revisions are calculated and
verified through the same application services an operator drives, and the report
is assembled from their persisted observations rather than from a fixture table.

The three value states are the subject rather than a detail. Modelo 130 at 1T is
chosen because it realises all three at once: measured figures, explicit zeros,
and one carry-forward casilla the registry proves does not apply to a first
quarter.
"""

from __future__ import annotations

import csv
import hashlib
import io
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.review_package_signing import (
    build_review_package_signing_keypair_capability,
)
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.modelo_export_support import isolated_backend
from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.application.modelo.action_errors import CalculationRevisionStateError
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.calculation_report import (
    CalculationReportRowRole,
    CalculationReportValueState,
    ModeloCalculationReport,
    local_calculation_report_notice,
)
from cadrumo.application.modelo.calculation_report_document import (
    CALCULATION_REPORT_CSV_FIELDNAMES,
    CALCULATION_REPORT_CSV_PREAMBLE_PREFIX,
    DOCUMENT_SERIALIZERS,
    calculation_report_csv_row,
    serialize_calculation_report,
)
from cadrumo.application.modelo.calculation_report_export import (
    ModeloCalculationReportCommand,
    ModeloCalculationReportResult,
    build_modelo_calculation_report_for_revision,
    export_modelo_calculation_report,
)
from cadrumo.application.modelo.export_ports import ModeloExportPorts
from cadrumo.application.modelo.export_sink import ModeloExportOutputPathError
from cadrumo.core.calculation_report_format import CalculationReportDocumentFormat
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.filing.software_identity import AeatSoftwareIdentityGrade
from cadrumo.domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    M130_INCOME_CASILLA,
    T1,
    Repos,
    calculation_ports_for_test,
    seed_work_unit,
    verify_revision,
)
from cadrumo.entrypoints.tests.profile_persistence.modelo_303_export_support import (
    build_verified_modelo_303_revision,
)

__all__ = ["isolated_backend"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_EXPORTED_AT = T1

#: The quarter ``build_verified_modelo_303_revision`` calculates and verifies.
_M303_PERIOD_CODE = "2T"

#: Modelo 130 casilla 05 carries the same-ejercicio prior-quarter pagos
#: fraccionados through a previous-filing binding whose expanding span is empty at
#: 1T. Leaving it out of the operator's inputs is the ordinary first-quarter case,
#: and the registry then materialises its zero absent by design -- the state this
#: module needs a live example of.
_PRIOR_QUARTER_CARRY_CASILLA = "05"
_BASELINE_INPUTS = {
    casilla_id: value
    for casilla_id, value in DEFAULT_130_BASELINE_INPUTS.items()
    if casilla_id != _PRIOR_QUARTER_CARRY_CASILLA
}


def _calculate_130(repos: Repos) -> tuple[WorkUnit, CalculationRevision]:
    """Calculate the shared Modelo 130 1T baseline through the real engine."""
    work_repo, calculation_repo, _, _, event_repo = repos
    work_unit = seed_work_unit(work_repo)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=event_repo,
    ) as ports:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator-A",
            casilla_inputs=dict(_BASELINE_INPUTS),
            binding_values=dict(DEFAULT_130_BINDING_VALUES),
            ports=ports,
            clock=T1,
        )
    return work_unit, revision


def _verified_130(repos: Repos) -> tuple[WorkUnit, CalculationRevision]:
    """Calculate and verify the Modelo 130 1T baseline, returning the sealed revision."""
    work_repo, calculation_repo, filing_repo, verification_repo, event_repo = repos
    work_unit, revision = _calculate_130(repos)
    report = verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        bucket_event_repository=event_repo,
        filing_repository=filing_repo,
        clock=T1,
    )
    assert report.granted_verificado_completo is True
    sealed = calculation_repo.load().revisions[revision.calculation_revision_id]
    assert sealed.state is CalculationRevisionState.VERIFICADO_COMPLETO
    return work_unit, sealed


def _export_ports(repos: Repos, work_unit: WorkUnit) -> ModeloExportPorts:
    work_repo, calculation_repo, filing_repo, verification_repo, event_repo = repos
    return modelo_export_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit=work_repo,
        calculation=calculation_repo,
        filing=filing_repo,
        verification=verification_repo,
        bucket_event=event_repo,
    )


def _report(
    repos: Repos,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    *,
    report_language: OutputLanguage = OutputLanguage.ES,
) -> ModeloCalculationReport:
    return build_modelo_calculation_report_for_revision(
        revision.calculation_revision_id,
        active_bucket_id=work_unit.bucket_id,
        export_ports=_export_ports(repos, work_unit),
        signing_keypair=build_review_package_signing_keypair_capability(bucket_id=work_unit.bucket_id),
        operation=published_authority_operation(),
        report_language=report_language,
        exported_at=_EXPORTED_AT,
    )


def _publish_csv(
    repos: Repos,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    output_path: Path,
    *,
    replace_existing: bool = False,
) -> ModeloCalculationReportResult:
    return export_modelo_calculation_report(
        ModeloCalculationReportCommand(
            calculation_revision_id=revision.calculation_revision_id,
            document_format=CalculationReportDocumentFormat.CSV,
            report_language=OutputLanguage.ES,
            output_path=output_path,
            replace_existing=replace_existing,
        ),
        export_ports=_export_ports(repos, work_unit),
        signing_keypair=build_review_package_signing_keypair_capability(bucket_id=work_unit.bucket_id),
        operation=published_authority_operation(),
        clock=_EXPORTED_AT,
    )


def _table_rows(payload: str) -> tuple[dict[str, str], ...]:
    """Parse the CSV table back, dropping the commented header-fact preamble."""
    table = "\n".join(
        line for line in payload.splitlines() if not line.startswith(CALCULATION_REPORT_CSV_PREAMBLE_PREFIX)
    )
    return tuple({str(column): str(cell) for column, cell in row.items()} for row in csv.DictReader(io.StringIO(table)))


def test_report_header_carries_every_traceability_coordinate(repos: Repos) -> None:
    """The header names the revision, its verification and the authority behind it."""
    work_unit, revision = _verified_130(repos)
    _, _, _, verification_repo, _ = repos
    header = _report(repos, work_unit, revision).header

    assert str(header.modelo) == "130"
    assert int(header.filing_year) == work_unit.filing_year
    assert header.period == work_unit.period
    assert header.calculation_revision_id == revision.calculation_revision_id
    assert header.calculation_revision_state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert header.work_unit_id == work_unit.work_unit_id
    assert header.registry_snapshot_ref == revision.registry_snapshot_ref
    assert header.authority_logical_generation == published_authority_operation().generation.logical_generation
    assert header.exported_at == _EXPORTED_AT
    assert header.local_calculation_notice == local_calculation_report_notice(OutputLanguage.ES)
    assert header.report_language is OutputLanguage.ES
    assert header.taxpayer_tax_id
    assert header.taxpayer_name
    assert header.filing_record_id is None

    verified = verification_repo.load().for_calculation_revision(revision.calculation_revision_id)
    assert header.verification_report_id == verified[-1].verification_report_id
    assert header.verification_outcome is verified[-1].completeness_status


def test_report_rows_follow_the_registry_order_of_the_pinned_snapshot(repos: Repos) -> None:
    """Row order is the registry's section order and casilla numbering, unaltered."""
    work_unit, revision = _verified_130(repos)
    report = _report(repos, work_unit, revision)

    operation = published_authority_operation()
    selected = operation.revision_for_context(
        str(work_unit.modelo),
        filing_year=work_unit.period.filing_year,
        period=work_unit.period.registry_token,
    )
    snapshot = operation.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.period.filing_year,
        period=work_unit.period.registry_token,
        revision_id=selected.id,
        grade=selected.effective_authority_grade,
    )
    assert report.rows
    assert tuple(row.casilla_id for row in report.rows) == tuple(casilla.id for casilla in snapshot.revision.casillas)
    assert report.header.row_count == len(report.rows)


def test_measured_zero_absent_and_not_applicable_stay_three_states(repos: Repos) -> None:
    """A proven zero, an unrealised casilla and a non-applicable one never merge."""
    work_unit, revision = _verified_130(repos)
    report = _report(repos, work_unit, revision)

    income = next(row for row in report.rows if row.casilla_id == M130_INCOME_CASILLA)
    assert income.value_state is CalculationReportValueState.VALUE
    assert Decimal(str(income.value)) == _BASELINE_INPUTS[M130_INCOME_CASILLA]

    zeros = [
        row
        for row in report.rows
        if row.value_state is CalculationReportValueState.VALUE and Decimal(str(row.value)) == Decimal("0")
    ]
    assert zeros, "the baseline supplies explicit zeros, which are values rather than absences"

    prior_quarter_carry = next(row for row in report.rows if row.casilla_id == _PRIOR_QUARTER_CARRY_CASILLA)
    assert prior_quarter_carry.value_state is CalculationReportValueState.NOT_APPLICABLE
    assert prior_quarter_carry.value is None

    # A verificado-completo Modelo 130 realises every casilla its revision
    # declares, so there is nothing absent to report here. The absent state is
    # exercised where it actually arises, over a revision that realises only part
    # of its schema, in the report builder's own tests.
    assert [row for row in report.rows if row.value_state is CalculationReportValueState.ABSENT] == []


def test_report_digest_describes_its_own_canonical_form(repos: Repos) -> None:
    """The digest is recomputable from the canonical bytes the report defines."""
    work_unit, revision = _verified_130(repos)
    report = _report(repos, work_unit, revision)

    assert report.report_sha256 == hashlib.sha256(report.canonical_bytes()).hexdigest()

    with pytest.raises(ValueError, match="row_count"):
        ModeloCalculationReport(header=report.header, rows=report.rows[:-1])


def test_csv_rows_parse_back_to_the_builder_rows(repos: Repos) -> None:
    """Every published CSV data row reads back as the row the builder produced."""
    work_unit, revision = _verified_130(repos)
    report = _report(repos, work_unit, revision)
    document = serialize_calculation_report(report, document_format=CalculationReportDocumentFormat.CSV)

    text = document.payload.decode("utf-8")
    preamble = [line for line in text.splitlines() if line.startswith(CALCULATION_REPORT_CSV_PREAMBLE_PREFIX)]
    parsed = _table_rows(text)

    assert parsed[0].keys() == set(CALCULATION_REPORT_CSV_FIELDNAMES)
    assert parsed == tuple(calculation_report_csv_row(row) for row in report.rows)
    assert document.row_count == len(report.rows)
    assert any(report.header.local_calculation_notice in line for line in preamble)
    assert any(report.report_sha256 in line for line in preamble)
    assert any(report.header.calculation_revision_id in line for line in preamble)


def test_csv_distinguishes_absent_from_zero_in_the_published_bytes(repos: Repos, tmp_path: Path) -> None:
    """The published table spells a zero and an absence differently."""
    work_unit, revision = _verified_130(repos)
    output_path = tmp_path / "modelo-130-report.csv"
    result = _publish_csv(repos, work_unit, revision, output_path)

    rows = {row["casilla_id"]: row for row in _table_rows(output_path.read_text(encoding="utf-8"))}
    prior_quarter_carry = rows[_PRIOR_QUARTER_CARRY_CASILLA]
    assert prior_quarter_carry["value_state"] == CalculationReportValueState.NOT_APPLICABLE.value
    assert prior_quarter_carry["value"] == ""

    zero_rows = [
        row
        for row in rows.values()
        if row["value_state"] == CalculationReportValueState.VALUE.value and Decimal(row["value"]) == Decimal("0")
    ]
    assert zero_rows
    assert all(row["value"] != "" for row in zero_rows)
    assert result.row_count == len(rows)


def test_publication_reports_the_landed_file_and_the_report_identity(repos: Repos, tmp_path: Path) -> None:
    """The receipt measures the file on disk and carries the report's own digest."""
    work_unit, revision = _verified_130(repos)
    output_path = tmp_path / "modelo-130-report.csv"
    result = _publish_csv(repos, work_unit, revision, output_path)

    landed = output_path.read_bytes()
    assert result.output_path == output_path
    assert result.byte_size == len(landed)
    assert result.file_sha256 == hashlib.sha256(landed).hexdigest()
    assert result.report_sha256 == _report(repos, work_unit, revision).report_sha256
    assert result.document_format is CalculationReportDocumentFormat.CSV
    assert result.local_calculation_notice == local_calculation_report_notice(OutputLanguage.ES)
    assert result.software_identity_grade in (None, *tuple(AeatSoftwareIdentityGrade))


def test_existing_file_is_refused_until_the_operator_chooses_to_replace(repos: Repos, tmp_path: Path) -> None:
    """A path already holding a file is a refusal, and the replace choice is the way past."""
    work_unit, revision = _verified_130(repos)
    output_path = tmp_path / "modelo-130-report.csv"
    first = _publish_csv(repos, work_unit, revision, output_path)

    with pytest.raises(ModeloExportOutputPathError):
        _publish_csv(repos, work_unit, revision, output_path)
    assert output_path.read_bytes()

    replaced = _publish_csv(repos, work_unit, revision, output_path, replace_existing=True)
    assert replaced.file_sha256 == first.file_sha256


def test_draft_revision_is_refused_before_any_report_exists(repos: Repos, tmp_path: Path) -> None:
    """An unverified revision states nothing settled, so no report is produced."""
    work_unit, revision = _calculate_130(repos)
    assert revision.state is CalculationRevisionState.BORRADOR
    output_path = tmp_path / "modelo-130-draft.csv"

    with pytest.raises(CalculationRevisionStateError):
        _publish_csv(repos, work_unit, revision, output_path)
    assert not output_path.exists()


def test_every_declared_document_format_has_a_serialiser() -> None:
    """A format an operator can ask for cannot be one with no serialiser enrolled."""
    assert set(DOCUMENT_SERIALIZERS) == set(CalculationReportDocumentFormat)


def test_report_rows_ground_every_casilla_without_inventing_a_source_trace(repos: Repos) -> None:
    """Grounding is the registry's own, and an unsourced revision reports no trace.

    The Modelo 130 baseline resolves its figures from operator inputs and a
    previous-filing binding rather than from the ledger mesh, so the revision
    persists no resolver provenance. The report carries that absence as absence:
    a row with no trace is not given one, and the keyed-provenance path is
    exercised where traces actually exist, on the Modelo 303 case below.
    """
    work_unit, revision = _verified_130(repos)
    report = _report(repos, work_unit, revision)

    assert revision.source_provenance == ()
    assert all(row.source_provenance == () for row in report.rows)
    assert all(row.legal_refs and row.source_refs for row in report.rows)
    assert all(row.label and row.section_path and row.number for row in report.rows)


def test_every_report_row_names_its_role_and_the_result_row_is_named_once(repos: Repos) -> None:
    """A reader separates inputs from derived figures without reading the registry."""
    work_unit, revision = _verified_130(repos)
    report = _report(repos, work_unit, revision)

    roles = {row.casilla_id: row.row_role for row in report.rows}
    assert set(roles.values()) <= set(CalculationReportRowRole)
    assert all(
        row.row_role is CalculationReportRowRole.INPUT
        for row in report.rows
        if row.declared_input_kind in {InputKind.MANUAL, InputKind.BOUND}
    )
    assert any(row.row_role is CalculationReportRowRole.COMPUTED for row in report.rows)
    assert len([row for row in report.rows if row.row_role is CalculationReportRowRole.RESULT]) <= 1


def test_verified_modelo_303_reports_its_own_casillas_and_publishes_them(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A second modelo family reports through the same builder and the same sink.

    Modelo 303 is the counterpart the fichero-BOE export exercises, and it reaches
    the report through a wallet decision, ledger IVA bindings and a prior filed
    quarter. Reporting it proves the builder is modelo-independent rather than
    tuned to one quarterly form.
    """
    with bundled_indexed_authority().operation() as operation:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            operation=operation,
        )
    export_ports = modelo_export_ports_for_test(
        bucket_id=bucket_id,
        taxpayer_tax_id=taxpayer_nif,
        work_unit=work_repo,
        calculation=calc_repo,
        bucket_event=event_repo,
    )
    output_path = tmp_path / "modelo-303-report.csv"
    result = export_modelo_calculation_report(
        ModeloCalculationReportCommand(
            calculation_revision_id=verified.calculation_revision_id,
            document_format=CalculationReportDocumentFormat.CSV,
            report_language=OutputLanguage.ES,
            output_path=output_path,
            replace_existing=False,
        ),
        export_ports=export_ports,
        signing_keypair=build_review_package_signing_keypair_capability(bucket_id=bucket_id),
        operation=published_authority_operation(),
        clock=_EXPORTED_AT,
    )

    assert str(result.modelo) == "303"
    assert result.period == Period.from_year_and_code(2026, _M303_PERIOD_CODE)
    assert result.calculation_revision_id == verified.calculation_revision_id
    assert result.row_count > 0
    assert result.software_identity_grade is not None, (
        "the Modelo 303 fichero-BOE carries an envelope header, so its report names the identity grade"
    )

    rows = _table_rows(output_path.read_text(encoding="utf-8"))
    assert len(rows) == result.row_count
    assert {row["value_state"] for row in rows} <= {state.value for state in CalculationReportValueState}
    assert any(Decimal(row["value"]) != Decimal("0") for row in rows if row["value"])

    # The report names the filer in full and gives every row a role, on a second
    # modelo family and through the real encrypted store rather than a fixture key.
    assert result.report_language is OutputLanguage.ES
    assert taxpayer_nif.encode("utf-8") in output_path.read_bytes()
    assert {row["row_role"] for row in rows} <= {role.value for role in CalculationReportRowRole}
    assert all(row["row_role"] for row in rows)
