"""Count the people covered by the illness-insurance deduction.

The registry owns the dated statutory population, age boundary, disability
threshold, and coverage-limb applicability. This module contains only the
typed result and the eventual mechanical reconstruction boundary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ..calculations.registry.authority import bundled_authority
from ..calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    ResolvedScalarFact,
    ScalarFactQuery,
)
from ..calculations.registry.queries import RegistryQueryService
from ..calculations.registry.schema_base import DateAxis

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


@dataclass(frozen=True, slots=True)
class _SeguroEnfermedadRegistryDeclarations:
    """The selected, dated declarations needed by this mechanical reducer."""

    disability_minimum_grade: int
    insured_child_maximum_age: int
    applicability: Mapping[str, str]

    def required(self, key: str) -> str:
        """Return one required applicability declaration without a local default."""
        value = self.applicability.get(key)
        if value is None or not value.strip():
            raise ValueError(f"insurance applicability declaration {key!r} is empty or absent")
        return value


def _resolve_seguro_enfermedad_registry_declarations(
    filing_year: int,
) -> _SeguroEnfermedadRegistryDeclarations:
    """Resolve the selected Modelo 100 and dated insurance fact declarations."""
    effective_date = date(filing_year, 12, 31)
    authority = bundled_authority()
    query_service = RegistryQueryService(authority)
    selected_model = query_service.describe_modelo("100", as_of=effective_date)
    if not selected_model.revision:
        raise ValueError("selected Modelo 100 registry revision is unavailable")

    resolved_grade = authority.resolve_governed_fact(
        ScalarFactQuery(
            fact_id="rirpf-art-72-disability-minimum-grade",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    resolved_age = authority.resolve_governed_fact(
        ScalarFactQuery(
            fact_id="lirpf-art-30-insured-child-maximum-age",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    resolved_applicability = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="lirpf-art-30-insured-coverage-applicability",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved_grade, ResolvedScalarFact):
        raise TypeError("insurance disability threshold must resolve as a scalar fact")
    if not isinstance(resolved_age, ResolvedScalarFact):
        raise TypeError("insurance child age boundary must resolve as a scalar fact")
    if not isinstance(resolved_applicability, ResolvedMappingFact):
        raise TypeError("insurance applicability must resolve as a mapping fact")
    try:
        disability_minimum_grade = int(resolved_grade.payload.value)
        insured_child_maximum_age = int(resolved_age.payload.value)
    except (TypeError, ValueError) as exc:
        raise ValueError("insurance scalar declarations must be integral") from exc
    applicability: dict[str, str] = {}
    for entry in resolved_applicability.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise TypeError("insurance applicability entries must be string-to-string")
        applicability[entry.key] = entry.value
    declarations = _SeguroEnfermedadRegistryDeclarations(
        disability_minimum_grade=disability_minimum_grade,
        insured_child_maximum_age=insured_child_maximum_age,
        applicability=MappingProxyType(applicability),
    )
    declarations.required("insured_population.taxpayer")
    declarations.required("insured_population.spouse")
    declarations.required("insured_population.child")
    declarations.required("insured_population.child.death_gate")
    declarations.required("coverage_limb.discapacidad")
    declarations.required("coverage_limb.general")
    return declarations


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


def _limb_for(
    grade: int | None,
    declarations: _SeguroEnfermedadRegistryDeclarations,
) -> str:
    """Resolve the registry-owned coverage limb for a declared grade."""
    if grade is not None and grade >= declarations.disability_minimum_grade:
        return "discapacidad"
    return "general"


def _insured_child(
    descendant: DescendantInfo,
    filing_year: int,
    declarations: _SeguroEnfermedadRegistryDeclarations,
) -> bool:
    """Resolve registry-owned child coverage applicability."""
    declarations.required("insured_population.child")
    declarations.required("insured_population.child.death_gate")
    if not descendant.convive_con_contribuyente:
        return False
    if descendant.age_at_year_end(filing_year) >= declarations.insured_child_maximum_age:
        return False
    return descendant.death_date is None or descendant.death_date.year >= filing_year


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
    declarations = _resolve_seguro_enfermedad_registry_declarations(filing_year)
    counts = {limb: 0 for limb in SeguroEnfermedadInsuredCounts.model_fields}

    def add_insured(grade: int | None) -> None:
        limb = _limb_for(grade, declarations)
        if limb not in counts:
            raise ValueError(f"insurance applicability selected unknown coverage limb {limb!r}")
        counts[limb] += 1

    declarations.required("insured_population.taxpayer")
    add_insured(taxpayer_discapacidad_grado)
    if has_spouse:
        declarations.required("insured_population.spouse")
        add_insured(spouse_discapacidad_grado)
    for descendant in descendientes:
        if _insured_child(descendant, filing_year, declarations):
            add_insured(descendant.discapacidad_grado)
    return SeguroEnfermedadInsuredCounts.model_validate(counts)


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
    from .descendant_facts import descendant_list_from_facts

    stored_facts = {str(path): str(value) for path, value in fact_index.items() if value is not None}
    descendientes = descendant_list_from_facts(stored_facts)
    return count_seguro_enfermedad_insured(
        descendientes,
        filing_year=filing_year,
        taxpayer_discapacidad_grado=_declared_grado(
            fact_index,
            "renta_taxpayer.disability_grade",
        ),
        spouse_discapacidad_grado=_declared_grado(
            fact_index,
            "renta_spouse.disability_grade",
        ),
        has_spouse=any(str(path).startswith("renta_spouse.") for path in fact_index),
    )


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
