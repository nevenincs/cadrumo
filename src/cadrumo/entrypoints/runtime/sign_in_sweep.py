"""Runtime-owned revocation of saved sign-ins without constructing profile workers."""

from __future__ import annotations

import os
from contextlib import ExitStack
from pathlib import Path
from uuid import UUID

from ...adapters.persistence.storage.bucket.keystore_paths import keystore_root
from ...adapters.persistence.storage.custody.acceleration_receipt import inspect_profile_session, revoke_profile_sign_in
from ...adapters.persistence.storage.custody.acceleration_receipt_crypto import profile_session_login_matches
from ...adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from ...adapters.persistence.storage.custody.errors import ProfileCustodyLockContendedError
from ...adapters.persistence.storage.custody.filesystem import profile_custody_root_lock
from ...adapters.persistence.storage.custody.filesystem_primitives import anchor_directory
from ...adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from ...application.runtime.installation import RuntimeInstallation
from ...application.user_profile.access_contracts import LoginEligibility, OsLockState, OsLoginContext
from ...application.user_profile.automation_custody_port import AutomationCustodyError
from ...core.base64_codec import b64_encode


def sweep_saved_sign_ins(
    *,
    root: Path,
    installation: RuntimeInstallation,
    logins: tuple[OsLoginContext, ...],
    inventory_complete: bool,
    hosted_profiles: frozenset[UUID] = frozenset(),
) -> tuple[UUID, ...]:
    """Revoke only positively locked/absent bound logins, under the mint's root lock.

    An observed but uncertain bound login wins over inventory absence. Positive
    custody replacement independently fences obsolete receipts, even if OS
    observation is unknown. A complete
    inventory is required to infer logout when no bound incarnation is present.
    Hosted profiles are normally handled by their admission guard; shutdown may
    include them here to persist the fence before workers are drained.
    """
    directory = keystore_root(root)
    if not os.path.lexists(directory):
        return ()
    retired: list[UUID] = []
    with ExitStack() as anchors:
        try:
            anchors.enter_context(profile_custody_root_lock(root, timeout_seconds=0.05))
        except ProfileCustodyLockContendedError:
            # The accept-loop sweep must not block IPC or kill an active login
            # while another custody transaction owns the root. Retry next poll;
            # no receipt was read or revoked and admission guards still apply.
            return ()
        anchor_directory(anchors, directory)
        for entry in directory.iterdir():
            try:
                profile_id = UUID(entry.name)
            except ValueError:
                continue
            if str(profile_id) != entry.name or profile_id in hosted_profiles:
                continue
            with ExitStack() as profile_anchor:
                anchor_directory(profile_anchor, entry)
                receipt = inspect_profile_session(storage_root=root, profile_id=profile_id)
                if receipt is None:
                    continue
                try:
                    binding = current_automation_profile_binding(
                        root=root,
                        profile_id=profile_id,
                        installation_id=installation.installation_id,
                        os_owner_id=installation.os_owner_id,
                    )
                except AutomationCustodyError:
                    # Missing/unreadable custody is not positive replacement
                    # evidence and cannot authorize deletion of its receipt.
                    continue
                custody_changed = (
                    receipt.custody_generation != binding.custody_generation
                    or receipt.dek_epoch != b64_encode(binding.dek_epoch.bytes)
                )
                matching = tuple(
                    login
                    for login in logins
                    if login.os_owner_id == installation.os_owner_id
                    and profile_session_login_matches(record=receipt, login_id=login.login_id)
                )
                positive = any(
                    login.lock_state is OsLockState.LOCKED
                    or (not login.active and login.unattended is LoginEligibility.INELIGIBLE)
                    for login in matching
                )
                if not custody_changed and not positive and (matching or not inventory_complete):
                    continue
                revoke_profile_sign_in(SignInGenerationCustody(root=root, binding=binding))
                retired.append(profile_id)
    return tuple(retired)
