"""Bind the canonical modelo readiness readers to the admitted profile."""

from __future__ import annotations

from ..application.modelo.query_read_operation import ModeloQueryReadPorts
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..core.identity.bucket import canonical_bucket_id
from .adapter_composition import build_state_projection_read_ports


def build_modelo_query_read_ports(*, bucket_id: str) -> ModeloQueryReadPorts:
    """Reject a changed worker binding before composing encrypted readers."""
    normalized_bucket_id = canonical_bucket_id(bucket_id)
    if require_active_bucket_id() != normalized_bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ModeloQueryReadPorts(
        bucket_id=normalized_bucket_id,
        read_ports=build_state_projection_read_ports(),
    )


__all__ = ["build_modelo_query_read_ports"]
