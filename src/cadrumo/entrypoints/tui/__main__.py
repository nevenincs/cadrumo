"""Module execution for the independent full-screen root."""

from __future__ import annotations

if __name__ == "__main__":
    import os
    import sys

    # Before the first import that builds a pydantic model: pydantic otherwise
    # scans every installed distribution's entry points on that build, which
    # costs about a tenth of a second per process. Cadrumo declares no pydantic
    # plugin, and a third-party one would observe taxpayer models it has no
    # business seeing. ``setdefault`` leaves an operator's explicit value alone.
    os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "__all__")

    from ...adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
    from ...application.runtime.contracts import RuntimeRefusalError
    from ...core.async_cleanup import AsyncResourceCleanupError
    from .launcher import TUI_MODULE_ARGUMENT_ERROR_EXIT_CODE, TuiModuleArgumentError, run_module

    try:
        raise SystemExit(run_module(sys.argv[1:]))
    except TuiModuleArgumentError as exc:
        sys.stderr.write(f"error: {exc}\n")
        raise SystemExit(TUI_MODULE_ARGUMENT_ERROR_EXIT_CODE) from None
    except (RuntimeFrontendRefusedError, RuntimeRefusalError, AsyncResourceCleanupError) as exc:
        if not isinstance(exc, AsyncResourceCleanupError) and not any(
            isinstance(exc.__dict__.get(name), AsyncResourceCleanupError)
            for name in ("async_cleanup_error", "cleanup_error")
        ):
            raise
        from .installed_session import SESSION_INVENTORY_UNAVAILABLE

        # Library callers retain the original failure and cleanup owner. At
        # process exit, emit only a fixed code rather than native error chains.
        sys.stderr.write("runtime_cleanup_incomplete\n")
        raise SystemExit(SESSION_INVENTORY_UNAVAILABLE) from None
