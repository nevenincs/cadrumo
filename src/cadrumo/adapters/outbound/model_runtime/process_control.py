"""Operating-system process control for starting and installing the model runtime.

Two operations, each over a fixed argv whose only variable element is the
absolute path of an executable the application layer already located:

* :func:`spawn_runtime_server` starts the runtime's server so it outlives the
  Cadrumo process and holds none of its console or handles.
* :func:`run_runtime_installer` runs one non-interactive package-manager
  install and returns its exit code.

Neither function inspects, signals or waits on any process it did not start.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from ....application.provisioning_host import RuntimeInstaller

__all__ = ["run_runtime_installer", "spawn_runtime_server"]


def _detached_launch_options() -> dict[str, object]:
    """Return the platform's options for a child that outlives this process."""
    options: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        options["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    else:
        options["start_new_session"] = True
    return options


def spawn_runtime_server(executable: Path, env: Mapping[str, str]) -> int:
    """Start ``<executable> serve`` detached with ``env`` and return its process id.

    The child is deliberately not retained: the runtime is a server the
    operator keeps using after this command exits, so Cadrumo neither waits on
    nor terminates it.
    """
    options = _detached_launch_options()
    options["env"] = dict(env)
    # CAST-RATIONALE-RUNTIME-LAUNCH-OPTIONS: the option set differs per platform,
    # so it is assembled as a mapping that no single Popen overload describes.
    process: subprocess.Popen[Any] = subprocess.Popen([str(executable), "serve"], **cast(Any, options))
    return process.pid


def run_runtime_installer(installer: RuntimeInstaller, executable: Path, timeout_s: float) -> int:
    """Run ``installer``'s non-interactive runtime install and return its exit code.

    ``executable`` is the package manager as located on ``PATH``, so a Windows
    ``.exe`` shim runs without a shell.

    Raises:
        ValueError: When ``installer`` names no package manager.
        TimeoutError: When the install does not finish within ``timeout_s``.
    """
    try:
        return _run_installer(installer, executable, timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"runtime install exceeded {timeout_s:.0f}s") from exc


def _run_installer(installer: RuntimeInstaller, executable: Path, timeout_s: float) -> int:
    options: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "timeout": timeout_s,
        "check": False,
    }
    if installer is RuntimeInstaller.WINGET:
        completed: subprocess.CompletedProcess[Any] = subprocess.run(
            [
                str(executable),
                "install",
                "--id",
                "Ollama.Ollama",
                "--exact",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            **cast(Any, options),
        )
        return int(completed.returncode)
    if installer is RuntimeInstaller.HOMEBREW:
        completed = subprocess.run([str(executable), "install", "ollama"], **cast(Any, options))
        return int(completed.returncode)
    raise ValueError("no install runs without a package manager")
