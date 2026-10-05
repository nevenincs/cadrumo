"""Exact, lock-aware project synchronization through ``uv``."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from dev._paths import AUTHORITY_ROOT_ENV, DEFAULT_AUTHORITY_ROOT

from ._venv import VENV, guard

#: The extras and groups an everyday development environment carries.
EXTRA = "workbook-windows"
GROUP = "dev"


def sync_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return the sync environment without the checkout-synthesized authority default.

    Developer tooling seeds the repo-root authority path so installed
    application imports resolve the checkout publication. A first ``uv sync``
    must instead let the build hook recognize that same path as its owned
    default and provision it. Relocated operator overrides remain untouched.
    """
    environment = dict(os.environ if source is None else source)
    configured = environment.get(AUTHORITY_ROOT_ENV)
    if configured is not None and Path(configured).resolve() == DEFAULT_AUTHORITY_ROOT.resolve():
        environment.pop(AUTHORITY_ROOT_ENV)
    return environment


def sync_command() -> tuple[str, ...]:
    """Return the sole command that converges the project environment."""
    return (
        "uv",
        "sync",
        "--locked",
        "--extra",
        EXTRA,
        "--group",
        GROUP,
    )


def install() -> int:
    """Synchronize runtime, workbook, and dev dependencies from ``uv.lock``.

    Returns:
        0 on success, 1 when the environment is locked or in use, otherwise
        the installer's exit code.
    """
    try:
        with guard(VENV):
            argv = sync_command()
            print(f"$ {' '.join(argv)}", flush=True)
            return subprocess.run(argv, check=False, env=sync_environment()).returncode
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 1
