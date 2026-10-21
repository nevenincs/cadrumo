"""Shared Windows HANDLE-to-descriptor mechanics for command entrypoints."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence
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


def dispatch_with_inherited_handles(
    *,
    bootstrap_module: str,
    program: str,
    tail_description: str,
    dispatch: Callable[[], None],
) -> None:
    """Parse one isolated HANDLE bootstrap invocation and dispatch its command once.

    ``bootstrap_module`` is the ``python -I -m`` module the parent launched,
    ``program`` the executable name written into the rebuilt argv, and
    ``tail_description`` names the required command tail in the usage error.
    ``dispatch`` imports and runs the executable's entrypoint; it runs inside
    the cleanup scope, so the adopted descriptors close even if that import fails.
    """
    parser = argparse.ArgumentParser(prog=f"python -I -m {bootstrap_module}")
    if not sys.flags.isolated:
        parser.error("inherited HANDLE bootstrap requires isolated Python; invoke with -I")
    parser.add_argument("--profile-handle", type=int)
    parser.add_argument("--secrets-handle", type=int)
    parser.add_argument("--recovery-handoff-handle", type=int)
    parser.add_argument("--recovery-verification-handle", type=int)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    parsed = parser.parse_args()
    command = parsed.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error(f"{tail_description} is required after --")
    handles = (
        parsed.profile_handle,
        parsed.secrets_handle,
        parsed.recovery_handoff_handle,
        parsed.recovery_verification_handle,
    )
    if all(handle is None for handle in handles):
        parser.error("at least one inherited HANDLE option is required")

    argv, descriptors = prepare_windows_secret_argv(
        program=program,
        profile_handle=parsed.profile_handle,
        secrets_handle=parsed.secrets_handle,
        recovery_handoff_handle=parsed.recovery_handoff_handle,
        recovery_verification_handle=parsed.recovery_verification_handle,
        command=command,
    )
    sys.argv[:] = argv
    try:
        dispatch()
    finally:
        close_secret_descriptors(descriptors)


__all__ = [
    "close_secret_descriptors",
    "descriptor_from_inherited_handle",
    "dispatch_with_inherited_handles",
    "prepare_windows_secret_argv",
]
