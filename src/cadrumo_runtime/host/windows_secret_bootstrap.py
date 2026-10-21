"""Isolated Windows HANDLE dispatcher for the runtime command entrypoint."""

from __future__ import annotations

from cadrumo_client.commands.windows_secret_channels import dispatch_with_inherited_handles


def _run_runtime() -> None:
    from .bootstrap import main as runtime_main

    runtime_main()


def main() -> None:
    """Adopt allowlisted HANDLEs and dispatch the runtime command once."""
    dispatch_with_inherited_handles(
        bootstrap_module="cadrumo_runtime.host.windows_secret_bootstrap",
        program="cadrumo-runtime",
        tail_description="a runtime command tail",
        dispatch=_run_runtime,
    )


if __name__ == "__main__":  # pragma: no cover - exercised as a process on Windows
    main()


__all__ = ["main"]
