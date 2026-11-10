"""Filing-handoff projections of the activity-asset register.

The Modelo 100 gaps and Modelo 130 accruals a handoff states, and the words and
element names they are served with.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import round_to_cents
from ...domain.renta.actividad_asset.claims import ClaimProjection, current_revisions
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from ...domain.renta.actividad_asset.schedule import last_day_covered
from .activity_asset_read_models import (
    ActivityAssetHandoffLeftOut,
    ActivityAssetHandoffLeftOutReason,
    ServedWords,
    text_in_meaning,
)
from .history import ActivityAssetHistory
from .ports import ActivityAssetForecastOperation
from .schedule_walk import (
    M100ClaimGap,
    M100GapKind,
    M130ElementAccrual,
    M130ElementOutcome,
    m100_claim_gaps,
    m100_unbound_box_gap,
)
from .served_words import left_out_entry, m100_gap_words, partial_words


class M130Contribution(BaseModel):
    """One amount behind Modelo 130 casilla 02, resting on one claim or on one schedule."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    amount: Decimal
    claim_id: str | None = None
    schedule_fingerprint: str | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _one_source(self) -> Self:
        if (self.claim_id is None) == (self.schedule_fingerprint is None):
            raise ValueError("a Modelo 130 contribution rests on exactly one claim or one schedule")
        return self


class M130AccrualProjection(BaseModel):
    """What one asset kind accrued in the year through the period's end.

    ``unavailable_asset_ids`` names elements whose schedule could not be worked
    out, ``free_gap_asset_ids`` those whose method leaves an unrecorded amount to
    the taxpayer, and ``agrarian_excluded_asset_ids`` those of an agrarian activity,
    which pays a share of income, so an amount that leaves them out says so.
    """

    model_config = STRICT_FROZEN_CONFIG

    target_casilla_id: CasillaId
    box_name: str | None = None
    """What the box is called in the filer's words, with the asset kind that tells it from the other kind's row."""
    tax_year: int
    amount: Decimal
    contributions: tuple[M130Contribution, ...] = ()
    unavailable_asset_ids: tuple[str, ...] = ()
    free_gap_asset_ids: tuple[str, ...] = ()
    agrarian_excluded_asset_ids: tuple[str, ...] = ()
    partial_words: ServedWords | None = None
    """The sentence saying the amount leaves out the elements that could not be worked out."""
    words_language: OutputLanguage | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _words_name_their_language(self) -> Self:
        if self.partial_words is not None and self.words_language is None:
            raise ValueError("served words name the language they are in")
        return self


class M100ClaimGapProjection(BaseModel):
    """An interval of the year Modelo 100 leaves out of an element, and what it would have accrued."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1)
    kind: M100GapKind
    covered_from: date
    covered_until: date
    accrued: Decimal | None = None
    words: ServedWords | None = None
    """The interval said whole, by the name the register holds for the element."""
    words_language: OutputLanguage | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _words_name_their_language(self) -> Self:
        if self.words is not None and self.words_language is None:
            raise ValueError("served words name the language they are in")
        return self


class ActivityAssetFilingHandoff(BaseModel):
    """Non-consuming projections for both supported IRPF filing destinations.

    ``m100_gaps`` says what the Modelo 100 boxes leave out because no claim records it, or because
    the edition binds no box for the element's kind.
    """

    model_config = STRICT_FROZEN_CONFIG

    material_m100: ClaimProjection | None
    intangible_m100: ClaimProjection | None
    """Absent for a kind the edition binds no Modelo 100 box for; ``m100_gaps`` then names its elements."""
    m100_gaps: tuple[M100ClaimGapProjection, ...] = ()
    material_m100_box_name: str | None = None
    intangible_m100_box_name: str | None = None
    """What each Modelo 100 box is called in the filer's words; the two boxes are different casillas."""
    material_m130: M130AccrualProjection | None = None
    intangible_m130: M130AccrualProjection | None = None
    """Both set for a Modelo 130 period, and both absent when the handoff states Modelo 100 alone."""
    left_out: tuple[ActivityAssetHandoffLeftOut, ...] = ()
    """What the Modelo 130 amounts leave out, one entry per reason across both asset kinds."""

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _m130_together(self) -> Self:
        if (self.material_m130 is None) != (self.intangible_m130 is None):
            raise ValueError("a filing handoff states the Modelo 130 accrual of both asset kinds or of neither")
        return self


def m130_projection(
    asset_kind: AssetKind,
    accruals: tuple[M130ElementAccrual, ...],
    m130_box: CasillaId,
    tax_year: int,
    box_name: str,
    language: OutputLanguage,
) -> M130AccrualProjection:
    """Project what one asset kind accrued in the year through the end of the period."""
    selected = tuple(accrual for accrual in accruals if accrual.revision.asset_kind is asset_kind)
    contributions = _m130_contributions(selected)
    unavailable = _asset_ids_with_outcome(selected, M130ElementOutcome.UNAVAILABLE)
    return M130AccrualProjection(
        target_casilla_id=m130_box,
        box_name=box_name,
        tax_year=tax_year,
        amount=round_to_cents(sum((item.amount for item in contributions), Decimal("0"))),
        contributions=contributions,
        unavailable_asset_ids=unavailable,
        free_gap_asset_ids=_asset_ids_with_outcome(selected, M130ElementOutcome.FREE_GAP),
        agrarian_excluded_asset_ids=_asset_ids_with_outcome(selected, M130ElementOutcome.AGRARIAN_EXCLUDED),
        partial_words=partial_words(len(unavailable), language) if unavailable else None,
        words_language=language if unavailable else None,
    )


def _asset_ids_with_outcome(selected: tuple[M130ElementAccrual, ...], outcome: M130ElementOutcome) -> tuple[str, ...]:
    return tuple(accrual.revision.asset_id for accrual in selected if accrual.outcome is outcome)


def left_out_of_handoff(
    projections: tuple[M130AccrualProjection, ...], names: Mapping[str, str], language: OutputLanguage
) -> tuple[ActivityAssetHandoffLeftOut, ...]:
    """Say what the Modelo 130 amounts leave out, one entry per reason across the asset kinds."""
    by_reason = (
        (ActivityAssetHandoffLeftOutReason.FREE_GAP, "free_gap_asset_ids"),
        (ActivityAssetHandoffLeftOutReason.AGRARIAN_EXCLUDED, "agrarian_excluded_asset_ids"),
        (ActivityAssetHandoffLeftOutReason.UNAVAILABLE, "unavailable_asset_ids"),
    )
    entries: list[ActivityAssetHandoffLeftOut] = []
    for reason, attribute in by_reason:
        ids = tuple(dict.fromkeys(asset_id for item in projections for asset_id in getattr(item, attribute)))
        if ids:
            entries.append(left_out_entry(reason, ids, names, language))
    return tuple(entries)


def asset_names(history: ActivityAssetHistory) -> dict[str, str]:
    """The name the register holds for each element that has one."""
    names: dict[str, str] = {}
    for asset_id in {revision.asset_id for revision in history.revisions}:
        descriptor = history.current_descriptor(asset_id)
        name = None if descriptor is None else text_in_meaning(descriptor.facts.name)
        if name is not None:
            names[asset_id] = name
    return names


def _m130_contributions(selected: tuple[M130ElementAccrual, ...]) -> tuple[M130Contribution, ...]:
    return tuple(
        M130Contribution(
            asset_id=item.asset_id,
            amount=item.amount,
            claim_id=item.claim_id,
            schedule_fingerprint=item.schedule_fingerprint,
        )
        for accrual in selected
        for item in accrual.contributions
    )


def m100_gap_projections(
    history: ActivityAssetHistory,
    forecast: ActivityAssetForecastOperation,
    tax_year: int,
    bound_kinds: AbstractSet[AssetKind],
    *,
    names: Mapping[str, str],
    language: OutputLanguage,
) -> tuple[M100ClaimGapProjection, ...]:
    """Project the intervals Modelo 100 leaves out of each current element, with their words."""

    def gaps_of(revision: ActivityAssetRevision) -> tuple[M100ClaimGap, ...]:
        if revision.asset_kind in bound_kinds:
            return m100_claim_gaps(revision, history, forecast=forecast, tax_year=tax_year)
        unbound = m100_unbound_box_gap(revision, tax_year=tax_year)
        return () if unbound is None else (unbound,)

    return tuple(
        M100ClaimGapProjection(
            asset_id=gap.revision.asset_id,
            kind=gap.kind,
            covered_from=gap.covered_from,
            covered_until=gap.covered_until,
            accrued=gap.accrued,
            words=m100_gap_words(
                gap.kind,
                name=names.get(gap.revision.asset_id),
                covered_from=gap.covered_from,
                covered_through=last_day_covered(gap.covered_until),
                accrued=gap.accrued,
                language=language,
            ),
            words_language=language,
        )
        for revision in current_revisions(history.revisions).values()
        for gap in gaps_of(revision)
    )


__all__ = [
    "ActivityAssetFilingHandoff",
    "M100ClaimGapProjection",
    "M130AccrualProjection",
    "M130Contribution",
    "asset_names",
    "left_out_of_handoff",
    "m100_gap_projections",
    "m130_projection",
]
