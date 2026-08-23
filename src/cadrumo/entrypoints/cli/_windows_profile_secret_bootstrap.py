"""Windows inherited-HANDLE bootstrap for root profile authentication.

Windows does not offer POSIX ``pass_fds`` semantics. A supervisor instead
allowlists one inheritable HANDLE in ``STARTUPINFOEX``, then invokes this
wrapper with that HANDLE and the ordinary ``aeat`` argument tail. The wrapper
converts ownership to one CRT descriptor, injects ``--profile-secrets-fd``, and
lets the canonical bounded reader close it. The HANDLE carries the secret; its
numeric value does not.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence


def descriptor_from_inherited_handle(handle: int) -> int:
    """Take ownership of one allowlisted inherited Windows HANDLE."""
    if sys.platform != "win32":
        raise RuntimeError("Windows profile-secret HANDLE bootstrap is only available on Windows")
    if handle <= 0:
        raise ValueError("an inherited Windows HANDLE must be a positive integer")
    import msvcrt

    return msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)


def bootstrap_argv(*, handle: int, command: Sequence[str]) -> tuple[str, ...]:
    """Map ``handle`` and build the canonical root-option invocation."""
    descriptor = descriptor_from_inherited_handle(handle)
    return ("aeat", "--profile-secrets-fd", str(descriptor), *command)


def main() -> None:
    """Convert an inherited HANDLE and dispatch the ordinary CLI once."""
    parser = argparse.ArgumentParser(
        prog="python -m cadrumo.entrypoints.cli._windows_profile_secret_bootstrap"
    )
    parser.add_argument("--handle", type=int, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    parsed = parser.parse_args()
    command = parsed.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("an aeat command tail is required after --")
    sys.argv[:] = bootstrap_argv(handle=parsed.handle, command=command)
    from .._cli_main import main as cli_main

    cli_main()


if __name__ == "__main__":  # pragma: no cover - exercised as a process on Windows
    main()


__all__ = ["bootstrap_argv", "descriptor_from_inherited_handle", "main"]
