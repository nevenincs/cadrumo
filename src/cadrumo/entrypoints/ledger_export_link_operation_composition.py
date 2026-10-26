"""Compose the existing ledger action ports for registered export and linkage."""

from __future__ import annotations

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..application.ledger.action_ports import LedgerActionPorts
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .ledger_action_composition import compose_ledger_action_ports


def build_ledger_export_link_operation_ports(
    *, bucket_id: str, operation: PinnedAuthorityOperation
) -> LedgerActionPorts:
    """Require the worker's exact bound profile before any repository composition."""
    if require_active_bucket_id() != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return compose_ledger_action_ports(bucket_id=bucket_id, operation=operation)
