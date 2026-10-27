"""Typed setup surface fixture; submission stops before execution."""

from __future__ import annotations

from .....adapters.outbound.components.tests.recorded_rows import recorded_absent_row
from .....application.components_operations import ProvisionOutcome, ProvisionResult
from .....application.dependency_contracts import DependencyItemKind
from ...operations.controller_port import OperationControllerPort


class SetupFixture:
    """Record surface submissions without replacing the behavior under assertion."""

    def __init__(self) -> None:
        self.reads = 0
        self.reviews: list[str] = []
        self.submissions: list[tuple[bool, tuple[DependencyItemKind, ...]]] = []

    async def read_status(self) -> ProvisionResult:
        self.reads += 1
        return ProvisionResult(
            outcome=ProvisionOutcome.OK, rows=(recorded_absent_row("browser"), recorded_absent_row("local_ai"))
        )

    async def review(self, operation_id: str) -> OperationControllerPort:
        """Record a known setup reference without starting it."""
        self.reviews.append(operation_id)
        raise StopSubmissionError(operation_id)

    async def submit(self, *, verify: bool, items: tuple[DependencyItemKind, ...]) -> OperationControllerPort:
        self.submissions.append((verify, items))
        raise StopSubmissionError


class StopSubmissionError(Exception):
    """Stop immediately after observing the surface's typed submission."""
