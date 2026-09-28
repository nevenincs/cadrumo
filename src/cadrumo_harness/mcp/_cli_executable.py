"""Single executable authority for harness-to-CLI process ports."""

from __future__ import annotations

import os
import shutil
import sys
import sysconfig
from pathlib import Path

from cadrumo.core.product_identity import PRODUCT_IDENTITY


def sibling_cli_executable() -> Path:
    """Return where the CLI installed beside the running interpreter lives.

    The MCP server and the CLI are console scripts of one distribution cohort,
    so the running interpreter's scripts directory holds the CLI whose command
    surface this process serves. The path is returned whether or not a file is
    there; each caller decides what an absent sibling means.
    """
    executable_name = PRODUCT_IDENTITY.cli_executable
    if sys.platform == "win32":
        executable_name = f"{executable_name}.exe"
    return (Path(sysconfig.get_path("scripts")) / executable_name).resolve()


def installed_cli_executable(*, purpose: str) -> str:
    """Resolve the explicitly bound CLI, then the sibling installation, then ``PATH``.

    An explicit ``CADRUMO_CLI_EXECUTABLE`` binding is the whole answer when it is
    set. Otherwise the CLI beside the running interpreter comes before any
    ``PATH`` lookup: an entry ahead of it on ``PATH`` may be another release or a
    development checkout, whose command surface would then answer for this
    installation's. ``PATH`` is consulted only when the environment carries no
    CLI of its own.
    """
    bound = os.environ.get("CADRUMO_CLI_EXECUTABLE")
    if bound:
        return bound
    sibling = sibling_cli_executable()
    if sibling.is_file():
        return str(sibling)
    executable = shutil.which(PRODUCT_IDENTITY.cli_executable)
    if not executable:
        raise RuntimeError(f"the installed aeat executable is required for {purpose}")
    return executable


__all__ = ["installed_cli_executable", "sibling_cli_executable"]
