"""Exact-profile worker operations for trusted review-package recipients."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import InternalInvariantError, pydantic_validation_boundary
from ...core.hashing import canonical_json_bytes
from ...core.hex import HEX_PATTERN_64
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
from ...core.time.utc import validate_utc_aware
from ..bucket_event_repository import BucketEventHistoryRepositoryFactory
from ..operations.access_port import OperationAccessResolver
from ..operations.access_resolution import (
    OBSERVATION_DISCLOSING_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access,
    operation_disclosures,
)
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_terminal_receipt_match
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationResultProjector,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .review_package_collab_audit import (
    emit_collab_recipient_registered_event,
    emit_collab_recipient_removed_event,
)
from .review_package_recipient_registry import (
    RecipientAlreadyRegisteredError,
    RecipientFingerprintRecord,
    RecipientNotRegisteredError,
    add_recipient_fingerprint,
    list_recipient_fingerprints,
    public_key_hex_from_raw_bytes,
    remove_recipient_fingerprint,
)
from .review_package_recipient_registry_ports import RecipientFingerprintRegistryPortsFactory

REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID = "config.collab.recipient.add"
REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID = "config.collab.recipient.list"
REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID = "config.collab.recipient.remove"
MAX_REVIEW_PACKAGE_RECIPIENT_ROWS = 4_096
_RESULT_DOCUMENT_MAX_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096


class ReviewPackageRecipientAddRequest(BaseModel):
    """Exact-profile request for one X25519 recipient trust registration."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    recipient_id: str = Field(min_length=1, max_length=200)
    public_key_hex: str = Field(strict=True, min_length=64, max_length=64, pattern=HEX_PATTERN_64)
    label: str = Field(default="", max_length=200)


class ReviewPackageRecipientListRequest(BaseModel):
    """Exact-profile request for the complete trusted-recipient register."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class ReviewPackageRecipientRemoveRequest(BaseModel):
    """Exact-profile request to revoke trust for one registered recipient."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    recipient_id: str = Field(min_length=1, max_length=200)


class ReviewPackageRecipientProjection(BaseModel):
    """Full public row released from a canonical recipient record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    recipient_id: str = Field(min_length=1, max_length=200)
    label: str = Field(max_length=200)
    public_key_hex: str = Field(strict=True, min_length=64, max_length=64, pattern=HEX_PATTERN_64)
    fingerprint_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern=HEX_PATTERN_64)
    added_at: datetime

    @field_validator("added_at")
    @classmethod
    @pydantic_validation_boundary
    def _added_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @classmethod
    def from_record(cls, record: RecipientFingerprintRecord) -> ReviewPackageRecipientProjection:
        """Preserve the canonical public fields of one registry record."""
        return cls(
            recipient_id=record.recipient_id,
            label=record.label,
            public_key_hex=record.public_key_hex,
            fingerprint_sha256=record.fingerprint_sha256,
            added_at=record.added_at,
        )

    @model_validator(mode="after")
    def _fingerprint_is_derived(self) -> ReviewPackageRecipientProjection:
        if (
            self.fingerprint_sha256
            != RecipientFingerprintRecord(
                recipient_id=self.recipient_id,
                label=self.label,
                public_key_hex=self.public_key_hex,
                added_at=self.added_at,
            ).fingerprint_sha256
        ):
            raise ValueError("recipient fingerprint must be derived from its public key")
        return self


class ReviewPackageRecipientAddProjection(BaseModel):
    """Registered add result, correlated to its exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    recipient: ReviewPackageRecipientProjection

    @model_validator(mode="after")
    def _row_is_complete(self) -> ReviewPackageRecipientAddProjection:
        if not self.recipient.recipient_id:
            raise ValueError("registered recipient result is incomplete")
        return self


class ReviewPackageRecipientListProjection(BaseModel):
    """Complete, sorted registered recipient inventory."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    recipients: tuple[ReviewPackageRecipientProjection, ...] = Field(max_length=MAX_REVIEW_PACKAGE_RECIPIENT_ROWS)
    count: NonNegativeInt

    @model_validator(mode="after")
    def _inventory_is_complete_and_sorted(self) -> ReviewPackageRecipientListProjection:
        identities = tuple(row.recipient_id for row in self.recipients)
        if self.count != len(self.recipients) or identities != tuple(sorted(identities)):
            raise ValueError("recipient inventory count or order is not canonical")
        if len(set(identities)) != len(identities):
            raise ValueError("recipient inventory repeats an identity")
        return self


class ReviewPackageRecipientRemoveProjection(BaseModel):
    """Committed removal result and the actual remaining register count."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    recipient_id: str = Field(min_length=1, max_length=200)
    remaining: NonNegativeInt


class _RecipientAddExecutionResult(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: ReviewPackageRecipientAddProjection


class _RecipientListExecutionResult(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: ReviewPackageRecipientListProjection


class _RecipientRemoveExecutionResult(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: ReviewPackageRecipientRemoveProjection


@dataclass(frozen=True, slots=True)
class _RecipientPorts:
    registry_factory: RecipientFingerprintRegistryPortsFactory
    event_repository_factory: BucketEventHistoryRepositoryFactory


class ReviewPackageRecipientAddExecutor:
    """Register one recipient and append its canonical audit event under COMMIT."""

    def __init__(self, ports: _RecipientPorts) -> None:
        """Retain the bucket-bound registry and history factories."""
        self._ports = ports

    async def execute(
        self,
        request: OperationRequest[ReviewPackageRecipientAddRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Persist a recipient and audit event, then release its complete row."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)
        # The request schema has already fixed this at exactly 32 bytes; the
        # canonical parser remains the owning X25519 boundary before mutation.
        canonical_key = public_key_hex_from_raw_bytes(bytes.fromhex(payload.public_key_hex))
        if canonical_key != payload.public_key_hex:
            raise InternalInvariantError("recipient request passed a noncanonical public key")
        registry_ports = self._ports.registry_factory(bucket_id=bucket_id)
        event_repository = self._ports.event_repository_factory(bucket_id=bucket_id)

        async def commit_and_publish() -> ReviewPackageRecipientAddProjection:
            async with context.cancellation.irreversible_section():
                if require_active_bucket_id() != bucket_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    updated = await asyncio.to_thread(
                        add_recipient_fingerprint,
                        recipient_id=payload.recipient_id,
                        public_key_hex=canonical_key,
                        label=payload.label,
                        ports=registry_ports,
                    )
                except RecipientAlreadyRegisteredError:
                    # The canonical service refuses duplicates before save.
                    await context.events.effect(OperationEffect.NONE)
                    raise
                await context.events.effect(OperationEffect.PARTIAL)
                matching = tuple(row for row in updated.records if row.recipient_id == payload.recipient_id)
                if len(matching) != 1 or matching[0].public_key_hex != canonical_key:
                    raise InternalInvariantError("recipient add did not return its committed canonical record")
                record = matching[0]
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    await asyncio.to_thread(
                        emit_collab_recipient_registered_event,
                        record,
                        bucket_id=bucket_id,
                        repository=event_repository,
                    )
                except Exception:
                    # Registry publication is known complete; the canonical
                    # audit append reports failure before this operation ends.
                    await context.events.effect(OperationEffect.PARTIAL)
                    raise
                await context.events.effect(OperationEffect.UPDATED)
                projection = ReviewPackageRecipientAddProjection(
                    profile_id=payload.profile_id,
                    recipient=ReviewPackageRecipientProjection.from_record(record),
                )
                _check_projection_size(projection)
                return projection

        projection = await await_cancellation_complete(commit_and_publish(), task_name="collab-recipient-add")
        return await context.operands.put(
            _RecipientAddExecutionResult(profile_id=payload.profile_id, result=projection),
            written_at=now(),
        )


class ReviewPackageRecipientListExecutor:
    """Read and disclose every recipient in canonical order."""

    def __init__(self, registry_factory: RecipientFingerprintRegistryPortsFactory) -> None:
        """Retain the bucket-bound recipient registry factory."""
        self._registry_factory = registry_factory

    async def execute(
        self,
        request: OperationRequest[ReviewPackageRecipientListRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Capture every canonical recipient row without changing either store."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def read() -> ReviewPackageRecipientListProjection:
            ports = self._registry_factory(bucket_id=bucket_id)
            records = list_recipient_fingerprints(ports=ports)
            if len(records) > MAX_REVIEW_PACKAGE_RECIPIENT_ROWS:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            projection = ReviewPackageRecipientListProjection(
                profile_id=payload.profile_id,
                recipients=tuple(
                    ReviewPackageRecipientProjection.from_record(row)
                    for row in sorted(records, key=lambda item: item.recipient_id)
                ),
                count=len(records),
            )
            _check_projection_size(projection)
            return projection

        async def capture() -> str:
            projection = await asyncio.to_thread(read)
            return await context.operands.put(
                _RecipientListExecutionResult(profile_id=payload.profile_id, result=projection),
                written_at=now(),
            )

        return await await_cancellation_complete(capture(), task_name="collab-recipient-list")


class ReviewPackageRecipientRemoveExecutor:
    """Revoke one trusted recipient and append its canonical audit event under COMMIT."""

    def __init__(self, ports: _RecipientPorts) -> None:
        """Retain the bucket-bound registry and history factories."""
        self._ports = ports

    async def execute(
        self,
        request: OperationRequest[ReviewPackageRecipientRemoveRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Remove a recipient and audit event, then report the actual remainder."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)
        registry_ports = self._ports.registry_factory(bucket_id=bucket_id)
        event_repository = self._ports.event_repository_factory(bucket_id=bucket_id)

        async def commit_and_publish() -> ReviewPackageRecipientRemoveProjection:
            async with context.cancellation.irreversible_section():
                if require_active_bucket_id() != bucket_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    updated = await asyncio.to_thread(
                        remove_recipient_fingerprint,
                        payload.recipient_id,
                        ports=registry_ports,
                    )
                except RecipientNotRegisteredError:
                    # The canonical service refuses a missing id before save.
                    await context.events.effect(OperationEffect.NONE)
                    raise
                await context.events.effect(OperationEffect.PARTIAL)
                if any(row.recipient_id == payload.recipient_id for row in updated.records):
                    raise InternalInvariantError("recipient removal retained its committed canonical record")
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    await asyncio.to_thread(
                        emit_collab_recipient_removed_event,
                        recipient_id=payload.recipient_id,
                        bucket_id=bucket_id,
                        repository=event_repository,
                    )
                except Exception:
                    await context.events.effect(OperationEffect.PARTIAL)
                    raise
                await context.events.effect(OperationEffect.UPDATED)
                projection = ReviewPackageRecipientRemoveProjection(
                    profile_id=payload.profile_id,
                    recipient_id=payload.recipient_id,
                    remaining=len(updated.records),
                )
                return projection

        projection = await await_cancellation_complete(commit_and_publish(), task_name="collab-recipient-remove")
        return await context.operands.put(
            _RecipientRemoveExecutionResult(profile_id=payload.profile_id, result=projection),
            written_at=now(),
        )


def _check_projection_size(projection: BaseModel) -> None:
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _RESULT_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _require_success_receipt(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
    effect: OperationEffect,
) -> None:
    contradiction = "recipient projection differs from its terminal receipt"
    require_terminal_receipt_match(
        receipt,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        message=contradiction,
    )
    if getattr(result, "profile_id", None) != profile_id:
        raise ValueError(contradiction)


def project_review_package_recipient_add_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> ReviewPackageRecipientAddProjection:
    """Release an add result only when its receipt confirms UPDATED."""
    if type(result) is not _RecipientAddExecutionResult:
        raise ValueError("invalid recipient add result")
    private = _RecipientAddExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    _require_success_receipt(
        private,
        receipt,
        definition_id=REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID,
        profile_id=private.profile_id,
        effect=OperationEffect.UPDATED,
    )
    _check_projection_size(private.result)
    return private.result


def project_review_package_recipient_list_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> ReviewPackageRecipientListProjection:
    """Release a list result only when its receipt confirms a read-only success."""
    if type(result) is not _RecipientListExecutionResult:
        raise ValueError("invalid recipient list result")
    private = _RecipientListExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    _require_success_receipt(
        private,
        receipt,
        definition_id=REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID,
        profile_id=private.profile_id,
        effect=OperationEffect.NONE,
    )
    _check_projection_size(private.result)
    return private.result


def project_review_package_recipient_remove_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> ReviewPackageRecipientRemoveProjection:
    """Release a removal result only when its receipt confirms UPDATED."""
    if type(result) is not _RecipientRemoveExecutionResult:
        raise ValueError("invalid recipient removal result")
    private = _RecipientRemoveExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    _require_success_receipt(
        private,
        receipt,
        definition_id=REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID,
        profile_id=private.profile_id,
        effect=OperationEffect.UPDATED,
    )
    return private.result


def _definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[ReviewPackageRecipientAddExecutor]
    | type[ReviewPackageRecipientListExecutor]
    | type[ReviewPackageRecipientRemoveExecutor],
    build: Callable[[], object],
    mutation: bool,
) -> OperationDefinition:
    effects = (
        frozenset({OperationEffect.NONE, OperationEffect.PARTIAL, OperationEffect.UPDATED, OperationEffect.UNKNOWN})
        if mutation
        else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    )
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_type=executor_type,
        build=build,
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=effects,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_review_package_recipient_add_definition(
    registry_factory: RecipientFingerprintRegistryPortsFactory,
    event_repository_factory: BucketEventHistoryRepositoryFactory,
) -> OperationDefinition:
    """Build the registered exact-profile recipient add operation."""
    ports = _RecipientPorts(registry_factory, event_repository_factory)
    return _definition(
        definition_id=REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID,
        request_type=ReviewPackageRecipientAddRequest,
        result_type=_RecipientAddExecutionResult,
        executor_type=ReviewPackageRecipientAddExecutor,
        build=lambda: ReviewPackageRecipientAddExecutor(ports),
        mutation=True,
    )


def build_review_package_recipient_list_definition(
    registry_factory: RecipientFingerprintRegistryPortsFactory,
) -> OperationDefinition:
    """Build the read-only operation for the complete recipient inventory."""
    return _definition(
        definition_id=REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID,
        request_type=ReviewPackageRecipientListRequest,
        result_type=_RecipientListExecutionResult,
        executor_type=ReviewPackageRecipientListExecutor,
        build=lambda: ReviewPackageRecipientListExecutor(registry_factory),
        mutation=False,
    )


def build_review_package_recipient_remove_definition(
    registry_factory: RecipientFingerprintRegistryPortsFactory,
    event_repository_factory: BucketEventHistoryRepositoryFactory,
) -> OperationDefinition:
    """Build the registered exact-profile recipient removal operation."""
    ports = _RecipientPorts(registry_factory, event_repository_factory)
    return _definition(
        definition_id=REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID,
        request_type=ReviewPackageRecipientRemoveRequest,
        result_type=_RecipientRemoveExecutionResult,
        executor_type=ReviewPackageRecipientRemoveExecutor,
        build=lambda: ReviewPackageRecipientRemoveExecutor(ports),
        mutation=True,
    )


def _resolve_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
    *,
    definition_id: str,
    request_type: type[ReviewPackageRecipientAddRequest]
    | type[ReviewPackageRecipientListRequest]
    | type[ReviewPackageRecipientRemoveRequest],
    mutation: bool,
) -> ResolvedOperationAccess:
    if context.contract.definition_id != definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = require_access_request_profile_payload(
        request,
        definition_id=definition_id,
        payload_type=request_type,
        access_profile_id=context.profile_id,
    ).profile_id
    actions = {
        AccessAction.SUBMIT,
        AccessAction.START,
        AccessAction.RESUME,
        AccessAction.OBSERVE,
        AccessAction.RESULT,
        AccessAction.CANCEL,
        AccessAction.DETACH,
    }
    if mutation:
        actions.add(AccessAction.COMMIT)
    disclosures = operation_disclosures(
        context,
        observed_by=OBSERVATION_DISCLOSING_ACTIONS,
        result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
        result_schema_id=None,
    )
    return bind_operation_access(
        context,
        profile_id=profile_id,
        definition_id=definition_id,
        actions=frozenset(actions),
        disclosures=disclosures,
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=False,
        requires_human=False,
        provider=Availability.NOT_REQUIRED,
    )


def resolve_review_package_recipient_add_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve add authority for the request's exact profile."""
    return _resolve_access(
        request,
        context,
        definition_id=REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID,
        request_type=ReviewPackageRecipientAddRequest,
        mutation=True,
    )


def resolve_review_package_recipient_list_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve full-register disclosure authority for the exact profile."""
    return _resolve_access(
        request,
        context,
        definition_id=REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID,
        request_type=ReviewPackageRecipientListRequest,
        mutation=False,
    )


def resolve_review_package_recipient_remove_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve removal authority for the request's exact profile."""
    return _resolve_access(
        request,
        context,
        definition_id=REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID,
        request_type=ReviewPackageRecipientRemoveRequest,
        mutation=True,
    )


def _registration(
    *,
    definition: OperationDefinition,
    result_type: type[BaseModel],
    projector: OperationResultProjector,
    resolver: OperationAccessResolver,
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=result_type,
        result_projector=projector,
        access_resolver=resolver,
    )


def build_review_package_recipient_add_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind public schemas, projector, and access resolver for add."""
    return _registration(
        definition=definition,
        result_type=ReviewPackageRecipientAddProjection,
        projector=project_review_package_recipient_add_result,
        resolver=resolve_review_package_recipient_add_access,
    )


def build_review_package_recipient_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind public schemas, projector, and access resolver for list."""
    return _registration(
        definition=definition,
        result_type=ReviewPackageRecipientListProjection,
        projector=project_review_package_recipient_list_result,
        resolver=resolve_review_package_recipient_list_access,
    )


def build_review_package_recipient_remove_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind public schemas, projector, and access resolver for remove."""
    return _registration(
        definition=definition,
        result_type=ReviewPackageRecipientRemoveProjection,
        projector=project_review_package_recipient_remove_result,
        resolver=resolve_review_package_recipient_remove_access,
    )


__all__ = [
    "MAX_REVIEW_PACKAGE_RECIPIENT_ROWS",
    "REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID",
    "REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID",
    "REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID",
    "ReviewPackageRecipientAddExecutor",
    "ReviewPackageRecipientAddProjection",
    "ReviewPackageRecipientAddRequest",
    "ReviewPackageRecipientListExecutor",
    "ReviewPackageRecipientListProjection",
    "ReviewPackageRecipientListRequest",
    "ReviewPackageRecipientProjection",
    "ReviewPackageRecipientRemoveExecutor",
    "ReviewPackageRecipientRemoveProjection",
    "ReviewPackageRecipientRemoveRequest",
    "build_review_package_recipient_add_definition",
    "build_review_package_recipient_add_registration",
    "build_review_package_recipient_list_definition",
    "build_review_package_recipient_list_registration",
    "build_review_package_recipient_remove_definition",
    "build_review_package_recipient_remove_registration",
    "project_review_package_recipient_add_result",
    "project_review_package_recipient_list_result",
    "project_review_package_recipient_remove_result",
    "resolve_review_package_recipient_add_access",
    "resolve_review_package_recipient_list_access",
    "resolve_review_package_recipient_remove_access",
]
