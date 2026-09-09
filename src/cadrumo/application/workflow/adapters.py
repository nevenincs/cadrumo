"""Adapter wiring the deadline engine to the workflow protocol.

See Also:
    :class:`~application.workflow.WorkflowEngine`
        Consumes the adapted deadline collaborator.
    :mod:`application.modelo._workflow_gate`
        Builds revision-scoped workflow engines with the same adapter
        boundaries for verification and local mark-as-filed paths.
"""

from __future__ import annotations

from datetime import date

from ...domain.deadlines.engine import DeadlineEngine
from ...domain.deadlines.models import Schedule, TaxpayerProfile


class DeadlineEngineAdapter:
    """Wrap :class:`~domain.deadlines.DeadlineEngine` as a workflow Protocol."""

    def __init__(self, engine: DeadlineEngine) -> None:
        """Store the wrapped :class:`DeadlineEngine`."""
        self._engine = engine

    def compute(
        self,
        profile: TaxpayerProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        """Delegate to :meth:`DeadlineEngine.compute` for the given :class:`TaxpayerProfile`.

        Returns a :class:`Schedule`.
        """
        return self._engine.compute(profile, year, today=today)


__all__ = ["DeadlineEngineAdapter"]
