"""Ruleset registry — maps ``(modelo, variant, period)`` to a :class:`Ruleset`.

The registry key is ``(modelo, variant, period)``. The ``variant`` axis
disambiguates partial (``summary``), alternate (``full``), and regional
(``canarias``) encodings of the same ``modelo + period``.

Overlap checking runs **per ``(modelo, variant)`` slot**: two
``variant="default"`` rulesets may not overlap, but a
``variant="canarias"`` ruleset may share an effective range with a
``variant="default"`` one.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ...core.errors import AmbiguousPeriodError, MissingRulesetError, RulesetValidationError
from ...core.logging import get_logger
from ..modelos import ModeloCode
from ._period import FiscalPeriod
from ._ruleset import Ruleset

_logger = get_logger(__name__)

__all__ = ["RulesetRegistry", "get_registry"]


class RulesetRegistry(BaseModel):
    """Immutable collection of rulesets with ``(modelo, variant, period)`` lookup.

    Attributes:
        rulesets: Every :class:`aeat.domain.formulas.Ruleset` known to
            the registry.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    rulesets: tuple[Ruleset, ...] = Field(default_factory=tuple)

    def model_post_init(self, _context: object) -> None:
        """Reject overlapping rulesets for the same ``(modelo, variant)`` slot."""
        # Overlap check runs per (modelo, variant) slot.
        by_slot: dict[tuple[ModeloCode, str], list[Ruleset]] = {}
        for ruleset in self.rulesets:
            by_slot.setdefault((ruleset.modelo, ruleset.variant), []).append(ruleset)

        for (modelo, variant), group in by_slot.items():
            for lhs_idx, lhs in enumerate(group):
                for rhs_idx, rhs in enumerate(group):
                    if lhs_idx >= rhs_idx:
                        continue
                    if _spans_overlap(lhs, rhs):
                        raise RulesetValidationError(
                            f"modelo {modelo.value} variant {variant!r}: "
                            f"rulesets {lhs.ruleset_id!r} and {rhs.ruleset_id!r} "
                            f"have overlapping effective spans"
                        )
        seen_ids: set[str] = set()
        for ruleset in self.rulesets:
            if ruleset.ruleset_id in seen_ids:
                raise RulesetValidationError(f"duplicate ruleset_id {ruleset.ruleset_id!r} in registry")
            seen_ids.add(ruleset.ruleset_id)

    def resolve(
        self,
        *,
        modelo: ModeloCode,
        period: FiscalPeriod,
        variant: str = "default",
    ) -> Ruleset:
        """Return the ruleset active for the supplied modelo / variant / period.

        Args:
            modelo: The :class:`aeat.domain.modelos.ModeloCode` to look
                up.
            period: The :class:`aeat.domain.formulas.FiscalPeriod` whose
                ``start``..``end`` span must be covered by the ruleset.
            variant: Disambiguates partial, alternate, and regional
                encodings of the same ``modelo + period``. Defaults to
                ``"default"`` so existing callers stay unchanged; pass
                ``"canarias"`` or ``"summary"`` to reach the
                corresponding variant slots.

        Returns:
            The single matching :class:`aeat.domain.formulas.Ruleset`.

        Raises:
            :exc:`aeat.core.errors.MissingRulesetError`: When no ruleset
                covers the requested slot.
            :exc:`aeat.core.errors.AmbiguousPeriodError`: When the period
                straddles multiple rulesets in the same slot.
        """
        matches = [
            ruleset
            for ruleset in self.rulesets
            if ruleset.modelo == modelo and ruleset.variant == variant and ruleset.covers(period.start, period.end)
        ]
        if not matches:
            raise MissingRulesetError(
                f"no ruleset for modelo={modelo.value} variant={variant!r} "
                f"period={period.year}" + (f" quarter={period.quarter.value}" if period.quarter is not None else "")
            )
        if len(matches) > 1:
            ids = sorted(r.ruleset_id for r in matches)
            raise AmbiguousPeriodError(
                f"period straddles multiple rulesets for modelo={modelo.value} variant={variant!r}: {ids!r}"
            )
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

        _logger.debug("initialising ruleset registry from ALL_RULESETS")
        _cached_registry = RulesetRegistry(rulesets=ALL_RULESETS)
        _logger.debug("ruleset registry ready: %d rulesets", len(_cached_registry.rulesets))
    return _cached_registry
