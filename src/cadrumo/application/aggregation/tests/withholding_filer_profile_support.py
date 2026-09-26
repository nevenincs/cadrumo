"""Synthetic filer profiles whose canonical schedule makes withholding quarterly or monthly.

The profiles are real records created under the pinned authority's profile
schema, so the cadence they produce comes from the published Modelo 111, 115
and 123 filing schedules rather than from a flag the test sets directly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from cadrumo.application.aggregation.withholding_filing_cadence import (
    WithholdingFilerCadence,
    resolve_withholding_filer_cadence,
)
from cadrumo.application.aggregation.withholding_producer import WithholdingEvidenceCaptureCommand
from cadrumo.application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from cadrumo.application.modelo.work_profile import ModeloWorkProfile
from cadrumo.application.user_profile.projections import projection_for_taxpayer
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

WITHHOLDING_FILER_PROFILE_ID: Final[str] = "7c1d2e3f-4a5b-4c6d-8e7f-90a1b2c3d4e5"
_CLOCK: Final[datetime] = datetime(2025, 1, 2, 9, tzinfo=UTC)

LARGE_COMPANY_FACTS: Final[tuple[UserProfileFact, ...]] = (UserProfileFact(path="censo.large_company", value=True),)
"""A large company: the Modelo 111 schedule makes it monthly and no Modelo 123 or 115 schedule covers it."""

PUBLIC_ADMINISTRATION_FACTS: Final[tuple[UserProfileFact, ...]] = (
    UserProfileFact(path="censo.public_administration_budget_gt_6000000", value=True),
)
"""A public administration over the budget threshold: monthly Modelo 111 only."""

REDEME_FACTS: Final[tuple[UserProfileFact, ...]] = (UserProfileFact(path="iva.redeme_enrolled", value=True),)
"""A REDEME filer: monthly for IVA, but no withholding schedule reads the enrolment."""


def _facts(overrides: tuple[UserProfileFact, ...]) -> tuple[UserProfileFact, ...]:
    replaced = {fact.path: fact for fact in overrides}
    merged = [replaced.pop(fact.path, fact) for fact in MODELO_READY_PROFILE_FACTS]
    return (*merged, *replaced.values())


def withholding_work_profile(
    operation: PinnedAuthorityOperation,
    *,
    facts: tuple[UserProfileFact, ...] = (),
    profile_id: str = WITHHOLDING_FILER_PROFILE_ID,
) -> ModeloWorkProfile:
    """Return a complete work profile carrying the readiness baseline plus ``facts``."""
    record = create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=profile_id,
        facts=_facts(facts),
        setup_state=ProfileSetupState.COMPLETE,
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    return ModeloWorkProfile(record=record, profile_decode_context=operation.profile_decode_context())


def withholding_filer_cadence(
    operation: PinnedAuthorityOperation,
    *,
    filing_year: int,
    facts: tuple[UserProfileFact, ...] = (),
) -> WithholdingFilerCadence:
    """Resolve the cadence of a synthetic filer through the canonical schedule resolver."""
    profile = withholding_work_profile(operation, facts=facts)
    taxpayer_profile = projection_for_taxpayer(profile.record, schema=profile.profile_decode_context.schema)
    return resolve_withholding_filer_cadence(taxpayer_profile, filing_year=filing_year, operation=operation)


def published_filer_cadence(
    filing_year: int,
    *,
    facts: tuple[UserProfileFact, ...] = (),
) -> WithholdingFilerCadence:
    """Resolve a synthetic filer's cadence against the published authority generation."""
    with bundled_indexed_authority().operation() as operation:
        return withholding_filer_cadence(operation, filing_year=filing_year, facts=facts)


def quarterly_filer_cadence(filing_year: int) -> WithholdingFilerCadence:
    """Return the cadence of an ordinary filer, whom every withholding schedule makes quarterly."""
    return published_filer_cadence(filing_year)


def quarterly_filer_cadence_for(command: WithholdingEvidenceCaptureCommand | None) -> WithholdingFilerCadence:
    """Return the ordinary filer's cadence for the year a capture command applies to."""
    if command is None:
        return quarterly_filer_cadence(_CLOCK.year)
    return quarterly_filer_cadence(command.recognition_evidence.applicable_year)


__all__ = [
    "LARGE_COMPANY_FACTS",
    "PUBLIC_ADMINISTRATION_FACTS",
    "REDEME_FACTS",
    "WITHHOLDING_FILER_PROFILE_ID",
    "published_filer_cadence",
    "quarterly_filer_cadence",
    "quarterly_filer_cadence_for",
    "withholding_filer_cadence",
    "withholding_work_profile",
]
