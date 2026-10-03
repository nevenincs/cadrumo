"""The registered workbench read retains exact human and result boundaries."""

from __future__ import annotations

import asyncio
import json
import multiprocessing
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.application import workbench_generation_operation as generation_operation_module
from cadrumo.application.modelo.declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceStateV1,
)
from cadrumo.application.modelo.declarations_workspace_contracts import (
    DeclarationsLifecycleKind,
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceCalculationRevisionRefV1,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceFilingRefV1,
    DeclarationsWorkspaceLifecycleRefV1,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceSource,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneStateV1,
)
from cadrumo.application.modelo.work_addressing import ModeloExactWorkUnitTarget
from cadrumo.application.modelo.work_review import BlockerRef
from cadrumo.application.modelo.workspace import resolve_static_inspection_result
from cadrumo.application.modelo.workspace_models import (
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceStaticInspectionResultV1,
)
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.public_mirror import (
    PublicScalarValueV1,
    PublicTextEntryV1,
    project_public_mirror,
    restore_public_mirror,
)
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.overview.calendar_models import (
    OverviewCalendarEntrySource,
    OverviewCalendarRange,
    OverviewPeriodState,
)
from cadrumo.application.overview.home import (
    HomeAccountSession,
    HomeAvailability,
    HomeProjectionInput,
    HomeSessionPosture,
    HomeZoneState,
)
from cadrumo.application.overview.next_actions import declare_next_action
from cadrumo.application.search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.workbench_generation import (
    InstalledWorkbenchGenerationProviderV1,
    assemble_workbench_generation,
)
from cadrumo.application.workbench_generation_contracts import (
    WorkbenchGenerationInputsV1,
    WorkbenchGenerationSourceResultV1,
    WorkbenchGenerationV1,
)
from cadrumo.application.workbench_generation_modelo_contracts import (
    PublicBlockerRef,
    PublicModeloWorkConditionalRecargoPreview,
)
from cadrumo.application.workbench_generation_operation import (
    WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
    WorkbenchGenerationExecutor,
    WorkbenchGenerationOperationRequest,
    build_workbench_generation_operation_definition,
    build_workbench_generation_operation_registration,
    resolve_workbench_generation_access,
)
from cadrumo.application.workbench_generation_projection import (
    WorkbenchGenerationOperationProjection,
    project_workbench_generation,
    restore_workbench_generation,
)
from cadrumo.application.workbench_generation_reader import SecureProfileWorkbenchGenerationReadDoorV1
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.operations import OperationEffect, profile_operation_subject
from cadrumo.core.operator_action_enums import OperatorActionAxis
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.deadlines.festivos import DeadlineHolidayCoverage
from cadrumo.domain.deadlines.models import ObligationStatus
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
)
from cadrumo.domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from cadrumo.domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileRecord, create_user_profile_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_NOW = datetime(2026, 9, 27, 18, tzinfo=UTC)


@dataclass
class _Repository[ValueT]:
    value: ValueT
    bucket_id: str

    def exists(self) -> bool:
        return True

    def load(self, *, operation: object | None = None) -> ValueT:
        return self.value

    def load_revisioned(self, *, operation: PinnedAuthorityOperation | None = None) -> tuple[ValueT, str]:
        del operation
        return self.value, "revision-1"

    def save(self, catalogue: ValueT) -> None:
        self.value = catalogue


@dataclass
class _ProfileRepository:
    profile_id: str
    record: UserProfileRecord

    def load(self, profile_id: str) -> UserProfileRecord:
        assert profile_id == self.profile_id
        return self.record


def _generation(
    declarations: DeclarationsWorkspaceProjectionV1 | None = None,
    calendar: DeclarationsCalendarProjectionV1 | None = None,
    *,
    empty_modelo: bool = False,
) -> WorkbenchGenerationV1:
    if declarations is not None and calendar is None:
        calendar = _empty_calendar()

    def zone(name: str) -> HomeZoneState:
        return HomeZoneState(availability=HomeAvailability.NEVER_CAPTURED, reason_code=f"source.{name}")

    missing = WorkbenchGenerationSourceResultV1.never_captured(refusal="source.missing")
    home = HomeProjectionInput(
        generated_at=_NOW,
        account=HomeAccountSession(posture=HomeSessionPosture.NO_PROFILE),
        actions_state=zone("actions"),
        declarations_state=zone("declarations"),
        ledger_state=zone("ledger"),
        agenda_state=zone("agenda"),
        agenda_evidence_state=zone("agenda_evidence"),
        messages_state=zone("messages"),
    )

    def admission(destination: str) -> WorkbenchDestinationAdmission:
        return WorkbenchDestinationAdmission(
            destination=destination,
            state=WorkbenchDestinationAdmissionState.NEVER_CAPTURED,
            reason_code=f"{destination}.not_captured",
        )

    return assemble_workbench_generation(
        WorkbenchGenerationInputsV1(
            assembled_at=_NOW,
            home=WorkbenchGenerationSourceResultV1.available(home, observed_at=_NOW),
            ledger=missing,
            declarations=(
                WorkbenchGenerationSourceResultV1.available(declarations, observed_at=_NOW)
                if declarations is not None
                else missing
            ),
            declarations_calendar=(
                WorkbenchGenerationSourceResultV1.available(calendar, observed_at=_NOW)
                if calendar is not None
                else missing
            ),
            aeat_sync=missing,
            modelo=(WorkbenchGenerationSourceResultV1.available((), observed_at=_NOW) if empty_modelo else missing),
            ledger_admission=admission("workbench.ledger"),
            declarations_admission=(
                WorkbenchDestinationAdmission(
                    destination="workbench.declarations",
                    state=WorkbenchDestinationAdmissionState.AVAILABLE,
                )
                if declarations is not None
                else admission("workbench.declarations")
            ),
            aeat_sync_admission=admission("workbench.aeat_sync"),
        )
    )


def _declarations(profile_id: UUID) -> DeclarationsWorkspaceProjectionV1:
    period = Period.from_year_and_code(2026, "1T")
    unit_id, revision_id, filing_id = "a" * 64, "b" * 64, "c" * 64
    sources = {
        DeclarationsWorkspaceZone.DECLARATIONS: (DeclarationsWorkspaceSource.LOCAL_DECLARATIONS,),
        DeclarationsWorkspaceZone.CALCULATION_REVISIONS: (
            DeclarationsWorkspaceSource.LOCAL_DECLARATIONS,
            DeclarationsWorkspaceSource.LOCAL_CALCULATIONS,
        ),
        DeclarationsWorkspaceZone.FILING_HISTORY: (
            DeclarationsWorkspaceSource.LOCAL_DECLARATIONS,
            DeclarationsWorkspaceSource.LOCAL_CALCULATIONS,
            DeclarationsWorkspaceSource.LOCAL_FILINGS,
            DeclarationsWorkspaceSource.LOCAL_LIFECYCLE,
            DeclarationsWorkspaceSource.AEAT_EVIDENCE,
        ),
    }
    return DeclarationsWorkspaceProjectionV1(
        bucket_id=str(profile_id),
        zones=tuple(
            DeclarationsWorkspaceZoneStateV1(
                zone=zone,
                availability=DeclarationsWorkspaceAvailability.AVAILABLE,
                observed_at=_NOW,
                sources=sources[zone],
                item_count=1,
            )
            for zone in DeclarationsWorkspaceZone
        ),
        declarations=(
            DeclarationsWorkspaceDeclarationRefV1(
                work_unit_id=unit_id,
                modelo="130",
                filing_year=2026,
                period=period,
                state=WorkUnitState.BORRADOR,
                has_current_calculation=True,
                has_current_filing=True,
            ),
        ),
        calculation_revisions=(
            DeclarationsWorkspaceCalculationRevisionRefV1(
                calculation_revision_id=revision_id,
                work_unit_id=unit_id,
                modelo="130",
                filing_year=2026,
                period=period,
                state=CalculationRevisionState.PRESENTADO,
                created_at=_NOW,
                updated_at=_NOW,
                is_current=True,
                is_filed=True,
            ),
        ),
        filings=(
            DeclarationsWorkspaceFilingRefV1(
                filing_record_id=filing_id,
                work_unit_id=unit_id,
                calculation_revision_id=revision_id,
                modelo="130",
                filing_year=2026,
                period=period,
                filed_at=_NOW,
                local_status=ModeloRecordStatus.VIGENTE,
                origin=FilingOrigin.LOCAL,
                confirmation=AeatConfirmationState.PENDIENTE,
                declaration_kind=FilingDeclarationKind.RECTIFICATIVA,
                amends_filing_record_id="d" * 64,
            ),
        ),
        lifecycle=(
            DeclarationsWorkspaceLifecycleRefV1(
                fact_id="event-1",
                work_unit_id=unit_id,
                modelo="130",
                filing_year=2026,
                period=period,
                occurred_at=_NOW,
                kind=DeclarationsLifecycleKind.CREATED,
            ),
        ),
    )


def _calendar_with_recovery() -> DeclarationsCalendarProjectionV1:
    deadline = date(2026, 4, 20)
    as_of = date(2026, 9, 27)
    sources = (
        DeclarationsCalendarSourceStateV1(
            source=DeclarationsCalendarSource.SCHEDULE,
            availability=HomeAvailability.AVAILABLE,
            observed_at=_NOW,
            item_count=1,
        ),
        *(
            DeclarationsCalendarSourceStateV1(
                source=source,
                availability=HomeAvailability.NEVER_CAPTURED,
                reason_code=f"calendar.{source.value}.never",
            )
            for source in (DeclarationsCalendarSource.LOCAL_FILING, DeclarationsCalendarSource.AEAT_EVIDENCE)
        ),
    )
    return DeclarationsCalendarProjectionV1(
        as_of=as_of,
        generated_at=_NOW,
        query_range=OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
        sources=sources,
        entries=(
            DeclarationsCalendarEntryRefV1(
                modelo="130",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                opens_on=date(2026, 4, 1),
                closes_on=deadline,
                adjusted_closes_on=deadline,
                shift_reason="fixture",
                holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
                evaluated_on=as_of,
                days_overdue=(as_of - deadline).days,
                legal_status=ObligationStatus.OVERDUE,
                user_state=OverviewPeriodState.LATE,
                local_filing_state=None,
                aeat_submission_state=None,
                justificante_verified=None,
                evidence_conflicted=False,
                source=OverviewCalendarEntrySource.REGISTRY_DEADLINE,
                recovery_action=declare_next_action(
                    "operator.modelo.work.create", modelo="130", year=2026, period="1T"
                ),
            ),
        ),
    )


def _empty_calendar() -> DeclarationsCalendarProjectionV1:
    return DeclarationsCalendarProjectionV1(
        as_of=date(2026, 9, 27),
        generated_at=_NOW,
        query_range=OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
        sources=(
            DeclarationsCalendarSourceStateV1(
                source=DeclarationsCalendarSource.SCHEDULE,
                availability=HomeAvailability.AVAILABLE,
                observed_at=_NOW,
                item_count=0,
            ),
            *(
                DeclarationsCalendarSourceStateV1(
                    source=source,
                    availability=HomeAvailability.NEVER_CAPTURED,
                    reason_code=f"calendar.{source.value}.never",
                )
                for source in (DeclarationsCalendarSource.LOCAL_FILING, DeclarationsCalendarSource.AEAT_EVIDENCE)
            ),
        ),
        entries=(),
    )


def _registry() -> OperationRegistry:
    definition = build_workbench_generation_operation_definition()
    registration = build_workbench_generation_operation_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _request(
    profile_id: UUID, *, language: OutputLanguage = OutputLanguage.ES
) -> OperationRequest[WorkbenchGenerationOperationRequest]:
    return OperationRequest(
        definition_id=WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=WorkbenchGenerationOperationRequest(profile_id=profile_id, output_language=language),
    )


def test_request_is_credential_free_and_registration_is_human_cli_tui_only() -> None:
    profile_id = uuid4()
    request = _request(profile_id, language=OutputLanguage.CA)
    assert WorkbenchGenerationOperationRequest.model_validate_json(request.payload.model_dump_json()) == request.payload
    with pytest.raises(ValidationError):
        WorkbenchGenerationOperationRequest.model_validate(
            {"profile_id": str(profile_id), "output_language": "ca", "session_id": str(uuid4())}
        )
    registry = _registry()
    contract = registry.lookup_public_contract(WORKBENCH_GENERATION_OPERATION_DEFINITION_ID)
    assert contract.permitted_frontends == frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
    assert contract.result_schema is not None
    assert registry.lookup_public_registration(contract.definition_id).result_projector is None


def test_result_requires_profile_and_tax_disclosures_for_exact_subject() -> None:
    registry = _registry()
    profile_id, destination_id = uuid4(), uuid4()
    request = _request(profile_id)
    contract = registry.lookup_public_contract(request.definition_id)
    for action, categories in (
        (AccessAction.SUBMIT, set()),
        (AccessAction.OBSERVE, {DisclosureCategory.OPERATION_METADATA}),
        (AccessAction.RESULT, {DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES}),
    ):
        resolved = resolve_operation_access(
            registry=registry,
            request=cast(OperationRequest[BaseModel], cast(object, request)),
            context=OperationAccessContext(
                profile_id=profile_id,
                destination_id=destination_id,
                action=action,
                frontend=OperationFrontendProjection.TUI,
                contract=contract,
                published_authority=Availability.AVAILABLE,
            ),
        )
        assert resolved.policy.requires_human
        assert {item.category for item in resolved.policy.disclosures} == categories
        assert all(item.destination_id == destination_id for item in resolved.policy.disclosures)
    with pytest.raises(ProfileAccessRefusedError) as mismatch:
        resolve_operation_access(
            registry=registry,
            request=cast(OperationRequest[BaseModel], cast(object, request)),
            context=OperationAccessContext(
                profile_id=uuid4(),
                destination_id=destination_id,
                action=AccessAction.RESULT,
                frontend=OperationFrontendProjection.TUI,
                contract=contract,
                published_authority=Availability.AVAILABLE,
            ),
        )
    assert mismatch.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_result_without_a_registered_result_schema_is_refused_not_silently_undisclosed() -> None:
    profile_id = uuid4()
    request = cast(OperationRequest[BaseModel], cast(object, _request(profile_id)))
    contract = _registry().lookup_public_contract(WORKBENCH_GENERATION_OPERATION_DEFINITION_ID)
    schemaless = contract.model_copy(update={"result_schema": None})

    def context(action: AccessAction) -> OperationAccessContext:
        return OperationAccessContext(
            profile_id=profile_id,
            destination_id=uuid4(),
            action=action,
            frontend=OperationFrontendProjection.CLI,
            contract=schemaless,
            published_authority=Availability.AVAILABLE,
        )

    assert resolve_workbench_generation_access(request, context(AccessAction.SUBMIT)).policy.disclosures == frozenset()
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_workbench_generation_access(request, context(AccessAction.RESULT))
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_public_projection_restores_generation_without_search_identity_transport() -> None:
    profile_id = uuid4()
    generation = _generation()
    result = project_workbench_generation(profile_id, generation)
    assert result.profile_id == profile_id
    assert not hasattr(result.generation.search, "projection")
    assert restore_workbench_generation(result) == generation
    assert WorkbenchGenerationOperationProjection.model_validate_json(result.model_dump_json()) == result


def _restore_in_fresh_process(document: str, result_path: str) -> None:
    from cadrumo.application.workbench_generation_projection import (
        WorkbenchGenerationOperationProjection,
        restore_workbench_generation,
    )

    projection = WorkbenchGenerationOperationProjection.model_validate_json(document)
    restored = restore_workbench_generation(projection)
    assert restored.modelo.projection == ()
    Path(result_path).write_text("ok", encoding="utf-8")


def test_fresh_import_restores_empty_modelo_projection_from_json(tmp_path: Path) -> None:
    profile_id = uuid4()
    generation = _generation(empty_modelo=True)
    assert generation.modelo.projection == ()
    public = project_workbench_generation(profile_id, generation)
    result_path = tmp_path / "restored.txt"
    process = multiprocessing.get_context("spawn").Process(
        target=_restore_in_fresh_process,
        args=(public.model_dump_json(), str(result_path)),
    )
    process.start()
    process.join(timeout=20)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
    assert process.exitcode == 0
    assert result_path.read_text(encoding="utf-8") == "ok"


def test_local_human_projection_preserves_reviewed_declaration_join_fields() -> None:
    profile_id = uuid4()
    generation = _generation(_declarations(profile_id))
    public = project_workbench_generation(profile_id, generation)
    serialized = public.model_dump_json()
    assert '"work_unit_id":"' + "a" * 64 + '"' in serialized
    assert '"calculation_revision_id":"' + "b" * 64 + '"' in serialized
    assert '"filing_record_id":"' + "c" * 64 + '"' in serialized
    assert '"amends_filing_record_id":"' + "d" * 64 + '"' in serialized
    assert '"fact_id":"event-1"' in serialized
    assert '"identity_basis"' not in serialized
    assert '"documents"' not in serialized
    restored = restore_workbench_generation(WorkbenchGenerationOperationProjection.model_validate_json(serialized))
    assert restored == generation
    assert restored.declarations.projection is not None
    assert restored.declarations.projection.filings[0].amends_prior_entry


def test_envelope_profile_must_match_nested_declaration_binding() -> None:
    source_profile, claimed_profile = uuid4(), uuid4()
    generation = _generation(_declarations(source_profile))
    with pytest.raises(ValueError, match="profile mismatch"):
        project_workbench_generation(claimed_profile, generation)
    public = project_workbench_generation(source_profile, generation)
    with pytest.raises(ValueError, match="profile mismatch"):
        restore_workbench_generation(public.model_copy(update={"profile_id": claimed_profile}))
    with pytest.raises(ValidationError, match="profile mismatch"):
        WorkbenchGenerationOperationProjection.model_validate(
            {**public.model_dump(mode="python"), "profile_id": claimed_profile}
        )


def test_new_excluded_field_requires_explicit_review(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = uuid4()
    field = DeclarationsWorkspaceDeclarationRefV1.model_fields["modelo"]
    monkeypatch.setattr(field, "exclude", True)
    with pytest.raises(ValueError, match="excluded-field inventory changed"):
        project_workbench_generation(profile_id, _generation(_declarations(profile_id)))


def test_catalogue_recovery_action_survives_strict_public_round_trip() -> None:
    profile_id = uuid4()
    generation = _generation(calendar=_calendar_with_recovery())
    public = project_workbench_generation(profile_id, generation)
    decoded = WorkbenchGenerationOperationProjection.model_validate_json(public.model_dump_json())
    restored = restore_workbench_generation(decoded)
    assert restored.declarations_calendar.projection is not None
    assert restored.declarations_calendar.projection.entries[0].recovery_action == (
        generation.declarations_calendar.projection.entries[0].recovery_action
        if generation.declarations_calendar.projection is not None
        else None
    )


def test_secure_canonical_generation_round_trips_without_search_documents() -> None:
    profile_id = uuid4()
    with bundled_indexed_authority().operation() as operation:
        record = create_user_profile_record(
            context=operation.profile_create_context(),
            profile_id=str(profile_id),
            setup_state=ProfileSetupState.INCOMPLETE,
        )
        period = Period.from_year_and_code(2026, "1T")
        revision_id = operation.snapshot("130", filing_year=2026, period="1T").revision.id
        unit = WorkUnit(
            work_unit_id=derive_work_unit_id(
                bucket_id=str(profile_id),
                modelo="130",
                filing_year=2026,
                period=period,
                revision_id=revision_id,
            ),
            bucket_id=str(profile_id),
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id=revision_id,
            name="declaration",
            created_at=_NOW,
            updated_at=_NOW,
        )
        work_units = _Repository(WorkUnitCatalogue(work_units={unit.work_unit_id: unit}), str(profile_id))
        static_result = resolve_static_inspection_result(
            ModeloWorkspaceExactWorkUnitTargetV1(
                target=ModeloExactWorkUnitTarget(work_unit_id=unit.work_unit_id, bucket_id=unit.bucket_id)
            ),
            bucket_id=str(profile_id),
            catalogue_repository=cast(WorkUnitCatalogueRepositoryProtocol, work_units),
            authority=operation,
            output_language=OutputLanguage.ES,
        )
        assert isinstance(static_result, ModeloWorkspaceStaticInspectionResultV1)
        static_projection = static_result.projection
        generation = InstalledWorkbenchGenerationProviderV1(
            SecureProfileWorkbenchGenerationReadDoorV1(
                profile_id=str(profile_id),
                operation=operation,
                profile_repository=_ProfileRepository(str(profile_id), record),
                work_unit_repository=cast(WorkUnitCatalogueRepositoryProtocol, work_units),
                calculation_repository=cast(
                    CalculationRevisionCatalogueRepositoryProtocol,
                    _Repository(CalculationRevisionCatalogue(), str(profile_id)),
                ),
                filing_repository=cast(
                    ModeloRecordCatalogueRepositoryProtocol, _Repository(ModeloRecordCatalogue(), str(profile_id))
                ),
                clock=lambda: _NOW,
                account_session_reader=lambda: HomeAccountSession(
                    posture=HomeSessionPosture.ACTIVE,
                    profile_label="Local human",
                    expires_at=_NOW,
                ),
                modelo_projection_reader=lambda _unit: static_projection,
            )
        )()
    public = project_workbench_generation(profile_id, generation)
    decoded = WorkbenchGenerationOperationProjection.model_validate_json(public.model_dump_json())
    assert restore_workbench_generation(decoded) == generation
    assert '"documents"' not in public.model_dump_json()
    assert generation.modelo.projection is not None


def test_ordered_fact_entries_retain_decimal_precision_and_refuse_duplicate_keys() -> None:
    canonical = BlockerRef(
        axis=OperatorActionAxis.RE_VERIFY,
        native_code="source.review",
        facts={"amount": Decimal("1.2300"), "false": False},
    )
    public = cast(PublicBlockerRef, project_public_mirror(canonical, BlockerRef, PublicBlockerRef))
    assert [(item.key, item.kind, item.text) for item in public.facts] == [
        ("amount", "decimal", "1.2300"),
        ("false", "boolean", "false"),
    ]
    decoded = PublicBlockerRef.model_validate_json(public.model_dump_json())
    assert restore_public_mirror(decoded, BlockerRef, PublicBlockerRef) == canonical
    with pytest.raises(ValidationError, match="duplicate blocker fact key"):
        PublicBlockerRef.model_validate(
            {"axis": public.axis, "native_code": public.native_code, "facts": (*public.facts, public.facts[0])}
        )


def test_malformed_mapping_and_reused_model_are_refused_without_coercion() -> None:
    with pytest.raises(TypeError, match="mapping key must be text"):
        project_public_mirror({1: "value"}, Mapping[str, str], tuple[PublicTextEntryV1, ...])
    with pytest.raises(TypeError, match="mapping value must be text"):
        project_public_mirror({"key": 7}, Mapping[str, str], tuple[PublicTextEntryV1, ...])
    malformed_account = HomeAccountSession.model_construct(
        posture=HomeSessionPosture.NO_PROFILE,
        profile_label="contradictory",
    )
    with pytest.raises(ValidationError, match="no-profile session"):
        project_public_mirror(malformed_account, HomeAccountSession, HomeAccountSession)


def test_malformed_decimal_date_and_utc_values_refuse_at_public_boundary() -> None:
    with pytest.raises(ValidationError, match="invalid surcharge percentage"):
        PublicModeloWorkConditionalRecargoPreview.model_validate(
            {
                "band_id": "band",
                "surcharge_pct": "NaN",
                "interest_applies": False,
                "legal_ref": "law",
                "rate_reference_on": "2026-09-27",
                "assessment_status": "unassessed",
            }
        )
    with pytest.raises(ValueError, match="invalid public-mirror decimal"):
        restore_public_mirror("not-a-decimal", Decimal, str)
    with pytest.raises(ValidationError, match="invalid date scalar"):
        PublicScalarValueV1(kind="date", text="2026-99-99")
    valid = project_workbench_generation(uuid4(), _generation())
    tampered = valid.model_dump(mode="json")
    tampered["generation"]["assembled_at"] = "2026-09-27T20:00:00+02:00"
    with pytest.raises(ValidationError, match="UTC"):
        WorkbenchGenerationOperationProjection.model_validate_json(json.dumps(tampered))


@pytest.mark.asyncio
async def test_unpageable_success_refuses_before_any_result_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = uuid4()
    request = _request(profile_id)
    monkeypatch.setattr(generation_operation_module, "PROJECTION_DOCUMENT_MAX_BYTES", 128)
    calls: list[str] = []

    async def phase(*_args: object, **_kwargs: object) -> None:
        calls.append("phase")

    async def effect(*_args: object, **_kwargs: object) -> None:
        calls.append("effect")

    async def put(*_args: object, **_kwargs: object) -> None:
        calls.append("put")

    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="a" * 64,
                definition_id=request.definition_id,
                subject_ref=request.subject_ref,
            ),
            events=SimpleNamespace(phase=phase, effect=effect),
            operands=SimpleNamespace(put=put),
        ),
    )

    async def reader(
        _identity: OperationIdentity, _payload: WorkbenchGenerationOperationRequest
    ) -> WorkbenchGenerationV1:
        return _generation()

    executor = build_workbench_generation_operation_definition(reader).executor_factory.create()
    assert isinstance(executor, WorkbenchGenerationExecutor)
    with pytest.raises(ProfileAccessRefusedError) as refusal:
        await executor.execute(request, context)
    assert refusal.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    assert "put" not in calls
    assert "effect" not in calls


@pytest.mark.asyncio
async def test_executor_stores_actual_generation_and_none_effect_only_after_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = uuid4()
    request = _request(profile_id, language=OutputLanguage.CA)
    generated = _generation()
    calls: list[object] = []
    loop = asyncio.get_running_loop()
    validate = generation_operation_module._require_pageable_result

    def responsive_validation(projection: WorkbenchGenerationOperationProjection) -> None:
        heartbeat = Event()
        loop.call_soon_threadsafe(heartbeat.set)
        assert heartbeat.wait(2), "projection validation blocked runtime observations and lease renewal"
        validate(projection)

    monkeypatch.setattr(generation_operation_module, "_require_pageable_result", responsive_validation)

    async def reader(
        identity: OperationIdentity, payload: WorkbenchGenerationOperationRequest
    ) -> WorkbenchGenerationV1:
        assert identity.subject_ref == request.subject_ref
        assert payload == request.payload
        calls.append("read")
        return generated

    class Events:
        async def phase(self, value: str) -> None:
            calls.append(("phase", value))

        async def effect(self, value: OperationEffect) -> None:
            calls.append(("effect", value))

    class Operands:
        async def put(self, value: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            assert value == project_workbench_generation(profile_id, generated)
            calls.append("put")
            return "b" * 64

    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="a" * 64,
                definition_id=request.definition_id,
                subject_ref=request.subject_ref,
            ),
            events=Events(),
            operands=Operands(),
        ),
    )
    executor = build_workbench_generation_operation_definition(reader).executor_factory.create()
    assert isinstance(executor, WorkbenchGenerationExecutor)
    assert await executor.execute(request, context) == "b" * 64
    assert calls == [
        ("phase", "workbench.generation.execute"),
        "read",
        "put",
        ("effect", OperationEffect.NONE),
    ]


@pytest.mark.asyncio
async def test_uncomposed_reader_refuses_without_issuing_a_result() -> None:
    request = _request(uuid4())
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="a" * 64,
                definition_id=request.definition_id,
                subject_ref=request.subject_ref,
            )
        ),
    )
    executor = build_workbench_generation_operation_definition().executor_factory.create()
    assert isinstance(executor, WorkbenchGenerationExecutor)
    with pytest.raises(ProfileAccessRefusedError) as refusal:
        await executor.execute(request, context)
    assert refusal.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
