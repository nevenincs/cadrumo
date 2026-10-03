"""Exact-profile worker capture of read-only AEAT identity checks."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.bucket_pointer import require_active_bucket_id
from ...core.identity.bucket import BucketId
from ...core.identity.tax_id import tax_id_identity_token
from ...core.identity_check_verdict import IdentityCheckVerdictValue
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
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_history_operation import FiledHistoryBrowserResourcesFactory, FiledHistoryProviderPreflight
from .verify import VerifyObservation, VerifyService, VerifySurface
from .verify_ports import VerifyObservationPersistencePort

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

VERIFY_NIF_IVA_CAPTURE_DEFINITION_ID = "live.verify.nif-iva"
VERIFY_TGVI_CAPTURE_DEFINITION_ID = "live.verify.tgvi"
_PHASES = ("live-verify.preflight", "live-verify.acquire", "live-verify.persist", "live-verify.result")


class VerifyLiveObservation(BaseModel):
    """Closed observation returned by one composed browser acquisition."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    nif: str = Field(min_length=1, max_length=32)
    verdict: IdentityCheckVerdictValue
    raw_evidence_locator: str | None = Field(default=None, max_length=512)


class VerifyCaptureRequest(BaseModel):
    """Protect the requested NIF and expectation in secure operation input."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    nif: str = Field(min_length=1, max_length=32)
    expected: IdentityCheckVerdictValue | None = None


class VerifyCapturePublicResultV1(BaseModel):
    """Complete established CLI row, excluding the private evidence locator."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    observation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    surface: VerifySurface
    nif: str
    verdict: IdentityCheckVerdictValue
    expected: IdentityCheckVerdictValue | None
    matched_expectation: bool | None
    checked_at: datetime

    @classmethod
    def from_record(cls, record: VerifyObservation) -> VerifyCapturePublicResultV1:
        """Copy only the fields the existing verify command publishes."""
        return cls(
            bucket_id=record.bucket_id,
            observation_id=record.observation_id,
            surface=record.surface,
            nif=record.nif,
            verdict=record.verdict,
            expected=record.expected,
            matched_expectation=record.matched_expectation,
            checked_at=record.checked_at,
        )


class VerifyCaptureOperationReport(BaseModel):
    """Private observation plus evidence of the actual local effect."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    observation: VerifyObservation
    newly_persisted: bool


type VerifyCaptureAcquire = Callable[
    [VerifySurface, str, IdentityCheckVerdictValue | None, PinnedAuthorityOperation],
    Awaitable[VerifyLiveObservation],
]
type VerifyPersistenceFactory = Callable[[str], VerifyObservationPersistencePort]


def _definition_id(surface: VerifySurface) -> str:
    if surface is VerifySurface.NIF_IVA:
        return VERIFY_NIF_IVA_CAPTURE_DEFINITION_ID
    return VERIFY_TGVI_CAPTURE_DEFINITION_ID


def _project_capture(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    report = VerifyCaptureOperationReport.model_validate(result, strict=True)
    observation = report.observation
    expected_effect = OperationEffect.UPDATED if report.newly_persisted else OperationEffect.NONE
    if (
        receipt.identity.definition_id != _definition_id(observation.surface)
        or receipt.identity.subject_ref != profile_operation_subject(str(observation.bucket_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not expected_effect
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("verify capture result contradicts its terminal receipt")
    return VerifyCapturePublicResultV1.from_record(observation)


class VerifyCaptureExecutor:
    """Own browser processes, then guard one encrypted local observation."""

    def __init__(
        self,
        *,
        surface: VerifySurface,
        persistence_factory: VerifyPersistenceFactory,
        acquire: VerifyCaptureAcquire,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
    ) -> None:
        """Bind the exact worker's acquisition and persistence capabilities."""
        self._surface = surface
        self._persistence_factory = persistence_factory
        self._acquire = acquire
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight

    async def execute(
        self,
        request: OperationRequest[VerifyCaptureRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Fetch remotely before a fresh COMMIT guard for the local event."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if (
            request.definition_id != _definition_id(self._surface)
            or request.subject_ref != profile_operation_subject(bucket_id)
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        resources = self._browser_resources_factory()
        context.cleanup.own(resources, family=OperationOwnedResource.PROCESS)
        await context.events.phase(_PHASES[1])
        with resources.activate():
            observed = await self._acquire(self._surface, payload.nif, payload.expected, context.authority_operation)
        if tax_id_identity_token(observed.nif) != tax_id_identity_token(payload.nif):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)

        await context.events.phase(_PHASES[2])
        async with context.cancellation.irreversible_section():
            await context.events.effect(OperationEffect.UNKNOWN)
            service = VerifyService(persistence=self._persistence_factory(bucket_id))
            record, newly_persisted = service.record_with_outcome(
                bucket_id=bucket_id,
                surface=self._surface,
                nif=observed.nif,
                verdict=observed.verdict,
                checked_at=now(),
                expected=payload.expected,
                raw_evidence_locator=observed.raw_evidence_locator,
            )
        if record.bucket_id != bucket_id or record.surface is not self._surface:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.effect(OperationEffect.UPDATED if newly_persisted else OperationEffect.NONE)

        await context.events.phase(_PHASES[3])
        async with context.cancellation.irreversible_section():
            return await context.operands.put(
                VerifyCaptureOperationReport(observation=record, newly_persisted=newly_persisted), written_at=now()
            )


def build_verify_capture_definition(
    surface: VerifySurface,
    *,
    persistence_factory: VerifyPersistenceFactory,
    acquire: VerifyCaptureAcquire,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare one secure-input browser-owning exact-profile capture."""

    def build() -> VerifyCaptureExecutor:
        return VerifyCaptureExecutor(
            surface=surface,
            persistence_factory=persistence_factory,
            acquire=acquire,
            browser_resources_factory=browser_resources_factory,
            provider_preflight=provider_preflight,
        )

    return OperationDefinition(
        definition_id=_definition_id(surface),
        request_type=VerifyCaptureRequest,
        result_type=VerifyCaptureOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=VerifyCaptureRequest, executor_type=VerifyCaptureExecutor, build=build
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset({OperationOwnedResource.PROCESS}),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_verify_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile identity disclosure and a local COMMIT fence."""
    if request.definition_id not in {
        VERIFY_NIF_IVA_CAPTURE_DEFINITION_ID,
        VERIFY_TGVI_CAPTURE_DEFINITION_ID,
    } or not isinstance(request.payload, VerifyCaptureRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def build_verify_capture_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind safe observation projection and exact-profile capture access."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=VerifyCaptureRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=VerifyCapturePublicResultV1
        ),
        result_projector=_project_capture,
        access_resolver=resolve_verify_capture_access,
    )


__all__ = [
    "VERIFY_NIF_IVA_CAPTURE_DEFINITION_ID",
    "VERIFY_TGVI_CAPTURE_DEFINITION_ID",
    "VerifyCapturePublicResultV1",
    "VerifyCaptureRequest",
    "VerifyLiveObservation",
    "build_verify_capture_definition",
    "build_verify_capture_registration",
    "resolve_verify_capture_access",
]
