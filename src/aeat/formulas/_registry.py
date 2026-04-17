"""Ruleset registry — maps ``(modelo, period)`` to a :class:`Ruleset`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..errors import AmbiguousPeriodError, MissingRulesetError, RulesetValidationError
from ..models import ModeloCode
from ._period import FiscalPeriod
from ._ruleset import Ruleset

__all__ = ["RulesetRegistry", "get_registry"]


class RulesetRegistry(BaseModel):
    """Immutable collection of rulesets with ``(modelo, period)`` lookup."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    rulesets: tuple[Ruleset, ...] = Field(default_factory=tuple)

    def model_post_init(self, _context: object) -> None:
        by_modelo: dict[ModeloCode, list[Ruleset]] = {}
        for ruleset in self.rulesets:
            by_modelo.setdefault(ruleset.modelo, []).append(ruleset)

        for modelo, group in by_modelo.items():
            for lhs_idx, lhs in enumerate(group):
                for rhs_idx, rhs in enumerate(group):
                    if lhs_idx >= rhs_idx:
                        continue
                    if _spans_overlap(lhs, rhs):
                        raise RulesetValidationError(
                            f"modelo {modelo.value}: rulesets {lhs.ruleset_id!r} and "
                            f"{rhs.ruleset_id!r} have overlapping effective spans"
                        )
        seen_ids: set[str] = set()
        for ruleset in self.rulesets:
            if ruleset.ruleset_id in seen_ids:
                raise RulesetValidationError(f"duplicate ruleset_id {ruleset.ruleset_id!r} in registry")
            seen_ids.add(ruleset.ruleset_id)

    def resolve(self, *, modelo: ModeloCode, period: FiscalPeriod) -> Ruleset:
        """Return the ruleset active for the supplied modelo and period."""
        matches = [
            ruleset
            for ruleset in self.rulesets
            if ruleset.modelo == modelo and ruleset.covers(period.start, period.end)
        ]
        if not matches:
            raise MissingRulesetError(
                f"no ruleset for modelo={modelo.value} period={period.year}"
                + (f" quarter={period.quarter.value}" if period.quarter is not None else "")
            )
        if len(matches) > 1:
            ids = sorted(r.ruleset_id for r in matches)
            raise AmbiguousPeriodError(f"period straddles multiple rulesets for modelo={modelo.value}: {ids!r}")
        return matches[0]


def _spans_overlap(lhs: Ruleset, rhs: Ruleset) -> bool:
    """Return ``True`` when two rulesets' effective spans overlap."""
    lhs_end = lhs.effective_to
    rhs_end = rhs.effective_to
    if lhs_end is None and rhs_end is None:
        return True
    if lhs_end is None:
        return lhs.effective_from <= (rhs_end or lhs.effective_from)
    if rhs_end is None:
        return rhs.effective_from <= lhs_end
    return lhs.effective_from <= rhs_end and rhs.effective_from <= lhs_end


_cached_registry: RulesetRegistry | None = None


def get_registry() -> RulesetRegistry:
    """Return the shared :class:`RulesetRegistry` bundling every ruleset."""
    global _cached_registry
    if _cached_registry is None:
        from ._rulesets import ALL_RULESETS

        _cached_registry = RulesetRegistry(rulesets=ALL_RULESETS)
    return _cached_registry
