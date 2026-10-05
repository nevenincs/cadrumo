"""Registered verification-report reads retain the complete saved report."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
    derive_verification_report_id,
)
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    OperationAccessRequest,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import verification_report_read_capture as capture_module
from ..verification_report_public_facts import ModeloVerificationReportProjection
from ..verification_report_read_capture import capture_verification_report_list, capture_verification_report_view
from ..verification_report_read_contracts import (
    MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID,
    MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID,
    ModeloVerificationReportListRequest,
    ModeloVerificationReportViewRequest,
)
from ..verification_report_read_operation import (
    build_modelo_verification_report_list_definition,
    build_modelo_verification_report_list_registration,
    build_modelo_verification_report_view_definition,
    build_modelo_verification_report_view_registration,
)
from ..verification_report_read_projection import (
    ModeloVerificationReportListProjection,
    ModeloVerificationReportViewProjection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_RESULT_REFERENCE = "f" * 64


def _revision_and_unit(operation: PinnedAuthorityOperation, period_code: str) -> tuple[CalculationRevision, WorkUnit]:
    """Build one minimal profile-owned calculation at a published coordinate."""
    period = Period.from_year_and_code(2026, period_code)
    published_revision = operation.revision_for_context("303", filing_year=2026, period=period_code)
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(_PROFILE),
            modelo="303",
            filing_year=2026,
            period=period,
            revision_id=published_revision.id,
        ),
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id=published_revision.id,
        name=f"Synthetic {period_code} work unit",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id=published_revision.id,
            modelo_year=2026,
            period=period_code,
        ),
        state=CalculationRevisionState.BORRADOR,
        created_at=_NOW,
        updated_at=_NOW,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return revision, unit


def _report(
    revision: CalculationRevision,
    *,
    ordinal: int,
    run_at: datetime,
    blocking: bool = False,
) -> VerificationReport:
    """Build one report with every renderer-visible finding reference axis."""
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE if blocking else ModeloVerificationFindingKind.ADVISORY,
        severity=(
            ModeloVerificationFindingSeverity.BLOCKING if blocking else ModeloVerificationFindingSeverity.WARNING
        ),
        casilla_id="casilla.synthetic",
        expectation_id="expectation.synthetic",
        message_locale_key="modelo.verification.synthetic.finding",
        message_facts={"accepted": True, "amount": Decimal(f"{ordinal}.25"), "count": ordinal},
        legal_refs=("law.synthetic.article-1",),
        source_refs=("official-manual",),
    )
    completeness = VerificationCompletenessStatus.BLOCKED if blocking else VerificationCompletenessStatus.INCOMPLETE
    findings = (finding,)
    verified_by = "synthetic operator"
    return VerificationReport(
        verification_report_id=derive_verification_report_id(
            calculation_revision_id=revision.calculation_revision_id,
            completeness_status=completeness,
            findings=findings,
            verified_by=verified_by,
        ),
        calculation_revision_id=revision.calculation_revision_id,
        registry_snapshot_ref=revision.registry_snapshot_ref,
        completeness_status=completeness,
        findings=findings,
        resolved_casilla_ids=("resolved.synthetic",),
        missing_required_casilla_ids=("missing.synthetic",),
        run_at=run_at,
        verified_by=verified_by,
        granted_verificado_completo=False,
    )


class _Repository:
    def __init__(self, bucket_id: str, catalogue: BaseModel) -> None:
        self.bucket_id = bucket_id
        self._catalogue = catalogue
        self.read_threads: list[int] = []

    def load(self, *, operation: PinnedAuthorityOperation | None = None) -> BaseModel:
        self.read_threads.append(threading.get_ident())
        return self._catalogue


def _bundle(
    revisions: tuple[CalculationRevision, ...],
    units: tuple[WorkUnit, ...],
    reports: tuple[VerificationReport, ...],
    *,
    repository_bucket_id: str | None = None,
):
    """Provide only the exact-profile repositories used by this operation."""
    bucket_id = repository_bucket_id or str(_PROFILE)
    return SimpleNamespace(
        calculation=_Repository(
            bucket_id,
            CalculationRevisionCatalogue(revisions={row.calculation_revision_id: row for row in revisions}),
        ),
        work_unit=_Repository(bucket_id, WorkUnitCatalogue(work_units={row.work_unit_id: row for row in units})),
        verification=_Repository(
            bucket_id,
            VerificationReportCatalogue(reports={row.verification_report_id: row for row in reports}),
        ),
    )


def _read_definitions_and_registrations(factory):
    """Build both report-read definitions and registrations as the composition root does."""
    list_definition = build_modelo_verification_report_list_definition(factory)
    view_definition = build_modelo_verification_report_view_definition(factory)
    registrations = (
        build_modelo_verification_report_list_registration(list_definition, factory),
        build_modelo_verification_report_view_registration(view_definition, factory),
    )
    return (list_definition, view_definition), registrations


def _setup(bundle):
    def factory(profile_id: str, *, operation: PinnedAuthorityOperation):
        assert profile_id == str(_PROFILE)
        assert operation is not None
        return bundle

    definitions, registrations = _read_definitions_and_registrations(factory)
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    return factory, definitions, registrations, registry


def _request(
    *,
    definition_id: str,
    payload: BaseModel,
) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )


def _context(
    registration,
    *,
    operation: PinnedAuthorityOperation,
    action: AccessAction = AccessAction.SUBMIT,
    admitted: OperationAccessRequest | None = None,
    profile_id: UUID = _PROFILE,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=operation,
        admitted_request=admitted,
    )


def test_report_projection_round_trip_preserves_complete_finding_detail() -> None:
    with bundled_indexed_authority().operation() as operation:
        revision, _unit = _revision_and_unit(operation, "1T")
        report = _report(revision, ordinal=3, run_at=_NOW)
        _factory, definitions, registrations, _registry = _setup(_bundle((revision,), (), (report,)))

        projection = ModeloVerificationReportProjection.from_report(report)
        restored = ModeloVerificationReportProjection.model_validate_json(projection.model_dump_json())

    assert restored == projection
    assert restored.verification_report_id == report.verification_report_id
    assert restored.registry_snapshot_ref.period == report.registry_snapshot_ref.period
    assert restored.resolved_casilla_ids == report.resolved_casilla_ids
    assert restored.missing_required_casilla_ids == report.missing_required_casilla_ids
    finding = restored.findings[0]
    assert finding.legal_refs == report.findings[0].legal_refs
    assert finding.source_refs == report.findings[0].source_refs
    assert [(fact.key, fact.value_kind, fact.value) for fact in finding.message_facts] == [
        ("accepted", "boolean", True),
        ("amount", "decimal", "3.25"),
        ("count", "integer", 3),
    ]
    assert [definition.definition_id for definition in definitions] == [
        MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID,
        MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID,
    ]
    assert len(registrations) == 2


def test_capture_filters_orders_reports_and_refuses_incomplete_overlimit_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with bundled_indexed_authority().operation() as operation:
        revision_a, unit_a = _revision_and_unit(operation, "1T")
        revision_b, unit_b = _revision_and_unit(operation, "2T")
        report_a_late = _report(revision_a, ordinal=2, run_at=_NOW + timedelta(minutes=2))
        report_a_early = _report(revision_a, ordinal=1, run_at=_NOW)
        report_b = _report(revision_b, ordinal=4, run_at=_NOW + timedelta(minutes=1))
        bundle = _bundle(
            (revision_a, revision_b),
            (unit_a, unit_b),
            (report_a_late, report_a_early, report_b),
        )
        factory, _, _, _ = _setup(bundle)
        payload = ModeloVerificationReportListRequest(
            profile_id=_PROFILE,
            calculation_revision_id=revision_a.calculation_revision_id,
        )
        projection = capture_verification_report_list(payload, factory, operation=operation)

        assert projection.profile_id == _PROFILE
        assert projection.calculation_revision_id_filter == revision_a.calculation_revision_id
        assert projection.report_count == 2
        assert tuple(row.verification_report_id for row in projection.reports) == (
            report_a_early.verification_report_id,
            report_a_late.verification_report_id,
        )
        view = capture_verification_report_view(
            ModeloVerificationReportViewRequest(
                profile_id=_PROFILE,
                verification_report_id=report_a_late.verification_report_id,
            ),
            factory,
            operation=operation,
        )
        assert view.profile_id == _PROFILE
        assert view.report.verification_report_id == report_a_late.verification_report_id
        assert view.report.findings[0].legal_refs == report_a_late.findings[0].legal_refs
        assert view.report.findings[0].source_refs == report_a_late.findings[0].source_refs

        monkeypatch.setattr(capture_module, "MAX_MODELO_VERIFICATION_REPORT_LIST_ROWS", 1)
        with pytest.raises(ProfileAccessRefusedError) as oversized:
            capture_verification_report_list(
                ModeloVerificationReportListRequest(profile_id=_PROFILE),
                factory,
                operation=operation,
            )
        assert oversized.value.reason is AccessDenialCode.OPERATION_DENIED

        monkeypatch.setattr(capture_module, "MAX_MODELO_VERIFICATION_REPORT_LIST_ROWS", 4_096)
        monkeypatch.setattr(capture_module, "VERIFICATION_REPORT_RESULT_DOCUMENT_MAX_BYTES", 1)
        with pytest.raises(ProfileAccessRefusedError) as too_large:
            capture_verification_report_view(
                ModeloVerificationReportViewRequest(
                    profile_id=_PROFILE,
                    verification_report_id=report_a_late.verification_report_id,
                ),
                factory,
                operation=operation,
            )
        assert too_large.value.reason is AccessDenialCode.OPERATION_DENIED


def test_access_scopes_filtered_reads_and_tax_value_disclosure_to_exact_profile_period() -> None:
    with bundled_indexed_authority().operation() as operation:
        revision, unit = _revision_and_unit(operation, "1T")
        report = _report(revision, ordinal=5, run_at=_NOW, blocking=True)
        bundle = _bundle((revision,), (unit,), (report,))
        _factory, definitions, registrations, registry = _setup(bundle)
        list_definition, view_definition = definitions
        list_registration, view_registration = registrations
        list_request = _request(
            definition_id=list_definition.definition_id,
            payload=ModeloVerificationReportListRequest(
                profile_id=_PROFILE,
                calculation_revision_id=revision.calculation_revision_id,
            ),
        )
        view_request = _request(
            definition_id=view_definition.definition_id,
            payload=ModeloVerificationReportViewRequest(
                profile_id=_PROFILE,
                verification_report_id=report.verification_report_id,
            ),
        )

        admitted_list = resolve_operation_access(
            registry=registry,
            request=list_request,
            context=_context(list_registration, operation=operation),
        )
        assert admitted_list.request.periods == frozenset({unit.period})
        assert not admitted_list.request.period_independent
        list_result_context = _context(
            list_registration,
            operation=operation,
            action=AccessAction.RESULT,
            admitted=admitted_list.request,
        )
        list_result = resolve_operation_access(registry=registry, request=list_request, context=list_result_context)
        assert next(iter(list_result.policy.disclosures)).category is DisclosureCategory.TAX_VALUES

        admitted_view = resolve_operation_access(
            registry=registry,
            request=view_request,
            context=_context(view_registration, operation=operation),
        )
        assert admitted_view.request.periods == frozenset({unit.period})
        view_result_context = _context(
            view_registration,
            operation=operation,
            action=AccessAction.RESULT,
            admitted=admitted_view.request,
        )
        view_result = resolve_operation_access(registry=registry, request=view_request, context=view_result_context)
        assert next(iter(view_result.policy.disclosures)).category is DisclosureCategory.TAX_VALUES

        whole_profile_request = _request(
            definition_id=list_definition.definition_id,
            payload=ModeloVerificationReportListRequest(profile_id=_PROFILE),
        )
        whole_profile = resolve_operation_access(
            registry=registry,
            request=whole_profile_request,
            context=_context(list_registration, operation=operation),
        )
        assert whole_profile.request.period_independent
        assert whole_profile.request.periods == frozenset()
        assert whole_profile.policy.requires_all_periods

        with pytest.raises(ProfileAccessRefusedError) as mismatch:
            resolve_operation_access(
                registry=registry,
                request=list_request,
                context=_context(list_registration, operation=operation, profile_id=_OTHER_PROFILE),
            )
        assert mismatch.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_executor_captures_on_worker_and_publishes_one_complete_projection() -> None:
    with bundled_indexed_authority().operation() as operation:
        revision, unit = _revision_and_unit(operation, "1T")
        report = _report(revision, ordinal=6, run_at=_NOW)
        bundle = _bundle((revision,), (unit,), (report,))
        factory, definitions, _registrations, _registry = _setup(bundle)
        definition = definitions[0]
        request = _request(
            definition_id=definition.definition_id,
            payload=ModeloVerificationReportListRequest(profile_id=_PROFILE),
        )
        owner_thread = threading.get_ident()
        phases: list[str] = []
        effects: list[OperationEffect] = []
        stored: list[BaseModel] = []

        class Events:
            async def phase(self, phase_code: str) -> None:
                phases.append(phase_code)

            async def effect(self, effect: OperationEffect) -> None:
                effects.append(effect)

        class Operands:
            async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
                assert written_at.tzinfo is not None
                stored.append(operand)
                return _RESULT_REFERENCE

        context = SimpleNamespace(
            authority_operation=operation,
            identity=SimpleNamespace(definition_id=definition.definition_id, subject_ref=request.subject_ref),
            events=Events(),
            operands=Operands(),
        )
        reference = asyncio.run(definition.executor_factory.create().execute(request, context))

    assert reference == _RESULT_REFERENCE
    assert phases == [MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID]
    assert effects == [OperationEffect.NONE]
    assert len(stored) == 1
    assert type(stored[0]) is ModeloVerificationReportListProjection
    assert stored[0].profile_id == _PROFILE
    assert stored[0].report_count == 1
    assert bundle.calculation.read_threads[0] != owner_thread
    assert factory is not None


def test_view_projection_rejects_mismatched_receipt_and_schema_binds() -> None:
    with bundled_indexed_authority().operation() as operation:
        revision, _unit = _revision_and_unit(operation, "1T")
        report = _report(revision, ordinal=7, run_at=_NOW)

    projection = ModeloVerificationReportProjection.from_report(report)
    with pytest.raises(ValidationError):
        ModeloVerificationReportViewProjection(
            profile_id=_PROFILE,
            verification_report_id="a" * 64,
            report=projection,
        )

    def schema_factory(_profile_id: str, *, operation: PinnedAuthorityOperation):
        del operation
        raise AssertionError("schema binding must not resolve profile repositories")

    definitions, registrations = _read_definitions_and_registrations(schema_factory)
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)

    assert registry.lookup(MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID).result_type is (
        ModeloVerificationReportListProjection
    )
    assert registry.lookup(MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID).result_type is (
        ModeloVerificationReportViewProjection
    )
    view_result_schema = registry.lookup_public_registration(
        MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID
    ).contract.result_schema
    assert view_result_schema is not None
