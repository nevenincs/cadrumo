"""Module execution for the independent full-screen root."""

from __future__ import annotations

from .launcher import TUI_MODULE_ARGUMENT_ERROR_EXIT_CODE, TuiModuleArgumentError, run_module

if __name__ == "__main__":
    import sys

    try:
        raise SystemExit(run_module(sys.argv[1:]))
    except TuiModuleArgumentError as exc:
        sys.stderr.write(f"error: {exc}\n")
        raise SystemExit(TUI_MODULE_ARGUMENT_ERROR_EXIT_CODE) from None
