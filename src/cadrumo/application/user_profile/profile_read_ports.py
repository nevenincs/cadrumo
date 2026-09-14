"""Application-owned profile read capabilities.

Calculation services consume a small, path-keyed profile projection.  The
projection is deliberately a capability rather than a repository lookup: the
encrypted record/session implementation is composed by an outer adapter and
the application only sees the stable mapping and absence semantics.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


class ProfilePathValuesReadPort(Protocol):
    """Read the canonical path-keyed profile projection for one bucket."""

    def load_path_values(self, *, bucket_id: str) -> Mapping[str, str] | None:
        """Return projected profile values, or ``None`` when the profile is absent."""
        ...


@dataclass(frozen=True, slots=True)
class ProfileReadPorts:
    """Required profile-read capabilities for a composed application path."""

    path_values: ProfilePathValuesReadPort


class ProfileReadPortsFactory(Protocol):
    """Construct profile-read capabilities for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> ProfileReadPorts:
        """Return the required profile projection capability."""
        ...


__all__ = ["ProfilePathValuesReadPort", "ProfileReadPorts", "ProfileReadPortsFactory"]
