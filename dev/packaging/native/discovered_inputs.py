"""Record repository files read by a discovery-enabled cached producer."""

from __future__ import annotations

import atexit
import json
import os
import sys
from pathlib import Path
from typing import Final, cast
from urllib.parse import unquote

from dev._paths import REPO_ROOT

from ..google_oauth import GOOGLE_OAUTH_RESOURCE

DISCOVERED_INPUTS_VARIABLE: Final = "CADRUMO_DISCOVERED_INPUTS"
"""Names the file a discovering producer writes the repository files it imported or read into."""
_UNDISCOVERED_ROOTS: Final = ("build", ".venv", ".tmp", "node_modules", "env")
#: Private build settings a producer may read; the actions that depend on them key them by
#: a salted identity, so a receipt never records their digest.
_PRIVATE_INPUTS: Final = (GOOGLE_OAUTH_RESOURCE,)
_WRITE_FLAGS: Final = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


def record_discovered_inputs(root: Path = REPO_ROOT) -> None:
    """Record every checkout file this producer process imports or reads, for its cached action.

    A producer's real inputs are the modules it executes and the files they
    read, which a hand-written list cannot keep up with: a projection that
    imports one locale module may transitively execute a thousand. Called
    first in a producer that a ``DISCOVER`` action runs, this writes those
    files when the process exits, and the action keys its next decision on
    them as well as on its declared inputs. Outside such an action it does
    nothing.

    Args:
        root: The checkout whose files are recorded; files outside it, and its
            build, environment, scratch and dependency trees, are not inputs.
    """
    target = os.environ.get(DISCOVERED_INPUTS_VARIABLE)
    if target is None or target == "":
        return
    opened: set[str] = set()

    def audit(event: str, arguments: tuple[object, ...]) -> None:
        path = _audited_read_path(event, arguments)
        if path is not None:
            opened.add(path)

    sys.addaudithook(audit)
    atexit.register(_write_discovered_inputs, Path(target), root.resolve(), opened)


def _is_read_open(mode: object, flags: object) -> bool:
    if isinstance(mode, str):
        return not any(letter in mode for letter in "wax+")
    return not (isinstance(flags, int) and flags & _WRITE_FLAGS)


def _audited_read_path(event: str, arguments: tuple[object, ...]) -> str | None:
    """Identify a read-only file or SQLite connection from a Python audit event."""
    if event == "open":
        path, mode, flags = arguments[0], arguments[1], arguments[2]
        if not _is_read_open(mode, flags):
            return None
    elif event == "sqlite3.connect":
        path = arguments[0]
        if isinstance(path, str) and path.startswith("file:"):
            path = unquote(path.removeprefix("file:").partition("?")[0])
    else:
        return None
    if not isinstance(path, (str, bytes, os.PathLike)):
        return None
    return os.path.abspath(os.fsdecode(cast("str | bytes | os.PathLike[str]", path)))


def _write_discovered_inputs(target: Path, root: Path, opened: set[str]) -> None:
    files = set(opened)
    files.update(
        os.path.abspath(module_file)
        for module in list(sys.modules.values())
        if isinstance(module_file := getattr(module, "__file__", None), str)
    )
    excluded = tuple(root / name for name in _UNDISCOVERED_ROOTS)
    private = {root / name for name in _PRIVATE_INPUTS}
    discovered = {path.as_posix() for name in files if _is_discoverable(path := Path(name), root, excluded, private)}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(sorted(discovered)), encoding="utf-8")


def _is_discoverable(path: Path, root: Path, excluded: tuple[Path, ...], private: set[Path]) -> bool:
    """Admit only existing checkout files outside build, private and cache paths."""
    return (
        "__pycache__" not in path.parts
        and path.is_relative_to(root)
        and path.is_file()
        and path not in private
        and not any(path.is_relative_to(directory) for directory in excluded)
    )
