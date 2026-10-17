"""The command that starts this package's Python interpreter in a child process."""

from __future__ import annotations

import sys
from typing import Final

ROLE_IMAGE_OPTION: Final = "cadrumo_role_image"
"""The ``-X`` option naming the Cadrumo binary that hosts this interpreter."""

INTERPRETER_ROLE: Final = ("--role", "python")
"""The leading arguments that start the Cadrumo binary as the package interpreter."""


def interpreter_command() -> tuple[str, ...]:
    """Return the argument prefix that starts the package interpreter as a child.

    A process the Cadrumo binary hosts is told so by the ``-X`` option the binary passes;
    its children then run that binary's interpreter role and stay in its process tree.
    Any other process starts ``sys.executable``.
    """
    options = getattr(sys, "_xoptions", {})
    image = options.get(ROLE_IMAGE_OPTION) if isinstance(options, dict) else None
    if isinstance(image, str) and image:
        return (image, *INTERPRETER_ROLE)
    return (sys.executable,)
