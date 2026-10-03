"""Exact-profile auth read operation execution and registration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ..operations.access_resolution import (
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access,
    operation_disclosures,
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
    OperationSchemaBindingV1,
)
from ..state_projection_ports import StateProjectionReadPorts
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .auth_read_contracts import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AUTH_READ_RESULT_SCHEMA_ID,
    AuthDiagnosticDetailSnapshot,
    AuthDiagnosticSummarySnapshot,
    AuthReadProjection,
    AuthReadRequest,
    AuthReadResult,
    AuthStatusSnapshot,
    AuthTestSnapshot,
)
from .certificate_secret_backend import CertificateSecretBackendFactory
from .diagnostics import (
    list_auth_diagnostics,
    load_auth_diagnostic,
)
from .diagnostics_ports import AuthDiagnosticPersistencePort
from .operator import inspect_operator_auth, test_operator_auth
from .operator_probe_ports import OperatorProbePorts
from .operator_scope_ports import OperatorScopePorts

_FRONTENDS = frozenset(OperationFrontendProjection)


_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT})


@dataclass(frozen=True, slots=True)
class AuthReadPorts:
    """Trusted worker capabilities consumed by the canonical read services."""

    certificate_secret_backend_factory: CertificateSecretBackendFactory
    operator_probe_ports: OperatorProbePorts
    operator_scope_ports: OperatorScopePorts
    read_ports: StateProjectionReadPorts
    diagnostics_persistence: AuthDiagnosticPersistencePort


class AuthReadExecutor:
    """Run one existing read service in immutable profile-worker custody."""

    def __init__(self, ports_factory: Callable[[UUID], AuthReadPorts]) -> None:
        """Retain the factory until execution in the exact profile worker."""
        self._ports_factory = ports_factory

    async def execute(self, request: OperationRequest[AuthReadRequest], context: OperationExecutorContext) -> str:
        """Read canonical auth state and persist its encrypted result."""
        payload = request.payload
        if request.subject_ref != profile_operation_subject(str(payload.profile_id)):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if require_active_bucket_id() != str(payload.profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase("auth.local-read.execute")

        def read() -> AuthReadResult:
            if require_active_bucket_id() != str(payload.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            ports = self._ports_factory(payload.profile_id)
            if payload.kind in {"status", "test"}:
                if payload.kind == "status":
                    result = AuthReadResult(
                        profile_id=payload.profile_id,
                        kind="status",
                        status=inspect_operator_auth(
                            payload.provider,
                            certificate_secret_backend_factory=ports.certificate_secret_backend_factory,
                            operator_probe_ports=ports.operator_probe_ports,
                            operator_scope_ports=ports.operator_scope_ports,
                            read_ports=ports.read_ports,
                            operation=context.authority_operation,
                        ),
                    )
                else:
                    result = AuthReadResult(
                        profile_id=payload.profile_id,
                        kind="test",
                        test=test_operator_auth(
                            payload.provider,
                            certificate_secret_backend_factory=ports.certificate_secret_backend_factory,
                            operator_probe_ports=ports.operator_probe_ports,
                            operator_scope_ports=ports.operator_scope_ports,
                            read_ports=ports.read_ports,
                            operation=context.authority_operation,
                        ),
                    )
            elif payload.kind == "diagnostics_list":
                result = AuthReadResult(
                    profile_id=payload.profile_id,
                    kind="diagnostics_list",
                    diagnostics_list=list_auth_diagnostics(persistence=ports.diagnostics_persistence),
                )
            else:
                if payload.diagnostic_id is None:
                    raise ValueError("diagnostic id required")
                detail = load_auth_diagnostic(payload.diagnostic_id, persistence=ports.diagnostics_persistence)
                result = AuthReadResult(
                    profile_id=payload.profile_id,
                    kind="diagnostics_view",
                    diagnostics_view=detail,
                    diagnostic_found=detail is not None,
                )
            return result

        result = await await_cancellation_complete(asyncio.to_thread(read), task_name="auth-local-read")
        reference = await await_cancellation_complete(
            context.operands.put(result, written_at=now()), task_name="auth-local-read-result"
        )
        await context.events.effect(OperationEffect.NONE)
        return reference


def resolve_auth_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Limit all phases and result disclosure to the exact human profile."""
    payload = request.payload
    if type(payload) is not AuthReadRequest or request.definition_id != AUTH_READ_OPERATION_DEFINITION_ID:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    require_declared_frontend_and_action(context, frontends=_FRONTENDS, actions=_ACTIONS)
    disclosures = operation_disclosures(
        context,
        observed_by=frozenset({AccessAction.OBSERVE}),
        result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
        result_schema_id=AUTH_READ_RESULT_SCHEMA_ID,
    )
    return bind_operation_access(
        context,
        profile_id=payload.profile_id,
        definition_id=request.definition_id,
        actions=_ACTIONS,
        disclosures=disclosures,
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=False,
        requires_human=False,
        provider=Availability.NOT_REQUIRED,
    )


def project_auth_read_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the declared redacted model for a successful exact subject."""
    validated = _validated_auth_read_result(result, receipt)
    return AuthReadProjection(
        profile_id=validated.profile_id,
        kind=validated.kind,
        status=AuthStatusSnapshot.from_status(validated.status) if validated.status else None,
        test=AuthTestSnapshot.from_test(validated.test) if validated.test else None,
        diagnostics_rows=(
            tuple(
                AuthDiagnosticSummarySnapshot.model_validate(row.model_dump())
                for row in validated.diagnostics_list.rows
            )
            if validated.diagnostics_list
            else None
        ),
        diagnostics_view=(
            AuthDiagnosticDetailSnapshot.from_detail(validated.diagnostics_view) if validated.diagnostics_view else None
        ),
        diagnostic_found=validated.diagnostic_found,
    )


def _validated_auth_read_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
) -> AuthReadResult:
    """Enforce the read's exact definition, terminal effect, and subject before projection."""
    if (
        type(result) is not AuthReadResult
        or receipt.identity.definition_id != AUTH_READ_OPERATION_DEFINITION_ID
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
    ):
        raise ValueError("invalid auth read result")
    if receipt.identity.subject_ref != profile_operation_subject(str(result.profile_id)):
        raise ValueError("auth read result profile mismatch")
    return AuthReadResult.model_validate_json(result.model_dump_json(), strict=True)


def build_auth_read_definition(ports_factory: Callable[[UUID], AuthReadPorts]) -> OperationDefinition:
    """Build the real read executor for production enrollment."""
    return OperationDefinition(
        definition_id=AUTH_READ_OPERATION_DEFINITION_ID,
        request_type=AuthReadRequest,
        result_type=AuthReadResult,
        executor_factory=OperationExecutorFactory(
            request_type=AuthReadRequest,
            executor_type=AuthReadExecutor,
            build=lambda: AuthReadExecutor(ports_factory),
        ),
        phase_codes=("auth.local-read.execute",),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_STORED_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=_FRONTENDS,
    )


def build_auth_read_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll strict request/result schemas and current disclosure policy."""
    if definition.definition_id != AUTH_READ_OPERATION_DEFINITION_ID:
        raise ValueError("unexpected auth read definition")
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=AUTH_READ_OPERATION_DEFINITION_ID + ".request", schema_version=1, model_type=AuthReadRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=AUTH_READ_RESULT_SCHEMA_ID, schema_version=1, model_type=AuthReadProjection
        ),
        result_projector=project_auth_read_result,
        access_resolver=resolve_auth_read_access,
    )
