"""Single executable authority for harness-to-CLI process ports."""

from __future__ import annotations

import os
import shutil


def installed_cli_executable(*, purpose: str) -> str:
    """Resolve the explicitly bound CLI first, then an ambient installation."""
    executable = os.environ.get("CADRUMO_CLI_EXECUTABLE") or shutil.which("aeat")
    if not executable:
        raise RuntimeError(f"the installed aeat executable is required for {purpose}")
    return executable


__all__ = ["installed_cli_executable"]
