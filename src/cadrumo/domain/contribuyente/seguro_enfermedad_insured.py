"""Who LIRPF art. 30.2.5.a insures, and which of its two limits each of them carries.

The article, verbatim from the bundled consolidated corpus:

    a) Las primas de seguro de enfermedad satisfechas por el contribuyente en la
    parte correspondiente a su propia cobertura y a la de su conyuge e hijos
    menores de veinticinco anos que convivan con el. El limite maximo de deduccion
    sera de 500 euros por cada una de las personas senaladas anteriormente o de
    1.500 euros por cada una de ellas con discapacidad.

Two separate questions live in that sentence and this module keeps them apart.
MEMBERSHIP is settled by the first sentence -- the contribuyente, the conyuge, and
hijos under twenty-five who cohabit. THE LIMB is settled by the second -- 500, or
1.500 for a person with discapacidad. Discapacidad does not widen membership: a
thirty-year-old child with discapacidad is outside this article entirely, however
the minimo por descendientes treats them.

**This population is deliberately NOT the Art. 58.1 one, and borrowing it would
over-grant twice.** Art. 58.1 admits a descendant on cohabitation OR assimilated
economic dependency, and on age under twenty-five OR any discapacidad. Both limbs
are wider than this article's, so
:meth:`~domain.contribuyente.RentaFamilyProfile.descendientes_eligible_minimum`
would count a non-cohabiting dependent child and an over-25 child with
discapacidad into a cap the article does not extend to either.

RIRPF art. 72 settles who qualifies for the higher limb: *tendran la consideracion
de persona con discapacidad aquellos contribuyentes con un grado de minusvalia
igual o superior al 33 por ciento*.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ._descendant_facts import descendant_list_from_facts
from ._renta_codes import RentaMaritalStatus

if TYPE_CHECKING:
    from ._descendant import DescendantInfo

__all__ = [
    "DISCAPACIDAD_MINIMUM_GRADE",
    "SeguroEnfermedadInsuredCounts",
    "count_seguro_enfermedad_insured",
    "seguro_enfermedad_insured_counts_from_facts",
]

#: Prefix the stored descendant facts share, matching the one the canonical
#: descendant reconstruction reads.
_DESCENDANT_FACT_PREFIX: Final[str] = "renta_family.descendiente."

#: RIRPF art. 72: a grado de minusvalia at or above this qualifies for the higher
#: limb. The shipped ``discapacidad_grado`` is a closed ``Literal[0, 33, 65]``, so
#: the threshold partitions it exactly and no percentage parsing is involved.
DISCAPACIDAD_MINIMUM_GRADE: Final[int] = 33

#: LIRPF art. 30.2.5.a covers "hijos menores de veinticinco anos". Declared here
#: rather than borrowed from the Art. 58.1 constant of the same value: the two
#: articles happen to agree on the number today and are not the same rule, so a
#: change to one must not silently move the other.
MAX_AGE_INSURED_CHILD: Final[int] = 25


class SeguroEnfermedadInsuredCounts(BaseModel):
    """How many insured persons fall under each of the article's two limits.

    Attributes:
        general: Persons carrying the ordinary 500 euro limit.
        discapacidad: Persons carrying the 1.500 euro limit.
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
    """Return which limb a person with this declared grado carries.

    An UNDECLARED grado resolves to the ordinary limb rather than to nothing.
    Membership is already settled by the time this is asked, so the question is
    only which limit applies, and the article grants the ordinary limit absent the
    condition the higher one requires. Resolving an unknown grado to "neither"
    would drop a real insured person out of the cap entirely, which costs the
    filer 500 euros of allowance and is a worse answer than the one that shipped
    before either limb existed.
    """
    if grade is not None and grade >= DISCAPACIDAD_MINIMUM_GRADE:
        return "discapacidad"
    return "general"


def _insured_child(descendant: DescendantInfo, filing_year: int) -> bool:
    """Return whether this descendant is inside the article's insured population.

    Membership, not limb. A child who died before the filing year is out: birth
    date alone goes on satisfying "menores de veinticinco anos" indefinitely, and
    the sibling Art. 58 predicate gates on exactly this for the same reason.
    """
    if descendant.death_date is not None and descendant.death_date.year < filing_year:
        return False
    if not descendant.convive_con_contribuyente:
        return False
    return descendant.age_at_year_end(filing_year) < MAX_AGE_INSURED_CHILD


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
        descendientes: The declared descendants. Empty is normal: the
            contribuyente is still counted, because the article insures their own
            cover whether or not any family facts exist.
        filing_year: Ejercicio whose year-end settles each child's age.
        taxpayer_discapacidad_grado: The contribuyente's declared grado, if any.
        spouse_discapacidad_grado: The conyuge's declared grado, if any.
        has_spouse: Whether a conyuge is declared at all. Kept separate from the
            grado so that an undeclared spouse is not conjured into the count by
            a grado that happens to be absent for both reasons.

    Returns:
        The per-limb counts.
    """
    tally = {"general": 0, "discapacidad": 0}
    tally[_limb_for(taxpayer_discapacidad_grado)] += 1
    if has_spouse:
        tally[_limb_for(spouse_discapacidad_grado)] += 1
    for descendant in descendientes:
        if _insured_child(descendant, filing_year):
            tally[_limb_for(descendant.discapacidad_grado)] += 1
    return SeguroEnfermedadInsuredCounts(
        general=tally["general"],
        discapacidad=tally["discapacidad"],
    )


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

    The conyuge limb reads the marital status against CASADO specifically. The
    article insures "su conyuge", and a pareja de hecho is not one; admitting the
    wider partnered set would extend the cap to a person the article does not name.

    Args:
        fact_index: The stored profile facts.
        filing_year: Ejercicio whose year-end settles each child's age.

    Returns:
        The per-limb counts.
    """
    descendant_facts = {
        key: str(value)
        for key, value in fact_index.items()
        if key.startswith(_DESCENDANT_FACT_PREFIX)
    }
    marital_status = str(fact_index.get("renta_taxpayer.marital_status", "")).strip()
    return count_seguro_enfermedad_insured(
        descendant_list_from_facts(descendant_facts),
        filing_year=filing_year,
        taxpayer_discapacidad_grado=_declared_grado(fact_index, "renta_taxpayer.disability_grade"),
        spouse_discapacidad_grado=_declared_grado(fact_index, "renta_spouse.disability_grade"),
        has_spouse=marital_status == RentaMaritalStatus.CASADO.value,
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
