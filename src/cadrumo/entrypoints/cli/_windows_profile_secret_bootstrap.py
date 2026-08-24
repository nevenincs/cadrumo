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
from pathlib import Path


def bootstrap_interpreter() -> str:
    """Return the real CPython executable that must inherit allowlisted HANDLEs.

    A virtual-environment ``python.exe`` may be a launcher which creates a
    second process without forwarding ``STARTUPINFOEX.handle_list``.  Windows
    supervisors must therefore start the base interpreter directly.
    """
    candidate = getattr(sys, "_base_executable", None)
    if not isinstance(candidate, str) or not candidate:
        raise RuntimeError("the base CPython executable is unavailable")
    resolved = Path(candidate).resolve(strict=True)
    if resolved.name.lower() not in {"python.exe", "pythonw.exe"}:
        raise RuntimeError("the base CPython executable is invalid")
    return str(resolved)


def descriptor_from_inherited_handle(handle: int, *, writable: bool = False) -> int:
    """Take ownership of one allowlisted inherited Windows HANDLE."""
    if sys.platform != "win32":
        raise RuntimeError("Windows profile-secret HANDLE bootstrap is only available on Windows")
    if handle <= 0:
        raise ValueError("an inherited Windows HANDLE must be a positive integer")
    import msvcrt

    access = os.O_WRONLY if writable else os.O_RDONLY
    return msvcrt.open_osfhandle(handle, access | os.O_BINARY)


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
    profile_descriptor: int | None = None
    leaf_descriptor: int | None = None
    recovery_handoff_descriptor: int | None = None
    recovery_verification_descriptor: int | None = None
    try:
        if profile_handle is not None:
            profile_descriptor = descriptor_from_inherited_handle(profile_handle)
        if secrets_handle is not None:
            # One HANDLE named at both scopes represents one selected backing
            # channel. Convert it exactly once so parsed dispatch sees the same
            # CRT descriptor number and can refuse the cross-scope collision
            # before either scope reads it. Opening ownership over the same
            # HANDLE twice produces two descriptor numbers and is also an
            # invalid double-ownership relationship.
            leaf_descriptor = (
                profile_descriptor
                if profile_handle is not None and secrets_handle == profile_handle
                else descriptor_from_inherited_handle(secrets_handle)
            )
        if recovery_handoff_handle is not None:
            recovery_handoff_descriptor = descriptor_from_inherited_handle(recovery_handoff_handle, writable=True)
        if recovery_verification_handle is not None:
            recovery_verification_descriptor = descriptor_from_inherited_handle(recovery_verification_handle)
    except Exception:
        for descriptor in (
            profile_descriptor,
            leaf_descriptor,
            recovery_handoff_descriptor,
            recovery_verification_descriptor,
        ):
            if descriptor is not None:
                with suppress(OSError):
                    os.close(descriptor)
        raise

    root = () if profile_descriptor is None else ("--profile-secrets-fd", str(profile_descriptor))
    leaf = () if leaf_descriptor is None else ("--secrets-fd", str(leaf_descriptor))
    handoff = (
        ()
        if recovery_handoff_descriptor is None
        else ("--recovery-handoff-fd", str(recovery_handoff_descriptor))
    )
    verification = (
        ()
        if recovery_verification_descriptor is None
        else ("--recovery-verification-fd", str(recovery_verification_descriptor))
    )
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


__all__ = ["bootstrap_argv", "bootstrap_interpreter", "descriptor_from_inherited_handle", "main"]
