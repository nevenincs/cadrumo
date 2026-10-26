"""Synthetic runtime composition over proof-only borrowing and supplied-key verification.

This fixture substitutes the verified login identity, not the production receipt
reader. It never falls back to an in-process keyring-to-DEK reader.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

from ..acceleration_receipt import (
    ProfileSessionResumeOutcome,
    borrow_profile_session_key,
    resume_profile_session_with_key,
)
from .receipt_sign_in import RECEIPT_LOGIN_ID, committed_sign_in


def resume_receipt_as_runtime(
    *,
    storage_root: Path,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    now: datetime,
) -> tuple[ProfileSessionResumeOutcome, bytearray | None]:
    """Borrow proof and have the runtime reader validate the synthetic connection."""
    observed, proof = borrow_profile_session_key(storage_root=storage_root, profile_id=profile_id)
    if not observed.resumed or proof is None:
        return observed, None
    try:
        return resume_profile_session_with_key(
            storage_root=storage_root,
            profile_id=profile_id,
            custody_generation=custody_generation,
            dek_epoch=dek_epoch,
            now=now,
            receipt_key=proof,
            login_id=RECEIPT_LOGIN_ID,
            sign_in=committed_sign_in(storage_root, profile_id),
        )
    finally:
        proof[:] = bytes(len(proof))
