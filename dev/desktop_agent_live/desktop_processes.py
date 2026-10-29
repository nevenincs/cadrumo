"""Find and isolate the person's desktop and its installed storage."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import psutil

from .lane_errors import UnavailableError

_TESTING: Final = Path(__file__).resolve().parents[2] / "build" / "windows-x64" / "desktop" / "testing"
_CLOSE_SECONDS: Final = 60.0
_AMBIENT_EXCLUDED: Final = ("CADRUMO_", "PYTHON", "VIRTUAL_ENV", "UV_", "WEBVIEW2_")


@dataclass(frozen=True, slots=True)
class Desktop:
    """One Cadrumo desktop process running for this account."""

    pid: int
    executable: Path | None
    test_build: bool
    orphaned: bool


def person_storage_root() -> Path:
    """The per-user storage root the installed desktop uses, as the canonical environment definition names it."""
    from cadrumo.core.storage_environment import host_installed_default_root

    try:
        root = host_installed_default_root(os.environ)
    except (OSError, ValueError) as refused:
        raise UnavailableError(f"this account has no installed storage root: {refused}") from refused
    if not root.is_dir():
        raise UnavailableError(f"no Cadrumo profile is stored at {root}; create one in the desktop first")
    return root


def person_environment(root: Path, package: Path) -> dict[str, str]:
    """The ambient environment without this checkout's settings, on the person's root and the run's package.

    No secret store is pinned: the desktop reads the sign-in it resumes from
    the account's own credential store, as the installed desktop does.
    """
    environment = {name: value for name, value in os.environ.items() if not name.upper().startswith(_AMBIENT_EXCLUDED)}
    environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root)
    environment["CADRUMO_DESKTOP_PACKAGE_ROOT"] = str(package)
    return environment


def _under(path: Path, directory: Path) -> bool:
    return os.path.normcase(str(path)).startswith(os.path.normcase(str(directory)) + os.sep)


def classify_desktops(processes: Iterable[Mapping[str, Any]], testing: Path) -> list[Desktop]:
    """The desktop processes among ``processes``, each with whether it is a test build and its lane is gone.

    A ``cadrumo.exe`` that runs a ``--role`` is one of the package's own
    commands, not a desktop. A process whose image cannot be read is taken for
    the person's own.
    """
    found: list[Desktop] = []
    for process in processes:
        if str(process.get("name") or "").lower() != "cadrumo.exe":
            continue
        if "--role" in (process.get("cmdline") or ()):
            continue
        image = process.get("exe")
        executable = Path(image) if image else None
        test_build = executable is not None and _under(executable, testing)
        found.append(Desktop(int(process["pid"]), executable, test_build, not process.get("parent_alive", True)))
    return found


def _desktop_processes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for process in psutil.process_iter(["pid", "name", "exe", "cmdline", "ppid", "create_time"]):
        info = dict(process.info)
        try:
            parent = psutil.Process(int(info["ppid"])) if info.get("ppid") else None
            info["parent_alive"] = parent is not None and parent.create_time() <= float(info["create_time"] or 0)
        except psutil.Error:
            info["parent_alive"] = False
        rows.append(info)
    return rows


def require_no_desktop() -> None:
    """Refuse while the person's desktop runs, and stop a test-build desktop whose lane is gone.

    The desktop is one instance per account, so the run's own would only hand
    its window to the one already open.
    """
    for desktop in classify_desktops(_desktop_processes(), _TESTING):
        if not desktop.test_build:
            raise UnavailableError(
                f"the Cadrumo desktop is open (process {desktop.pid}); close it, then run the lane again"
            )
        if not desktop.orphaned:
            raise UnavailableError(
                f"another run's test desktop is open (process {desktop.pid}, {desktop.executable}); let it end first"
            )
        with suppress(psutil.NoSuchProcess):
            process = psutil.Process(desktop.pid)
            tree = [*process.children(recursive=True), process]
            for member in tree:
                with suppress(psutil.NoSuchProcess):
                    member.kill()
            _gone, alive = psutil.wait_procs(tree, timeout=_CLOSE_SECONDS)
            if alive:
                raise UnavailableError(f"a leftover test desktop (process {desktop.pid}) did not end")
            print(json.dumps({"step": "leftover_test_desktop_stopped", "pid": desktop.pid}), flush=True)
