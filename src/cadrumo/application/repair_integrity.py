"""Secure-object repair session coordination."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from ..core.logging import get_logger

_log = get_logger(__name__)


@contextmanager
def active_bucket_repair_session() -> Generator[None]:
    """Reuse the operator's bucket session for active-bucket repair probes.

    Repair diagnostics never open a session themselves. When the active session
    does not serve the target bucket, the storage substrate fails closed before
    any row is classified or quarantined.
    """
    from ..adapters.persistence.storage.master_key.active_session import (
        active_bucket_session_serves,
        has_active_bucket_session,
    )
    from ..core.bucket_pointer import resolve_active_bucket_id

    target_bucket_id = resolve_active_bucket_id()
    reusable = (
        active_bucket_session_serves(target_bucket_id) if target_bucket_id is not None else has_active_bucket_session()
    )
    if not reusable:
        _log.debug("repair integrity found no bucket session to reuse; the substrate refusal answers")
    yield


__all__ = ["active_bucket_repair_session"]
