"""Observe shared sign-in and the selection without constructing a profile host or touching keychain custody."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import inspect_profile_session
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt_crypto import profile_session_login_matches
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyRecordError
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.adapters.persistence.storage.errors import StorageError
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.application.user_profile.access_contracts import OsLockState, OsLoginContext
from cadrumo.application.workflow.errors import ProfileLabelAmbiguousError
from cadrumo.application.workflow.profile_bucket_models import ProfileBucketPointer
from cadrumo.application.workflow.profile_bucket_scan import resolve_profile_bucket
from cadrumo.core.base64_codec import b64_encode
from cadrumo.core.bucket_pointer import read_pointer_selection
from cadrumo.core.errors.hierarchy import ActiveProfilePointerError
from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.sign_in import SignInPresence, SignInStatus
from cadrumo_client.transport.installation import read_runtime_installation


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
    except (OSError, ValueError, StorageError, ProfileCustodyRecordError, AutomationCustodyError, RefusalError):
        return SignInStatus(presence=SignInPresence.UNKNOWN)


def observe_active_profile(
    *,
    root: Path,
    storage_identity: str,
    login: OsLoginContext,
    instant: datetime,
) -> tuple[UUID | None, UUID | None, SignInPresence]:
    """Return the selected profile, the signed-in profile and the sign-in's presence, granting nothing.

    One profile is signed in at a time, and the runtime selects the profile it
    signs in, so the live sign-in is read for the selected profile alone. A
    selection that cannot be read is unknown, never "nothing selected".
    """
    try:
        selected = read_pointer_selection(root).bucket_id
    except (OSError, ValueError, ActiveProfilePointerError):
        return None, None, SignInPresence.UNKNOWN
    if selected is None:
        return None, None, SignInPresence.ABSENT
    try:
        profile_id = UUID(selected)
    except ValueError:
        return None, None, SignInPresence.UNKNOWN
    status = observe_sign_in(
        root=root, storage_identity=storage_identity, profile_id=profile_id, login=login, instant=instant
    )
    signed_in = profile_id if status.presence is SignInPresence.PRESENT else None
    return profile_id, signed_in, status.presence


def resolve_login_target(*, root: Path, name: str) -> ProfileBucketPointer | None:
    """Return the live profile ``name`` names by identifier or exact label, or ``None``.

    An ambiguous label names no profile: the operator names it by its identifier.
    The request's connection thread inherits no composition, so the profile
    persistence it reads is bound for the length of the read.
    """
    with composed_profile_persistence_ports():
        try:
            return resolve_profile_bucket(name.strip(), root=root)
        except ProfileLabelAmbiguousError:
            return None
