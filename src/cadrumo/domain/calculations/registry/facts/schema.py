"""Closed schema contracts for registry-governed facts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Annotated

from pydantic import Field, model_validator

from .....core.errors.hierarchy import pydantic_validation_boundary
from .....core.frozen_mapping import FROZEN_MAPPING
from ..errors import RegistryValidationError
from ..ids import RegistryRevisionNodeId
from ..revision_contracts import RevisionWindow, validate_revision_predecessors
from ..schema_base import RegistryModel
from ..schema_references import DateSupportEnvelope, RegistryValidityWindow
from .payloads import GovernedFactFamilyField
from .variants import GovernedFactVariant

__all__ = [
    "FactId",
    "FactProviderId",
    "GovernedFact",
    "GovernedFactCatalogue",
]


_REGISTRY_ID_PATTERN = r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$"
FactId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REGISTRY_ID_PATTERN)]
FactProviderId = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"),
]


class GovernedFact(RegistryModel):
    """A stable semantic fact and all legally distinct variants of that fact."""

    fact_id: FactId
    family: GovernedFactFamilyField
    provider_id: FactProviderId | None = Field(default=None, exclude_if=lambda value: value is None)
    variants: tuple[GovernedFactVariant, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_fact(self) -> GovernedFact:
        variant_ids = [variant.variant_id for variant in self.variants]
        _validate_unique_fact_variant_ids(self, variant_ids)
        _validate_fact_payload_families(self)
        precedence = _validate_fact_precedence(self, variant_ids)
        _validate_fact_precedence_cycles(self.fact_id, variant_ids, precedence)
        _validate_fact_support_floor(self)
        materialized = self.materialized_windows()
        _validate_fact_track_pairs(self, precedence, materialized)
        _validate_fact_predecessor_chains(self, materialized)
        return self

    def validity_window(
        self,
        variant: GovernedFactVariant,
        support: DateSupportEnvelope | None = None,
    ) -> RegistryValidityWindow:
        """Materialise one variant's authored or floor-propagated endpoints."""
        return self.materialized_windows(support)[variant.variant_id]

    @staticmethod
    def track_key(variant: GovernedFactVariant) -> tuple[object, ...]:
        """Return the exact axis, selector, and typed-period identity of a revision track."""
        selectors = tuple(
            sorted((item.name, type(item.value).__name__, repr(item.value)) for item in variant.selectors)
        )
        period = variant.period_selector
        period_key = (
            None
            if period is None
            else (
                period.years,
                period.year_from,
                period.year_to,
                period.periods,
                tuple((item.year, item.periods) for item in period.period_overrides),
            )
        )
        return variant.date_axis, selectors, period_key

    def materialized_windows(
        self,
        support: DateSupportEnvelope | None = None,
    ) -> Mapping[RegistryRevisionNodeId, RegistryValidityWindow]:
        """Resolve delta-authored bounds against the registry support envelope.

        Explicit endpoints are retained verbatim. The one variant per track that
        omits ``valid_from`` reaches the envelope floor; without an envelope (the
        structural validation of a single component) it reaches the earliest
        representable date, which orders it first without inventing a floor.
        """
        floor = date.min if support is None else support.floor
        return {
            variant.variant_id: RegistryValidityWindow(
                valid_from=floor if variant.valid_from is None else variant.valid_from,
                valid_to=variant.valid_to,
            )
            for variant in self.variants
        }


def _validate_unique_fact_variant_ids(fact: GovernedFact, variant_ids: list[str]) -> None:
    if len(set(variant_ids)) != len(variant_ids):
        raise RegistryValidationError(f"governed fact {fact.fact_id!r} variant ids must be unique")


def _validate_fact_payload_families(fact: GovernedFact) -> None:
    if any(variant.payload.kind != fact.family for variant in fact.variants):
        raise RegistryValidationError(
            f"governed fact {fact.fact_id!r} variants must use the declared {fact.family!r} family"
        )


def _validate_fact_precedence(
    fact: GovernedFact,
    variant_ids: list[str],
) -> dict[str, tuple[str, ...]]:
    known_ids = set(variant_ids)
    for variant in fact.variants:
        unknown = set(variant.precedence_over) - known_ids
        if unknown:
            raise RegistryValidationError(
                f"governed fact {fact.fact_id!r} precedence names unknown variants {sorted(unknown)!r}"
            )
        for target_id in variant.precedence_over:
            target = next(item for item in fact.variants if item.variant_id == target_id)
            if fact.track_key(variant) != fact.track_key(target):
                raise RegistryValidationError(f"governed fact {fact.fact_id!r} precedence cannot cross temporal tracks")
    return {variant.variant_id: variant.precedence_over for variant in fact.variants}


def _validate_fact_precedence_cycles(
    fact_id: FactId,
    variant_ids: list[str],
    precedence: Mapping[str, tuple[str, ...]],
) -> None:
    for variant_id in variant_ids:
        if _graph_reaches(variant_id, variant_id, precedence):
            raise RegistryValidationError(
                f"governed fact {fact_id!r} precedence graph contains a cycle at {variant_id!r}"
            )


def _validate_fact_support_floor(fact: GovernedFact) -> None:
    floor_reaching: dict[tuple[object, ...], int] = {}
    for variant in fact.variants:
        if variant.valid_from is not None:
            continue
        track = fact.track_key(variant)
        floor_reaching[track] = floor_reaching.get(track, 0) + 1
        if floor_reaching[track] > 1:
            raise RegistryValidationError(
                f"governed fact {fact.fact_id!r} track {track!r} has more than one variant omitting "
                "valid_from; only the first declaration can reach the support floor"
            )


def _validate_fact_track_pairs(
    fact: GovernedFact,
    precedence: Mapping[str, tuple[str, ...]],
    materialized: Mapping[RegistryRevisionNodeId, RegistryValidityWindow],
) -> None:
    for index, left in enumerate(fact.variants):
        for right in fact.variants[index + 1 :]:
            if fact.track_key(left) != fact.track_key(right):
                continue
            _validate_fact_track_pair(fact.fact_id, left, right, precedence, materialized)


def _validate_fact_track_pair(
    fact_id: FactId,
    left: GovernedFactVariant,
    right: GovernedFactVariant,
    precedence: Mapping[str, tuple[str, ...]],
    materialized: Mapping[RegistryRevisionNodeId, RegistryValidityWindow],
) -> None:
    left_window = materialized[left.variant_id]
    right_window = materialized[right.variant_id]
    overlaps = left_window.valid_from <= (right_window.valid_to or date.max) and right_window.valid_from <= (
        left_window.valid_to or date.max
    )
    ordered = _graph_reaches(left.variant_id, right.variant_id, precedence) or _graph_reaches(
        right.variant_id,
        left.variant_id,
        precedence,
    )
    directly_ordered = right.variant_id in left.precedence_over or left.variant_id in right.precedence_over
    if overlaps and not ordered:
        raise RegistryValidationError(
            f"governed fact {fact_id!r} variants {left.variant_id!r} and "
            f"{right.variant_id!r} overlap without explicit precedence"
        )
    if directly_ordered and not overlaps:
        raise RegistryValidationError(
            f"governed fact {fact_id!r} variants {left.variant_id!r} and "
            f"{right.variant_id!r} declare precedence across non-overlapping coordinates"
        )


def _validate_fact_predecessor_chains(
    fact: GovernedFact,
    materialized: Mapping[RegistryRevisionNodeId, RegistryValidityWindow],
) -> None:
    tracks: dict[tuple[object, ...], list[GovernedFactVariant]] = {}
    for variant in fact.variants:
        tracks.setdefault(fact.track_key(variant), []).append(variant)
    for track, variants in tracks.items():
        validate_revision_predecessors(
            f"{fact.fact_id}:{track!r}",
            {variant.variant_id: variant for variant in variants},
            windows={
                variant.variant_id: RevisionWindow(
                    valid_from=materialized[variant.variant_id].valid_from,
                    valid_to=materialized[variant.variant_id].valid_to,
                    period_selector=variant.period_selector,
                )
                for variant in variants
            },
            subject_kind="governed fact track",
            overlap_allows_parallel=False,
        )


class GovernedFactCatalogue(RegistryModel):
    """Governed facts keyed by their stable semantic identity."""

    facts: Annotated[Mapping[FactId, GovernedFact], FROZEN_MAPPING] = Field(default_factory=dict, validate_default=True)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_fact_keys(self) -> GovernedFactCatalogue:
        for fact_id, fact in self.facts.items():
            if fact_id != fact.fact_id:
                raise RegistryValidationError(
                    f"governed fact catalogue key {fact_id!r} does not match fact_id {fact.fact_id!r}",
                )
        return self


def _graph_reaches(start: str, target: str, edges: Mapping[str, tuple[str, ...]]) -> bool:
    pending = list(edges.get(start, ()))
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current not in seen:
            seen.add(current)
            pending.extend(edges.get(current, ()))
    return False
