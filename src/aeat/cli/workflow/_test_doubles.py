"""Shared test doubles for the ``aeat workflow`` CLI test suite.

Concrete, deterministic stand-ins for the deadline engine, draft
builder, submission engine, and inputs provider that the workflow CLI
helpers consume. Used by every test module in this package so the
stubs stay in one place and cannot drift between callers.

These are real classes with deterministic behaviour - they satisfy the
project mandate against `unittest.mock`, `pytest_mock`, patches, fakes,
and stubs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import cast

import pytest

from ...config import Settings
from ...deadlines import (
    AutonomoProfile,
    FilingObligation,
    IVARegime,
    ObligationStatus,
    Schedule,
)
from ...submission import DraftStatus, FilingFinding
from ...workflow import (
    FilingDraftBuilderProtocol,
    SubmissionEngineProtocol,
    SubmittedFilingLike,
    WorkflowEngine,
    WorkflowError,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


@dataclass
class Draft:
    """Deterministic test draft."""

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
    """Draft builder stand-in returning a deterministic ``Draft``."""

    def build(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
        inputs: Mapping[str, object],
        fail_on_warning: bool = False,
    ) -> Draft:
        return Draft(modelo=modelo, period=period, profile_tax_id=profile.tax_id)


class SubmissionEngine:
    """Submission engine stand-in for dry-run paths only."""

    def preflight(self, draft: Draft, *, today: date) -> None:
        return None

    async def submit_draft(
        self,
        draft: Draft,
        *,
        dry_run: bool,
        today: date | None = None,
    ) -> SubmittedFilingLike:
        return SubmittedFilingLike(
            submission_id="sub-x",
            draft_id=draft.draft_id,
            modelo=draft.modelo,
            period=draft.period,
            status="PENDING",
            submitted_at=datetime(2026, 4, 12, tzinfo=UTC),
        )


class InputsProvider:
    """Inputs provider stand-in returning a single casilla."""

    def load_inputs(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
    ) -> Mapping[str, object]:
        return {"01": "1000"}


def make_profile() -> AutonomoProfile:
    """Return the canonical test :class:`AutonomoProfile`."""
    return AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def make_engine() -> WorkflowEngine:
    """Return a fully wired :class:`WorkflowEngine` using the stand-ins."""
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
    """Engine factory that raises :class:`WorkflowError` to drive the
    helpers' catch-and-exit-1 path under test.
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
