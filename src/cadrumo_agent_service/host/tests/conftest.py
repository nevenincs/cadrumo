"""A disposable directory outside every Git checkout, for tests that start the real agent in it."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest


def _git_ancestor(directory: Path) -> Path | None:
    for ancestor in (directory, *directory.parents):
        if (ancestor / ".git").exists():
            return ancestor
    return None


@pytest.fixture
def outside_git_path() -> Iterator[Path]:
    """Yield a fresh directory under ``CADRUMO_DEV_AGENT_HOSTED_ROOT`` and remove it afterwards.

    The agent refuses a hosted root with a ``.git`` entry at or above it, and
    the run's storage root and pinned temporary directory both sit inside the
    checkout, so a test that starts the agent keeps its roots in the directory
    the operator names for it in ``env/.env.example``.
    """
    configured = os.environ.get("CADRUMO_DEV_AGENT_HOSTED_ROOT", "").strip()
    if not configured or not Path(configured).is_absolute():
        pytest.fail(
            "CADRUMO_DEV_AGENT_HOSTED_ROOT must name an absolute directory outside every Git checkout "
            "for tests that start the real agent",
            pytrace=False,
        )
    base = Path(configured)
    base.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="cadrumo-agent-test-", dir=base)).resolve()
    try:
        ancestor = _git_ancestor(directory)
        if ancestor is not None:
            pytest.fail(f"the agent's test root {directory} sits inside the Git checkout {ancestor}", pytrace=False)
        yield directory
    finally:
        _remove(directory)


# How long a directory the agent ran in may stay held after its tree has ended.
_RELEASE_BOUND_SECONDS = 10.0


def _remove(directory: Path) -> None:
    """Remove ``directory``, waiting while Windows still holds it after the agent's tree ended.

    The tree's job is empty when a stop returns, but the system can release a
    handle on the directory the tree ran in a moment later, so its removal is
    refused as in use by another process until then.
    """
    deadline = time.monotonic() + _RELEASE_BOUND_SECONDS
    while True:
        try:
            shutil.rmtree(directory)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)
