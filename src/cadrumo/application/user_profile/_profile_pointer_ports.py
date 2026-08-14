"""Application-owned ports for active-profile pointer coordination."""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol


class ProfileCustodyRootLockPort(Protocol):
    """Acquire the shared profile-custody root lock for one operation."""

    def __call__(self, root: Path, *, timeout_seconds: float) -> AbstractContextManager[None]:
        """Return a context manager holding the canonical root lock."""
        ...


__all__ = ["ProfileCustodyRootLockPort"]
