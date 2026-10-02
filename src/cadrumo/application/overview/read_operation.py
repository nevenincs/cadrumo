"""Registered exact-profile overview reads over canonical capture ports."""

from __future__ import annotations

import asyncio
from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import override_settings
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .coverage import ObligationCoverageReport
from .read_calendar_projection import OverviewAgendaSnapshot, OverviewBacklogSnapshot, OverviewCalendarSnapshot
from .read_ports import OverviewReadPortsFactory
from .read_projection import (
    OverviewCalendarSurveySnapshot,
    OverviewExplainSnapshot,
    OverviewNoticeSnapshot,
    OverviewPeriodStatusSnapshot,
    OverviewPrepareSnapshot,
    OverviewStatusSnapshot,
)


class OverviewReadKind(StrEnum):
    """Installed read leaves sharing the same authenticated capture seam."""

    STATUS = "status"
    CALENDAR = "calendar"
    AGENDA = "agenda"
    BACKLOG = "backlog"
    EXPLAIN = "explain"
    PREPARE = "prepare"


OVERVIEW_READ_DEFINITION_IDS = {kind: f"overview.{kind.value}" for kind in OverviewReadKind}


class OverviewReadRequest(CredentialFreeOperationRequest):
    """One immutable query, with irrelevant fields structurally refused."""

    profile_id: UUID
    kind: OverviewReadKind
    output_language: OutputLanguage
    period: PublicPeriod | None = None
    from_date: date | None = None
    to_date: date | None = None
    as_of: date | None = None
    horizon_days: int | None = None
    modelo: str | None = Field(default=None, pattern=r"^[0-9]{3}$", max_length=3)
    year: FilingYear | None = None
    verbose: bool | None = None
    allow_incomplete: bool | None = None
    show_suppressed: bool | None = None
    all_profiles: bool | None = None

    @model_validator(mode="after")
    def _query(self) -> Self:
        common = {"profile_id", "kind", "output_language"}
        allowed = {
            OverviewReadKind.STATUS: {"period", "verbose"},
            OverviewReadKind.CALENDAR: {"from_date", "to_date", "allow_incomplete", "show_suppressed", "all_profiles"},
            OverviewReadKind.AGENDA: {"as_of", "horizon_days", "allow_incomplete"},
            OverviewReadKind.BACKLOG: {"from_date", "to_date", "allow_incomplete"},
            OverviewReadKind.EXPLAIN: {"modelo", "year"},
            OverviewReadKind.PREPARE: {"modelo", "period"},
        }[self.kind]
        if any(getattr(self, field) is not None for field in type(self).model_fields.keys() - common - allowed):
            raise ValueError("overview query contains fields from another command")
        if self.kind is OverviewReadKind.CALENDAR and (self.from_date is None or self.to_date is None):
            raise ValueError("calendar query requires a date window")
        if self.from_date is not None and self.to_date is not None and self.from_date > self.to_date:
            raise ValueError("overview date window is reversed")
        if self.kind in {OverviewReadKind.EXPLAIN, OverviewReadKind.PREPARE} and not self.modelo:
            raise ValueError("overview query requires a modelo")
        if self.kind is OverviewReadKind.PREPARE and self.period is None:
            raise ValueError("preparation query requires an exact period")
        if self.horizon_days is not None and not 1 <= self.horizon_days <= 365:
            raise ValueError("agenda horizon must be between one and 365 days")
        return self


class OverviewStatusRead(BaseModel):
    """Full workspace status or the selected period's draft list."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["status"] = "status"
    report: OverviewStatusSnapshot | None = None
    period_report: OverviewPeriodStatusSnapshot | None = None
    coverage_advised_count: int = 0
    coverage: ObligationCoverageReport | None = None
    notices: tuple[OverviewNoticeSnapshot, ...] = ()

    @model_validator(mode="after")
    def _one(self) -> Self:
        if (self.report is None) == (self.period_report is None):
            raise ValueError("overview status requires exactly one report")
        return self


class OverviewCalendarRead(BaseModel):
    """One bound calendar or a survey with locked public pointers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["calendar"] = "calendar"
    calendar: OverviewCalendarSnapshot | None = None
    survey: OverviewCalendarSurveySnapshot | None = None
    notices: tuple[OverviewNoticeSnapshot, ...] = ()
    deemed_served_legal_ref: str | None = None
    refusal_requirements: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _one(self) -> Self:
        if (self.calendar is None) == (self.survey is None):
            raise ValueError("overview calendar requires exactly one result")
        return self


class OverviewAgendaRead(BaseModel):
    """Canonical agenda cohorts with no underlying profile record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["agenda"] = "agenda"
    agenda: OverviewAgendaSnapshot
    refusal_requirements: tuple[str, ...] = ()


class OverviewBacklogRead(BaseModel):
    """Canonical late cohort and optional work-unit degradation notice."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["backlog"] = "backlog"
    backlog: OverviewBacklogSnapshot
    notices: tuple[OverviewNoticeSnapshot, ...] = ()
    refusal_requirements: tuple[str, ...] = ()


class OverviewExplainRead(BaseModel):
    """Registry-grounded applicability report and pending payer notices."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["explain"] = "explain"
    explanation: OverviewExplainSnapshot
    notices: tuple[OverviewNoticeSnapshot, ...] = ()


class OverviewPrepareRead(BaseModel):
    """Exact-period canonical preparation checklist."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["prepare"] = "prepare"
    preparation: OverviewPrepareSnapshot


type OverviewReadPayload = Annotated[
    OverviewStatusRead
    | OverviewCalendarRead
    | OverviewAgendaRead
    | OverviewBacklogRead
    | OverviewExplainRead
    | OverviewPrepareRead,
    Field(discriminator="kind"),
]


def _validate_result(profile_id: UUID, request: OverviewReadRequest, payload: OverviewReadPayload) -> None:
    if request.profile_id != profile_id or payload.kind != request.kind.value:
        raise ValueError("overview read identity differs from its request")
    if isinstance(payload, OverviewStatusRead):
        if (payload.period_report is None) != (request.period is None):
            raise ValueError("overview status scope differs from its request")
        if payload.period_report is not None and payload.period_report.period != request.period:
            raise ValueError("overview period status differs from requested period")
    elif isinstance(payload, OverviewCalendarRead):
        if (payload.survey is not None) != bool(request.all_profiles):
            raise ValueError("overview calendar profile mode differs from request")
        calendar = (
            payload.calendar
            if payload.calendar is not None
            else payload.survey.active_calendar
            if payload.survey
            else None
        )
        if calendar is not None and (
            calendar.range.from_date != request.from_date or calendar.range.to_date != request.to_date
        ):
            raise ValueError("overview calendar window differs from request")
        if payload.survey is not None and (
            payload.survey.from_date != request.from_date or payload.survey.to_date != request.to_date
        ):
            raise ValueError("overview survey window differs from request")
        if payload.survey is not None and payload.survey.active_profile_id not in {None, str(profile_id)}:
            raise ValueError("overview survey exposed another active profile")
    elif isinstance(payload, OverviewAgendaRead):
        if request.as_of is not None and payload.agenda.as_of != request.as_of:
            raise ValueError("overview agenda date differs from request")
        if request.horizon_days is not None and payload.agenda.horizon_days != request.horizon_days:
            raise ValueError("overview agenda horizon differs from request")
    elif isinstance(payload, OverviewExplainRead):
        if payload.explanation.modelo != request.modelo or (
            request.year is not None and payload.explanation.year != request.year
        ):
            raise ValueError("overview explanation differs from request")
    elif isinstance(payload, OverviewPrepareRead):
        if (
            payload.preparation.modelo != request.modelo
            or request.period is None
            or payload.preparation.filing_year != request.period.filing_year
            or payload.preparation.period != request.period.code
        ):
            raise ValueError("overview preparation differs from requested scope")


class OverviewReadResult(BaseModel):
    """Encrypted canonical capture with immutable request provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    request: OverviewReadRequest
    payload: OverviewReadPayload

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_result(self.profile_id, self.request, self.payload)
        return self


class OverviewReadProjection(BaseModel):
    """Independent result disclosure with only closed captured facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    request: OverviewReadRequest
    payload: OverviewReadPayload

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_result(self.profile_id, self.request, self.payload)
        return self


def project_overview_read_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> OverviewReadProjection:
    """Release only a successful no-effect result for its exact profile subject."""
    if type(result) is not OverviewReadResult:
        raise ValueError("invalid overview read result")
    private = OverviewReadResult.model_validate(result.model_dump(mode="python"), strict=True)
    if (
        receipt.identity.definition_id != OVERVIEW_READ_DEFINITION_IDS[private.request.kind]
        or receipt.identity.subject_ref != profile_operation_subject(str(private.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
    ):
        raise ValueError("overview read result contradicts its terminal receipt")
    return OverviewReadProjection(profile_id=private.profile_id, request=private.request, payload=private.payload)


class OverviewReadExecutor:
    """Capture one selected canonical overview report in the profile worker."""

    def __init__(self, factory: OverviewReadPortsFactory, definition_id: str) -> None:
        """Hold only the profile-bound read factory and operation identity."""
        self._factory = factory
        self._definition_id = definition_id

    def _capture(self, payload: OverviewReadRequest, operation: PinnedAuthorityOperation) -> OverviewReadResult:
        bucket_id = str(payload.profile_id)
        ports = self._factory(bucket_id=bucket_id, operation=operation)
        if ports.bucket_id != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        with override_settings(cadrumo_output_language=payload.output_language.value):
            projection = ports.capture(payload, operation=operation)
        return OverviewReadResult(profile_id=payload.profile_id, request=payload, payload=projection)

    async def execute(self, request: OperationRequest[OverviewReadRequest], context: OperationExecutorContext) -> str:
        """Retain cancellation ownership through capture and encrypted publication."""
        payload = request.payload
        if (
            request.definition_id != self._definition_id
            or self._definition_id != OVERVIEW_READ_DEFINITION_IDS[payload.kind]
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(self._definition_id)

        async def capture() -> str:
            result = await asyncio.to_thread(self._capture, payload, context.authority_operation)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="overview-read")


def build_overview_read_definition(kind: OverviewReadKind, factory: OverviewReadPortsFactory) -> OperationDefinition:
    """Build one installed overview leaf over the shared exact-profile seam."""
    definition_id = OVERVIEW_READ_DEFINITION_IDS[kind]
    return OperationDefinition(
        definition_id=definition_id,
        request_type=OverviewReadRequest,
        result_type=OverviewReadResult,
        executor_factory=OperationExecutorFactory(
            request_type=OverviewReadRequest,
            executor_type=OverviewReadExecutor,
            build=lambda: OverviewReadExecutor(factory, definition_id),
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_overview_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile consent except for exact period status/preparation."""
    payload = request.payload
    if (
        not isinstance(payload, OverviewReadRequest)
        or request.definition_id != OVERVIEW_READ_DEFINITION_IDS[payload.kind]
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    periods: frozenset[Period] = frozenset[Period]()
    if payload.period is not None and payload.kind in {OverviewReadKind.STATUS, OverviewReadKind.PREPARE}:
        periods = frozenset({payload.period.to_period()})
    return resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=periods)


def build_overview_read_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind one named leaf to exact request and independent result schemas."""
    if definition.definition_id not in OVERVIEW_READ_DEFINITION_IDS.values():
        raise ValueError("unrecognized overview read definition")
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=OverviewReadRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=OverviewReadProjection
        ),
        access_resolver=resolve_overview_read_access,
        result_projector=project_overview_read_result,
    )


__all__ = [
    "OVERVIEW_READ_DEFINITION_IDS",
    "OverviewReadKind",
    "OverviewReadProjection",
    "OverviewReadRequest",
    "build_overview_read_definition",
    "build_overview_read_registration",
]
