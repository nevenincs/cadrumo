"""Registered exact-profile operations for provider-settings status and the person's changes.

Status is an ordinary read on every frontend. Set, remove and reset are the
person's own acts (:mod:`cadrumo.application.operations.person_acts`): the
runtime refuses them on any frontend that is not the person's. Set takes the
key only through the operation's one-shot secret channel, never as a request
field, and no result carries a secret or anything derived from one.

A refusal the service returns is a typed result value, not an operation
failure, so every frontend reads the same closed refusal code the service
chose. Only a refusal after a committed write reports an updated effect.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, SecretStr, StringConstraints, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationEffect
from ...core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ...core.time.clock import now
from ..operations.access_resolution import (
    HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS,
    LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_declared_action,
    require_period_independent_admission,
)
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES,
    RECORDED_IDEMPOTENT_SECURE_STORED_UPDATE_CAPABILITIES,
)
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.secret_submission import OperationEphemeralSecretDeclaration
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .contracts import (
    ProviderSettingsActionAccepted,
    ProviderSettingsActionResult,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderSettingsStatus,
    ProviderStatusEntry,
)
from .service import BaseUrlChange, ProviderSettingsService

PROVIDER_SETTINGS_STATUS_OPERATION_DEFINITION_ID = "provider-settings.status"
PROVIDER_SETTINGS_SET_OPERATION_DEFINITION_ID = "provider-settings.set"
PROVIDER_SETTINGS_REMOVE_OPERATION_DEFINITION_ID = "provider-settings.remove"
PROVIDER_SETTINGS_RESET_OPERATION_DEFINITION_ID = "provider-settings.reset"
PROVIDER_SETTINGS_CREDENTIAL_KIND = "provider-settings.credential"

PROVIDER_SETTINGS_CHANGE_OPERATION_DEFINITION_IDS = frozenset(
    {
        PROVIDER_SETTINGS_SET_OPERATION_DEFINITION_ID,
        PROVIDER_SETTINGS_REMOVE_OPERATION_DEFINITION_ID,
        PROVIDER_SETTINGS_RESET_OPERATION_DEFINITION_ID,
    }
)
"""The person's provider-credential acts, by definition id."""

type _ProviderText = Annotated[str, StringConstraints(min_length=1, max_length=64)]
type _RevisionText = Annotated[str, StringConstraints(min_length=1, max_length=128)]
type _BaseUrlText = Annotated[str, StringConstraints(min_length=1, max_length=2048)]


class ProviderSettingsStatusRequest(CredentialFreeOperationRequest):
    """The exact profile whose provider settings are read."""

    profile_id: UUID


class ProviderSettingsChangeRequest(CredentialFreeOperationRequest):
    """One guarded change to one provider; the key itself never travels here.

    The provider id and revision are checked by the service, so an unknown
    provider or a malformed revision is a typed refusal rather than a request
    fault. ``base_url`` and ``clear_base_url`` apply to set only.
    """

    profile_id: UUID
    provider_id: _ProviderText
    expected_revision: _RevisionText
    base_url: _BaseUrlText | None = None
    clear_base_url: bool = False

    @model_validator(mode="after")
    def _one_base_url_change(self) -> ProviderSettingsChangeRequest:
        if self.base_url is not None and self.clear_base_url:
            raise ValueError("a base URL cannot be stored and cleared at once")
        return self


class ProviderSettingsStatusResult(BaseModel):
    """Masked status of every provider, or the typed refusal that stopped the read."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    status: ProviderSettingsStatus | None
    refused: ProviderSettingsRefusalCode | None

    @model_validator(mode="after")
    def _exactly_one(self) -> ProviderSettingsStatusResult:
        if (self.status is None) == (self.refused is None):
            raise ValueError("a status result carries a status or a refusal, not both")
        return self


class ProviderSettingsChangeResult(BaseModel):
    """The provider's status read back after a change, or the typed refusal."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    provider_id: _ProviderText
    entry: ProviderStatusEntry | None
    refused: ProviderSettingsRefusalCode | None

    @model_validator(mode="after")
    def _exactly_one(self) -> ProviderSettingsChangeResult:
        if (self.entry is None) == (self.refused is None):
            raise ValueError("a change result carries an entry or a refusal, not both")
        if self.entry is not None and self.entry.id != self.provider_id:
            raise ValueError("a change result names another provider")
        return self


class _ChangeKind(StrEnum):
    SET = "set"
    REMOVE = "remove"
    RESET = "reset"


_CHANGE_DEFINITION_IDS: dict[_ChangeKind, str] = {
    _ChangeKind.SET: PROVIDER_SETTINGS_SET_OPERATION_DEFINITION_ID,
    _ChangeKind.REMOVE: PROVIDER_SETTINGS_REMOVE_OPERATION_DEFINITION_ID,
    _ChangeKind.RESET: PROVIDER_SETTINGS_RESET_OPERATION_DEFINITION_ID,
}


type ProviderSettingsServiceFactory = Callable[[UUID], ProviderSettingsService]
"""Build the service bound to one exact admitted profile; supplied by the composition root."""


@dataclass(frozen=True, slots=True)
class ProviderSettingsOperationPorts:
    """The composition-owned factory for the profile-bound provider-settings service."""

    service: ProviderSettingsServiceFactory


def change_effect(
    definition_id: str, request: ProviderSettingsChangeRequest, result: ProviderSettingsActionResult
) -> OperationEffect:
    """Return the committed extent of one change result.

    A refusal changes nothing, except a refusal after commit; a reset of a
    provider that had no record changes nothing either.
    """
    if isinstance(result, ProviderSettingsRefusal):
        if result.code is ProviderSettingsRefusalCode.COMMITTED_READBACK_FAILED:
            return OperationEffect.UPDATED
        return OperationEffect.NONE
    if (
        definition_id == PROVIDER_SETTINGS_RESET_OPERATION_DEFINITION_ID
        and request.expected_revision == ABSENT_SECURE_OBJECT_REVISION_ID
    ):
        return OperationEffect.NONE
    return OperationEffect.UPDATED


class ProviderSettingsStatusExecutor:
    """Read every provider's masked status inside the exact profile's worker."""

    def __init__(self, ports: ProviderSettingsOperationPorts) -> None:
        """Keep the composition-owned service factory."""
        self._ports = ports

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        """Publish the status or the typed refusal, with no effect."""
        payload = request.payload
        if type(payload) is not ProviderSettingsStatusRequest or not isinstance(payload, ProviderSettingsStatusRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if request.definition_id != PROVIDER_SETTINGS_STATUS_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        profile_id = payload.profile_id

        async def run() -> str:
            await context.events.phase(PROVIDER_SETTINGS_STATUS_OPERATION_DEFINITION_ID)
            status = await asyncio.to_thread(lambda: self._ports.service(profile_id).status())
            result = (
                ProviderSettingsStatusResult(profile_id=profile_id, status=None, refused=status.code)
                if isinstance(status, ProviderSettingsRefusal)
                else ProviderSettingsStatusResult(profile_id=profile_id, status=status, refused=None)
            )
            await context.events.effect(OperationEffect.NONE)
            return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(run(), task_name="provider-settings-status")


class ProviderSettingsChangeExecutor:
    """Apply one person's change to one provider under a revision guard."""

    def __init__(self, ports: ProviderSettingsOperationPorts, kind: _ChangeKind) -> None:
        """Keep the service factory and the one change this definition makes."""
        self._ports = ports
        self._kind = kind

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        """Commit the change, read it back, and publish the entry or the refusal."""
        payload = request.payload
        definition_id = _CHANGE_DEFINITION_IDS[self._kind]
        if type(payload) is not ProviderSettingsChangeRequest or not isinstance(payload, ProviderSettingsChangeRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if request.definition_id != definition_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if self._kind is not _ChangeKind.SET and (payload.base_url is not None or payload.clear_base_url):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(definition_id)
        if self._kind is not _ChangeKind.SET:
            return await await_cancellation_complete(
                self._publish(payload, context, None), task_name=f"provider-settings-{self._kind.value}"
            )
        async with context.ephemeral_secret.consume() as secret:
            try:
                value = bytes(secret).decode("utf-8")
            except UnicodeDecodeError:
                value = ""
            try:
                return await await_cancellation_complete(
                    self._publish(payload, context, SecretStr(value)),
                    task_name="provider-settings-set",
                )
            finally:
                value = ""

    async def _publish(
        self,
        payload: ProviderSettingsChangeRequest,
        context: OperationExecutorContext,
        secret: SecretStr | None,
    ) -> str:
        definition_id = _CHANGE_DEFINITION_IDS[self._kind]
        async with context.cancellation.irreversible_section():
            await context.events.effect(OperationEffect.UNKNOWN)
            outcome = await asyncio.to_thread(self._invoke, payload, secret)
            await context.events.effect(change_effect(definition_id, payload, outcome))
            result = ProviderSettingsChangeResult(
                profile_id=payload.profile_id,
                provider_id=payload.provider_id,
                entry=outcome.entry if isinstance(outcome, ProviderSettingsActionAccepted) else None,
                refused=outcome.code if isinstance(outcome, ProviderSettingsRefusal) else None,
            )
            return await context.operands.put(result, written_at=now())

    def _invoke(self, payload: ProviderSettingsChangeRequest, secret: SecretStr | None) -> ProviderSettingsActionResult:
        service = self._ports.service(payload.profile_id)
        if self._kind is _ChangeKind.REMOVE:
            return service.remove_credential(payload.provider_id, expected_revision=payload.expected_revision)
        if self._kind is _ChangeKind.RESET:
            return service.reset(payload.provider_id, expected_revision=payload.expected_revision)
        if secret is None:
            raise ValueError("a provider credential set requires its one-shot secret")
        base_url: str | BaseUrlChange = (
            payload.base_url
            if payload.base_url is not None
            else BaseUrlChange.CLEAR
            if payload.clear_base_url
            else BaseUrlChange.KEEP
        )
        return service.set_credential(
            payload.provider_id,
            secret=secret,
            expected_revision=payload.expected_revision,
            base_url=base_url,
        )


def build_provider_settings_status_definition(ports: ProviderSettingsOperationPorts) -> OperationDefinition:
    """Declare the exact-profile provider-settings status read."""
    return build_single_phase_definition(
        definition_id=PROVIDER_SETTINGS_STATUS_OPERATION_DEFINITION_ID,
        request_type=ProviderSettingsStatusRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=ProviderSettingsStatusResult,
        executor_type=ProviderSettingsStatusExecutor,
        build=lambda: ProviderSettingsStatusExecutor(ports),
        capabilities=RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES,
    )


def _change_definition(kind: _ChangeKind, ports: ProviderSettingsOperationPorts) -> OperationDefinition:
    return build_single_phase_definition(
        definition_id=_CHANGE_DEFINITION_IDS[kind],
        request_type=ProviderSettingsChangeRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=ProviderSettingsChangeResult,
        executor_type=ProviderSettingsChangeExecutor,
        build=lambda: ProviderSettingsChangeExecutor(ports, kind),
        capabilities=RECORDED_IDEMPOTENT_SECURE_STORED_UPDATE_CAPABILITIES,
        ephemeral_secret=(
            OperationEphemeralSecretDeclaration(
                secret_kind=PROVIDER_SETTINGS_CREDENTIAL_KIND, lifetime=timedelta(minutes=5)
            )
            if kind is _ChangeKind.SET
            else None
        ),
    )


def build_provider_settings_change_definitions(
    ports: ProviderSettingsOperationPorts,
) -> tuple[OperationDefinition, OperationDefinition, OperationDefinition]:
    """Declare set, remove and reset over the one profile-bound service."""
    return (
        _change_definition(_ChangeKind.SET, ports),
        _change_definition(_ChangeKind.REMOVE, ports),
        _change_definition(_ChangeKind.RESET, ports),
    )


def resolve_provider_settings_status_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Scope the status read to the exact profile on every frontend."""
    require_access_request_profile_payload(
        request,
        definition_id=PROVIDER_SETTINGS_STATUS_OPERATION_DEFINITION_ID,
        payload_type=ProviderSettingsStatusRequest,
        access_profile_id=context.profile_id,
    )
    admitted = context.admitted_request
    if admitted is not None:
        require_period_independent_admission(
            admitted, profile_id=context.profile_id, definition_id=request.definition_id
        )
    return bind_operation_access_profile(
        context,
        LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        periods=frozenset(),
    )


def resolve_provider_settings_change_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact human profile authority at submit, commit and disclosure."""
    if request.definition_id not in PROVIDER_SETTINGS_CHANGE_OPERATION_DEFINITION_IDS:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    require_access_request_profile_payload(
        request,
        definition_id=request.definition_id,
        payload_type=ProviderSettingsChangeRequest,
        access_profile_id=context.profile_id,
    )
    access_profile = HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS
    require_declared_action(context, actions=access_profile.actions)
    return bind_operation_access_profile(
        context, access_profile, profile_id=context.profile_id, definition_id=request.definition_id, periods=frozenset()
    )


def build_provider_settings_status_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the status request and result schemas and the every-frontend read policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ProviderSettingsStatusResult,
        access_resolver=resolve_provider_settings_status_access,
    )


def build_provider_settings_change_registrations(
    definitions: tuple[OperationDefinition, OperationDefinition, OperationDefinition],
) -> tuple[
    OperationPublicDefinitionRegistrationV1,
    OperationPublicDefinitionRegistrationV1,
    OperationPublicDefinitionRegistrationV1,
]:
    """Bind each change's schemas and the person's human access policy."""
    set_definition, remove_definition, reset_definition = definitions
    return (
        _change_registration(set_definition),
        _change_registration(remove_definition),
        _change_registration(reset_definition),
    )


def _change_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ProviderSettingsChangeResult,
        access_resolver=resolve_provider_settings_change_access,
    )


__all__ = [
    "PROVIDER_SETTINGS_CHANGE_OPERATION_DEFINITION_IDS",
    "PROVIDER_SETTINGS_CREDENTIAL_KIND",
    "PROVIDER_SETTINGS_REMOVE_OPERATION_DEFINITION_ID",
    "PROVIDER_SETTINGS_RESET_OPERATION_DEFINITION_ID",
    "PROVIDER_SETTINGS_SET_OPERATION_DEFINITION_ID",
    "PROVIDER_SETTINGS_STATUS_OPERATION_DEFINITION_ID",
    "ProviderSettingsChangeExecutor",
    "ProviderSettingsChangeRequest",
    "ProviderSettingsChangeResult",
    "ProviderSettingsOperationPorts",
    "ProviderSettingsServiceFactory",
    "ProviderSettingsStatusExecutor",
    "ProviderSettingsStatusRequest",
    "ProviderSettingsStatusResult",
    "build_provider_settings_change_definitions",
    "build_provider_settings_change_registrations",
    "build_provider_settings_status_definition",
    "build_provider_settings_status_registration",
    "change_effect",
    "resolve_provider_settings_change_access",
    "resolve_provider_settings_status_access",
]
