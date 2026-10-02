"""Registered exact-profile read of canonical ledger LLM diagnostics."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
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
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.public_scalar import PublicDecimal
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .llm_diagnostics import (
    DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    LlmConfidenceProviderMetrics,
    LlmDiagnosticsReport,
    LlmUsageCostProviderMetrics,
    build_llm_diagnostics_report,
)
from .llm_diagnostics_ports import LlmDiagnosticsPorts

LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID = "ledger.llm-diagnostics"
_FRONTENDS = frozenset(OperationFrontendProjection)
_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT})


def _public_decimal(value: Decimal | None) -> PublicDecimal | None:
    return None if value is None else PublicDecimal(decimal=str(value))


def _decimal(value: PublicDecimal | None) -> Decimal | None:
    return None if value is None else Decimal(value.decimal)


class LedgerLlmDiagnosticsRequest(BaseModel):
    """One profile, inclusive usage dates, and a canonical confidence floor."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    since: date | None = None
    until: date | None = None
    low_confidence_threshold: PublicDecimal = Field(
        default_factory=lambda: PublicDecimal(decimal=str(DEFAULT_LOW_CONFIDENCE_THRESHOLD))
    )

    @model_validator(mode="after")
    def _unit_threshold(self) -> Self:
        threshold = Decimal(self.low_confidence_threshold.decimal)
        if threshold < 0 or threshold > 1:
            raise ValueError("low-confidence threshold must be within the unit interval")
        return self


class LedgerLlmUsageCostProviderSnapshot(BaseModel):
    """Lossless public copy of one canonical provider usage row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    provider: str
    calls: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cost_estimate_usd: PublicDecimal | None
    unpriced_calls: int = Field(ge=0)

    @classmethod
    def from_row(cls, row: LlmUsageCostProviderMetrics) -> LedgerLlmUsageCostProviderSnapshot:
        """Keep every provider counter and optional decimal cost."""
        return cls(
            provider=row.provider,
            calls=row.calls,
            cache_hits=row.cache_hits,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            total_tokens=row.total_tokens,
            cost_estimate_usd=_public_decimal(row.cost_estimate_usd),
            unpriced_calls=row.unpriced_calls,
        )

    def to_row(self) -> LlmUsageCostProviderMetrics:
        """Restore the canonical provider row with exact decimal precision."""
        return LlmUsageCostProviderMetrics(
            provider=self.provider,
            calls=self.calls,
            cache_hits=self.cache_hits,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.total_tokens,
            cost_estimate_usd=_decimal(self.cost_estimate_usd),
            unpriced_calls=self.unpriced_calls,
        )


class LedgerLlmConfidenceProviderSnapshot(BaseModel):
    """Lossless public copy of one canonical confidence distribution."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    provider: str
    classified_count: int = Field(ge=0)
    low_confidence_count: int = Field(ge=0)
    high_confidence_count: int = Field(ge=0)
    medium_confidence_count: int = Field(ge=0)
    min_confidence: PublicDecimal | None
    max_confidence: PublicDecimal | None
    mean_confidence: PublicDecimal | None

    @classmethod
    def from_row(cls, row: LlmConfidenceProviderMetrics) -> LedgerLlmConfidenceProviderSnapshot:
        """Keep every count and optional precision-bearing score."""
        return cls(
            provider=row.provider,
            classified_count=row.classified_count,
            low_confidence_count=row.low_confidence_count,
            high_confidence_count=row.high_confidence_count,
            medium_confidence_count=row.medium_confidence_count,
            min_confidence=_public_decimal(row.min_confidence),
            max_confidence=_public_decimal(row.max_confidence),
            mean_confidence=_public_decimal(row.mean_confidence),
        )

    def to_row(self) -> LlmConfidenceProviderMetrics:
        """Restore exact canonical confidence decimals and row order."""
        return LlmConfidenceProviderMetrics(
            provider=self.provider,
            classified_count=self.classified_count,
            low_confidence_count=self.low_confidence_count,
            high_confidence_count=self.high_confidence_count,
            medium_confidence_count=self.medium_confidence_count,
            min_confidence=_decimal(self.min_confidence),
            max_confidence=_decimal(self.max_confidence),
            mean_confidence=_decimal(self.mean_confidence),
        )


class LedgerLlmDiagnosticsReportSnapshot(BaseModel):
    """Complete public wire copy of the canonical cost/confidence report."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    since: date | None
    until: date | None
    low_confidence_threshold: PublicDecimal
    usage_providers: tuple[LedgerLlmUsageCostProviderSnapshot, ...]
    total_calls: int = Field(ge=0)
    total_cache_hits: int = Field(ge=0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_cost_estimate_usd: PublicDecimal | None
    total_unpriced_calls: int = Field(ge=0)
    confidence_providers: tuple[LedgerLlmConfidenceProviderSnapshot, ...]
    total_classified: int = Field(ge=0)
    total_low_confidence: int = Field(ge=0)

    @classmethod
    def from_report(cls, report: LlmDiagnosticsReport) -> LedgerLlmDiagnosticsReportSnapshot:
        """Copy every canonical field without rounding, sorting, or filling absence."""
        return cls(
            since=report.since,
            until=report.until,
            low_confidence_threshold=PublicDecimal(decimal=str(report.low_confidence_threshold)),
            usage_providers=tuple(LedgerLlmUsageCostProviderSnapshot.from_row(row) for row in report.usage_providers),
            total_calls=report.total_calls,
            total_cache_hits=report.total_cache_hits,
            total_input_tokens=report.total_input_tokens,
            total_output_tokens=report.total_output_tokens,
            total_cost_estimate_usd=_public_decimal(report.total_cost_estimate_usd),
            total_unpriced_calls=report.total_unpriced_calls,
            confidence_providers=tuple(
                LedgerLlmConfidenceProviderSnapshot.from_row(row) for row in report.confidence_providers
            ),
            total_classified=report.total_classified,
            total_low_confidence=report.total_low_confidence,
        )

    def to_report(self) -> LlmDiagnosticsReport:
        """Restore the existing CLI's full canonical typed report."""
        return LlmDiagnosticsReport(
            since=self.since,
            until=self.until,
            low_confidence_threshold=Decimal(self.low_confidence_threshold.decimal),
            usage_providers=tuple(row.to_row() for row in self.usage_providers),
            total_calls=self.total_calls,
            total_cache_hits=self.total_cache_hits,
            total_input_tokens=self.total_input_tokens,
            total_output_tokens=self.total_output_tokens,
            total_cost_estimate_usd=_decimal(self.total_cost_estimate_usd),
            total_unpriced_calls=self.total_unpriced_calls,
            confidence_providers=tuple(row.to_row() for row in self.confidence_providers),
            total_classified=self.total_classified,
            total_low_confidence=self.total_low_confidence,
        )


class LedgerLlmDiagnosticsProjection(BaseModel):
    """Exact-profile settled report and the coordinates that produced it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    operation_id: Literal["ledger.llm-diagnostics"]
    outcome: Literal["completed"]
    effect: OperationEffect
    since: date | None
    until: date | None
    low_confidence_threshold: PublicDecimal
    report: LedgerLlmDiagnosticsReportSnapshot

    @model_validator(mode="after")
    def _exact_result(self) -> Self:
        if (
            self.operation_id != LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID
            or self.outcome != "completed"
            or self.effect is not OperationEffect.NONE
            or self.since != self.report.since
            or self.until != self.report.until
            or self.low_confidence_threshold != self.report.low_confidence_threshold
        ):
            raise ValueError("LLM diagnostics result differs from its request coordinates")
        return self

    def to_report(self) -> LlmDiagnosticsReport:
        """Restore the exact canonical result for existing CLI presenters."""
        return self.report.to_report()


class LedgerLlmDiagnosticsExecutionResult(BaseModel):
    """Private encrypted operand awaiting current authorized result release."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerLlmDiagnosticsProjection


@dataclass(frozen=True, slots=True)
class LedgerLlmDiagnosticsOperationPorts:
    """Exact profile and retained authority pin around canonical read ports."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    diagnostics: LlmDiagnosticsPorts


class LedgerLlmDiagnosticsOperationPortsFactory(Protocol):
    """Compose the two canonical readers for exactly the requested profile."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> LedgerLlmDiagnosticsOperationPorts:
        """Return identity-checked diagnostic readers without ambient selection."""
        ...


def project_ledger_llm_diagnostics_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only a settled effect-free report under its exact subject."""
    if type(result) is not LedgerLlmDiagnosticsExecutionResult:
        raise ValueError("invalid private LLM diagnostics result")
    projection = result.projection
    if (
        receipt.identity.definition_id != LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("LLM diagnostics result differs from its terminal receipt")
    return projection


class LedgerLlmDiagnosticsExecutor:
    """Read canonical usage and ledger confidence in exact profile-worker custody."""

    def __init__(self, factory: LedgerLlmDiagnosticsOperationPortsFactory) -> None:
        """Retain only the exact-profile composition capability."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[LedgerLlmDiagnosticsRequest], context: OperationExecutorContext
    ) -> str:
        """Store the complete canonical report and publish a NONE effect."""
        payload = request.payload
        if (
            request.definition_id != LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or await asyncio.to_thread(require_active_bucket_id) != str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID)

        def read() -> LedgerLlmDiagnosticsExecutionResult:
            if require_active_bucket_id() != str(payload.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            operation = context.authority_operation
            ports = self._factory(profile_id=payload.profile_id, operation=operation)
            if ports.profile_id != payload.profile_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            report = build_llm_diagnostics_report(
                ports=ports.diagnostics,
                since=payload.since,
                until=payload.until,
                low_confidence_threshold=Decimal(payload.low_confidence_threshold.decimal),
            )
            return LedgerLlmDiagnosticsExecutionResult(
                projection=LedgerLlmDiagnosticsProjection(
                    profile_id=payload.profile_id,
                    operation_id=LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
                    outcome="completed",
                    effect=OperationEffect.NONE,
                    since=payload.since,
                    until=payload.until,
                    low_confidence_threshold=payload.low_confidence_threshold,
                    report=LedgerLlmDiagnosticsReportSnapshot.from_report(report),
                )
            )

        async def capture() -> str:
            result = await asyncio.to_thread(read)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name=LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID)


def resolve_ledger_llm_diagnostics_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require all-period exact-profile access and both public result categories."""
    payload = request.payload
    if (
        request.definition_id != LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID
        or type(payload) is not LedgerLlmDiagnosticsRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if context.frontend not in _FRONTENDS:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    if context.action not in _ACTIONS:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    admitted = context.admitted_request
    if admitted is not None and context.action in {AccessAction.OBSERVE, AccessAction.RESULT}:
        if (
            admitted.profile_id != context.profile_id
            or admitted.definition_id != request.definition_id
            or admitted.destination_id != context.destination_id
            or admitted.action is not AccessAction.SUBMIT
            or admitted.periods
            or not admitted.period_independent
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    elif context.authority_operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    disclosures = frozenset[DisclosurePermission]()
    if context.action is AccessAction.OBSERVE:
        disclosures = frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            )
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None or schema.schema_id != request.definition_id + ".result":
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            DisclosurePermission(
                destination_id=context.destination_id, projection_id=schema.schema_id, category=category
            )
            for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=payload.profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=request.definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=_ACTIONS,
            disclosures=disclosures,
            periods=frozenset(),
            allow_period_independent=True,
            requires_all_periods=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


def build_ledger_llm_diagnostics_definition(
    factory: LedgerLlmDiagnosticsOperationPortsFactory,
) -> OperationDefinition:
    """Declare the existing diagnostics report as a read-only registered verb."""
    return OperationDefinition(
        definition_id=LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
        request_type=LedgerLlmDiagnosticsRequest,
        result_type=LedgerLlmDiagnosticsExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerLlmDiagnosticsRequest,
            executor_type=LedgerLlmDiagnosticsExecutor,
            build=lambda: LedgerLlmDiagnosticsExecutor(factory),
        ),
        phase_codes=(LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=_FRONTENDS,
    )


def build_ledger_llm_diagnostics_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind closed request/result schemas and exact-profile disclosure policy."""
    if definition.definition_id != LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID:
        raise ValueError("unexpected ledger LLM diagnostics definition")
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=LedgerLlmDiagnosticsRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerLlmDiagnosticsProjection,
        ),
        result_projector=project_ledger_llm_diagnostics_result,
        access_resolver=resolve_ledger_llm_diagnostics_access,
    )


__all__ = [
    "LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID",
    "LedgerLlmConfidenceProviderSnapshot",
    "LedgerLlmDiagnosticsExecutionResult",
    "LedgerLlmDiagnosticsOperationPorts",
    "LedgerLlmDiagnosticsOperationPortsFactory",
    "LedgerLlmDiagnosticsProjection",
    "LedgerLlmDiagnosticsReportSnapshot",
    "LedgerLlmDiagnosticsRequest",
    "LedgerLlmUsageCostProviderSnapshot",
    "build_ledger_llm_diagnostics_definition",
    "build_ledger_llm_diagnostics_registration",
    "project_ledger_llm_diagnostics_result",
    "resolve_ledger_llm_diagnostics_access",
]
