"""Find and delete the stored sign-in keys a disposable root's profile leaves in the account's credential store.

A profile that signs in with a stored sign-in leaves generic credentials keyed by its opaque id; the run removes
exactly those so none outlives the root.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Final
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.acceleration_keychain import PROFILE_SESSION_KEYCHAIN_SERVICE

_GENERIC_CREDENTIAL: Final = 1
_NO_CREDENTIALS: Final = 1168


def profile_credentials(stored: Iterable[Mapping[str, Any]], profile_id: UUID) -> list[str]:
    """Target names of the generic credentials holding exactly this profile's stored sign-in keys."""
    prefix = f"{profile_id}:"
    service = PROFILE_SESSION_KEYCHAIN_SERVICE
    return sorted(
        credential["TargetName"]
        for credential in stored
        if credential.get("Type") == _GENERIC_CREDENTIAL
        and (account := credential.get("UserName") or "").startswith(prefix)
        and credential.get("TargetName") in {service, f"{account}@{service}"}
    )


def remove_profile_credentials(
    profile_id: UUID,
    enumerate_stored: Callable[[], Iterable[Mapping[str, Any]]],
    delete: Callable[[str], None],
) -> list[str]:
    """Delete this profile's stored sign-in keys; return a failure for each one that stays."""
    failures = []
    targets = profile_credentials(enumerate_stored(), profile_id)
    for target in targets:
        try:
            delete(target)
        except OSError as error:
            failures.append(f"a stored sign-in key of profile {profile_id} was not deleted: {error}")
    print(json.dumps({"step": "credentials_removed", "count": len(targets) - len(failures)}), flush=True)
    return failures


def windows_credentials() -> list[Mapping[str, Any]]:
    """Every credential in the account's Windows credential store; none when the store holds none."""
    import pywintypes
    import win32cred

    try:
        return list(win32cred.CredEnumerate(None, 0) or [])
    except pywintypes.error as error:
        if error.winerror == _NO_CREDENTIALS:
            return []
        raise OSError(error.winerror, error.strerror) from error


def delete_windows_credential(target: str) -> None:
    """Delete one generic credential from the account's Windows credential store."""
    import pywintypes
    import win32cred

    try:
        win32cred.CredDelete(target, _GENERIC_CREDENTIAL, 0)
    except pywintypes.error as error:
        raise OSError(error.winerror, error.strerror) from error
