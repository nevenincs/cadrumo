"""Isolated Windows HANDLE dispatcher for the public ``aeat`` CLI."""

from __future__ import annotations

from cadrumo_client.commands.windows_secret_channels import dispatch_with_inherited_handles


def _run_aeat() -> None:
    from .bootstrap import main as aeat_main

    aeat_main()


def main() -> None:
    """Adopt allowlisted HANDLEs and dispatch AEAT once in this process."""
    dispatch_with_inherited_handles(
        bootstrap_module="cadrumo_runtime.host.frontend.cli.windows_secret_bootstrap",
        program="aeat",
        tail_description="an aeat command tail",
        dispatch=_run_aeat,
    )


if __name__ == "__main__":  # pragma: no cover - exercised as a process on Windows
    main()


__all__ = ["main"]
