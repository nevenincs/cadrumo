"""Trusted outer capabilities for registered exact-profile auth reads."""

from __future__ import annotations

from uuid import UUID

from ..adapters.persistence.profile.auth_diagnostics import build_auth_diagnostic_persistence
from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from ..adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ..application.auth.read_operation import AuthReadPorts
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from .adapter_composition import build_operator_probe_ports, build_state_projection_read_ports


def compose_auth_read_ports(profile_id: UUID) -> AuthReadPorts:
    """Compose existing canonical reads inside the profile worker lifetime."""
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return AuthReadPorts(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        operator_probe_ports=build_operator_probe_ports(),
        operator_scope_ports=build_operator_scope_ports(),
        read_ports=build_state_projection_read_ports(),
        diagnostics_persistence=build_auth_diagnostic_persistence(),
    )
