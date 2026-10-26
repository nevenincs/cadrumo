"""Explicit profile-bound persistence for recorded workflow queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from .run_models import WorkflowResult


class WorkflowRunReader(Protocol):
    """Read canonical encrypted workflow records without ambient store selection."""

    def load(self, run_id: str) -> WorkflowResult:
        """Read the exact run identity or raise the canonical repository error."""
        ...

    def list(self, *, since: date | None = None) -> tuple[WorkflowResult, ...]:
        """Return recorded runs in the canonical newest-first order."""
        ...


@dataclass(frozen=True, slots=True)
class WorkflowRunReadPorts:
    """A read capability composed for one immutable profile bucket."""

    bucket_id: str
    runs: WorkflowRunReader


class WorkflowRunReadPortsFactory(Protocol):
    """Bind workflow history to the requested execution profile."""

    def __call__(self, *, bucket_id: str) -> WorkflowRunReadPorts:
        """Construct an exact-profile reader without a fallback bucket."""
        ...
