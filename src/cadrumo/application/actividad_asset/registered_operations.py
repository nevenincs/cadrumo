"""Profile-bound registered operations for IRPF activity assets."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal, Protocol, Self, cast
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...application.user_profile.profile_read_ports import ProfilePathValuesReadPort
from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import pydantic_validation_boundary
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
from ...domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetIncompleteError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from ...domain.user_profile.plantilla_media import plantilla_media_years
from ..calculations.actividad_asset_schedule import forecast_activity_asset_charge
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
from ..operations.public_scalar import PublicDecimal
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationResultProjector,
    OperationSchemaBindingV1,
)
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from .modality import direct_estimation_modality
from .operation_dtos import (
    ActivityAssetFilingHandoffSnapshot,
    ActivityAssetHistoryClaimResultSnapshot,
    ActivityAssetHistorySnapshot,
    ActivityAssetRevisionSnapshot,
    ScheduledAmortizationChargeSnapshot,
)
from .operations import ActivityAssetFilingHandoff, ActivityAssetOperations
from .ports import ActivityAssetHistoryRepository

ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID = "ledger.actividad-asset.create"
ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID = "ledger.actividad-asset.inspect"
ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID = "ledger.actividad-asset.correct"
ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID = "ledger.actividad-asset.forecast"
ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID = "ledger.actividad-asset.claim"
ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID = "ledger.actividad-asset.filing-handoff"

_REFUSED_VALIDATION = "REFUSED_ACTIVIDAD_ASSET_VALIDATION"
_REFUSED_UNSUPPORTED = "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED"
_REFUSED_INCOMPLETE = "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE"
_REFUSED_CLAIM_CONFLICT = "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT"
_REFUSAL_CODES = frozenset({_REFUSED_VALIDATION, _REFUSED_UNSUPPORTED, _REFUSED_INCOMPLETE, _REFUSED_CLAIM_CONFLICT})

_AssetId = Annotated[str, Field(min_length=1, max_length=128)]
_OperationName = Annotated[str, Field(min_length=1, max_length=256)]
_TaxYear = Annotated[int, Field(ge=1900, le=9999)]
_Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
_RefusalCode = Literal[
    "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
    "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED",
    "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE",
    "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT",
]


@dataclass(frozen=True, slots=True)
class ActivityAssetOperationPorts:
    """Canonical encrypted history and pinned-schema profile read ports."""

    history_repository: ActivityAssetHistoryRepository
    profile_path_values: ProfilePathValuesReadPort


class ActivityAssetOperationPortsFactory(Protocol):
    """Compose repositories for the immutable worker profile and authority pin."""

    def __call__(
        self,
        *,
        bucket_id: str,
        operation: PinnedAuthorityOperation,
    ) -> ActivityAssetOperationPorts:
        """Return only ports bound to ``bucket_id`` and ``operation``."""
        ...


class ActivityAssetAuthorityProvenance(BaseModel):
    """Exact published generation and reader incarnation used by this operation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    logical_generation: _Digest
    reader_incarnation: _Digest


class ActivityAssetRefusal(BaseModel):
    """Bounded public refusal detail without persisted exception prose."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: _RefusalCode
    precondition_verdict: PreconditionVerdictSnapshot | None = None


class _ActivityAssetRefusalResult(BaseModel):
    """Private refusal detail retained behind the encrypted result reference."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: _RefusalCode
    precondition_verdict: PreconditionVerdict | None = None


class _ActivityAssetOperationResult(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    authority: ActivityAssetAuthorityProvenance
    outcome: Literal["succeeded", "refused"]
    refusal: _ActivityAssetRefusalResult | None = None

    def _require_outcome(self, *, has_payload: bool) -> None:
        refused = self.outcome == "refused"
        if refused != (self.refusal is not None) or refused == has_payload:
            raise ValueError("activity-asset result outcome differs from its typed payload")


class ActivityAssetCreateRequest(BaseModel):
    """Create one immutable first revision in the exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    revision: ActivityAssetRevisionSnapshot


class ActivityAssetInspectRequest(BaseModel):
    """Inspect one complete immutable revision chain."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    asset_id: _AssetId


class ActivityAssetCorrectRequest(BaseModel):
    """Append one correction to the current immutable asset revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    revision: ActivityAssetRevisionSnapshot


class ActivityAssetForecastRequest(BaseModel):
    """Request a non-consuming charge forecast from pinned authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    asset_id: _AssetId
    covered_from: date
    covered_until: date
    requested_free_amount: PublicDecimal | None = None
    supersedes_claim_id: _Digest | None = None


class ActivityAssetClaimRequest(BaseModel):
    """Materialize a forecast as one explicit idempotent claim."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    forecast: ScheduledAmortizationChargeSnapshot
    creating_operation: _OperationName
    supersedes_claim_id: _Digest | None = None


class ActivityAssetFilingHandoffRequest(CredentialFreeOperationRequest):
    """Read the exact profile's existing M100 and M130 claim projections."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    tax_year: _TaxYear
    m130_period: Annotated[str, Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_canonical_period(self) -> Self:
        Period.from_year_and_code(self.tax_year, self.m130_period)
        return self


class ActivityAssetCreateResult(_ActivityAssetOperationResult):
    history: ActivityAssetHistory | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.history is not None)
        return self


class ActivityAssetInspectionRevision(BaseModel):
    """One typed revision plus its deterministic identity for correction."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    revision: ActivityAssetRevisionSnapshot
    revision_id: _Digest

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _identity_matches(self) -> Self:
        if self.revision_id != self.revision.to_domain().revision_id:
            raise ValueError("activity-asset inspection revision identity does not reproduce")
        return self


class ActivityAssetInspectResult(_ActivityAssetOperationResult):
    asset_id: _AssetId | None = None
    revisions: tuple[ActivityAssetInspectionRevision, ...] | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.revisions is not None)
        if self.outcome == "succeeded" and self.asset_id is None:
            raise ValueError("successful activity-asset inspection must identify its asset")
        if self.revisions is not None and (
            not self.revisions
            or self.asset_id is None
            or any(item.revision.asset_id != self.asset_id for item in self.revisions)
        ):
            raise ValueError("activity-asset inspection revisions must describe the requested asset")
        return self


class ActivityAssetCorrectResult(_ActivityAssetOperationResult):
    history: ActivityAssetHistory | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.history is not None)
        return self


class ActivityAssetForecastResult(_ActivityAssetOperationResult):
    forecast: ScheduledAmortizationCharge | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.forecast is not None)
        if self.forecast is not None and self.forecast.authority_generation != self.authority.logical_generation:
            raise ValueError("activity-asset forecast differs from its pinned authority generation")
        return self


class ActivityAssetClaimResult(_ActivityAssetOperationResult):
    claim_result: ActivityAssetHistoryClaimResult | None = None
    claim_id: _Digest | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.claim_result is not None and self.claim_id is not None)
        if (self.claim_result is None) != (self.claim_id is None):
            raise ValueError("activity-asset claim result and identity must appear together")
        if self.claim_result is not None and self.claim_id != self.claim_result.claim.claim_id:
            raise ValueError("activity-asset claim identity does not reproduce")
        return self


class ActivityAssetFilingHandoffResult(_ActivityAssetOperationResult):
    tax_year: _TaxYear | None = None
    m130_period: Annotated[str, Field(min_length=1, max_length=16)] | None = None
    filing_handoff: ActivityAssetFilingHandoff | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.filing_handoff is not None)
        if self.outcome == "succeeded" and (self.tax_year is None or self.m130_period is None):
            raise ValueError("successful activity-asset handoff must identify its filing frame")
        if self.filing_handoff is not None:
            if self.tax_year is None or self.m130_period is None:
                raise ValueError("activity-asset filing handoff requires its requested filing frame")
            expected = (
                self.filing_handoff.material_m100.tax_year,
                self.filing_handoff.intangible_m100.tax_year,
            )
            if expected != (self.tax_year, self.tax_year):
                raise ValueError("activity-asset filing handoff differs from its requested tax year")
            Period.from_year_and_code(self.tax_year, self.m130_period)
        return self


class _ActivityAssetOperationProjection(BaseModel):
    """Public, closed receipt common to all activity-asset result projections."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    authority: ActivityAssetAuthorityProvenance
    outcome: Literal["succeeded", "refused"]
    refusal: ActivityAssetRefusal | None = None

    def _require_outcome(self, *, has_payload: bool) -> None:
        refused = self.outcome == "refused"
        if refused != (self.refusal is not None) or refused == has_payload:
            raise ValueError("activity-asset projection outcome differs from its typed payload")


class ActivityAssetCreateProjection(_ActivityAssetOperationProjection):
    """Public create result with the complete persisted revision and claim history."""

    history: ActivityAssetHistorySnapshot | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.history is not None)
        return self


class ActivityAssetInspectProjection(_ActivityAssetOperationProjection):
    """Public typed revision chain, including correction identities."""

    asset_id: _AssetId | None = None
    revisions: tuple[ActivityAssetInspectionRevision, ...] | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.revisions is not None)
        if self.outcome == "succeeded" and self.asset_id is None:
            raise ValueError("successful activity-asset inspection must identify its asset")
        if self.revisions is not None and (
            not self.revisions
            or self.asset_id is None
            or any(item.revision.asset_id != self.asset_id for item in self.revisions)
        ):
            raise ValueError("activity-asset inspection revisions must describe the requested asset")
        return self


class ActivityAssetCorrectProjection(_ActivityAssetOperationProjection):
    """Public correction result with the complete persisted revision and claim history."""

    history: ActivityAssetHistorySnapshot | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.history is not None)
        return self


class ActivityAssetForecastProjection(_ActivityAssetOperationProjection):
    """Public typed forecast retaining the generation embedded in its schedule."""

    forecast: ScheduledAmortizationChargeSnapshot | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.forecast is not None)
        if self.forecast is not None and self.forecast.authority_generation != self.authority.logical_generation:
            raise ValueError("activity-asset forecast differs from its pinned authority generation")
        return self


class ActivityAssetClaimProjection(_ActivityAssetOperationProjection):
    """Public complete history/claim receipt and its deterministic claim ID."""

    claim_result: ActivityAssetHistoryClaimResultSnapshot | None = None
    claim_id: _Digest | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.claim_result is not None and self.claim_id is not None)
        if (self.claim_result is None) != (self.claim_id is None):
            raise ValueError("activity-asset claim result and identity must appear together")
        if self.claim_result is not None and self.claim_id != self.claim_result.claim.to_domain().claim_id:
            raise ValueError("activity-asset claim identity does not reproduce")
        return self


class ActivityAssetFilingHandoffProjection(_ActivityAssetOperationProjection):
    """Public typed filing handoff without recomputing or consuming claims."""

    tax_year: _TaxYear | None = None
    m130_period: Annotated[str, Field(min_length=1, max_length=16)] | None = None
    filing_handoff: ActivityAssetFilingHandoffSnapshot | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.filing_handoff is not None)
        if self.outcome == "succeeded" and (self.tax_year is None or self.m130_period is None):
            raise ValueError("successful activity-asset handoff must identify its filing frame")
        if self.filing_handoff is not None:
            if self.tax_year is None or self.m130_period is None:
                raise ValueError("activity-asset filing handoff requires its requested filing frame")
            expected = (
                self.filing_handoff.material_m100.tax_year,
                self.filing_handoff.intangible_m100.tax_year,
            )
            if expected != (self.tax_year, self.tax_year):
                raise ValueError("activity-asset filing handoff differs from its requested tax year")
            Period.from_year_and_code(self.tax_year, self.m130_period)
        return self


def _authority_provenance(operation: PinnedAuthorityOperation) -> ActivityAssetAuthorityProvenance:
    pin = operation.pin()
    return ActivityAssetAuthorityProvenance(
        logical_generation=pin.logical_generation,
        reader_incarnation=pin.reader_incarnation,
    )


def _activity_asset_operations(
    *,
    bucket_id: str,
    ports: ActivityAssetOperationPorts,
    operation: PinnedAuthorityOperation,
) -> ActivityAssetOperations:
    """Bind the canonical domain service to one worker profile and authority pin."""

    def profile_values() -> dict[str, str] | None:
        values = ports.profile_path_values.load_path_values(bucket_id=bucket_id)
        return None if values is None else dict(values)

    def taxpayer_modality():
        values = profile_values()
        token = None if values is None else values.get("irpf.estimation_regime")
        return direct_estimation_modality(token, authority=operation)

    def taxpayer_workforce():
        values = profile_values()
        return () if values is None else plantilla_media_years(values)

    def forecast(
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None,
    ) -> ScheduledAmortizationCharge:
        return forecast_activity_asset_charge(
            revision,
            modelo_100_revision=operation.revision_for_context(
                "100",
                filing_year=covered_from.year,
                period="0A",
            ),
            authority_generation=operation.pin().logical_generation,
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            taxpayer_workforce=taxpayer_workforce,
            legal_reference=operation.legal_reference,
            requested_free_amount=requested_free_amount,
        )

    return ActivityAssetOperations(
        repository=ports.history_repository,
        forecast_operation=forecast,
        taxpayer_modality=taxpayer_modality,
    )


def _worker_bucket(
    request: OperationRequest[Any],
    context: OperationExecutorContext,
    *,
    definition_id: str,
    profile_id: UUID,
) -> str:
    bucket_id = str(profile_id)
    expected_subject = profile_operation_subject(bucket_id)
    if (
        request.definition_id != definition_id
        or request.subject_ref != expected_subject
        or context.identity.definition_id != definition_id
        or context.identity.subject_ref != expected_subject
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bucket_id


def _refusal(error: Exception) -> _ActivityAssetRefusalResult | None:
    if isinstance(error, ActividadAssetIncompleteError):
        verdict = error.terminal_precondition_verdict
        return _ActivityAssetRefusalResult(
            code=_REFUSED_INCOMPLETE,
            precondition_verdict=verdict if isinstance(verdict, PreconditionVerdict) else None,
        )
    if isinstance(error, ActividadAssetUnsupportedError):
        return _ActivityAssetRefusalResult(code=_REFUSED_UNSUPPORTED)
    if isinstance(error, ActividadAssetClaimConflictError):
        return _ActivityAssetRefusalResult(code=_REFUSED_CLAIM_CONFLICT)
    if isinstance(error, ActividadAssetValidationError):
        return _ActivityAssetRefusalResult(code=_REFUSED_VALIDATION)
    return None


async def _store_refusal(
    context: OperationExecutorContext,
    *,
    result_type: type[_ActivityAssetOperationResult],
    profile_id: UUID,
    authority: ActivityAssetAuthorityProvenance,
    error: Exception,
    asset_id: str | None = None,
    tax_year: int | None = None,
    m130_period: str | None = None,
) -> OperationRefusalEvidence:
    refusal = _refusal(error)
    if refusal is None:
        raise error
    result = result_type(
        profile_id=profile_id,
        authority=authority,
        outcome="refused",
        refusal=refusal,
        **({"asset_id": asset_id} if result_type is ActivityAssetInspectResult else {}),
        **(
            {"tax_year": tax_year, "m130_period": m130_period}
            if result_type is ActivityAssetFilingHandoffResult
            else {}
        ),
    )
    detail_ref = await context.operands.put(result, written_at=now())
    await context.events.effect(OperationEffect.NONE)
    return OperationRefusalEvidence(refusal_code=refusal.code, detail_ref=detail_ref)


async def _load_operations(
    ports_factory: ActivityAssetOperationPortsFactory,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> ActivityAssetOperations:
    ports = await asyncio.to_thread(ports_factory, bucket_id=bucket_id, operation=operation)
    if not isinstance(ports, ActivityAssetOperationPorts):
        raise TypeError("activity-asset composition returned incompatible operation ports")
    return _activity_asset_operations(bucket_id=bucket_id, ports=ports, operation=operation)


class ActivityAssetCreateExecutor:
    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetCreateRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        payload = request.payload
        bucket_id = _worker_bucket(
            cast(OperationRequest[Any], request),
            context,
            definition_id=ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID)

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                operations = await _load_operations(
                    self._ports_factory,
                    bucket_id=bucket_id,
                    operation=context.authority_operation,
                )
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    history = await asyncio.to_thread(operations.create, payload.revision.to_domain())
                except (
                    ActividadAssetClaimConflictError,
                    ActividadAssetIncompleteError,
                    ActividadAssetUnsupportedError,
                    ActividadAssetValidationError,
                ) as error:
                    return await _store_refusal(
                        context,
                        result_type=ActivityAssetCreateResult,
                        profile_id=payload.profile_id,
                        authority=authority,
                        error=error,
                    )
                result = ActivityAssetCreateResult(
                    profile_id=payload.profile_id,
                    authority=authority,
                    outcome="succeeded",
                    history=history,
                )
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(commit(), task_name="activity-asset-create")


class ActivityAssetInspectExecutor:
    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetInspectRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        payload = request.payload
        bucket_id = _worker_bucket(
            cast(OperationRequest[Any], request),
            context,
            definition_id=ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID)

        async def capture() -> str | OperationRefusalEvidence:
            operations = await _load_operations(
                self._ports_factory,
                bucket_id=bucket_id,
                operation=context.authority_operation,
            )
            try:
                revisions = await asyncio.to_thread(operations.inspect, payload.asset_id)
            except (
                ActividadAssetClaimConflictError,
                ActividadAssetIncompleteError,
                ActividadAssetUnsupportedError,
                ActividadAssetValidationError,
            ) as error:
                return await _store_refusal(
                    context,
                    result_type=ActivityAssetInspectResult,
                    profile_id=payload.profile_id,
                    authority=authority,
                    error=error,
                    asset_id=payload.asset_id,
                )
            result = ActivityAssetInspectResult(
                profile_id=payload.profile_id,
                authority=authority,
                outcome="succeeded",
                asset_id=payload.asset_id,
                revisions=tuple(
                    ActivityAssetInspectionRevision(
                        revision=ActivityAssetRevisionSnapshot.from_domain(revision),
                        revision_id=revision.revision_id,
                    )
                    for revision in revisions
                ),
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="activity-asset-inspect")


class ActivityAssetCorrectExecutor:
    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetCorrectRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        payload = request.payload
        bucket_id = _worker_bucket(
            cast(OperationRequest[Any], request),
            context,
            definition_id=ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID)

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                operations = await _load_operations(
                    self._ports_factory,
                    bucket_id=bucket_id,
                    operation=context.authority_operation,
                )
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    history = await asyncio.to_thread(operations.correct, payload.revision.to_domain())
                except (
                    ActividadAssetClaimConflictError,
                    ActividadAssetIncompleteError,
                    ActividadAssetUnsupportedError,
                    ActividadAssetValidationError,
                ) as error:
                    return await _store_refusal(
                        context,
                        result_type=ActivityAssetCorrectResult,
                        profile_id=payload.profile_id,
                        authority=authority,
                        error=error,
                    )
                result = ActivityAssetCorrectResult(
                    profile_id=payload.profile_id,
                    authority=authority,
                    outcome="succeeded",
                    history=history,
                )
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(commit(), task_name="activity-asset-correct")


class ActivityAssetForecastExecutor:
    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetForecastRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        payload = request.payload
        bucket_id = _worker_bucket(
            cast(OperationRequest[Any], request),
            context,
            definition_id=ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID)

        async def capture() -> str | OperationRefusalEvidence:
            operations = await _load_operations(
                self._ports_factory,
                bucket_id=bucket_id,
                operation=context.authority_operation,
            )
            try:
                forecast = await asyncio.to_thread(
                    operations.forecast,
                    asset_id=payload.asset_id,
                    covered_from=payload.covered_from,
                    covered_until=payload.covered_until,
                    requested_free_amount=(
                        Decimal(payload.requested_free_amount.decimal)
                        if payload.requested_free_amount is not None
                        else None
                    ),
                    supersedes_claim_id=payload.supersedes_claim_id,
                )
            except (
                ActividadAssetClaimConflictError,
                ActividadAssetIncompleteError,
                ActividadAssetUnsupportedError,
                ActividadAssetValidationError,
            ) as error:
                return await _store_refusal(
                    context,
                    result_type=ActivityAssetForecastResult,
                    profile_id=payload.profile_id,
                    authority=authority,
                    error=error,
                )
            result = ActivityAssetForecastResult(
                profile_id=payload.profile_id,
                authority=authority,
                outcome="succeeded",
                forecast=forecast,
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="activity-asset-forecast")


class ActivityAssetClaimExecutor:
    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetClaimRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        payload = request.payload
        bucket_id = _worker_bucket(
            cast(OperationRequest[Any], request),
            context,
            definition_id=ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID)

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                operations = await _load_operations(
                    self._ports_factory,
                    bucket_id=bucket_id,
                    operation=context.authority_operation,
                )
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    claim_result = await asyncio.to_thread(
                        operations.record_claim,
                        payload.forecast.to_domain(),
                        creating_operation=payload.creating_operation,
                        supersedes_claim_id=payload.supersedes_claim_id,
                    )
                except (
                    ActividadAssetClaimConflictError,
                    ActividadAssetIncompleteError,
                    ActividadAssetUnsupportedError,
                    ActividadAssetValidationError,
                ) as error:
                    return await _store_refusal(
                        context,
                        result_type=ActivityAssetClaimResult,
                        profile_id=payload.profile_id,
                        authority=authority,
                        error=error,
                    )
                result = ActivityAssetClaimResult(
                    profile_id=payload.profile_id,
                    authority=authority,
                    outcome="succeeded",
                    claim_result=claim_result,
                    claim_id=claim_result.claim.claim_id,
                )
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(
                    OperationEffect.NONE if claim_result.reused_existing_claim else OperationEffect.UPDATED
                )
                return reference

        return await await_cancellation_complete(commit(), task_name="activity-asset-claim")


class ActivityAssetFilingHandoffExecutor:
    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetFilingHandoffRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        payload = request.payload
        bucket_id = _worker_bucket(
            cast(OperationRequest[Any], request),
            context,
            definition_id=ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID)

        async def capture() -> str | OperationRefusalEvidence:
            operations = await _load_operations(
                self._ports_factory,
                bucket_id=bucket_id,
                operation=context.authority_operation,
            )
            period = Period.from_year_and_code(payload.tax_year, payload.m130_period)
            try:
                handoff = await asyncio.to_thread(
                    operations.filing_handoff,
                    tax_year=payload.tax_year,
                    m130_period=period,
                )
            except (
                ActividadAssetClaimConflictError,
                ActividadAssetIncompleteError,
                ActividadAssetUnsupportedError,
                ActividadAssetValidationError,
            ) as error:
                return await _store_refusal(
                    context,
                    result_type=ActivityAssetFilingHandoffResult,
                    profile_id=payload.profile_id,
                    authority=authority,
                    error=error,
                    tax_year=payload.tax_year,
                    m130_period=payload.m130_period,
                )
            result = ActivityAssetFilingHandoffResult(
                profile_id=payload.profile_id,
                authority=authority,
                outcome="succeeded",
                tax_year=payload.tax_year,
                m130_period=payload.m130_period,
                filing_handoff=handoff,
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="activity-asset-filing-handoff")


def _require_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    request_type: type[BaseModel],
    mutation: bool,
) -> ResolvedOperationAccess:
    if request.definition_id != definition_id or not isinstance(request.payload, request_type):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = cast(Any, request.payload)
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=payload.profile_id,
        periods=frozenset(),
    )
    if not mutation:
        return resolved
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def resolve_activity_asset_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind every asset operation to the exact complete profile history."""
    targets: dict[str, tuple[type[BaseModel], bool]] = {
        ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID: (ActivityAssetCreateRequest, True),
        ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID: (ActivityAssetInspectRequest, False),
        ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID: (ActivityAssetCorrectRequest, True),
        ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID: (ActivityAssetForecastRequest, False),
        ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID: (ActivityAssetClaimRequest, True),
        ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID: (ActivityAssetFilingHandoffRequest, False),
    }
    target = targets.get(request.definition_id)
    if target is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    request_type, mutation = target
    return _require_access(
        request,
        context,
        definition_id=request.definition_id,
        request_type=request_type,
        mutation=mutation,
    )


def _definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type,
    ports_factory: ActivityAssetOperationPortsFactory,
    sensitive_input: bool,
    mutation: bool,
) -> OperationDefinition:
    effects = frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    if mutation:
        effects = effects | {OperationEffect.UPDATED}
    request_storage = (
        OperationRequestStoragePolicy.SECURE_REFERENCE
        if sensitive_input
        else OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
    )
    sensitive = (
        OperationSensitiveInputPolicy.SECURE_REFERENCE if sensitive_input else OperationSensitiveInputPolicy.NONE
    )
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=lambda: executor_type(ports_factory),
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=request_storage,
            sensitive_input=sensitive,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=effects,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {
                OperationFrontendProjection.CLI,
                OperationFrontendProjection.MCP,
                OperationFrontendProjection.TUI,
            }
        ),
        refusal_detail_codes=_REFUSAL_CODES,
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    projection_type: type[BaseModel],
    result_projector: OperationResultProjector,
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=projection_type,
        ),
        access_resolver=resolve_activity_asset_access,
        result_projector=result_projector,
    )


def _receipt_matches(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
    effect: OperationEffect,
    condition: OperationTerminalCondition,
    refusal_code: str | None,
) -> None:
    refused = condition is OperationTerminalCondition.REFUSED
    if (
        receipt.identity.definition_id != definition_id
        or receipt.identity.subject_ref != profile_operation_subject(str(profile_id))
        or receipt.condition is not condition
        or receipt.effect is not effect
        or receipt.refusal_ref != refusal_code
        or (receipt.refusal_detail_ref is not None) != refused
        or (receipt.result_ref is not None) != (not refused)
    ):
        raise ValueError("activity-asset projection differs from its terminal receipt")


def _private_result(
    result: BaseModel, result_type: type[_ActivityAssetOperationResult]
) -> _ActivityAssetOperationResult:
    if type(result) is not result_type:
        raise ValueError("invalid activity-asset operation result")
    return result_type.model_validate(result.model_dump(mode="python"), strict=True)


def _project_refusal(refusal: _ActivityAssetRefusalResult | None) -> ActivityAssetRefusal | None:
    if refusal is None:
        return None
    return ActivityAssetRefusal(
        code=refusal.code,
        precondition_verdict=(
            PreconditionVerdictSnapshot.from_verdict(refusal.precondition_verdict)
            if refusal.precondition_verdict is not None
            else None
        ),
    )


def _verify_private_receipt(
    private: _ActivityAssetOperationResult,
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    success_effect: OperationEffect,
) -> None:
    refused = private.outcome == "refused"
    refusal_code = private.refusal.code if private.refusal is not None else None
    effect = OperationEffect.NONE if refused else success_effect
    if definition_id == ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID and not refused:
        claim_result = cast(ActivityAssetClaimResult, private).claim_result
        if claim_result is None:
            raise ValueError("successful activity-asset claim lacks its claim result")
        effect = OperationEffect.NONE if claim_result.reused_existing_claim else OperationEffect.UPDATED
    _receipt_matches(
        receipt,
        definition_id=definition_id,
        profile_id=private.profile_id,
        effect=effect,
        condition=OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED,
        refusal_code=refusal_code,
    )


def _project_create(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ActivityAssetCreateProjection:
    private = cast(ActivityAssetCreateResult, _private_result(result, ActivityAssetCreateResult))
    _verify_private_receipt(
        private,
        receipt,
        definition_id=ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
        success_effect=OperationEffect.UPDATED,
    )
    return ActivityAssetCreateProjection(
        profile_id=private.profile_id,
        authority=private.authority,
        outcome=private.outcome,
        refusal=_project_refusal(private.refusal),
        history=ActivityAssetHistorySnapshot.from_domain(private.history) if private.history is not None else None,
    )


def _project_inspect(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ActivityAssetInspectProjection:
    private = cast(ActivityAssetInspectResult, _private_result(result, ActivityAssetInspectResult))
    _verify_private_receipt(
        private,
        receipt,
        definition_id=ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
        success_effect=OperationEffect.NONE,
    )
    return ActivityAssetInspectProjection(
        profile_id=private.profile_id,
        authority=private.authority,
        outcome=private.outcome,
        refusal=_project_refusal(private.refusal),
        asset_id=private.asset_id,
        revisions=private.revisions,
    )


def _project_correct(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ActivityAssetCorrectProjection:
    private = cast(ActivityAssetCorrectResult, _private_result(result, ActivityAssetCorrectResult))
    _verify_private_receipt(
        private,
        receipt,
        definition_id=ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
        success_effect=OperationEffect.UPDATED,
    )
    return ActivityAssetCorrectProjection(
        profile_id=private.profile_id,
        authority=private.authority,
        outcome=private.outcome,
        refusal=_project_refusal(private.refusal),
        history=ActivityAssetHistorySnapshot.from_domain(private.history) if private.history is not None else None,
    )


def _project_forecast(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ActivityAssetForecastProjection:
    private = cast(ActivityAssetForecastResult, _private_result(result, ActivityAssetForecastResult))
    _verify_private_receipt(
        private,
        receipt,
        definition_id=ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
        success_effect=OperationEffect.NONE,
    )
    return ActivityAssetForecastProjection(
        profile_id=private.profile_id,
        authority=private.authority,
        outcome=private.outcome,
        refusal=_project_refusal(private.refusal),
        forecast=(
            ScheduledAmortizationChargeSnapshot.from_domain(private.forecast) if private.forecast is not None else None
        ),
    )


def _project_claim(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ActivityAssetClaimProjection:
    private = cast(ActivityAssetClaimResult, _private_result(result, ActivityAssetClaimResult))
    _verify_private_receipt(
        private,
        receipt,
        definition_id=ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
        success_effect=OperationEffect.UPDATED,
    )
    return ActivityAssetClaimProjection(
        profile_id=private.profile_id,
        authority=private.authority,
        outcome=private.outcome,
        refusal=_project_refusal(private.refusal),
        claim_result=(
            ActivityAssetHistoryClaimResultSnapshot.from_domain(private.claim_result)
            if private.claim_result is not None
            else None
        ),
        claim_id=private.claim_id,
    )


def _project_filing_handoff(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> ActivityAssetFilingHandoffProjection:
    private = cast(ActivityAssetFilingHandoffResult, _private_result(result, ActivityAssetFilingHandoffResult))
    _verify_private_receipt(
        private,
        receipt,
        definition_id=ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
        success_effect=OperationEffect.NONE,
    )
    return ActivityAssetFilingHandoffProjection(
        profile_id=private.profile_id,
        authority=private.authority,
        outcome=private.outcome,
        refusal=_project_refusal(private.refusal),
        tax_year=private.tax_year,
        m130_period=private.m130_period,
        filing_handoff=(
            ActivityAssetFilingHandoffSnapshot.from_domain(private.filing_handoff)
            if private.filing_handoff is not None
            else None
        ),
    )


def build_activity_asset_create_definition(ports_factory: ActivityAssetOperationPortsFactory) -> OperationDefinition:
    """Build the guarded operation that creates one asset revision."""
    return _definition(
        definition_id=ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetCreateRequest,
        result_type=ActivityAssetCreateResult,
        executor_type=ActivityAssetCreateExecutor,
        ports_factory=ports_factory,
        sensitive_input=True,
        mutation=True,
    )


def build_activity_asset_create_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the typed create request and projection schemas."""
    return _registration(
        definition,
        request_type=ActivityAssetCreateRequest,
        projection_type=ActivityAssetCreateProjection,
        result_projector=_project_create,
    )


def build_activity_asset_inspect_definition(ports_factory: ActivityAssetOperationPortsFactory) -> OperationDefinition:
    """Build the read-only operation that returns one full revision chain."""
    return _definition(
        definition_id=ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetInspectRequest,
        result_type=ActivityAssetInspectResult,
        executor_type=ActivityAssetInspectExecutor,
        ports_factory=ports_factory,
        sensitive_input=True,
        mutation=False,
    )


def build_activity_asset_inspect_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the typed inspect request and projection schemas."""
    return _registration(
        definition,
        request_type=ActivityAssetInspectRequest,
        projection_type=ActivityAssetInspectProjection,
        result_projector=_project_inspect,
    )


def build_activity_asset_correct_definition(ports_factory: ActivityAssetOperationPortsFactory) -> OperationDefinition:
    """Build the guarded operation that appends one current correction."""
    return _definition(
        definition_id=ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetCorrectRequest,
        result_type=ActivityAssetCorrectResult,
        executor_type=ActivityAssetCorrectExecutor,
        ports_factory=ports_factory,
        sensitive_input=True,
        mutation=True,
    )


def build_activity_asset_correct_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the typed correction request and projection schemas."""
    return _registration(
        definition,
        request_type=ActivityAssetCorrectRequest,
        projection_type=ActivityAssetCorrectProjection,
        result_projector=_project_correct,
    )


def build_activity_asset_forecast_definition(ports_factory: ActivityAssetOperationPortsFactory) -> OperationDefinition:
    """Build the non-consuming pinned-authority forecast operation."""
    return _definition(
        definition_id=ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetForecastRequest,
        result_type=ActivityAssetForecastResult,
        executor_type=ActivityAssetForecastExecutor,
        ports_factory=ports_factory,
        sensitive_input=True,
        mutation=False,
    )


def build_activity_asset_forecast_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the typed forecast request and projection schemas."""
    return _registration(
        definition,
        request_type=ActivityAssetForecastRequest,
        projection_type=ActivityAssetForecastProjection,
        result_projector=_project_forecast,
    )


def build_activity_asset_claim_definition(ports_factory: ActivityAssetOperationPortsFactory) -> OperationDefinition:
    """Build the guarded operation that records or replays a forecast claim."""
    return _definition(
        definition_id=ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetClaimRequest,
        result_type=ActivityAssetClaimResult,
        executor_type=ActivityAssetClaimExecutor,
        ports_factory=ports_factory,
        sensitive_input=True,
        mutation=True,
    )


def build_activity_asset_claim_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Register the typed claim request and projection schemas."""
    return _registration(
        definition,
        request_type=ActivityAssetClaimRequest,
        projection_type=ActivityAssetClaimProjection,
        result_projector=_project_claim,
    )


def build_activity_asset_filing_handoff_definition(
    ports_factory: ActivityAssetOperationPortsFactory,
) -> OperationDefinition:
    """Build the read-only M100/M130 activity-asset filing projection."""
    return _definition(
        definition_id=ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetFilingHandoffRequest,
        result_type=ActivityAssetFilingHandoffResult,
        executor_type=ActivityAssetFilingHandoffExecutor,
        ports_factory=ports_factory,
        sensitive_input=False,
        mutation=False,
    )


def build_activity_asset_filing_handoff_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the typed filing handoff request and projection schemas."""
    return _registration(
        definition,
        request_type=ActivityAssetFilingHandoffRequest,
        projection_type=ActivityAssetFilingHandoffProjection,
        result_projector=_project_filing_handoff,
    )


__all__ = [
    "ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID",
    "ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID",
    "ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID",
    "ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID",
    "ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID",
    "ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID",
    "ActivityAssetAuthorityProvenance",
    "ActivityAssetClaimProjection",
    "ActivityAssetClaimRequest",
    "ActivityAssetCorrectProjection",
    "ActivityAssetCorrectRequest",
    "ActivityAssetCreateProjection",
    "ActivityAssetCreateRequest",
    "ActivityAssetFilingHandoffProjection",
    "ActivityAssetFilingHandoffRequest",
    "ActivityAssetForecastProjection",
    "ActivityAssetForecastRequest",
    "ActivityAssetInspectProjection",
    "ActivityAssetInspectRequest",
    "ActivityAssetOperationPorts",
    "ActivityAssetOperationPortsFactory",
    "build_activity_asset_claim_definition",
    "build_activity_asset_claim_registration",
    "build_activity_asset_correct_definition",
    "build_activity_asset_correct_registration",
    "build_activity_asset_create_definition",
    "build_activity_asset_create_registration",
    "build_activity_asset_filing_handoff_definition",
    "build_activity_asset_filing_handoff_registration",
    "build_activity_asset_forecast_definition",
    "build_activity_asset_forecast_registration",
    "build_activity_asset_inspect_definition",
    "build_activity_asset_inspect_registration",
    "resolve_activity_asset_access",
]
