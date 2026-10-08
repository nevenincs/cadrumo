"""Observe shared sign-in without constructing a profile host or touching keychain custody."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

from ...adapters.local_runtime.installation import read_runtime_installation
from ...adapters.persistence.storage.custody.acceleration_receipt import inspect_profile_session
from ...adapters.persistence.storage.custody.acceleration_receipt_crypto import profile_session_login_matches
from ...adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from ...adapters.persistence.storage.custody.errors import ProfileCustodyRecordError
from ...adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from ...adapters.persistence.storage.errors import StorageError
from ...application.runtime.contracts import RuntimeRefusalError
from ...application.runtime.sign_in import SignInPresence, SignInStatus
from ...application.user_profile.access_contracts import OsLockState, OsLoginContext
from ...application.user_profile.automation_custody_port import AutomationCustodyError
from ...core.base64_codec import b64_encode


def observe_sign_in(
    *,
    root: Path,
    storage_identity: str,
    profile_id: UUID,
    login: OsLoginContext,
    instant: datetime,
) -> SignInStatus:
    """Read metadata twice around generation/login checks; uncertainty grants no authority."""
    try:
        receipt = inspect_profile_session(storage_root=root, profile_id=profile_id)
        if receipt is None:
            return SignInStatus(presence=SignInPresence.ABSENT)
        installation = read_runtime_installation(
            storage_root=root, os_owner_id=login.os_owner_id, storage_identity=storage_identity
        )
        binding = current_automation_profile_binding(
            root=root,
            profile_id=profile_id,
            installation_id=installation.installation_id,
            os_owner_id=login.os_owner_id,
        )
        generation = SignInGenerationCustody(root=root, binding=binding)
        observed = generation.observe()
        if observed.current is None:
            return SignInStatus(presence=SignInPresence.UNKNOWN)
        if (
            receipt.profile_id != profile_id
            or receipt.custody_generation != binding.custody_generation
            or receipt.dek_epoch != b64_encode(binding.dek_epoch.bytes)
            or receipt.sign_in != observed.current
            or not profile_session_login_matches(record=receipt, login_id=login.login_id)
            or instant >= min(receipt.idle_deadline, receipt.absolute_deadline)
            or login.lock_state is OsLockState.LOCKED
        ):
            return SignInStatus(presence=SignInPresence.ABSENT)
        if not login.active or login.lock_state is OsLockState.UNKNOWN or instant < receipt.issued_at:
            return SignInStatus(presence=SignInPresence.UNKNOWN)
        if (
            generation.observe() != observed
            or inspect_profile_session(storage_root=root, profile_id=profile_id) != receipt
        ):
            return SignInStatus(presence=SignInPresence.UNKNOWN)
        return SignInStatus(
            presence=SignInPresence.PRESENT,
            idle_deadline=receipt.idle_deadline,
            absolute_deadline=receipt.absolute_deadline,
        )
    except (OSError, ValueError, StorageError, ProfileCustodyRecordError, AutomationCustodyError, RuntimeRefusalError):
        return SignInStatus(presence=SignInPresence.UNKNOWN)
