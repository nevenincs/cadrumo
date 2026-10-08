"""Closed public contracts and redacted schemas for exact-profile auth reads."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.models import CredentialFreeOperationRequest
from ..operator_actions.projection import PreconditionVerdictSnapshot
from .diagnostics import (
    AuthDiagnosticDetail,
    AuthDiagnosticListReport,
    AuthDiagnosticSummary,
)
from .operator_results import AuthStatusResult, AuthTestResult
from .probes import ProviderProbeResult

AUTH_READ_OPERATION_DEFINITION_ID = "auth.local-read"


AUTH_READ_RESULT_SCHEMA_ID = "auth.local-read.result"


type AuthReadKind = Literal["status", "test", "diagnostics_list", "diagnostics_view"]


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
