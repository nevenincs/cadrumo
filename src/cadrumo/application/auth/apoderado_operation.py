"""Registered exact-profile apoderado configuration and sealed live check."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol, Self, cast
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import Settings
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
from ...domain.auth.apoderamientos.catalogue import UnknownScopeError
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
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operations.secret_submission import OperationEphemeralSecretDeclaration
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
from .apoderado_repository import ApoderadoConfigurationRepositoryFactory
from .apoderado_service import (
    ApoderadoConfiguration,
    ApoderadoLiveCheckUnavailableError,
    ApoderadoRepresentedNifInvalidError,
    ApoderadoService,
    ApoderadoStatus,
)
from .apoderado_text import ApoderadoNotes

APODERADO_STATUS_OPERATION_DEFINITION_ID = "auth.apoderado.status"
APODERADO_CONFIGURE_OPERATION_DEFINITION_ID = "auth.apoderado.configure"
APODERADO_CLEAR_OPERATION_DEFINITION_ID = "auth.apoderado.clear"
APODERADO_CHECK_OPERATION_DEFINITION_ID = "auth.apoderado.check"
APODERADO_REPRESENTED_NIF_SECRET_KIND = "auth.apoderado.represented-nif"  # noqa: S105 - protocol kind, not a secret
type ApoderadoOperationId = Literal[
    "auth.apoderado.status", "auth.apoderado.configure", "auth.apoderado.clear", "auth.apoderado.check"
]
_IDS = (
    APODERADO_STATUS_OPERATION_DEFINITION_ID,
    APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
    APODERADO_CLEAR_OPERATION_DEFINITION_ID,
    APODERADO_CHECK_OPERATION_DEFINITION_ID,
)
_REFUSAL_CODES = frozenset(
    {
        "REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE",
        "REFUSED_APODERADO_INVALID_REPRESENTED_NIF",
        "REFUSED_APODERADO_UNKNOWN_SCOPE",
    }
)
_READ_FRONTENDS = frozenset(OperationFrontendProjection)
_WRITE_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
_READ_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT})
_WRITE_ACTIONS = _READ_ACTIONS | {AccessAction.COMMIT}


class ApoderadoStatusRequest(BaseModel):
    """Read one exact profile's offline delegation configuration."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class ApoderadoConfigureRequest(BaseModel):
    """Nonidentity choices; represented tax identity uses a one-use secret slot."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    scope_tokens: tuple[str, ...] = Field(min_length=1, max_length=64)
    notes: ApoderadoNotes = ""


class ApoderadoClearRequest(BaseModel):
    """Retire only the named profile's encrypted configuration."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class ApoderadoCheckRequest(BaseModel):
    """Request the sealed live-read path, which currently refuses."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class ApoderadoStatusSnapshot(BaseModel):
    """Closed wire copy of every offline status field."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    bucket_id: UUID
    configured: bool
    represented_nif: str | None = Field(default=None, max_length=16)
    granted_scopes: tuple[str, ...] = ()
    catalogue_version: str | None = None
    configured_at: datetime | None = None

    @classmethod
    def from_status(cls, status: ApoderadoStatus) -> ApoderadoStatusSnapshot:
        """Copy canonical status without a coercive bucket ID validator."""
        return cls(
            bucket_id=UUID(str(status.bucket_id)),
            configured=status.configured,
            represented_nif=status.represented_nif,
            granted_scopes=status.granted_scopes,
            catalogue_version=status.catalogue_version,
            configured_at=status.configured_at,
        )


class ApoderadoConfigurationSnapshot(BaseModel):
    """Closed wire copy of every configured delegation field."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    bucket_id: UUID
    represented_nif: str = Field(min_length=1, max_length=16)
    granted_scopes: tuple[str, ...]
    catalogue_version: str = Field(min_length=1)
    configured_at: datetime
    notes: ApoderadoNotes = ""

    @classmethod
    def from_configuration(cls, configuration: ApoderadoConfiguration) -> ApoderadoConfigurationSnapshot:
        """Copy the full canonical encrypted record into its public result."""
        return cls(
            bucket_id=UUID(str(configuration.bucket_id)),
            represented_nif=configuration.represented_nif,
            granted_scopes=configuration.granted_scopes,
            catalogue_version=configuration.catalogue_version,
            configured_at=configuration.configured_at,
            notes=configuration.notes,
        )


class ApoderadoOperationProjection(BaseModel):
    """Complete CLI facts or a typed, prewrite refusal for one verb."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    operation_id: ApoderadoOperationId
    outcome: Literal["completed", "prewrite_refusal"]
    effect: OperationEffect
    status: ApoderadoStatusSnapshot | None = None
    configuration: ApoderadoConfigurationSnapshot | None = None
    cleared: bool | None = None
    refusal_code: str | None = None

    @model_validator(mode="after")
    def _one_outcome(self) -> Self:
        if self.outcome == "prewrite_refusal":
            if (
                self.effect is not OperationEffect.NONE
                or self.refusal_code not in _REFUSAL_CODES
                or self.status is not None
                or self.configuration is not None
                or self.cleared is not None
            ):
                raise ValueError("apoderado refusal has an invalid effect or payload")
            return self
        if self.refusal_code is not None:
            raise ValueError("apoderado success cannot carry refusal evidence")
        if self.operation_id == APODERADO_STATUS_OPERATION_DEFINITION_ID:
            status = self.status
            valid = (
                status is not None
                and self.configuration is None
                and self.cleared is None
                and self.effect is OperationEffect.NONE
                and status.bucket_id == self.profile_id
            )
        elif self.operation_id == APODERADO_CONFIGURE_OPERATION_DEFINITION_ID:
            configuration = self.configuration
            valid = (
                configuration is not None
                and self.status is None
                and self.cleared is None
                and self.effect is OperationEffect.UPDATED
                and configuration.bucket_id == self.profile_id
            )
        elif self.operation_id == APODERADO_CLEAR_OPERATION_DEFINITION_ID:
            valid = self.cleared is not None and self.status is None and self.configuration is None
            valid = valid and self.effect is (OperationEffect.UPDATED if self.cleared else OperationEffect.NONE)
        else:
            valid = False
        if not valid:
            raise ValueError("apoderado success differs from the requested verb or profile")
        return self


class ApoderadoExecutionResult(BaseModel):
    """Encrypted result retained until exact-profile disclosure is authorized."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: ApoderadoOperationProjection


@dataclass(frozen=True, slots=True)
class ApoderadoOperationPorts:
    """Repository and catalogue inputs bound to one immutable profile and pin."""

    bucket_id: str
    operation: PinnedAuthorityOperation
    repository_factory: ApoderadoConfigurationRepositoryFactory
    settings: Settings


class ApoderadoOperationPortsFactory(Protocol):
    """Compose only the requested profile's canonical apoderado service ports."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> ApoderadoOperationPorts:
        """Return exact-profile ports without ambient profile selection."""
        ...


def project_apoderado_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the projection matching the terminal receipt and profile."""
    if type(result) is not ApoderadoExecutionResult:
        raise ValueError("invalid private apoderado result")
    projection = result.projection
    if (
        receipt.identity.definition_id != projection.operation_id
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.effect is not projection.effect
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("apoderado result differs from its terminal receipt")
    if projection.outcome == "completed":
        if (
            receipt.condition is not OperationTerminalCondition.SUCCEEDED
            or receipt.result_ref is None
            or receipt.refusal_ref is not None
            or receipt.refusal_detail_ref is not None
        ):
            raise ValueError("apoderado success has incompatible terminal evidence")
    elif (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.result_ref is not None
        or receipt.refusal_ref != projection.refusal_code
        or receipt.refusal_detail_ref is None
    ):
        raise ValueError("apoderado refusal has incompatible terminal evidence")
    return projection


class ApoderadoOperationExecutor:
    """Use the canonical service under one retained authority and write fence."""

    def __init__(self, factory: ApoderadoOperationPortsFactory) -> None:
        """Retain the exact-profile factory until owner execution."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[BaseModel], context: OperationExecutorContext
    ) -> str | OperationRefusalEvidence:
        """Validate before entry; fence only the encrypted save or delete."""
        payload = request.payload
        operation_id = request.definition_id
        request_types = {
            APODERADO_STATUS_OPERATION_DEFINITION_ID: ApoderadoStatusRequest,
            APODERADO_CONFIGURE_OPERATION_DEFINITION_ID: ApoderadoConfigureRequest,
            APODERADO_CLEAR_OPERATION_DEFINITION_ID: ApoderadoClearRequest,
            APODERADO_CHECK_OPERATION_DEFINITION_ID: ApoderadoCheckRequest,
        }
        if operation_id not in request_types or type(payload) is not request_types[operation_id]:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if not isinstance(
            payload, (ApoderadoStatusRequest, ApoderadoConfigureRequest, ApoderadoClearRequest, ApoderadoCheckRequest)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        typed_operation_id = cast(ApoderadoOperationId, operation_id)
        profile_id = payload.profile_id
        bucket_id = str(profile_id)
        if (
            request.subject_ref != profile_operation_subject(bucket_id)
            or context.identity.definition_id != operation_id
            or context.identity.subject_ref != request.subject_ref
            or await asyncio.to_thread(require_active_bucket_id) != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        authority = context.authority_operation
        await context.events.phase(operation_id)

        def make_service() -> ApoderadoService:
            if require_active_bucket_id() != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            ports = self._factory(bucket_id=bucket_id, operation=authority)
            if ports.bucket_id != bucket_id or ports.operation is not authority:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return ApoderadoService(
                repository_factory=ports.repository_factory,
                operation=authority,
                settings=ports.settings,
            )

        async def publish(projection: ApoderadoOperationProjection) -> str:
            reference = await context.operands.put(ApoderadoExecutionResult(projection=projection), written_at=now())
            await context.events.effect(projection.effect)
            return reference

        async def refuse(code: str) -> OperationRefusalEvidence:
            projection = ApoderadoOperationProjection(
                profile_id=profile_id,
                operation_id=typed_operation_id,
                outcome="prewrite_refusal",
                effect=OperationEffect.NONE,
                refusal_code=code,
            )
            reference = await publish(projection)
            return OperationRefusalEvidence(refusal_code=code, detail_ref=reference)

        async def run() -> str | OperationRefusalEvidence:
            service = await asyncio.to_thread(make_service)
            if operation_id == APODERADO_STATUS_OPERATION_DEFINITION_ID:
                status = await asyncio.to_thread(service.status, bucket_id=bucket_id)
                return await publish(
                    ApoderadoOperationProjection(
                        profile_id=profile_id,
                        operation_id=typed_operation_id,
                        outcome="completed",
                        effect=OperationEffect.NONE,
                        status=ApoderadoStatusSnapshot.from_status(status),
                    )
                )
            if operation_id == APODERADO_CHECK_OPERATION_DEFINITION_ID:
                try:
                    await asyncio.to_thread(service.check, bucket_id=bucket_id)
                except ApoderadoLiveCheckUnavailableError:
                    return await refuse("REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE")
                raise ValueError("apoderado live check returned without a verified live result")
            if operation_id == APODERADO_CONFIGURE_OPERATION_DEFINITION_ID:
                if not isinstance(payload, ApoderadoConfigureRequest):
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
                async with context.ephemeral_secret.consume() as secret:
                    try:
                        represented_nif = bytes(secret).decode("utf-8")
                    except UnicodeDecodeError:
                        return await refuse("REFUSED_APODERADO_INVALID_REPRESENTED_NIF")
                    try:
                        try:
                            configuration = await asyncio.to_thread(
                                service.prepare_configuration,
                                bucket_id=bucket_id,
                                represented_nif=represented_nif,
                                scope_tokens=payload.scope_tokens,
                                notes=payload.notes,
                            )
                        except ApoderadoRepresentedNifInvalidError:
                            return await refuse("REFUSED_APODERADO_INVALID_REPRESENTED_NIF")
                        except UnknownScopeError:
                            return await refuse("REFUSED_APODERADO_UNKNOWN_SCOPE")
                        async with context.cancellation.irreversible_section():
                            await context.events.effect(OperationEffect.UNKNOWN)
                            await asyncio.to_thread(service.persist_configuration, configuration)
                            await context.events.effect(OperationEffect.UPDATED)
                    finally:
                        represented_nif = ""
                return await publish(
                    ApoderadoOperationProjection(
                        profile_id=profile_id,
                        operation_id=typed_operation_id,
                        outcome="completed",
                        effect=OperationEffect.UPDATED,
                        configuration=ApoderadoConfigurationSnapshot.from_configuration(configuration),
                    )
                )
            if operation_id == APODERADO_CLEAR_OPERATION_DEFINITION_ID:
                async with context.cancellation.irreversible_section():
                    await context.events.effect(OperationEffect.UNKNOWN)
                    cleared = await asyncio.to_thread(service.clear, bucket_id=bucket_id)
                    effect = OperationEffect.UPDATED if cleared else OperationEffect.NONE
                    await context.events.effect(effect)
                return await publish(
                    ApoderadoOperationProjection(
                        profile_id=profile_id,
                        operation_id=typed_operation_id,
                        outcome="completed",
                        effect=effect,
                        cleared=cleared,
                    )
                )
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

        return await await_cancellation_complete(run(), task_name=operation_id)


def _resolve_access(request: OperationRequest[BaseModel], context: OperationAccessContext) -> ResolvedOperationAccess:
    payload = request.payload
    operation_id = request.definition_id
    if operation_id not in _IDS or not isinstance(
        payload, (ApoderadoStatusRequest, ApoderadoConfigureRequest, ApoderadoClearRequest, ApoderadoCheckRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    mutating = operation_id in {APODERADO_CONFIGURE_OPERATION_DEFINITION_ID, APODERADO_CLEAR_OPERATION_DEFINITION_ID}
    frontends = _WRITE_FRONTENDS if mutating else _READ_FRONTENDS
    actions = _WRITE_ACTIONS if mutating else _READ_ACTIONS
    if context.frontend not in frontends:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    if context.action not in actions:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    admitted = context.admitted_request
    if admitted is not None and context.action in {AccessAction.OBSERVE, AccessAction.RESULT}:
        if (
            admitted.profile_id != context.profile_id
            or admitted.definition_id != operation_id
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
        if schema is None or schema.schema_id != operation_id + ".result":
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
            definition_id=operation_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=operation_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=actions,
            disclosures=disclosures,
            periods=frozenset(),
            allow_period_independent=True,
            requires_all_periods=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=mutating,
        ),
    )


def build_apoderado_operation_definitions(factory: ApoderadoOperationPortsFactory) -> tuple[OperationDefinition, ...]:
    """Declare each existing verb with truthful read/write and secret custody."""
    request_types: dict[ApoderadoOperationId, type[BaseModel]] = {
        APODERADO_STATUS_OPERATION_DEFINITION_ID: ApoderadoStatusRequest,
        APODERADO_CONFIGURE_OPERATION_DEFINITION_ID: ApoderadoConfigureRequest,
        APODERADO_CLEAR_OPERATION_DEFINITION_ID: ApoderadoClearRequest,
        APODERADO_CHECK_OPERATION_DEFINITION_ID: ApoderadoCheckRequest,
    }
    definitions: list[OperationDefinition] = []
    for operation_id, request_type in request_types.items():
        mutating = operation_id in {
            APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
            APODERADO_CLEAR_OPERATION_DEFINITION_ID,
        }
        definitions.append(
            OperationDefinition(
                definition_id=operation_id,
                request_type=request_type,
                result_type=ApoderadoExecutionResult,
                executor_factory=OperationExecutorFactory(
                    request_type=request_type,
                    executor_type=ApoderadoOperationExecutor,
                    build=lambda: ApoderadoOperationExecutor(factory),
                ),
                phase_codes=(operation_id,),
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
                    permitted_effects=frozenset(
                        {OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED}
                    )
                    if mutating
                    else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
                    close_policy=OperationClosePolicy.DETACH_ALLOWED,
                ),
                reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
                permitted_frontends=_WRITE_FRONTENDS if mutating else _READ_FRONTENDS,
                ephemeral_secret=(
                    OperationEphemeralSecretDeclaration(
                        secret_kind=APODERADO_REPRESENTED_NIF_SECRET_KIND, lifetime=timedelta(minutes=5)
                    )
                    if operation_id == APODERADO_CONFIGURE_OPERATION_DEFINITION_ID
                    else None
                ),
                refusal_detail_codes=(
                    frozenset({"REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE"})
                    if operation_id == APODERADO_CHECK_OPERATION_DEFINITION_ID
                    else frozenset({"REFUSED_APODERADO_INVALID_REPRESENTED_NIF", "REFUSED_APODERADO_UNKNOWN_SCOPE"})
                    if operation_id == APODERADO_CONFIGURE_OPERATION_DEFINITION_ID
                    else frozenset()
                ),
            )
        )
    return tuple(sorted(definitions, key=lambda definition: definition.definition_id))


def build_apoderado_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind the four closed schemas and exact-profile authorization resolvers."""
    registrations: list[OperationPublicDefinitionRegistrationV1] = []
    for definition in definitions:
        if definition.definition_id not in _IDS:
            raise ValueError("unknown apoderado operation definition")
        registrations.append(
            OperationPublicDefinitionRegistrationV1.compose(
                definition=definition,
                request_schema=OperationSchemaBindingV1.bind(
                    schema_id=definition.definition_id + ".request",
                    schema_version=1,
                    model_type=definition.request_type,
                ),
                result_schema=OperationSchemaBindingV1.bind(
                    schema_id=definition.definition_id + ".result",
                    schema_version=1,
                    model_type=ApoderadoOperationProjection,
                ),
                result_projector=project_apoderado_operation_result,
                access_resolver=_resolve_access,
            )
        )
    return tuple(sorted(registrations, key=lambda registration: registration.contract.definition_id))


__all__ = [
    "APODERADO_CHECK_OPERATION_DEFINITION_ID",
    "APODERADO_CLEAR_OPERATION_DEFINITION_ID",
    "APODERADO_CONFIGURE_OPERATION_DEFINITION_ID",
    "APODERADO_REPRESENTED_NIF_SECRET_KIND",
    "APODERADO_STATUS_OPERATION_DEFINITION_ID",
    "ApoderadoCheckRequest",
    "ApoderadoClearRequest",
    "ApoderadoConfigurationSnapshot",
    "ApoderadoConfigureRequest",
    "ApoderadoExecutionResult",
    "ApoderadoOperationPorts",
    "ApoderadoOperationPortsFactory",
    "ApoderadoOperationProjection",
    "ApoderadoStatusRequest",
    "ApoderadoStatusSnapshot",
    "build_apoderado_operation_definitions",
    "build_apoderado_operation_registrations",
    "project_apoderado_operation_result",
]
