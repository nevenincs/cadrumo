"""Start the runtime under an isolated interpreter before application imports."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    """Exclude ambient import paths and third-party model plugins at the launch door."""
    environment = {
        key: value for key, value in os.environ.items() if not key.upper().startswith(("PYTHON", "LD_", "DYLD_"))
    }
    environment["PYDANTIC_DISABLE_PLUGINS"] = "__all__"
    if not sys.flags.isolated:
        arguments = [sys.executable, "-I", "-m", "cadrumo.entrypoints.runtime", *sys.argv[1:]]
        if sys.platform == "win32":
            # Windows has no exec-style process replacement. Keep the manager's
            # launcher alive until its isolated runtime exits, without a shell.
            result = subprocess.run(arguments, env=environment, check=False)  # noqa: S603 -- exact interpreter/module.
            raise SystemExit(result.returncode)
        os.execve(  # noqa: S606 -- exact interpreter and module; no shell or credential arguments.
            sys.executable,
            arguments,
            environment,
        )
    os.environ.clear()
    os.environ.update(environment)
    from .main import run

    raise SystemExit(run())
