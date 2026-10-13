"""Leveled, attributed console output for the helpers CMake runs during a build.

Every line starts with ``[cadrumo:<step>]`` so output from parallel build steps
stays attributable, and levels use CMake's own message vocabulary. The build
selects its level with ``CADRUMO_BUILD_LOG_LEVEL``; a non-empty ``VERBOSE``,
which ``make`` and CMake's verbose builds already honour, raises it to at least
``VERBOSE``. ``STATUS`` is the default: what each step does, whether it reuses
or rebuilds and why, and where its output lands. ``VERBOSE`` adds phase timings
and per-step detail; ``DEBUG`` adds the commands and fingerprints behind them.

Status and detail go to standard output and warnings and errors to standard
error, as CMake does. Every line is flushed so that it keeps its place among the
output of the commands a helper runs.
"""

from __future__ import annotations

import os
import shlex
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from dev._paths import REPO_ROOT

LEVEL_VARIABLE = "CADRUMO_BUILD_LOG_LEVEL"
LEVELS = ("ERROR", "WARNING", "NOTICE", "STATUS", "VERBOSE", "DEBUG", "TRACE")
DEFAULT_LEVEL = "STATUS"


def selected_level(environment: Mapping[str, str] | None = None) -> str:
    """Return the build's log level, refusing a name CMake does not define."""
    environment = os.environ if environment is None else environment
    requested = environment.get(LEVEL_VARIABLE, "").strip().upper()
    if requested and requested not in LEVELS:
        raise ValueError(f"{LEVEL_VARIABLE} must be one of {', '.join(LEVELS)}, not {requested!r}")
    level = requested or DEFAULT_LEVEL
    if bool(environment.get("VERBOSE")) and LEVELS.index(level) < LEVELS.index("VERBOSE"):
        level = "VERBOSE"
    return level


def display_path(path: Path | str) -> str:
    """Name a path as CMake's summary does: checkout-relative when inside it, with forward slashes."""
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return candidate.as_posix()


def command_line(argv: Sequence[str]) -> str:
    """Render an argv for reading, quoting only the arguments that need it."""
    return " ".join(shlex.quote(argument) for argument in argv)


class BuildLog:
    """One build step's console output, filtered by the selected level."""

    def __init__(self, step: str, *, level: str | None = None) -> None:
        """Attribute every line to ``step`` and read the level once."""
        self.step = step
        self.level = selected_level() if level is None else level
        if self.level not in LEVELS:
            raise ValueError(f"Unknown build log level: {self.level!r}")

    def enabled(self, level: str) -> bool:
        """Whether a message at ``level`` is printed."""
        return LEVELS.index(level) <= LEVELS.index(self.level)

    def error(self, message: str) -> None:
        """Report why the step failed."""
        self._emit("ERROR", message, sys.stderr, "error: ")

    def warning(self, message: str) -> None:
        """Report something the step tolerated but the operator should act on."""
        self._emit("WARNING", message, sys.stderr, "warning: ")

    def notice(self, message: str) -> None:
        """Report diagnostic context, such as the tail of a failed command's log."""
        self._emit("NOTICE", message, sys.stderr)

    def status(self, message: str) -> None:
        """Report what the step does, decides and produces."""
        self._emit("STATUS", message, sys.stdout)

    def verbose(self, message: str) -> None:
        """Report detail an operator reads when a step behaves unexpectedly."""
        self._emit("VERBOSE", message, sys.stdout)

    def debug(self, message: str) -> None:
        """Report the commands and identities behind a step's decisions."""
        self._emit("DEBUG", message, sys.stdout)

    def _emit(self, level: str, message: str, stream: TextIO, label: str = "") -> None:
        if not self.enabled(level):
            return
        prefix = f"[cadrumo:{self.step}] {label}"
        for line in message.splitlines() or [""]:
            print(prefix + line, file=stream, flush=True)
