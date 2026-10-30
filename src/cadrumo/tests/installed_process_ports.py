"""Explicit process environment and runtime-lifetime ports for product tests."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol


class InstalledProcessWorld(Protocol):
    """Repository orchestration supplied explicitly to installed-process assertions."""

    def environment(self, *, storage_root: Path, authority_root: Path) -> dict[str, str]: ...

    def runtime(self, cli: Path, environment: Mapping[str, str], log: Path) -> AbstractContextManager[None]: ...
