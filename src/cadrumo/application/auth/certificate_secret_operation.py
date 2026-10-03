"""Registered exact-profile changes to named certificate passphrase custody."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel, SecretStr

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ..operations.access_resolution import (
    HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_declared_frontend_and_action,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_STORED_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..operations.secret_submission import OperationEphemeralSecretDeclaration
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .certificate_secret_backend import CertificateSecretBackendFactory
from .certificate_source_operations import (
    remove_operator_certificate_source_secret,
    set_operator_certificate_source_secret,
)
from .models import CertificateSourceName
from .operator_results import CertificateSourceNotFoundError, CertificateSourceSecretMutationResult
from .operator_scope_ports import OperatorScopePorts

CERTIFICATE_CREDENTIAL_SET_OPERATION_DEFINITION_ID = "auth.certificate.secret.set"
CERTIFICATE_CREDENTIAL_REMOVE_OPERATION_DEFINITION_ID = "auth.certificate.secret.remove"
CERTIFICATE_CREDENTIAL_KIND = "auth.certificate.passphrase"
_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})


class CertificateSecretMutationRequest(BaseModel):
    """Credential-free exact profile and named source; bytes use the one-shot broker."""

    model_config = STRICT_FROZEN_CONFIG
    profile_id: UUID
    name: CertificateSourceName


class CertificateSecretMutationProjection(BaseModel):
    """Only the named source and nonsecret effect facts leave worker custody."""

    model_config = STRICT_FROZEN_CONFIG
    profile_id: UUID
    result: CertificateSourceSecretMutationResult


@dataclass(frozen=True, slots=True)
class CertificateSecretOperationPorts:
    """The canonical auth service's existing secure-store and scope capabilities."""

    operator_scope_ports: OperatorScopePorts
    certificate_secret_backend_factory: CertificateSecretBackendFactory


class CertificateSecretMutationExecutor:
    """Publish one bounded set/remove under fresh human COMMIT authority."""

    def __init__(
        self,
        *,
        ports: CertificateSecretOperationPorts,
        removing: bool,
        set_secret: Callable[..., CertificateSourceSecretMutationResult] = set_operator_certificate_source_secret,
        remove_secret: Callable[..., CertificateSourceSecretMutationResult] = remove_operator_certificate_source_secret,
    ) -> None:
        self._ports = ports
        self._removing = removing
        self._set_secret = set_secret
        self._remove_secret = remove_secret

    async def execute(
        self, request: OperationRequest[CertificateSecretMutationRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        expected_definition_id = (
            CERTIFICATE_CREDENTIAL_REMOVE_OPERATION_DEFINITION_ID
            if self._removing
            else CERTIFICATE_CREDENTIAL_SET_OPERATION_DEFINITION_ID
        )
        if (
            request.definition_id != expected_definition_id
            or require_active_bucket_id() != str(payload.profile_id)
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase("auth.certificate-secret.preflight")

        if self._removing:
            return await await_cancellation_complete(
                self._publish(payload, context, None), task_name="certificate-secret-remove-publication"
            )
        await context.events.phase("auth.certificate-secret.consume")
        async with context.ephemeral_secret.consume() as secret:
            passphrase = bytes(secret).decode("utf-8")
            try:
                return await await_cancellation_complete(
                    self._publish(payload, context, SecretStr(passphrase)),
                    task_name="certificate-secret-set-publication",
                )
            finally:
                passphrase = ""

    async def _publish(
        self,
        payload: CertificateSecretMutationRequest,
        context: OperationExecutorContext,
        secret_value: SecretStr | None,
    ) -> str:
        async with context.cancellation.irreversible_section():
            await context.events.effect(OperationEffect.UNKNOWN)
            await context.events.phase("auth.certificate-secret.execute")
            try:
                result = await self._invoke_service(payload, context, secret_value)
            except CertificateSourceNotFoundError:
                await context.events.effect(OperationEffect.NONE)
                raise
            validated = _validate_certificate_secret_mutation(result, payload, removing=self._removing)
            changed = not self._removing or validated.removed
            await context.events.effect(OperationEffect.UPDATED if changed else OperationEffect.NONE)
            await context.events.phase("auth.certificate-secret.settlement")
            return await context.operands.put(validated, written_at=now())

    async def _invoke_service(
        self,
        payload: CertificateSecretMutationRequest,
        context: OperationExecutorContext,
        secret_value: SecretStr | None,
    ) -> CertificateSourceSecretMutationResult:
        if self._removing:
            return await asyncio.to_thread(
                self._remove_secret,
                name=payload.name,
                certificate_secret_backend_factory=self._ports.certificate_secret_backend_factory,
                operation=context.authority_operation,
                operator_scope_ports=self._ports.operator_scope_ports,
            )
        if secret_value is None:
            raise ValueError("certificate passphrase set requires one-shot proof")
        return await asyncio.to_thread(
            self._set_secret,
            name=payload.name,
            secret=secret_value,
            certificate_secret_backend_factory=self._ports.certificate_secret_backend_factory,
            operation=context.authority_operation,
            operator_scope_ports=self._ports.operator_scope_ports,
        )


def _validate_certificate_secret_mutation(
    result: object, payload: CertificateSecretMutationRequest, *, removing: bool
) -> CertificateSourceSecretMutationResult:
    if type(result) is not CertificateSourceSecretMutationResult:
        raise ValueError("certificate secret mutation returned an invalid result")
    validated = CertificateSourceSecretMutationResult.model_validate_json(result.model_dump_json(), strict=True)
    if (
        validated.name != payload.name.strip()
        or validated.has_secret is removing
        or (not removing and validated.removed)
        or (removing and validated.rotated)
    ):
        raise ValueError("certificate secret mutation returned a mismatched result")
    return validated


def _definition(*, removing: bool, ports: CertificateSecretOperationPorts) -> OperationDefinition:
    definition_id = (
        CERTIFICATE_CREDENTIAL_REMOVE_OPERATION_DEFINITION_ID
        if removing
        else CERTIFICATE_CREDENTIAL_SET_OPERATION_DEFINITION_ID
    )
    return OperationDefinition(
        definition_id=definition_id,
        request_type=CertificateSecretMutationRequest,
        result_type=CertificateSourceSecretMutationResult,
        executor_factory=OperationExecutorFactory(
            request_type=CertificateSecretMutationRequest,
            executor_type=CertificateSecretMutationExecutor,
            build=lambda: CertificateSecretMutationExecutor(ports=ports, removing=removing),
        ),
        phase_codes=(
            "auth.certificate-secret.preflight",
            *(("auth.certificate-secret.consume",) if not removing else ()),
            "auth.certificate-secret.execute",
            "auth.certificate-secret.settlement",
        ),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_STORED_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=_FRONTENDS,
        ephemeral_secret=(
            None
            if removing
            else OperationEphemeralSecretDeclaration(
                secret_kind=CERTIFICATE_CREDENTIAL_KIND, lifetime=timedelta(minutes=5)
            )
        ),
    )


def build_certificate_secret_operation_definitions(
    ports: CertificateSecretOperationPorts,
) -> tuple[OperationDefinition, OperationDefinition]:
    """Enroll one set and one remove over the canonical mutation services."""
    return _definition(removing=False, ports=ports), _definition(removing=True, ports=ports)


def resolve_certificate_secret_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact human profile authority at submit, commit and disclosure."""
    if (
        request.definition_id
        not in {
            CERTIFICATE_CREDENTIAL_SET_OPERATION_DEFINITION_ID,
            CERTIFICATE_CREDENTIAL_REMOVE_OPERATION_DEFINITION_ID,
        }
        or type(request.payload) is not CertificateSecretMutationRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(context.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    access_profile = HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS
    require_declared_frontend_and_action(context, frontends=_FRONTENDS, actions=access_profile.actions)
    return bind_operation_access_profile(
        context, access_profile, profile_id=context.profile_id, definition_id=request.definition_id, periods=frozenset()
    )


def project_certificate_secret_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the nonsecret source status from a successful exact-profile receipt."""
    _require_certificate_secret_receipt(result, receipt)
    profile_id = _certificate_secret_profile_id(receipt)
    validated = CertificateSourceSecretMutationResult.model_validate_json(result.model_dump_json(), strict=True)
    removing = receipt.identity.definition_id == CERTIFICATE_CREDENTIAL_REMOVE_OPERATION_DEFINITION_ID
    _require_certificate_secret_effect(validated, receipt, removing=removing)
    return CertificateSecretMutationProjection(profile_id=profile_id, result=validated)


def _require_certificate_secret_receipt(result: BaseModel, receipt: OperationTerminalReceipt) -> None:
    if (
        type(result) is not CertificateSourceSecretMutationResult
        or receipt.identity.definition_id
        not in {
            CERTIFICATE_CREDENTIAL_SET_OPERATION_DEFINITION_ID,
            CERTIFICATE_CREDENTIAL_REMOVE_OPERATION_DEFINITION_ID,
        }
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
    ):
        raise ValueError("invalid certificate secret result")


def _certificate_secret_profile_id(receipt: OperationTerminalReceipt) -> UUID:
    try:
        profile_id = UUID(receipt.identity.subject_ref.removeprefix("profile:"))
    except ValueError:
        raise ValueError("invalid certificate secret subject") from None
    if receipt.identity.subject_ref != profile_operation_subject(str(profile_id)):
        raise ValueError("invalid certificate secret subject")
    return profile_id


def _require_certificate_secret_effect(
    validated: CertificateSourceSecretMutationResult,
    receipt: OperationTerminalReceipt,
    *,
    removing: bool,
) -> None:
    if (
        not validated.name.strip()
        or validated.has_secret is removing
        or (not removing and (validated.removed or receipt.effect is not OperationEffect.UPDATED))
        or (
            removing
            and (
                validated.rotated
                or receipt.effect is not (OperationEffect.UPDATED if validated.removed else OperationEffect.NONE)
            )
        )
    ):
        raise ValueError("invalid certificate secret effect")


def build_certificate_secret_operation_registrations(
    definitions: tuple[OperationDefinition, OperationDefinition],
) -> tuple[OperationPublicDefinitionRegistrationV1, OperationPublicDefinitionRegistrationV1]:
    """Bind current request/result schemas and the shared human access policy."""
    registrations = tuple(
        OperationPublicDefinitionRegistrationV1.compose_request_result(
            definition=definition,
            public_result_type=CertificateSecretMutationProjection,
            result_projector=project_certificate_secret_result,
            access_resolver=resolve_certificate_secret_access,
        )
        for definition in definitions
    )
    return registrations[0], registrations[1]


__all__ = [
    "CERTIFICATE_CREDENTIAL_KIND",
    "CERTIFICATE_CREDENTIAL_REMOVE_OPERATION_DEFINITION_ID",
    "CERTIFICATE_CREDENTIAL_SET_OPERATION_DEFINITION_ID",
    "CertificateSecretMutationProjection",
    "CertificateSecretMutationRequest",
    "CertificateSecretOperationPorts",
    "build_certificate_secret_operation_definitions",
    "build_certificate_secret_operation_registrations",
]
