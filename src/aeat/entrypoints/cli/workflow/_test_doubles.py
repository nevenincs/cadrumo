"""Shared test doubles for the ``aeat workflow`` CLI test suite.

Provides concrete, deterministic stand-ins for the deadline engine, draft
builder, submission engine, and inputs provider consumed by the workflow
CLI helpers. Centralising them here keeps every test module in this
package aligned and prevents drift between callers.

These are real classes with deterministic behaviour: they satisfy the
project mandate against ``unittest.mock``, ``pytest-mock``, patches, fakes,
and stubs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import cast

import pytest

from ....adapters.outbound.aeat.export import DraftStatus, FilingFinding
from ....application.workflow import (
    FilingDraftBuilderProtocol,
    SubmissionEngineProtocol,
    WorkflowEngine,
    WorkflowError,
)
from ....core.config import Settings
from ....domain.deadlines import (
    AutonomoProfile,
    FilingObligation,
    IVARegime,
    ObligationStatus,
    Schedule,
)

# This module is a shared test-helper file — no test functions live
# here, but its filename matches the project's `_test_*.py` glob
# which the marker-integrity walker enforces. Carry the same
# pytestmark every sibling test module declares so the contract
# stays uniform across the package.
pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@dataclass
class Draft:
    """Deterministic test draft mirroring the production filing draft contract.

    Attributes:
        draft_id: Stable draft identifier.
        modelo: Modelo identifier (e.g. ``"130"``).
        period: Period identifier (e.g. ``"2026Q1"``).
        profile_tax_id: Tax id of the owning
            :class:`aeat.domain.deadlines.AutonomoProfile`.
        status: Approval status; defaults to
            :attr:`aeat.adapters.outbound.aeat.export.DraftStatus.APPROVED`.
        values: Casilla values keyed by code.
        findings: Optional tuple of
            :class:`aeat.adapters.outbound.aeat.export.FilingFinding`.
    """

    draft_id: str = "draft-x"
    modelo: str = "130"
    period: str = "2026Q1"
    profile_tax_id: str = "X1234567L"
    status: DraftStatus = DraftStatus.APPROVED
    values: Mapping[str, str] = field(default_factory=lambda: {"01": "1000"})
    findings: tuple[FilingFinding, ...] = ()


class DeadlineEngine:
    """Deadline engine stand-in returning one fixed UPCOMING obligation."""

    def compute(
        self,
        profile: AutonomoProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        """Return a fixed-shape :class:`aeat.domain.deadlines.Schedule`."""
        return Schedule(
            profile=profile,
            year=year,
            obligations=(
                FilingObligation(
                    modelo="130",
                    period="2026Q1",
                    opens_on=date(2026, 4, 1),
                    closes_on=date(2099, 12, 31),
                    status=ObligationStatus.UPCOMING,
                    applies_because="test",
                ),
            ),
            generated_at=datetime(2026, 4, 12, tzinfo=UTC),
        )


class DraftBuilder:
    """Draft builder stand-in returning a deterministic :class:`Draft`."""

    def build(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
        inputs: Mapping[str, object],
        fail_on_warning: bool = False,
    ) -> Draft:
        """Return a :class:`Draft` echoing ``modelo``, ``period``, and tax id."""
        return Draft(modelo=modelo, period=period, profile_tax_id=profile.tax_id)


class SubmissionEngine:
    """Submission engine stand-in for read-only preflight paths."""

    def preflight(self, draft: Draft, *, today: date) -> None:
        """No-op preflight: read-only path always returns ``None``."""
        return None


class InputsProvider:
    """Inputs provider stand-in returning a single casilla."""

    def load_inputs(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
    ) -> Mapping[str, object]:
        """Return a deterministic single-casilla inputs mapping."""
        return {"01": "1000"}


def make_profile() -> AutonomoProfile:
    """Return the canonical test :class:`aeat.domain.deadlines.AutonomoProfile`."""
    return AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def make_engine() -> WorkflowEngine:
    """Return a fully wired :class:`aeat.application.workflow.WorkflowEngine`.

    Composes the deterministic stand-ins from this module into a real
    engine instance suitable for end-to-end CLI tests.
    """
    return WorkflowEngine(
        deadline_engine=DeadlineEngine(),
        filing_draft_builder=cast(FilingDraftBuilderProtocol, DraftBuilder()),
        submission_engine=cast(SubmissionEngineProtocol, SubmissionEngine()),
        sync_runner=None,
        session=None,
        certificate_bundle=None,
        inputs_provider=InputsProvider(),
        settings=Settings(),
    )


def make_failing_engine() -> WorkflowEngine:
    """Engine factory that always raises :exc:`aeat.application.workflow.WorkflowError`.

    Drives the helpers' catch-and-exit-1 path under test.

    Raises:
        :exc:`aeat.application.workflow.WorkflowError`: Always.
    """
    raise WorkflowError("simulated wiring failure")


__all__ = [
    "DeadlineEngine",
    "Draft",
    "DraftBuilder",
    "InputsProvider",
    "SubmissionEngine",
    "make_engine",
    "make_failing_engine",
    "make_profile",
]
