"""Windows inherited-HANDLE bootstrap for explicit CLI secret channels.

Windows does not offer POSIX ``pass_fds`` semantics. A supervisor instead
allowlists one or two inheritable HANDLEs in ``STARTUPINFOEX``, then invokes
this wrapper with the root-profile HANDLE, the leaf-secret HANDLE, or both and
the ordinary ``aeat`` argument tail. The wrapper converts ownership to CRT
descriptors, injects the matching canonical options, and lets the bounded
reader close them. HANDLE values are not portable numeric descriptors.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from contextlib import suppress
from typing import NamedTuple


def descriptor_from_inherited_handle(handle: int, *, writable: bool = False) -> int:
    """Take ownership of one allowlisted inherited Windows HANDLE."""
    if sys.platform != "win32":
        raise RuntimeError("Windows profile-secret HANDLE bootstrap is only available on Windows")
    if handle <= 0:
        raise ValueError("an inherited Windows HANDLE must be a positive integer")
    import msvcrt

    access = os.O_WRONLY if writable else os.O_RDONLY
    return msvcrt.open_osfhandle(handle, access | os.O_BINARY)


class _BootstrapDescriptors(NamedTuple):
    profile: int | None
    leaf: int | None
    recovery_handoff: int | None
    recovery_verification: int | None


def _close_descriptors(descriptors: Sequence[int | None]) -> None:
    """Close every descriptor that was opened before a later conversion failed."""
    for descriptor in descriptors:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)


def _open_inherited_descriptor(handle: int | None, *, writable: bool = False) -> int | None:
    """Convert one optional allowlisted HANDLE, preserving absent channels."""
    if handle is None:
        return None
    return descriptor_from_inherited_handle(handle, writable=writable)


def _open_leaf_descriptor(
    profile_handle: int | None,
    secrets_handle: int | None,
    profile_descriptor: int | None,
) -> int | None:
    """Open the leaf channel, aliasing a HANDLE already owned at root scope."""
    if secrets_handle is None:
        return None
    if profile_handle is not None and secrets_handle == profile_handle:
        return profile_descriptor
    return descriptor_from_inherited_handle(secrets_handle)


def _open_bootstrap_descriptors(
    *,
    profile_handle: int | None,
    secrets_handle: int | None,
    recovery_handoff_handle: int | None,
    recovery_verification_handle: int | None,
) -> _BootstrapDescriptors:
    """Take ownership of requested HANDLEs and clean up on partial failure."""
    profile_descriptor: int | None = None
    leaf_descriptor: int | None = None
    recovery_handoff_descriptor: int | None = None
    recovery_verification_descriptor: int | None = None
    try:
        profile_descriptor = _open_inherited_descriptor(profile_handle)
        leaf_descriptor = _open_leaf_descriptor(profile_handle, secrets_handle, profile_descriptor)
        recovery_handoff_descriptor = _open_inherited_descriptor(recovery_handoff_handle, writable=True)
        recovery_verification_descriptor = _open_inherited_descriptor(recovery_verification_handle)
    except Exception:
        _close_descriptors(
            (
                profile_descriptor,
                leaf_descriptor,
                recovery_handoff_descriptor,
                recovery_verification_descriptor,
            ),
        )
        raise
    return _BootstrapDescriptors(
        profile=profile_descriptor,
        leaf=leaf_descriptor,
        recovery_handoff=recovery_handoff_descriptor,
        recovery_verification=recovery_verification_descriptor,
    )


def _descriptor_option(option: str, descriptor: int | None) -> tuple[str, ...]:
    """Return one canonical CLI option pair when its descriptor is present."""
    if descriptor is None:
        return ()
    return option, str(descriptor)


def bootstrap_argv(
    *,
    profile_handle: int | None,
    secrets_handle: int | None,
    recovery_handoff_handle: int | None = None,
    recovery_verification_handle: int | None = None,
    command: Sequence[str],
) -> tuple[str, ...]:
    """Map allowlisted HANDLEs and build the matching canonical invocation."""
    if all(
        handle is None
        for handle in (profile_handle, secrets_handle, recovery_handoff_handle, recovery_verification_handle)
    ):
        raise ValueError("at least one inherited secret HANDLE is required")
    descriptors = _open_bootstrap_descriptors(
        profile_handle=profile_handle,
        secrets_handle=secrets_handle,
        recovery_handoff_handle=recovery_handoff_handle,
        recovery_verification_handle=recovery_verification_handle,
    )
    root = _descriptor_option("--profile-secrets-fd", descriptors.profile)
    leaf = _descriptor_option("--secrets-fd", descriptors.leaf)
    handoff = _descriptor_option("--recovery-handoff-fd", descriptors.recovery_handoff)
    verification = _descriptor_option("--recovery-verification-fd", descriptors.recovery_verification)
    return ("aeat", *root, *command, *leaf, *handoff, *verification)


def main() -> None:
    """Convert an inherited HANDLE and dispatch the ordinary CLI once."""
    parser = argparse.ArgumentParser(prog="python -m cadrumo.entrypoints.cli._windows_profile_secret_bootstrap")
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
        parser.error("an aeat command tail is required after --")
    if all(
        handle is None
        for handle in (
            parsed.profile_handle,
            parsed.secrets_handle,
            parsed.recovery_handoff_handle,
            parsed.recovery_verification_handle,
        )
    ):
        parser.error("at least one inherited HANDLE option is required")
    argv = bootstrap_argv(
        profile_handle=parsed.profile_handle,
        secrets_handle=parsed.secrets_handle,
        recovery_handoff_handle=parsed.recovery_handoff_handle,
        recovery_verification_handle=parsed.recovery_verification_handle,
        command=command,
    )
    descriptors = list(
        dict.fromkeys(
            int(argv[argv.index(option) + 1])
            for option in (
                "--profile-secrets-fd",
                "--secrets-fd",
                "--recovery-handoff-fd",
                "--recovery-verification-fd",
            )
            if option in argv
        )
    )
    sys.argv[:] = argv
    from .._cli_main import main as cli_main

    try:
        cli_main()
    finally:
        for descriptor in descriptors:
            with suppress(OSError):
                os.close(descriptor)


if __name__ == "__main__":  # pragma: no cover - exercised as a process on Windows
    main()


__all__ = ["bootstrap_argv", "descriptor_from_inherited_handle", "main"]
