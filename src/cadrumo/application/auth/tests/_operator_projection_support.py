"""Concrete authority and projection capabilities for auth surface tests.

The operator services deliberately require their composition capabilities at
the call site.  These tests exercise several application and persistence
surfaces, so this small test-only seam keeps the repeated composition in one
place while still leasing the real bundled authority and the real persistence
projection adapter for every invocation.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo.adapters.persistence.profile.state_projection import StateProjectionPersistenceAdapter
from cadrumo.adapters.persistence.profile.usage_ratios import load_usage_ratios
from cadrumo.application.auth.credentials import ActiveAuthProjectionSnapshot
from cadrumo.application.auth.operator import (
    build_live_auth_preflight_report as _build_live_auth_preflight_report,
)
from cadrumo.application.auth.operator import (
    configure_operator_auth as _configure_operator_auth,
)
from cadrumo.application.auth.operator import inspect_operator_auth as _inspect_operator_auth
from cadrumo.application.auth.operator import test_operator_auth as _test_operator_auth
from cadrumo.application.auth.operator_probe_ports import OperatorProbePorts
from cadrumo.application.auth.operator_results import (
    AuthConfigureResult,
    AuthStatusResult,
    AuthTestResult,
    LiveAuthPreflightReport,
)
from cadrumo.application.auth.operator_scope_ports import OperatorScopePorts
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.diagnostics_ports import DiagnosticSecureObjectNamespace, DiagnosticsPorts
from cadrumo.application.state_projection import (
    ModeloReadinessRequest,
    OperatorStateProjection,
)
from cadrumo.application.state_projection import (
    build_operator_state_projection as _build_operator_state_projection,
)
from cadrumo.application.state_projection_ports import StateProjectionReadPorts
from cadrumo.application.workflow.state_models import WorkflowState
from cadrumo.core.config import Settings
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

if TYPE_CHECKING:
    from cadrumo.application.auth.certificate_secret_backend import CertificateSecretBackendFactory


class _EmptyDiagnosticRepository:
    """Provide an empty, concrete diagnostics input to the real read adapter."""

    def list_namespaces(self) -> tuple[str, ...]:
        return ()

    def probe_namespace_integrity(self, namespace: str) -> DiagnosticSecureObjectNamespace:
        raise AssertionError(f"unexpected integrity probe for {namespace}")

    def quarantine_unreadable_rows(self) -> tuple[DiagnosticSecureObjectNamespace, ...]:
        return ()


def state_projection_read_ports() -> StateProjectionReadPorts:
    """Compose the persistence-backed projection read ports used by auth tests."""

    adapter = StateProjectionPersistenceAdapter(
        diagnostics_ports=DiagnosticsPorts(
            secure_object_repository=_EmptyDiagnosticRepository(),
            session_failure_classifier=lambda _error: False,
        ),
    )
    return StateProjectionReadPorts(
        workspace=adapter,
        profile=adapter,
        usage_ratio_profile_loader=load_usage_ratios,
    )


@contextmanager
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one real generation-pinned bundled authority operation."""

    with bundled_indexed_authority().operation() as operation:
        yield operation


def _certificate_factory(
    factory: CertificateSecretBackendFactory | None,
) -> CertificateSecretBackendFactory:
    return factory if factory is not None else InMemoryCertificateSecretBackendFactory()


def configure_operator_auth(
    provider: str,
    *,
    certificate_path: Path | None = None,
    operator_scope_ports: OperatorScopePorts,
) -> AuthConfigureResult:
    """Invoke auth configuration with a caller-owned real authority lease."""

    with authority_operation() as operation:
        return _configure_operator_auth(
            provider,
            certificate_path=certificate_path,
            operator_scope_ports=operator_scope_ports,
            operation=operation,
        )


def inspect_operator_auth(
    provider: str | None = None,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory | None = None,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    read_ports: StateProjectionReadPorts | None = None,
) -> AuthStatusResult:
    """Invoke auth status with one real operation and projection read bundle."""

    with authority_operation() as operation:
        return _inspect_operator_auth(
            provider,
            certificate_secret_backend_factory=_certificate_factory(certificate_secret_backend_factory),
            operator_probe_ports=operator_probe_ports,
            operator_scope_ports=operator_scope_ports,
            read_ports=read_ports if read_ports is not None else state_projection_read_ports(),
            operation=operation,
        )


def test_operator_auth(
    provider: str | None = None,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory | None = None,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    settings: Settings | None = None,
    read_ports: StateProjectionReadPorts | None = None,
) -> AuthTestResult:
    """Invoke auth test with one real operation and projection read bundle."""

    with authority_operation() as operation:
        return _test_operator_auth(
            provider,
            certificate_secret_backend_factory=_certificate_factory(certificate_secret_backend_factory),
            operator_probe_ports=operator_probe_ports,
            operator_scope_ports=operator_scope_ports,
            read_ports=read_ports if read_ports is not None else state_projection_read_ports(),
            operation=operation,
            settings=settings,
        )


def build_live_auth_preflight_report(
    provider: str | None = None,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory | None = None,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    settings: Settings | None = None,
    read_ports: StateProjectionReadPorts | None = None,
) -> LiveAuthPreflightReport:
    """Invoke auth preflight with one real operation and projection read bundle."""

    with authority_operation() as operation:
        return _build_live_auth_preflight_report(
            provider,
            certificate_secret_backend_factory=_certificate_factory(certificate_secret_backend_factory),
            operator_probe_ports=operator_probe_ports,
            operator_scope_ports=operator_scope_ports,
            read_ports=read_ports if read_ports is not None else state_projection_read_ports(),
            operation=operation,
            settings=settings,
        )


def build_operator_state_projection(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    read_ports: StateProjectionReadPorts | None = None,
    state: WorkflowState | None = None,
    auth_snapshot: ActiveAuthProjectionSnapshot | None = None,
    requested_provider: str | None = None,
    probe_live_backend: bool = False,
    include_workspace_summary: bool = True,
    include_pending_obligations: bool = True,
    modelo_readiness_requests: tuple[ModeloReadinessRequest, ...] = (),
    today: date | None = None,
) -> OperatorStateProjection:
    """Build a projection under a real operation for direct-producer tests."""

    with authority_operation() as operation:
        return _build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=operator_probe_ports,
            operator_scope_ports=operator_scope_ports,
            read_ports=read_ports if read_ports is not None else state_projection_read_ports(),
            operation=operation,
            state=state,
            auth_snapshot=auth_snapshot,
            requested_provider=requested_provider,
            probe_live_backend=probe_live_backend,
            include_workspace_summary=include_workspace_summary,
            include_pending_obligations=include_pending_obligations,
            modelo_readiness_requests=modelo_readiness_requests,
            today=today,
        )


__all__ = [
    "authority_operation",
    "build_live_auth_preflight_report",
    "build_operator_state_projection",
    "configure_operator_auth",
    "inspect_operator_auth",
    "state_projection_read_ports",
    "test_operator_auth",
]
