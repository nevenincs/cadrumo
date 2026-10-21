"""The command that starts this package's Python interpreter in a child process."""

from __future__ import annotations

import sys
from typing import Final, TypeIs

ROLE_IMAGE_OPTION: Final = "cadrumo_role_image"
"""The ``-X`` option naming the Cadrumo binary that hosts this interpreter."""

INTERPRETER_ROLE: Final = ("--role", "python")
"""The leading arguments that start the Cadrumo binary as the package interpreter."""


def _is_option_table(options: object) -> TypeIs[dict[str, object]]:
    """Whether ``options`` is the interpreter's ``-X`` table, keyed by option name."""
    return isinstance(options, dict)


def interpreter_command() -> tuple[str, ...]:
    """Return the argument prefix that starts the package interpreter as a child.

    A process the Cadrumo binary hosts is told so by the ``-X`` option the binary passes;
    its children then run that binary's interpreter role and stay in its process tree.
    Any other process starts ``sys.executable``.
    """
    options: object = getattr(sys, "_xoptions", {})
    image = options.get(ROLE_IMAGE_OPTION) if _is_option_table(options) else None
    if isinstance(image, str) and image:
        return (image, *INTERPRETER_ROLE)
    return (sys.executable,)
