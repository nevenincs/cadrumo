"""Provisioning of `env/.env` from its committed example.

Idempotent by contract: an existing `env/.env` is left untouched, because it
carries the operator's own local secrets and overwriting it is unrecoverable.
"""

from __future__ import annotations

import shutil
import sys

from dev._paths import REPO_ROOT

EXAMPLE = REPO_ROOT / "env" / ".env.example"
TARGET = REPO_ROOT / "env" / ".env"


def env_setup() -> int:
    """Copy the example environment file when the real one is absent.

    Returns:
        0 when `env/.env` exists or was created, 1 when the example is missing.
    """
    if not EXAMPLE.is_file():
        print(
            f"{EXAMPLE.relative_to(REPO_ROOT).as_posix()} not found - cannot provision env/.env",
            file=sys.stderr,
            flush=True,
        )
        return 1
    if TARGET.exists():
        print("env/.env already exists - leaving it untouched.", flush=True)
        return 0
    shutil.copyfile(EXAMPLE, TARGET)
    print("Created env/.env from env/.env.example.", flush=True)
    return 0
