"""Registered removal of the bound profile's recovery enrollment, proved by its passphrase.

The passphrase is the authorisation, as it is for enrolling: a second door onto
the records is closed only by someone who holds the first. It is never part of
the request. It arrives once, as the operation's declared ephemeral secret, on
the protected secret frame every frontend delivers such a secret on, and the
frame is the passphrase's UTF-8 text and nothing else.

Revoking runs inside the profile's own worker. It takes the custody
transaction lock a passphrase rotation takes there, proves the passphrase
through the same supervised derivation, and removes one file the worker's
custody never pinned: the recovery wrapper sits beside the password envelope,
and neither the envelope, the sentinel nor the capsule's commit record names
it. The password generation and the data key's epoch are unchanged, so the
worker's session stays valid and nothing is retired afterwards.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ..operations.access_resolution import (
    HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_declared_action,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_STORED_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_terminal_receipt_match
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1, OperationReconciliationPolicy
from ..operations.secret_submission import OperationEphemeralSecretDeclaration
from ..operations.subject_reference import OperationSubjectReferenceV1
from .access_contracts import AccessDenialCode
from .access_errors import ProfileAccessRefusedError
from .recovery_custody import ProfileRecoveryEnrollmentOutcome, ProfileRecoveryError, revoke_profile_recovery

RECOVERY_REVOKE_OPERATION_DEFINITION_ID = "user-profile.recovery.revoke"
RECOVERY_REVOKE_PROOF_KIND = "profile.recovery.revoke-passphrase"
RECOVERY_REVOKE_PHASE_CONSUME = "user-profile.recovery.revoke.secret-consume"
RECOVERY_REVOKE_PHASE_EXECUTE = "user-profile.recovery.revoke.execute"
RECOVERY_REVOKE_PHASE_SETTLEMENT = "user-profile.recovery.revoke.settlement"

type RecoveryRevocation = Callable[..., ProfileRecoveryEnrollmentOutcome]
"""The custody service that proves the passphrase and removes the wrapper."""


class RecoveryRevokeRequest(BaseModel):
    """The exact profile whose recovery enrollment is removed; the passphrase is not here."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class RecoveryRevokeResult(BaseModel):
    """What one completed revocation left: no enrollment, and whether one was removed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    enrolled: Literal[False] = False
    changed: bool


class RecoveryRevokeProjection(RecoveryRevokeResult):
    """The receipt-validated public outcome: the members ``config profile recovery disable`` reports."""


def _passphrase_text(secret: memoryview) -> str:
    """Decode the one-shot frame, refusing bytes that cannot be the passphrase.

    The refusal is the one a wrong passphrase gets and is raised outside the
    decoder's scope, so no exception that could retain the rejected bytes is
    chained to it.
    """
    text: str | None = None
    with suppress(UnicodeError):
        text = bytes(secret).decode("utf-8")
    if not text:
        raise ProfileRecoveryError(translated_message="application.user_profile.errors.passphrase_current_rejected")
    return text


def _validated_outcome(value: object, *, profile_id: UUID) -> RecoveryRevokeResult:
    """Hold the custody outcome to this profile before a completed write is recorded."""
    if (
        type(value) is not ProfileRecoveryEnrollmentOutcome
        or value.profile_id != str(profile_id)
        or value.enrolled is not False
        or type(value.changed) is not bool
    ):
        raise ValueError("recovery revocation returned an invalid profile outcome")
    return RecoveryRevokeResult(profile_id=profile_id, changed=value.changed)


class RecoveryRevokeExecutor:
    """Consume the passphrase once and remove the enrollment under COMMIT authority."""

    def __init__(self, *, revoke: RecoveryRevocation = revoke_profile_recovery) -> None:
        """Bind the custody service that proves the passphrase and removes the wrapper."""
        self._revoke = revoke

    async def execute(self, request: OperationRequest[RecoveryRevokeRequest], context: OperationExecutorContext) -> str:
        """Prove the passphrase, remove the wrapper when one is enrolled, and store the outcome."""
        payload = request.payload
        if (
            type(payload) is not RecoveryRevokeRequest
            or request.definition_id != RECOVERY_REVOKE_OPERATION_DEFINITION_ID
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(RECOVERY_REVOKE_PHASE_CONSUME)
        async with context.ephemeral_secret.consume() as secret:
            passphrase = _passphrase_text(secret)
            try:
                await context.events.phase(RECOVERY_REVOKE_PHASE_EXECUTE)

                async def publish() -> str:
                    async with context.cancellation.irreversible_section():
                        await context.events.effect(OperationEffect.UNKNOWN)
                        try:
                            outcome = await asyncio.to_thread(
                                self._revoke, profile_id=payload.profile_id, current_passphrase=passphrase
                            )
                        except ProfileRecoveryError:
                            # The passphrase is proved before anything is removed,
                            # so a refused proof left the wrapper exactly as it was.
                            await context.events.effect(OperationEffect.NONE)
                            raise
                        result = _validated_outcome(outcome, profile_id=payload.profile_id)
                        await context.events.effect(OperationEffect.UPDATED if result.changed else OperationEffect.NONE)
                        await context.events.phase(RECOVERY_REVOKE_PHASE_SETTLEMENT)
                        return await context.operands.put(result, written_at=now())

                return await await_cancellation_complete(publish(), task_name="profile-recovery-revoke")
            finally:
                passphrase = ""


def resolve_recovery_revoke_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve exact-profile human actions and output; the frontend decides nothing."""
    payload = require_access_request_profile_payload(
        request,
        definition_id=RECOVERY_REVOKE_OPERATION_DEFINITION_ID,
        payload_type=RecoveryRevokeRequest,
        access_profile_id=context.profile_id,
    )
    access_profile = HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS
    require_declared_action(context, actions=access_profile.actions)
    return bind_operation_access_profile(
        context, access_profile, profile_id=payload.profile_id, definition_id=request.definition_id, periods=frozenset()
    )


def project_recovery_revoke_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> RecoveryRevokeProjection:
    """Release the outcome only against the successful receipt of its own profile and effect."""
    message = "recovery revocation contradicts its terminal receipt"
    if type(result) is not RecoveryRevokeResult:
        raise ValueError(message)
    require_terminal_receipt_match(
        receipt,
        definition_id=RECOVERY_REVOKE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED if result.changed else OperationEffect.NONE,
        message=message,
    )
    return RecoveryRevokeProjection.model_validate_json(result.model_dump_json(), strict=True)


def build_recovery_revoke_definition(*, revoke: RecoveryRevocation = revoke_profile_recovery) -> OperationDefinition:
    """Declare the revocation with its one-shot passphrase and its permitted effects."""
    return OperationDefinition(
        definition_id=RECOVERY_REVOKE_OPERATION_DEFINITION_ID,
        request_type=RecoveryRevokeRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=RecoveryRevokeResult,
        executor_factory=OperationExecutorFactory(
            request_type=RecoveryRevokeRequest,
            executor_type=RecoveryRevokeExecutor,
            build=lambda: RecoveryRevokeExecutor(revoke=revoke),
        ),
        phase_codes=(
            RECOVERY_REVOKE_PHASE_CONSUME,
            RECOVERY_REVOKE_PHASE_EXECUTE,
            RECOVERY_REVOKE_PHASE_SETTLEMENT,
        ),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_STORED_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        ephemeral_secret=OperationEphemeralSecretDeclaration(
            secret_kind=RECOVERY_REVOKE_PROOF_KIND, lifetime=timedelta(minutes=5)
        ),
        # A refused proof is told apart from any other refusal by its catalogue
        # key, which carries no context: nothing the caller typed is recorded.
        public_error_detail=True,
    )


def build_recovery_revoke_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the request and result schemas, the projector and the access resolver."""
    if definition.definition_id != RECOVERY_REVOKE_OPERATION_DEFINITION_ID:
        raise ValueError("unexpected recovery revocation definition")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=RecoveryRevokeProjection,
        result_projector=project_recovery_revoke_result,
        access_resolver=resolve_recovery_revoke_access,
    )


def recovery_revoke_operation() -> tuple[OperationDefinition, OperationPublicDefinitionRegistrationV1]:
    """Compose the definition and its public registration for an operation registry."""
    definition = build_recovery_revoke_definition()
    return definition, build_recovery_revoke_registration(definition)


__all__ = [
    "RECOVERY_REVOKE_OPERATION_DEFINITION_ID",
    "RECOVERY_REVOKE_PROOF_KIND",
    "RecoveryRevokeExecutor",
    "RecoveryRevokeProjection",
    "RecoveryRevokeRequest",
    "RecoveryRevokeResult",
    "build_recovery_revoke_definition",
    "build_recovery_revoke_registration",
    "project_recovery_revoke_result",
    "recovery_revoke_operation",
    "resolve_recovery_revoke_access",
]
