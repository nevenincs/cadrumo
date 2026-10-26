"""Isolated process environments for target-interpreter compatibility probes."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from dev.product_environment import clean_product_env

_RESOLVER_ENVIRONMENT: Final[tuple[str, ...]] = (
    "UV_DEFAULT_INDEX",
    "UV_EXTRA_INDEX_URL",
    "UV_FIND_LINKS",
    "UV_INDEX",
    "UV_INDEX_URL",
    "UV_NATIVE_TLS",
    "UV_NO_INDEX",
    "UV_OFFLINE",
    "UV_REQUEST_TIMEOUT",
    "PIP_EXTRA_INDEX_URL",
    "PIP_FIND_LINKS",
    "PIP_INDEX_URL",
    "PIP_NO_INDEX",
    "PIP_TRUSTED_HOST",
)


def _isolated_environment(work_dir: Path, executable_dir: Path) -> dict[str, str]:
    """Construct a child environment with checkout imports and ambient commands removed."""
    environment = clean_product_env()
    for name in (
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONUSERBASE",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "CONDA_DEFAULT_ENV",
        "UV_PROJECT_ENVIRONMENT",
    ):
        environment.pop(name, None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PATH"] = str(executable_dir)
    environment["CADRUMO_COMPATIBILITY_WORK_DIR"] = str(work_dir.resolve())
    return environment


def _binary_environment() -> dict[str, str]:
    """Return an installer environment with every ambient resolver input removed.

    The command-line ``--offline --no-index`` switches are the authoritative
    closure, but ambient ``UV_*`` and ``PIP_*`` values must not be allowed to
    add another candidate source or change resolver behavior.  Keeping this
    scrub local to the binary installer also leaves source probes free to use
    their normal networked build path.
    """
    environment = clean_product_env()
    for name in _RESOLVER_ENVIRONMENT:
        environment.pop(name, None)
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        environment.pop(name, None)
    return environment
