"""Sweep saved sign-ins using a validated installation and observed logins."""

from __future__ import annotations

from _thread import RLock
from pathlib import Path
from uuid import UUID

from cadrumo.application.user_profile.access_contracts import OsLoginContext
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.installation import Installation
from cadrumo_client.transport.installation import read_runtime_installation

from .profile_host import RuntimeProfileHost
from .sign_in_sweep import sweep_saved_sign_ins


def sweep_observed_sign_ins(
    logins: tuple[OsLoginContext, ...],
    *,
    complete: bool,
    include_hosted: bool,
    os_owner_id: str | None,
    current_installation: Installation | None,
    root: Path,
    storage_identity: str,
    guard: RLock,
    profiles: dict[UUID, RuntimeProfileHost],
) -> None:
    """Retain the installation validation and hosted-profile fence order."""
    owner = os_owner_id
    if owner is None and current_installation is not None:
        owner = current_installation.os_owner_id
    if owner is None:
        return
    try:
        installation = read_runtime_installation(
            storage_root=root, os_owner_id=owner, storage_identity=storage_identity
        )
    except RefusalError:
        # No validated installation means no saved receipt can be attributed.
        return
    with guard:
        hosted: frozenset[UUID] = frozenset[UUID]() if include_hosted else frozenset(profiles)
    sweep_saved_sign_ins(
        root=root,
        installation=installation,
        logins=logins,
        inventory_complete=complete,
        hosted_profiles=hosted,
    )
