"""A Modelo 390 whose prorrata register applies is blocked while its edition does not render apartado 12.

The annual summary prints each activity's prorrata in apartado 12. An edition whose
registry registers no casilla for those boxes would export the record blank, so
verification reports a blocking finding and local filing and export refuse with one
typed reason. The detection reads the register for the work unit's ejercicio and the
pinned revision's own casillas, so no year or flag lifts it. Real encrypted store,
calculation, verification, filing and export services over the published authority.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.prorrata_activity_authoring import upsert_activity_row
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.calculate_input import WorkCalculateInputBundle, calculate_modelo_work_revision
from cadrumo.application.modelo.export import export_modelo_revision
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.application.modelo.m390_prorrata_apartado_gate import (
    Modelo390ProrrataApartadoStage,
    Modelo390ProrrataApartadoUnrenderedError,
    registry_renders_prorrata_apartado,
    require_modelo_390_prorrata_apartado_rendered,
)
from cadrumo.application.modelo.preconditions import ModeloPreconditionFailure
from cadrumo.application.modelo.verification_model_findings import append_readable_model_findings
from cadrumo.application.modelo.verification_preconditions import project_verification_findings
from cadrumo.application.modelo.verification_report_facts import classify_verification_outcome
from cadrumo.application.modelo.work_addressing import law_selected_revision_for_work_target
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.errors.error_codes import get_registered_error_code, resolve_error_message
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.core.identity.hex_ids import CalculationRevisionId
from cadrumo.core.period import Period
from cadrumo.core.prorrata_register import ProrrataActivityRowType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.prorrata_register.register import ProrrataActivityRow
from cadrumo.entrypoints.adapter_composition_work_ports import build_filing_action_ports
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

from .modelo_gate_bucket_support import (
    ready_workflow_profile,
    seed_ready_capital_payer_profile,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "00000000-0000-4000-8000-000000000390"
_FINDING_KEY = "application.modelo.findings.m390_prorrata_apartado_unrendered"
_ANNUAL = "0A"
_DOOR = "operator.ledger.prorrata.list"
_LOCALES = ("en", "es", "ca", "hu")
_RECONCILIATION_BINDINGS = (
    "modelo-390-prev-303-cuota-devengada-total",
    "modelo-390-prev-303-cuota-deducible-total",
    "modelo-390-prev-303-resultado-regimen-general",
)


@dataclass(frozen=True, slots=True)
class _Bucket:
    objects: SecureObjectRepository
    work_unit: WorkUnit
    ejercicio: int


def _newest_filing_grade_year(operation: PinnedAuthorityOperation) -> int:
    """The newest supported year whose Modelo 390 edition carries filing authority, from the support envelope."""
    envelope = filing_year_envelope()
    for year in range(envelope.horizon, envelope.floor - 1, -1):
        try:
            operation.snapshot("390", filing_year=year, period=_ANNUAL)
        except RegistryValidationError:
            continue
        return year
    raise AssertionError("no supported year carries a filing-grade Modelo 390 edition")


def _activity_row(ejercicio: int) -> ProrrataActivityRow:
    return ProrrataActivityRow(
        ejercicio=ejercicio,
        activity_id="activity-one",
        slot=1,
        cnae_code="471",
        operaciones_total=Decimal("1000.00"),
        operaciones_con_derecho=Decimal("800.00"),
        prorrata_type=ProrrataActivityRowType.GENERAL,
        percentage=Decimal("80.00"),
        evidence_reference="operator-evidence:activity-one",
    )


@contextmanager
def _m390_bucket(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> Generator[_Bucket]:
    ejercicio = _newest_filing_grade_year(operation)
    at = datetime(ejercicio + 1, 2, 1, 9, 0, tzinfo=UTC)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M390 prorrata apartado") as profile:
        objects: SecureObjectRepository = profile.repository
        seed_ready_capital_payer_profile(bucket_id=_BUCKET_ID, at=at)
        period = Period.from_year_and_code(ejercicio, _ANNUAL)
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="390",
            filing_year=ejercicio,
            period=period,
            revision_id=law_selected_revision_for_work_target(
                modelo="390", filing_year=ejercicio, period=period, operation=operation
            ),
            ports=WorkLifecyclePorts(
                work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
            ),
            clock=at,
            operation=operation,
        )
        yield _Bucket(objects=objects, work_unit=work_unit, ejercicio=ejercicio)


def _register(bucket: _Bucket) -> ProrrataRegisterRepository:
    return ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=bucket.objects)


def _calculate(bucket: _Bucket) -> CalculationRevisionId:
    """Calculate the 390 with its three 303 reconciliation bindings answered by the operator, so none is left unknown."""
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=bucket.objects),
        invoice_repository=InvoiceCatalogueRepository(objects=bucket.objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects),
        work_unit_repository=WorkUnitCatalogueRepository(objects=bucket.objects),
    ) as ports:
        result = calculate_modelo_work_revision(
            work_unit_id=bucket.work_unit.work_unit_id,
            actor="test",
            inputs=WorkCalculateInputBundle.build(
                casilla_inputs={},
                binding_values=dict.fromkeys(_RECONCILIATION_BINDINGS, Decimal(0)),
                enum_binding_values={},
                relation_values={},
                detail_rows=(),
                borrador_snapshot_id=None,
            ),
            ports=ports,
        )
    return result.revision.calculation_revision_id


def _collected_findings(
    revision_id: CalculationRevisionId, bucket: _Bucket, *, operation: PinnedAuthorityOperation
) -> tuple[list[ModeloVerificationFinding], dict[int, ModeloPreconditionFailure]]:
    """Run verification's model-finding stage over the stored revision.

    The full verification entry point refuses a hand-built 390 earlier, on the calculation
    notes of its unresolved prorrata and compensation bindings, so the stage that
    owns this finding is run directly over the real stored revision and repositories.
    """
    target = (
        CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects).load().get(revision_id)
    )
    assert target is not None
    findings: list[ModeloVerificationFinding] = []
    failures: dict[int, ModeloPreconditionFailure] = {}
    append_readable_model_findings(
        findings,
        failures,
        bucket.work_unit,
        target,
        build_test_verification_repository_bundle(),
        operation,
    )
    return findings, failures


def _apartado_findings(findings: list[ModeloVerificationFinding]) -> list[ModeloVerificationFinding]:
    return [finding for finding in findings if finding.message_locale_key == _FINDING_KEY]


def test_verification_blocks_a_390_whose_register_applies_and_points_at_the_register_listing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The finding is blocking, carries the register door, and makes the check blocked."""
    with _m390_bucket(tmp_path, operation=operation) as bucket:
        upsert_activity_row(_register(bucket), _activity_row(bucket.ejercicio))
        findings, failures = _collected_findings(_calculate(bucket), bucket, operation=operation)

    (finding,) = _apartado_findings(findings)
    assert finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_facts["filing_year"] == bucket.ejercicio
    assert finding.message_facts["registered_activity_rows"] == 1
    failure = failures[id(finding)]
    assert failure.subject_leaf_key == "modelo.work.verify"
    assert failure.verdict.action is not None
    assert failure.verdict.action.action_id == _DOOR
    (projection,) = (
        item
        for item in project_verification_findings(findings, failures_by_finding_id=failures)
        if item.finding is finding
    )
    assert projection.precondition_failure == failure
    completeness, granted = classify_verification_outcome(findings=findings, missing_required=[])
    assert granted is False
    assert completeness is VerificationCompletenessStatus.BLOCKED


def test_verification_reports_nothing_for_a_390_without_a_register(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A taxpayer with no register for the ejercicio has no prorrata to print, so nothing is blocked on it."""
    with _m390_bucket(tmp_path, operation=operation) as bucket:
        findings, _ = _collected_findings(_calculate(bucket), bucket, operation=operation)

    assert _apartado_findings(findings) == []


def test_verification_ignores_a_register_that_belongs_to_another_ejercicio(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The register is read for the work unit's ejercicio only."""
    with _m390_bucket(tmp_path, operation=operation) as bucket:
        upsert_activity_row(_register(bucket), _activity_row(bucket.ejercicio - 1))
        findings, _ = _collected_findings(_calculate(bucket), bucket, operation=operation)

    assert _apartado_findings(findings) == []


def test_filing_and_export_refuse_with_the_typed_code_and_write_nothing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Local filing and export refuse the revision, name the register door, and leave no file or record."""
    export_path = tmp_path / "modelo-390.txt"
    with _m390_bucket(tmp_path, operation=operation) as bucket:
        upsert_activity_row(_register(bucket), _activity_row(bucket.ejercicio))
        revision_id = _calculate(bucket)

        with pytest.raises(Modelo390ProrrataApartadoUnrenderedError) as file_info:
            # No granting verification exists; the refusal precedes every lifecycle check.
            file_modelo_revision(
                revision_id,
                approved_verification_report_id="0" * 64,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                operator_scope_ports=build_operator_scope_ports(),
                ports=build_filing_action_ports(bucket_id=_BUCKET_ID, operation=operation),
                actor="test",
                workflow_profile=ready_workflow_profile(),
                operation=operation,
            )
        with pytest.raises(Modelo390ProrrataApartadoUnrenderedError) as export_info:
            export_modelo_revision(
                ModeloExportCommand(calculation_revision_id=revision_id, output_path=export_path, actor="test"),
                workflow_profile=ready_workflow_profile(),
                export_ports=modelo_export_ports_for_test(bucket_id=_BUCKET_ID, secure_objects=bucket.objects),
                operation=operation,
            )

    for error, leaf in ((file_info.value, "modelo.work.file"), (export_info.value, "modelo.export")):
        failure = error.precondition_failure
        assert failure is not None
        assert failure.subject_leaf_key == leaf
        assert failure.scenario_id == f"{leaf}.m390_prorrata_apartado.unrendered"
        assert failure.verdict.failed_condition_id == f"{leaf}.m390_prorrata_apartado.rendered"
        assert failure.verdict.action is not None
        assert failure.verdict.action.action_id == _DOOR
        assert get_registered_error_code(error).code == "REFUSED_MODELO_390_PRORRATA_APARTADO_UNRENDERED"
        for locale in _LOCALES:
            message = resolve_error_message(error, locale=locale)
            assert message
            assert "%{" not in message
            assert "errors." not in message
    assert not export_path.exists()


def test_the_gate_stands_aside_without_a_register(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> None:
    """No register for the ejercicio: the gate raises nothing at any stage."""
    with _m390_bucket(tmp_path, operation=operation) as bucket:
        revision_id = law_selected_revision_for_work_target(
            modelo="390",
            filing_year=bucket.ejercicio,
            period=bucket.work_unit.period,
            operation=operation,
        )
        for stage in Modelo390ProrrataApartadoStage:
            require_modelo_390_prorrata_apartado_rendered(
                bucket.work_unit,
                registry_revision_id=revision_id,
                prorrata_register_repository=_register(bucket),
                operation=operation,
                stage=stage,
            )


def test_the_finding_follows_the_revision_casillas_not_the_year(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The gate fires exactly while the pinned revision lacks the apartado's casillas, so registering them lifts it."""
    with _m390_bucket(tmp_path, operation=operation) as bucket:
        upsert_activity_row(_register(bucket), _activity_row(bucket.ejercicio))
        revision_id = law_selected_revision_for_work_target(
            modelo="390",
            filing_year=bucket.ejercicio,
            period=bucket.work_unit.period,
            operation=operation,
        )
        registry_revision = operation.revision("390", revision_id)
        renders = registry_renders_prorrata_apartado(registry_revision)
        refused = False
        try:
            require_modelo_390_prorrata_apartado_rendered(
                bucket.work_unit,
                registry_revision_id=revision_id,
                prorrata_register_repository=_register(bucket),
                operation=operation,
                stage=Modelo390ProrrataApartadoStage.EXPORT,
            )
        except Modelo390ProrrataApartadoUnrenderedError:
            refused = True

    assert refused is not renders
    # The pure reading of a revision: its own casillas with the apartado's boxes removed, then renumbered copies added.
    boxes = ("114", "115", "116", "117", "118")
    without = tuple(casilla for casilla in registry_revision.casillas if casilla.number not in boxes)
    template = without[0]
    added = tuple(template.model_copy(update={"id": f"{template.id}.apartado-{box}", "number": box}) for box in boxes)
    bare = registry_revision.model_copy(update={"casillas": without})
    lifted = registry_revision.model_copy(update={"casillas": (*without, *added)})
    partial = registry_revision.model_copy(update={"casillas": (*without, *added[:4])})
    assert registry_renders_prorrata_apartado(bare) is False
    assert registry_renders_prorrata_apartado(partial) is False
    assert registry_renders_prorrata_apartado(lifted) is True


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_finding_words_are_authored_in_every_language(locale: str) -> None:
    """Both the finding and the refusal have authored words in each locale, and the finding names its two facts."""
    finding = lookup_translation(_FINDING_KEY, locale=locale)
    assert finding is not None
    assert "%{filing_year}" in finding
    assert "%{registered_activity_rows}" in finding
    refusal = lookup_translation("errors.refused.refused_modelo_390_prorrata_apartado_unrendered", locale=locale)
    assert refusal is not None
    assert "%{" not in refusal
