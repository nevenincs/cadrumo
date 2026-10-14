"""Isolated Windows HANDLE dispatcher for the runtime command entrypoint."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    """Adopt allowlisted HANDLEs and dispatch the runtime command once."""
    parser = argparse.ArgumentParser(prog="python -I -m cadrumo_runtime.host.windows_secret_bootstrap")
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
        parser.error("a runtime command tail is required after --")
    handles = (
        parsed.profile_handle,
        parsed.secrets_handle,
        parsed.recovery_handoff_handle,
        parsed.recovery_verification_handle,
    )
    if all(handle is None for handle in handles):
        parser.error("at least one inherited HANDLE option is required")

    from cadrumo_client.commands.windows_secret_channels import (
        close_secret_descriptors,
        prepare_windows_secret_argv,
    )

    argv, descriptors = prepare_windows_secret_argv(
        program="cadrumo-runtime",
        profile_handle=parsed.profile_handle,
        secrets_handle=parsed.secrets_handle,
        recovery_handoff_handle=parsed.recovery_handoff_handle,
        recovery_verification_handle=parsed.recovery_verification_handle,
        command=command,
    )
    sys.argv[:] = argv
    from cadrumo_runtime.host.bootstrap import main as runtime_main

    try:
        runtime_main()
    finally:
        close_secret_descriptors(descriptors)


if __name__ == "__main__":  # pragma: no cover - exercised as a process on Windows
    main()


__all__ = ["main"]
