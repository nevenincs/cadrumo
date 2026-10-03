"""Recorded, exact-profile preview of one authenticated censal read."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from typing import TYPE_CHECKING, Annotated, Literal, Protocol
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator

from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...domain.user_profile.values import UserProfileFact, UserProfileRecord
from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
from ..auth.operator_scope_ports import OperatorScopePorts
from ..auth.protocols import BrowserSessionFactoryPort
from ..live.censo_ports import CensalFetchPort
from ..live.session import LiveSessionWriteReceipt, SessionWriteReporter, active_verified_session
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
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from .access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from .access_errors import ProfileAccessRefusedError
from .capsule_record import ProfileRecordConflictError
from .censal_access import profile_censal_access_disclosure, require_admitted_profile_censal_request
from .censal_observation import CensalObservation
from .censal_operation import CensalProfileBaseline
from .censo_sync import (
    CENSAL_ADOPTABLE_PATHS,
    CENSO_SOURCE_TAG,
    CensalReconciliation,
    censal_facts_from_read,
    reconcile_censal_read,
)
from .profile_record_repository import ProfileRecordRepository
from .projections import record_to_effective_facts

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext

CENSAL_PREVIEW_OPERATION_DEFINITION_ID = "user-profile.censo-preview"
CENSAL_PREVIEW_PHASE_PREFLIGHT = "user-profile.censo-preview.preflight"
CENSAL_PREVIEW_PHASE_REMOTE_READ = "user-profile.censo-preview.remote-read"
CENSAL_PREVIEW_PHASE_RECONCILIATION = "user-profile.censo-preview.reconciliation"
CENSAL_PREVIEW_PHASE_RESULT = "user-profile.censo-preview.result"
CENSAL_PREVIEW_PHASE_SETTLEMENT = "user-profile.censo-preview.settlement"
_CENSAL_PREVIEW_PHASES = (
    CENSAL_PREVIEW_PHASE_PREFLIGHT,
    CENSAL_PREVIEW_PHASE_REMOTE_READ,
    CENSAL_PREVIEW_PHASE_RECONCILIATION,
    CENSAL_PREVIEW_PHASE_RESULT,
    CENSAL_PREVIEW_PHASE_SETTLEMENT,
)
_CENSAL_PREVIEW_MAX_VALUE_LENGTH = 4_096
_CENSAL_PREVIEW_RESULT_MAX_BYTES = min(48 * 1024, PROJECTION_DOCUMENT_MAX_BYTES - 4_096)

_CensalPath = Annotated[str, Field(min_length=3, max_length=160)]
_CensalValue = Annotated[str, Field(max_length=_CENSAL_PREVIEW_MAX_VALUE_LENGTH)]


class CensalPreviewOperationRequest(CredentialFreeOperationRequest):
    """Bind the provider read to the exact profile revision prepared by the CLI."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    request_version: Literal[1] = 1
    baseline: CensalProfileBaseline


class CensalPreviewFactProjection(BaseModel):
    """One censal fact safe to return to the exact profile's frontend."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    path: _CensalPath
    value: _CensalValue
    source: Annotated[str, Field(min_length=1, max_length=128)]

    @model_validator(mode="after")
    def _validate_canonical_censal_fact(self) -> CensalPreviewFactProjection:
        if self.path not in CENSAL_ADOPTABLE_PATHS or self.source != CENSO_SOURCE_TAG:
            raise ValueError("censal preview facts must retain canonical path and source")
        UserProfileFact(path=self.path, value=self.value, source=self.source)
        return self


class CensalPreviewDivergenceProjection(BaseModel):
    """A reported disagreement, where ``None`` preserves an explicit clear."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    path: _CensalPath
    profile_value: _CensalValue | None
    aeat_value: _CensalValue

    @model_validator(mode="after")
    def _validate_canonical_censal_path(self) -> CensalPreviewDivergenceProjection:
        if self.path not in CENSAL_ADOPTABLE_PATHS:
            raise ValueError("censal preview divergence must use a canonical adoptable path")
        return self


class CensalPreviewOperationResult(BaseModel):
    """Bounded presentation-compatible preview result; it never claims apply."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    applied: Literal[False] = False
    source_url: AnyHttpUrl
    adopted: tuple[CensalPreviewFactProjection, ...] = ()
    unchanged: tuple[CensalPreviewFactProjection, ...] = ()
    divergences: tuple[CensalPreviewDivergenceProjection, ...] = ()

    @model_validator(mode="after")
    def _validate_partition(self) -> CensalPreviewOperationResult:
        groups = (
            tuple(item.path for item in self.adopted),
            tuple(item.path for item in self.unchanged),
            tuple(item.path for item in self.divergences),
        )
        _validate_censal_preview_partition(groups)
        return self


def _validate_censal_preview_partition(groups: tuple[tuple[str, ...], ...]) -> None:
    for paths in groups:
        _validate_canonical_preview_paths(paths)
    if len({path for group in groups for path in group}) != sum(map(len, groups)):
        raise ValueError("censal preview outcome paths must be disjoint")


def _validate_canonical_preview_paths(paths: tuple[str, ...]) -> None:
    if paths != tuple(path for path in CENSAL_ADOPTABLE_PATHS if path in paths):
        raise ValueError("censal preview outcomes must retain canonical field order")
    if len(paths) != len(set(paths)):
        raise ValueError("censal preview outcome paths must be unique")


type CensalPreviewAcquire = Callable[
    [PinnedAuthorityOperation, Callable[[], AbstractAsyncContextManager[None]], SessionWriteReporter],
    Awaitable[CensalObservation],
]
type CensalPreviewProviderPreflight = Callable[[UUID, PinnedAuthorityOperation], None]


class CensalPreviewBrowserResources(Protocol):
    """Worker-owned Playwright process scope used for the live read."""

    def activate(self) -> AbstractContextManager[None]:
        """Attribute browser processes created in this operation to its owner."""
        ...

    async def close(self) -> None:
        """Settle every owned browser process before terminal settlement."""
        ...


type CensalPreviewBrowserResourcesFactory = Callable[[], CensalPreviewBrowserResources]


def _unconfigured_provider_preflight(profile_id: UUID, operation: PinnedAuthorityOperation) -> None:
    """Refuse provider acquisition when composition supplied no readiness check."""
    del profile_id, operation
    raise ProfileAccessRefusedError(AccessDenialCode.PROVIDER_REQUIRED)


def _load_exact_baseline(
    baseline: CensalProfileBaseline,
    *,
    profile_decode_context: ProfileDecodeContext,
) -> UserProfileRecord:
    """Load the full encrypted record and reject a stale or mis-scoped baseline."""
    profile_id = require_active_bucket_id()
    if profile_id != str(baseline.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    record = ProfileRecordRepository.for_current_session(
        profile_id,
        profile_decode_context=profile_decode_context,
    ).load(profile_id)
    if (
        record.profile_id != baseline.profile_id
        or record.record_revision != baseline.record_revision
        or record.content_digest != baseline.content_digest
    ):
        raise ProfileRecordConflictError("censal preview baseline is stale")
    return record


def _build_preview_result(
    *,
    profile_id: UUID,
    record: UserProfileRecord,
    observation: CensalObservation,
) -> CensalPreviewOperationResult:
    """Reconcile one observation against full fact history without writing."""
    if record.profile_id != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    projected = censal_facts_from_read(observation)
    reconciliation = reconcile_censal_read(
        record,
        projected,
        incoming_identity=observation.identity.nif,
    )
    adopted = _preview_facts(reconciliation.adopted)
    unchanged = _unchanged_preview_facts(projected, reconciliation)
    effective = record_to_effective_facts(record)
    divergences = tuple(
        CensalPreviewDivergenceProjection(
            path=path,
            profile_value=(current.value if (current := effective.get(path)) is not None else None),
            aeat_value=value,
        )
        for path, value in reconciliation.divergences
    )
    return CensalPreviewOperationResult(
        profile_id=profile_id,
        source_url=observation.source_url,
        adopted=adopted,
        unchanged=unchanged,
        divergences=divergences,
    )


def _preview_facts(facts: tuple[UserProfileFact, ...]) -> tuple[CensalPreviewFactProjection, ...]:
    """Project declared address facts, refusing any unexpected input."""
    if any(fact.path not in CENSAL_ADOPTABLE_PATHS or fact.source != CENSO_SOURCE_TAG for fact in facts):
        raise ValueError("censal preview received a fact outside its canonical paths or source")
    return tuple(
        CensalPreviewFactProjection(path=fact.path, value=str(fact.value), source=fact.source) for fact in facts
    )


def _unchanged_preview_facts(
    projected: tuple[UserProfileFact, ...],
    reconciliation: CensalReconciliation,
) -> tuple[CensalPreviewFactProjection, ...]:
    """Report covered values the reconciler leaves untouched, excluding identity."""
    if any(fact.path not in CENSAL_ADOPTABLE_PATHS and fact.path != "identity.tax_id" for fact in projected):
        raise ValueError("censal preview received an unknown projected path")
    decided = {fact.path for fact in reconciliation.adopted}
    decided.update(path for path, _ in reconciliation.divergences)
    return _preview_facts(
        tuple(fact for fact in projected if fact.path in CENSAL_ADOPTABLE_PATHS and fact.path not in decided)
    )


async def _acquire_censal_observation(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    censal_fetch_port: CensalFetchPort,
    authority_operation: PinnedAuthorityOperation,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]],
    on_session_write: SessionWriteReporter,
) -> CensalObservation:
    """Use canonical authenticated-session and censal-fetch application ports."""
    from ..live.censo import LIVE_CENSAL_READ_OPERATION

    session, settings = await active_verified_session(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        browser_session_factory=browser_session_factory,
        operator_scope_ports=operator_scope_ports,
        operation=LIVE_CENSAL_READ_OPERATION,
        authority_operation=authority_operation,
        effect_guard=effect_guard,
        on_session_write=on_session_write,
    )
    return await censal_fetch_port(session, taxpayer_nif=session.identity_nif, settings=settings)


class CensalPreviewOperationExecutor:
    """Run a pinned read, reconcile the exact profile, and publish no mutation."""

    def __init__(
        self,
        *,
        browser_resources_factory: CensalPreviewBrowserResourcesFactory,
        acquire: CensalPreviewAcquire,
        provider_preflight: CensalPreviewProviderPreflight,
    ) -> None:
        """Bind operation-owned browser cleanup and provider acquisition ports."""
        self._browser_resources_factory = browser_resources_factory
        self._acquire = acquire
        self._provider_preflight = provider_preflight

    async def execute(
        self,
        request: OperationRequest[CensalPreviewOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Acquire one observation and persist its bounded exact-profile preview."""
        baseline = request.payload.baseline
        profile_id = str(baseline.profile_id)
        if request.definition_id != CENSAL_PREVIEW_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, UUID(profile_id))

        await context.events.phase(CENSAL_PREVIEW_PHASE_PREFLIGHT)
        decode_context = context.authority_operation.profile_decode_context()
        await asyncio.to_thread(
            _load_exact_baseline,
            baseline,
            profile_decode_context=decode_context,
        )
        self._provider_preflight(UUID(profile_id), context.authority_operation)

        await context.events.phase(CENSAL_PREVIEW_PHASE_REMOTE_READ)
        browser_resources = self._browser_resources_factory()
        context.cleanup.own(browser_resources, family=OperationOwnedResource.PROCESS)
        with browser_resources.activate():
            await context.events.effect(OperationEffect.UNKNOWN)
            session_receipt = LiveSessionWriteReceipt(context.events.effect)
            observation = await self._acquire(
                context.authority_operation, context.cancellation.irreversible_section, session_receipt
            )

        await context.events.phase(CENSAL_PREVIEW_PHASE_RECONCILIATION)
        current = await asyncio.to_thread(
            _load_exact_baseline,
            baseline,
            profile_decode_context=decode_context,
        )
        result = _build_preview_result(profile_id=UUID(profile_id), record=current, observation=observation)
        if len(canonical_json_bytes(result.model_dump(mode="json"))) > _CENSAL_PREVIEW_RESULT_MAX_BYTES:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)

        await context.events.phase(CENSAL_PREVIEW_PHASE_RESULT)
        result_ref = await context.operands.put(result, written_at=now())
        await context.events.effect(session_receipt.combine(OperationEffect.NONE))
        await context.events.phase(CENSAL_PREVIEW_PHASE_SETTLEMENT)
        return result_ref


def build_censal_preview_operation_definition(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    censal_fetch_port: CensalFetchPort,
    browser_resources_factory: CensalPreviewBrowserResourcesFactory,
    provider_preflight: CensalPreviewProviderPreflight = _unconfigured_provider_preflight,
    acquire: CensalPreviewAcquire | None = None,
) -> OperationDefinition:
    """Build the recorded census preview with worker-scoped browser custody."""

    async def default_acquire(
        authority_operation: PinnedAuthorityOperation,
        effect_guard: Callable[[], AbstractAsyncContextManager[None]],
        on_session_write: SessionWriteReporter,
    ) -> CensalObservation:
        return await _acquire_censal_observation(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            browser_session_factory=browser_session_factory,
            operator_scope_ports=operator_scope_ports,
            censal_fetch_port=censal_fetch_port,
            authority_operation=authority_operation,
            effect_guard=effect_guard,
            on_session_write=on_session_write,
        )

    bound_acquire = acquire or default_acquire

    def build() -> CensalPreviewOperationExecutor:
        return CensalPreviewOperationExecutor(
            browser_resources_factory=browser_resources_factory,
            acquire=bound_acquire,
            provider_preflight=provider_preflight,
        )

    return OperationDefinition(
        definition_id=CENSAL_PREVIEW_OPERATION_DEFINITION_ID,
        request_type=CensalPreviewOperationRequest,
        result_type=CensalPreviewOperationResult,
        executor_factory=OperationExecutorFactory(
            request_type=CensalPreviewOperationRequest,
            executor_type=CensalPreviewOperationExecutor,
            build=build,
        ),
        phase_codes=_CENSAL_PREVIEW_PHASES,
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
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


def resolve_censal_preview_operation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve exact-profile preview access with provider readiness at worker start."""
    _validated_censal_preview_request(request, context)
    require_admitted_profile_censal_request(request, context)
    disclosure = profile_censal_access_disclosure(context)

    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=context.profile_id,
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
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                }
            ),
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
            periods=frozenset(),
            allow_period_independent=True,
            requires_all_periods=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=(Availability.NEEDS_USER if context.action is AccessAction.START else Availability.NOT_REQUIRED),
            transaction_authority_required=False,
        ),
    )


def _validated_censal_preview_request(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> CensalPreviewOperationRequest:
    payload = request.payload
    if request.definition_id != CENSAL_PREVIEW_OPERATION_DEFINITION_ID or not isinstance(
        payload, CensalPreviewOperationRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = str(payload.baseline.profile_id)
    if payload.baseline.profile_id != str(context.profile_id) or request.subject_ref != profile_operation_subject(
        profile_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload


def build_censal_preview_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the credential-free request and bounded public preview result."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=CensalPreviewOperationResult,
        access_resolver=resolve_censal_preview_operation_access,
    )


__all__ = [
    "CENSAL_PREVIEW_OPERATION_DEFINITION_ID",
    "CensalPreviewBrowserResources",
    "CensalPreviewBrowserResourcesFactory",
    "CensalPreviewDivergenceProjection",
    "CensalPreviewFactProjection",
    "CensalPreviewOperationExecutor",
    "CensalPreviewOperationRequest",
    "CensalPreviewOperationResult",
    "build_censal_preview_operation_definition",
    "build_censal_preview_operation_registration",
    "resolve_censal_preview_operation_access",
]
