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
    r"""Yield a fresh directory under ``%LOCALAPPDATA%\Temp`` and remove it afterwards.

    The agent refuses a hosted root with a ``.git`` entry at or above it, and
    the test run's own temporary directory sits inside the checkout, so a
    test that starts the agent keeps its roots here instead.
    """
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if not local:
        pytest.fail(r"LOCALAPPDATA is not set; the agent's test roots live in %LOCALAPPDATA%\Temp", pytrace=False)
    base = Path(local) / "Temp"
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
