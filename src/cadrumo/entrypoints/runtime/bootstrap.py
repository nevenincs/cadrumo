"""Start the runtime under an isolated interpreter before application imports."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace


def _runtime_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.upper().startswith(("PYTHON", "LD_", "DYLD_"))
    }
    environment["PYDANTIC_DISABLE_PLUGINS"] = "__all__"
    return environment


def _launch_isolated_interpreter(environment: Mapping[str, str]) -> None:
    arguments = [sys.executable, "-I", "-m", "cadrumo.entrypoints.runtime", *sys.argv[1:]]
    if sys.platform == "win32":
        # Windows has no exec-style process replacement. Keep the
        # launcher alive until its isolated runtime exits, without a shell.
        result = subprocess.run(arguments, env=environment, check=False)  # noqa: S603 -- exact interpreter/module.
        raise SystemExit(result.returncode)
    os.execve(  # noqa: S606 -- exact interpreter and module; no shell or credential arguments.
        sys.executable,
        arguments,
        environment,
    )


def _run_posix_runtime(options: Namespace) -> None:
    from .main import run

    raise SystemExit(run(options))


def main() -> None:
    """Exclude ambient import paths and third-party model plugins at the launch door."""
    environment = _runtime_environment()
    if not sys.flags.isolated:
        _launch_isolated_interpreter(environment)
    os.environ.clear()
    os.environ.update(environment)
    from .arguments import parse_runtime_arguments

    options = parse_runtime_arguments()
    if sys.platform != "win32":
        _run_posix_runtime(options)
    _run_isolated_windows_runtime(options)


def _run_isolated_windows_runtime(options: Namespace) -> None:
    started = time.monotonic()
    from ...core.logging import defer_logging_configuration, get_logger, resume_logging_configuration
    from ...core.startup_phase_log import log_startup_phase

    logger = get_logger(__name__)
    # Quiet phase records stay in the canonical bounded buffer until main has
    # validated its root. A pre-main hang has no durable diagnostic file yet.
    defer_logging_configuration()
    try:
        log_startup_phase(logger, "bootstrap", "enter", 0.0)
        run = _import_runtime_main(logger, started, log_startup_phase)
        raise SystemExit(run(options))
    finally:
        resume_logging_configuration()


def _import_runtime_main(
    logger: logging.Logger,
    started: float,
    log_startup_phase: Callable[..., None],
) -> Callable[[Namespace], int]:
    importing = time.monotonic()
    primary: list[BaseException] = []
    log_startup_phase(logger, "main_import", "enter", 0.0)
    try:
        from .main import run
    except BaseException as error:
        primary.append(error)
        raise
    finally:
        elapsed = time.monotonic() - importing
        log_startup_phase(logger, "main_import", "leave", elapsed, primary_error=primary[0] if primary else None)
        elapsed = time.monotonic() - started
        log_startup_phase(logger, "bootstrap", "leave", elapsed, primary_error=primary[0] if primary else None)
    return run
