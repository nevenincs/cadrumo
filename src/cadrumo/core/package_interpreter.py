"""The command that starts this package's Python interpreter in a child process."""

from __future__ import annotations

import sys
from pathlib import Path
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


def isolated_interpreter_command() -> tuple[str, ...]:
    """Return the argument prefix that starts a contained helper child of this interpreter.

    On Windows the child receives its import roots through PYTHONPATH, so it runs the
    base CPython directly and without ``site``: a virtual environment's ``python.exe``
    is a launcher that starts the base interpreter as a second process, and the
    site-packages ``.pth`` hooks import modules the child never uses. Both are pure
    start-up cost on every launch. Elsewhere the interpreter itself resolves the
    environment, so it is kept as is. A process the Cadrumo binary hosts starts the
    binary's interpreter role, also without ``site``.
    """
    command = interpreter_command()
    if len(command) > 1:
        return (*command, "-S")
    if sys.platform != "win32":
        return command
    base = getattr(sys, "_base_executable", None)
    executable = base if isinstance(base, str) and base and Path(base).is_file() else sys.executable
    return (executable, "-S")
