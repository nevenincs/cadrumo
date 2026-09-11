"""Count the people covered by the illness-insurance deduction.

The registry owns the dated statutory population, age boundary, disability
threshold, and coverage-limb applicability. This module contains only the
typed result and the eventual mechanical reconstruction boundary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG

if TYPE_CHECKING:
    from .descendant import DescendantInfo

__all__ = [
    "SeguroEnfermedadInsuredCounts",
    "count_seguro_enfermedad_insured",
    "seguro_enfermedad_insured_counts_from_facts",
]

#: Prefix the stored descendant facts share, matching the one the canonical
#: descendant reconstruction reads.
_DESCENDANT_FACT_PREFIX: Final[str] = "renta_family.descendiente."


class SeguroEnfermedadInsuredCounts(BaseModel):
    """How many insured persons fall under each statutory limit.

    Attributes:
        general: Persons carrying the ordinary limit.
        discapacidad: Persons carrying the disability limit.
    """

    model_config = STRICT_FROZEN_CONFIG

    general: int = Field(default=0, ge=0)
    discapacidad: int = Field(default=0, ge=0)

    @property
    def total(self) -> int:
        """Return how many insured persons were counted in all.

        Returns:
            The sum of both limbs.
        """
        return self.general + self.discapacidad


def _limb_for(grade: int | None) -> str:
    """Resolve the registry-owned coverage limb for a declared grade."""
    raise NotImplementedError("insurance coverage-limb applicability is unresolved")


def _insured_child(descendant: DescendantInfo, filing_year: int) -> bool:
    """Resolve registry-owned child coverage applicability."""
    raise NotImplementedError("insurance child-coverage applicability is unresolved")


def count_seguro_enfermedad_insured(
    descendientes: Sequence[DescendantInfo] = (),
    *,
    filing_year: int,
    taxpayer_discapacidad_grado: int | None = None,
    spouse_discapacidad_grado: int | None = None,
    has_spouse: bool = False,
) -> SeguroEnfermedadInsuredCounts:
    """Count the Art. 30.2.5.a insured persons, split by the limit each carries.

    Args:
        descendientes: The typed descendant records supplied to the resolver.
        filing_year: The filing-period coordinate supplied to the resolver.
        taxpayer_discapacidad_grado: The contribuyente's declared grado, if any.
        spouse_discapacidad_grado: The conyuge's declared grado, if any.
        has_spouse: The relationship-presence fact supplied to the resolver.

    Returns:
        The per-limb counts.
    """
    # TODO(fact-relocation): resolve insurance eligibility thresholds and coverage rules from registry authority
    raise NotImplementedError("insurance eligibility is unresolved")


def seguro_enfermedad_insured_counts_from_facts(
    fact_index: Mapping[str, object],
    *,
    filing_year: int,
) -> SeguroEnfermedadInsuredCounts:
    """Count the Art. 30.2.5.a insured persons straight from stored profile facts.

    Lives in the domain rather than in either application package because both of
    them need it and neither may import the other. It reads the descendants through
    :func:`descendant_list_from_facts`, the same reconstruction every other consumer
    of these facts uses, so there is one interpretation of the stored shape.

    The registry-owned applicability map determines which stored relationship
    facts contribute to each coverage limb.

    Args:
        fact_index: The stored profile facts.
        filing_year: Ejercicio whose year-end settles each child's age.

    Returns:
        The per-limb counts.
    """
    # TODO(fact-relocation): resolve insurance eligibility thresholds and coverage rules from registry authority
    raise NotImplementedError("insurance eligibility is unresolved")


def _declared_grado(fact_index: Mapping[str, object], path: str) -> int | None:
    """Return a declared discapacidad grado as an int, or ``None`` when unusable.

    An unparseable stored grado resolves to ``None`` rather than to zero. Zero is a
    declaration that the person has no discapacidad; absence is a declaration about
    nothing. Both take the ordinary limb, but only because that is the lawful
    default, not because the two could not be told apart.
    """
    raw = fact_index.get(path)
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None
