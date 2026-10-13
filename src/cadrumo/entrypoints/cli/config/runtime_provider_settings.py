"""Exact-profile CLI bridge for provider-settings status and the person's changes.

Every refusal leaves here as one :class:`CliRefusedBoundaryError` whose
``reason`` is a closed provider-settings refusal code, whether the service,
the runtime or the operation host refused. The key travels only as the
operation's one-shot secret and is wiped on every exit.
"""

from __future__ import annotations

from typing import Never
from uuid import UUID

import typer
from pydantic import BaseModel, ValidationError

from ....application.provider_settings.contracts import (
    ProviderSettingsActionAccepted,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderSettingsStatus,
    ProviderStatusEntry,
)
from ....application.provider_settings.registered_operations import (
    PROVIDER_SETTINGS_REMOVE_OPERATION_DEFINITION_ID,
    PROVIDER_SETTINGS_RESET_OPERATION_DEFINITION_ID,
    PROVIDER_SETTINGS_SET_OPERATION_DEFINITION_ID,
    PROVIDER_SETTINGS_STATUS_OPERATION_DEFINITION_ID,
    ProviderSettingsChangeRequest,
    ProviderSettingsChangeResult,
    ProviderSettingsStatusRequest,
    ProviderSettingsStatusResult,
    change_effect,
)
from ....application.runtime.contracts import RuntimeRefusalError
from ....application.user_profile.access_contracts import AccessDenialCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion
from ..registered_operation_errors import invalid_completion_error
from ..runtime_profile_binding import require_profile_client
from ..runtime_registered_operation import run_registered_operation
from ._profile_support import resolve_active_profile_pointer

_PERSON_ACT_REASONS = frozenset(
    {
        AccessDenialCode.PERSON_ACT_REQUIRED.value,
        AccessDenialCode.HUMAN_AUTHORITY_REQUIRED.value,
        AccessDenialCode.FRONTEND_DENIED.value,
    }
)
_LOCKED_REASONS = frozenset(
    {
        AccessDenialCode.PROFILE_LOCKED.value,
        AccessDenialCode.OS_LOCKED.value,
        AccessDenialCode.SESSION_EXPIRED.value,
        AccessDenialCode.SESSION_INACTIVE.value,
    }
)
_NOT_SIGNED_IN_REASONS = frozenset({AccessDenialCode.AUTHENTICATION_REQUIRED.value})


def refuse(code: ProviderSettingsRefusalCode, *, operation_id: str | None = None) -> Never:
    """Raise the one CLI refusal for ``code``, worded by its own catalogue key."""
    context: dict[str, object] = {"reason": code.value}
    if operation_id is not None:
        context["operation_id"] = operation_id
    raise CliRefusedBoundaryError(translated_message=f"cli.config.provider.refused.{code.value}", context=context)


def _contract_code(reason: object) -> ProviderSettingsRefusalCode:
    if reason in _PERSON_ACT_REASONS:
        return ProviderSettingsRefusalCode.PERSON_ACT_REQUIRED
    if reason in _LOCKED_REASONS:
        return ProviderSettingsRefusalCode.PROFILE_LOCKED
    if reason in _NOT_SIGNED_IN_REASONS:
        return ProviderSettingsRefusalCode.NOT_SIGNED_IN
    return ProviderSettingsRefusalCode.UNKNOWN


def _profile_id() -> UUID:
    pointer = resolve_active_profile_pointer()
    if pointer is None:
        refuse(ProviderSettingsRefusalCode.NOT_SIGNED_IN)
    return UUID(str(pointer.bucket_id))


def _run[ResultT: BaseModel](
    ctx: typer.Context,
    *,
    profile_id: UUID,
    definition_id: str,
    payload: BaseModel,
    result_type: type[ResultT],
    secret: bytearray | None = None,
) -> RegisteredOperationCompletion[ResultT]:
    try:
        client = require_profile_client(ctx, expected_profile_id=profile_id)
        return run_registered_operation(
            client,
            payload,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(profile_id)),
            result_type=result_type,
            request_version=1,
            result_version=1,
            timeout=120,
            secret=secret,
        )
    except RuntimeRefusalError as error:
        refuse(_contract_code(error.reason.value))
    except CliRefusedBoundaryError as error:
        context = error.context or {}
        operation_id = context.get("operation_id")
        refuse(
            _contract_code(context.get("reason")),
            operation_id=operation_id if isinstance(operation_id, str) else None,
        )


def _settled(
    completion: RegisteredOperationCompletion[ProviderSettingsStatusResult]
    | RegisteredOperationCompletion[ProviderSettingsChangeResult],
    effect: OperationEffect,
    profile_id: UUID,
) -> bool:
    return (
        completion.terminal_condition is OperationTerminalCondition.SUCCEEDED
        and completion.refusal_code is None
        and completion.effect is effect
        and completion.projection.profile_id == profile_id
    )


def read_status(ctx: typer.Context) -> ProviderSettingsStatus:
    """Read every provider's masked status through the exact profile's worker."""
    profile_id = _profile_id()
    completion = _run(
        ctx,
        profile_id=profile_id,
        definition_id=PROVIDER_SETTINGS_STATUS_OPERATION_DEFINITION_ID,
        payload=ProviderSettingsStatusRequest(profile_id=profile_id),
        result_type=ProviderSettingsStatusResult,
    )
    result = completion.projection
    if type(result) is not ProviderSettingsStatusResult or not _settled(completion, OperationEffect.NONE, profile_id):
        raise invalid_completion_error(completion)
    if result.refused is not None:
        refuse(result.refused, operation_id=completion.operation_id)
    if result.status is None:
        raise invalid_completion_error(completion)
    return result.status


def _change(
    ctx: typer.Context,
    *,
    definition_id: str,
    provider_id: str,
    expected_revision: str,
    base_url: str | None = None,
    clear_base_url: bool = False,
    secret: bytearray | None = None,
) -> ProviderStatusEntry:
    profile_id = _profile_id()
    if base_url is not None and (clear_base_url or not base_url or len(base_url) > 2048):
        refuse(ProviderSettingsRefusalCode.BASE_URL_REJECTED)
    try:
        request = ProviderSettingsChangeRequest(
            profile_id=profile_id,
            provider_id=provider_id,
            expected_revision=expected_revision,
            base_url=base_url,
            clear_base_url=clear_base_url,
        )
    except ValidationError:
        # An empty or overlong provider id or revision names no stored record.
        refuse(
            ProviderSettingsRefusalCode.UNKNOWN
            if not 0 < len(provider_id) <= 64
            else ProviderSettingsRefusalCode.REVISION_CONFLICT
        )
    completion = _run(
        ctx,
        profile_id=profile_id,
        definition_id=definition_id,
        payload=request,
        result_type=ProviderSettingsChangeResult,
        secret=secret,
    )
    result = completion.projection
    if type(result) is not ProviderSettingsChangeResult or result.provider_id != provider_id:
        raise invalid_completion_error(completion)
    outcome = ProviderSettingsActionAccepted(entry=result.entry) if result.entry is not None else _refusal(result)
    if not _settled(completion, change_effect(definition_id, request, outcome), profile_id):
        raise invalid_completion_error(completion)
    if result.refused is not None:
        refuse(result.refused, operation_id=completion.operation_id)
    if result.entry is None:
        raise invalid_completion_error(completion)
    return result.entry


def _refusal(result: ProviderSettingsChangeResult) -> ProviderSettingsRefusal:
    if result.refused is None:
        raise ValueError("a change result without an entry carries a refusal")
    return ProviderSettingsRefusal(code=result.refused)


def set_credential(
    ctx: typer.Context,
    *,
    provider_id: str,
    expected_revision: str,
    base_url: str | None,
    clear_base_url: bool,
    secret: bytearray,
) -> ProviderStatusEntry:
    """Store or replace one provider's key, sent only as the one-shot secret, then wipe it."""
    try:
        return _change(
            ctx,
            definition_id=PROVIDER_SETTINGS_SET_OPERATION_DEFINITION_ID,
            provider_id=provider_id,
            expected_revision=expected_revision,
            base_url=base_url,
            clear_base_url=clear_base_url,
            secret=secret,
        )
    finally:
        secret[:] = bytes(len(secret))


def remove_credential(ctx: typer.Context, *, provider_id: str, expected_revision: str) -> ProviderStatusEntry:
    """Turn one provider off: its key is dropped and no development fallback applies."""
    return _change(
        ctx,
        definition_id=PROVIDER_SETTINGS_REMOVE_OPERATION_DEFINITION_ID,
        provider_id=provider_id,
        expected_revision=expected_revision,
    )


def reset_provider(ctx: typer.Context, *, provider_id: str, expected_revision: str) -> ProviderStatusEntry:
    """Return one provider to unset."""
    return _change(
        ctx,
        definition_id=PROVIDER_SETTINGS_RESET_OPERATION_DEFINITION_ID,
        provider_id=provider_id,
        expected_revision=expected_revision,
    )


__all__ = [
    "read_status",
    "refuse",
    "remove_credential",
    "reset_provider",
    "set_credential",
]
