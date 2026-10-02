"""Exact-profile, human-authorized reads of local AEAT auth state."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
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
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..state_projection_ports import StateProjectionReadPorts
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
from .diagnostics import (
    AuthDiagnosticDetail,
    AuthDiagnosticListReport,
    AuthDiagnosticSummary,
    list_auth_diagnostics,
    load_auth_diagnostic,
)
from .diagnostics_ports import AuthDiagnosticPersistencePort
from .operator import inspect_operator_auth, test_operator_auth
from .operator_probe_ports import OperatorProbePorts
from .operator_results import AuthStatusResult, AuthTestResult
from .operator_scope_ports import OperatorScopePorts
from .probes import ProviderProbeResult

AUTH_READ_OPERATION_DEFINITION_ID = "auth.local-read"
AUTH_READ_RESULT_SCHEMA_ID = "auth.local-read.result"
type AuthReadKind = Literal["status", "test", "diagnostics_list", "diagnostics_view"]
_FRONTENDS = frozenset(OperationFrontendProjection)
_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT})


class AuthReadRequest(CredentialFreeOperationRequest):
    """Nonsecret routing for one private read; no caller-supplied authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    kind: AuthReadKind
    provider: str | None = Field(default=None, max_length=64)
    diagnostic_id: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def _coordinates(self) -> AuthReadRequest:
        if (self.diagnostic_id is not None) != (self.kind == "diagnostics_view"):
            raise ValueError("diagnostic id belongs only to a detail read")
        if self.provider is not None and self.kind not in {"status", "test"}:
            raise ValueError("provider belongs only to a readiness read")
        if self.provider is not None and not self.provider.strip():
            raise ValueError("provider must not be blank")
        if self.diagnostic_id is not None and not self.diagnostic_id.strip():
            raise ValueError("diagnostic id must not be blank")
        return self


class AuthReadResult(BaseModel):
    """Encrypted result body; exactly one canonical redacted read projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: AuthReadKind
    status: AuthStatusResult | None = None
    test: AuthTestResult | None = None
    diagnostics_list: AuthDiagnosticListReport | None = None
    diagnostics_view: AuthDiagnosticDetail | None = None
    diagnostic_found: bool | None = None

    @model_validator(mode="after")
    def _one_result(self) -> AuthReadResult:
        fields = {
            "status": self.status,
            "test": self.test,
            "diagnostics_list": self.diagnostics_list,
        }
        if any((item is not None) != (name == self.kind) for name, item in fields.items()):
            raise ValueError("auth read result does not match requested kind")
        if self.kind == "diagnostics_view":
            if self.diagnostic_found is None or (self.diagnostics_view is not None) != self.diagnostic_found:
                raise ValueError("diagnostic detail presence is inconsistent")
        elif self.diagnostic_found is not None or self.diagnostics_view is not None:
            raise ValueError("diagnostic detail belongs only to a detail read")
        return self


class AuthStatusSnapshot(BaseModel):
    """Closed public copy of the redacted local readiness facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    provider: str = ""
    configured: bool = False
    authenticated: bool = False
    available: bool = False
    active_profile: str = ""
    active_profile_status: str = ""
    active_profile_registered: bool = False
    active_profile_record_present: bool = False
    active_profile_precondition_verdict: PreconditionVerdictSnapshot | None = None
    backend_configured: bool = False
    backend_available: bool = False
    certificate_path: str = ""
    health_severity: str = ""
    health_summary: str = ""

    @classmethod
    def from_status(cls, status: AuthStatusResult) -> AuthStatusSnapshot:
        """Copy the canonical status into the public schema."""
        values = status.model_dump(exclude={"active_profile_precondition_verdict"})
        verdict = status.active_profile_precondition_verdict
        snapshot = PreconditionVerdictSnapshot.from_verdict(verdict) if verdict else None
        return cls(
            **values,
            active_profile_precondition_verdict=snapshot,
        )

    def to_status(self) -> AuthStatusResult:
        """Restore the existing CLI status contract."""
        values = self.model_dump(exclude={"active_profile_precondition_verdict"})
        verdict = self.active_profile_precondition_verdict
        return AuthStatusResult(**values, active_profile_precondition_verdict=verdict.to_verdict() if verdict else None)


class AuthTestSnapshot(AuthStatusSnapshot):
    """Closed public copy of the local probe and readiness facts."""

    persisted_session_present: bool = False
    persisted_session_expired: bool | None = None
    persisted_session_state: str = ""
    probe_summary: str = ""
    probe_result: ProviderProbeResult | None = None

    @classmethod
    def from_test(cls, result: AuthTestResult) -> AuthTestSnapshot:
        """Copy the canonical local probe into the public schema."""
        values = result.model_dump(exclude={"active_profile_precondition_verdict"})
        verdict = result.active_profile_precondition_verdict
        snapshot = PreconditionVerdictSnapshot.from_verdict(verdict) if verdict else None
        return cls(
            **values,
            active_profile_precondition_verdict=snapshot,
        )

    def to_test(self) -> AuthTestResult:
        """Restore the existing CLI local probe contract."""
        values = self.model_dump(exclude={"active_profile_precondition_verdict"})
        verdict = self.active_profile_precondition_verdict
        return AuthTestResult(**values, active_profile_precondition_verdict=verdict.to_verdict() if verdict else None)


class AuthDiagnosticSummarySnapshot(AuthDiagnosticSummary):
    """Typed public summary; the canonical service already redacts raw evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class AuthDiagnosticDetailSnapshot(AuthDiagnosticSummarySnapshot):
    """Typed redacted detail with a schema-visible operator verdict."""

    html_excerpt: str | None = None
    profile_tax_id_fingerprint: str = ""
    clave_identity_fingerprint: str = ""
    dni_fecha_fingerprint: str = ""
    nie_soporte_fingerprint: str = ""
    certificate_path_fingerprint: str = ""
    operator_report_verdict: PreconditionVerdictSnapshot | None = None

    @classmethod
    def from_detail(cls, detail: AuthDiagnosticDetail) -> AuthDiagnosticDetailSnapshot:
        """Copy redacted detail and its structured operator verdict."""
        values = detail.model_dump(exclude={"operator_report_verdict"})
        verdict = detail.operator_report_verdict
        snapshot = PreconditionVerdictSnapshot.from_verdict(verdict) if verdict else None
        return cls(**values, operator_report_verdict=snapshot)

    def to_detail(self) -> AuthDiagnosticDetail:
        """Restore the existing CLI diagnostic detail contract."""
        values = self.model_dump(exclude={"operator_report_verdict"})
        verdict = self.operator_report_verdict
        return AuthDiagnosticDetail(**values, operator_report_verdict=verdict.to_verdict() if verdict else None)


class AuthReadProjection(BaseModel):
    """Closed public variants of the redacted exact-profile read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: AuthReadKind
    status: AuthStatusSnapshot | None = None
    test: AuthTestSnapshot | None = None
    diagnostics_rows: tuple[AuthDiagnosticSummarySnapshot, ...] | None = None
    diagnostics_view: AuthDiagnosticDetailSnapshot | None = None
    diagnostic_found: bool | None = None

    def to_result(self) -> AuthReadResult:
        """Restore the canonical redacted response for existing CLI presenters."""
        return AuthReadResult(
            profile_id=self.profile_id,
            kind=self.kind,
            status=self.status.to_status() if self.status else None,
            test=self.test.to_test() if self.test else None,
            diagnostics_list=(
                AuthDiagnosticListReport(
                    row_count=len(self.diagnostics_rows),
                    rows=tuple(AuthDiagnosticSummary.model_validate(row.model_dump()) for row in self.diagnostics_rows),
                )
                if self.diagnostics_rows is not None
                else None
            ),
            diagnostics_view=self.diagnostics_view.to_detail() if self.diagnostics_view else None,
            diagnostic_found=self.diagnostic_found,
        )


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
        if schema is None or schema.schema_id != AUTH_READ_RESULT_SCHEMA_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=payload.profile_id,
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
            requires_human=False,
        ),
    )


def project_auth_read_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the declared redacted model for a successful exact subject."""
    if (
        type(result) is not AuthReadResult
        or receipt.identity.definition_id != AUTH_READ_OPERATION_DEFINITION_ID
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
    ):
        raise ValueError("invalid auth read result")
    if receipt.identity.subject_ref != profile_operation_subject(str(result.profile_id)):
        raise ValueError("auth read result profile mismatch")
    validated = AuthReadResult.model_validate_json(result.model_dump_json(), strict=True)
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
