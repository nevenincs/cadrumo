"""Run a registry import probe in a clean base interpreter and check the child it reports."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
from pathlib import Path

_HOST_IDENTITY_PRELUDE = """import platform

platform.uname()
"""
"""Resolve the host identity before a probe's body installs its effects guard.

On Windows the first ``platform.uname()`` asks WMI and, when that query fails or
times out under load, launches ``cmd`` for ``ver``. Imports under the guard read
the machine identity (SQLAlchemy does), so an unresolved first query there is a
process launch the guard refuses, and the probe fails by how busy the host is.
"""


def run_isolated_registry_probe(tmp_path: Path, probe: str) -> None:
    """Run ``probe`` in an isolated base interpreter and assert it exits cleanly without touching storage.

    The host identity is resolved first, so ``probe`` may guard against process
    launches from its first line.
    """
    source = Path(__file__).resolve().parents[3]
    base_executable = getattr(sys, "_base_executable", None)
    assert isinstance(base_executable, str)
    interpreter = Path(base_executable).resolve(strict=True)
    package_paths = sorted({sysconfig.get_path("purelib"), sysconfig.get_path("platlib")})
    allowed = {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "COMSPEC", "USERNAME", "USERDOMAIN"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment.update(
        {
            "CADRUMO_AUTHORITY_ROOT": os.environ["CADRUMO_AUTHORITY_ROOT"],
            "CADRUMO_STORAGE_ROOT": str(tmp_path / "storage"),
            "PYDANTIC_DISABLE_PLUGINS": "__all__",
            "TEMP": str(tmp_path),
            "TMP": str(tmp_path),
            "HOME": str(tmp_path),
            "USERPROFILE": str(tmp_path),
            "APPDATA": str(tmp_path),
            "LOCALAPPDATA": str(tmp_path),
        }
    )
    stdout_path = tmp_path / "registry-probe.stdout"
    stderr_path = tmp_path / "registry-probe.stderr"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(  # noqa: S603 - resolved base interpreter, fixed import-only probe, owned child
            [
                str(interpreter),
                "-I",
                "-S",
                "-B",
                "-c",
                _HOST_IDENTITY_PRELUDE + probe,
                str(source),
                json.dumps(package_paths),
            ],
            cwd=tmp_path,
            env=environment,
            stdout=stdout,
            stderr=stderr,
        )
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired as error:
            error.add_note(f"Owned child PID: {process.pid}")
            error.add_note(stdout_path.read_text(encoding="utf-8"))
            error.add_note(stderr_path.read_text(encoding="utf-8"))
            raise
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
    assert process.returncode == 0, stderr_path.read_text(encoding="utf-8")
    observation = json.loads(stdout_path.read_text(encoding="utf-8"))
    assert observation["pid"] == process.pid
    assert Path(observation["interpreter"]).resolve(strict=True) == interpreter
    assert not (tmp_path / "storage").exists()
