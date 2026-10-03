"""Worker-owned capabilities for representative configuration and auth reports."""

from __future__ import annotations

from uuid import UUID

from ..adapters.persistence.profile.apoderado import build_apoderado_config_repository
from ..adapters.persistence.profile.auth_diagnostics import build_auth_diagnostic_persistence
from ..application.auth.apoderado_execution import ApoderadoOperationPorts
from ..application.auth.diagnostic_report_operation import AuthDiagnosticReportPorts
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..core.config import load_settings
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def _require_bound_profile(bucket_id: str) -> None:
    if require_active_bucket_id() != str(UUID(bucket_id)):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def build_apoderado_operation_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ApoderadoOperationPorts:
    """Bind the existing encrypted writer inside the exact profile worker."""
    _require_bound_profile(bucket_id)
    return ApoderadoOperationPorts(
        bucket_id=bucket_id,
        operation=operation,
        repository_factory=build_apoderado_config_repository,
        settings=load_settings(),
    )


def build_auth_diagnostic_report_ports(*, bucket_id: str) -> AuthDiagnosticReportPorts:
    """Bind canonical diagnostic persistence to the admitted worker profile."""
    _require_bound_profile(bucket_id)
    return AuthDiagnosticReportPorts(
        bucket_id=bucket_id,
        persistence=build_auth_diagnostic_persistence(),
    )
