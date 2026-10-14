"""Shared Windows HANDLE-to-descriptor mechanics for command entrypoints."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from contextlib import suppress
from typing import NamedTuple


class _OpenedDescriptors(NamedTuple):
    profile: int | None
    leaf: int | None
    recovery_handoff: int | None
    recovery_verification: int | None


def descriptor_from_inherited_handle(handle: int, *, writable: bool = False) -> int:
    """Take ownership of one allowlisted inherited Windows HANDLE."""
    if sys.platform != "win32":
        raise RuntimeError("Windows secret HANDLE bootstrap is only available on Windows")
    if handle <= 0:
        raise ValueError("an inherited Windows HANDLE must be a positive integer")
    import msvcrt

    access = os.O_WRONLY if writable else os.O_RDONLY
    return msvcrt.open_osfhandle(handle, access | os.O_BINARY)


def close_secret_descriptors(descriptors: Sequence[int]) -> None:
    """Close each owned descriptor once, tolerating prior bounded-reader closure."""
    for descriptor in dict.fromkeys(descriptors):
        with suppress(OSError):
            os.close(descriptor)


def _close_partial(descriptors: Sequence[int | None]) -> None:
    close_secret_descriptors(tuple(descriptor for descriptor in descriptors if descriptor is not None))


def _open_descriptors(
    *,
    profile_handle: int | None,
    secrets_handle: int | None,
    recovery_handoff_handle: int | None,
    recovery_verification_handle: int | None,
) -> _OpenedDescriptors:
    profile: int | None = None
    leaf: int | None = None
    handoff: int | None = None
    verification: int | None = None
    try:
        if profile_handle is not None:
            profile = descriptor_from_inherited_handle(profile_handle)
        if secrets_handle is not None:
            if profile_handle is not None and secrets_handle == profile_handle:
                leaf = profile
            else:
                leaf = descriptor_from_inherited_handle(secrets_handle)
        if recovery_handoff_handle is not None:
            handoff = descriptor_from_inherited_handle(recovery_handoff_handle, writable=True)
        if recovery_verification_handle is not None:
            verification = descriptor_from_inherited_handle(recovery_verification_handle)
    except Exception:
        _close_partial((profile, leaf, handoff, verification))
        raise
    return _OpenedDescriptors(profile, leaf, handoff, verification)


def _option_pair(option: str, descriptor: int | None) -> tuple[str, ...]:
    if descriptor is None:
        return ()
    return option, str(descriptor)


def prepare_windows_secret_argv(
    *,
    program: str,
    command: Sequence[str],
    profile_handle: int | None = None,
    secrets_handle: int | None = None,
    recovery_handoff_handle: int | None = None,
    recovery_verification_handle: int | None = None,
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    """Adopt allowlisted HANDLEs and prepare one executable's canonical argv."""
    if not program:
        raise ValueError("a command program name is required")
    handles = (profile_handle, secrets_handle, recovery_handoff_handle, recovery_verification_handle)
    if all(handle is None for handle in handles):
        raise ValueError("at least one inherited secret HANDLE is required")

    opened = _open_descriptors(
        profile_handle=profile_handle,
        secrets_handle=secrets_handle,
        recovery_handoff_handle=recovery_handoff_handle,
        recovery_verification_handle=recovery_verification_handle,
    )
    argv = (
        program,
        *_option_pair("--profile-secrets-fd", opened.profile),
        *command,
        *_option_pair("--secrets-fd", opened.leaf),
        *_option_pair("--recovery-handoff-fd", opened.recovery_handoff),
        *_option_pair("--recovery-verification-fd", opened.recovery_verification),
    )
    descriptors = tuple(dict.fromkeys(value for value in opened if value is not None))
    return argv, descriptors


__all__ = [
    "close_secret_descriptors",
    "descriptor_from_inherited_handle",
    "prepare_windows_secret_argv",
]
