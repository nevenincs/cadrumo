"""Registered exact-profile changes to named certificate passphrase custody."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
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
from .certificate_secret_backend import CertificateSecretBackendFactory
from .certificate_source_operations import (
    remove_operator_certificate_source_secret,
    set_operator_certificate_source_secret,
)
from .operator_results import CertificateSourceNotFoundError, CertificateSourceSecretMutationResult
from .operator_scope_ports import OperatorScopePorts

CERTIFICATE_CREDENTIAL_SET_OPERATION_DEFINITION_ID = "auth.certificate.secret.set"
CERTIFICATE_CREDENTIAL_REMOVE_OPERATION_DEFINITION_ID = "auth.certificate.secret.remove"
CERTIFICATE_CREDENTIAL_KIND = "auth.certificate.passphrase"
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)
_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
_ACTIONS = frozenset(
    {AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, AccessAction.OBSERVE, AccessAction.RESULT}
)


class CertificateSecretMutationRequest(BaseModel):
    """Credential-free exact profile and named source; bytes use the one-shot broker."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    name: str = Field(min_length=1, max_length=128)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("certificate source name must not be blank")
        return normalized


class CertificateSecretMutationProjection(BaseModel):
    """Only the named source and nonsecret effect facts leave worker custody."""

    model_config = _PUBLIC_CONFIG
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

        async def publish(secret_value: SecretStr | None) -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                await context.events.phase("auth.certificate-secret.execute")
                try:
                    if self._removing:
                        result = await asyncio.to_thread(
                            self._remove_secret,
                            name=payload.name,
                            certificate_secret_backend_factory=self._ports.certificate_secret_backend_factory,
                            operation=context.authority_operation,
                            operator_scope_ports=self._ports.operator_scope_ports,
                        )
                    else:
                        if secret_value is None:
                            raise ValueError("certificate passphrase set requires one-shot proof")
                        result = await asyncio.to_thread(
                            self._set_secret,
                            name=payload.name,
                            secret=secret_value,
                            certificate_secret_backend_factory=self._ports.certificate_secret_backend_factory,
                            operation=context.authority_operation,
                            operator_scope_ports=self._ports.operator_scope_ports,
                        )
                except CertificateSourceNotFoundError:
                    await context.events.effect(OperationEffect.NONE)
                    raise
                if type(result) is not CertificateSourceSecretMutationResult:
                    raise ValueError("certificate secret mutation returned an invalid result")
                validated = CertificateSourceSecretMutationResult.model_validate_json(
                    result.model_dump_json(), strict=True
                )
                if (
                    validated.name != payload.name.strip()
                    or validated.has_secret is self._removing
                    or (not self._removing and validated.removed)
                    or (self._removing and validated.rotated)
                ):
                    raise ValueError("certificate secret mutation returned a mismatched result")
                changed = not self._removing or validated.removed
                await context.events.effect(OperationEffect.UPDATED if changed else OperationEffect.NONE)
                await context.events.phase("auth.certificate-secret.settlement")
                return await context.operands.put(validated, written_at=now())

        if self._removing:
            return await await_cancellation_complete(publish(None), task_name="certificate-secret-remove-publication")
        await context.events.phase("auth.certificate-secret.consume")
        async with context.ephemeral_secret.consume() as secret:
            passphrase = bytes(secret).decode("utf-8")
            try:
                return await await_cancellation_complete(
                    publish(SecretStr(passphrase)), task_name="certificate-secret-set-publication"
                )
            finally:
                passphrase = ""


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
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
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
    if context.frontend not in _FRONTENDS:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    if context.action not in _ACTIONS:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    disclosure = None
    if context.action is AccessAction.OBSERVE:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None or schema.schema_id != request.definition_id + ".result":
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
        )
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
            actions=_ACTIONS,
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
            periods=frozenset(),
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=True,
        ),
    )


def project_certificate_secret_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the nonsecret source status from a successful exact-profile receipt."""
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
    try:
        profile_id = UUID(receipt.identity.subject_ref.removeprefix("profile:"))
    except ValueError:
        raise ValueError("invalid certificate secret subject") from None
    if receipt.identity.subject_ref != profile_operation_subject(str(profile_id)):
        raise ValueError("invalid certificate secret subject")
    validated = CertificateSourceSecretMutationResult.model_validate_json(result.model_dump_json(), strict=True)
    removing = receipt.identity.definition_id == CERTIFICATE_CREDENTIAL_REMOVE_OPERATION_DEFINITION_ID
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
    return CertificateSecretMutationProjection(profile_id=profile_id, result=validated)


def build_certificate_secret_operation_registrations(
    definitions: tuple[OperationDefinition, OperationDefinition],
) -> tuple[OperationPublicDefinitionRegistrationV1, OperationPublicDefinitionRegistrationV1]:
    """Bind current request/result schemas and the shared human access policy."""
    registrations = tuple(
        OperationPublicDefinitionRegistrationV1.compose(
            definition=definition,
            request_schema=OperationSchemaBindingV1.bind(
                schema_id=definition.definition_id + ".request",
                schema_version=1,
                model_type=CertificateSecretMutationRequest,
            ),
            result_schema=OperationSchemaBindingV1.bind(
                schema_id=definition.definition_id + ".result",
                schema_version=1,
                model_type=CertificateSecretMutationProjection,
            ),
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
