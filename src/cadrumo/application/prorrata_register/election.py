"""Which provisional prorrata percentages an operator may declare, and on what evidence.

LIVA art. 105 admits four provenances for the provisional percentage, and they
do not all reach the register the same way. Three are declared by the taxpayer;
the fourth is computed. Two of the three stand on a document, and the register
records its reference because the percentage is only defensible with it.

Encoding that in one frontend meant a second one had to restate it, and the
failure is not cosmetic: electing under a provenance the law does not admit, or
recording an authorised percentage with no authorisation, produces a register
entry the taxpayer cannot defend. The rules live here so both readings of art.
105 come from the same place.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from ...core.prorrata_register import ProrrataProvisionalProvenance

#: The provenances a taxpayer states. ``INTERRUMPIDA_TRES_ULTIMOS`` is absent on
#: purpose: art. 105.Cinco's interrupted-activity percentage is COMPUTED from
#: the register's own stored volumes over the last three active years, so
#: accepting it as a declaration would let an operator assert a figure the law
#: says is derived — and a fabricated one would silently replace the
#: computation for that ejercicio.
ELECTABLE_PROVENANCES: Final[tuple[ProrrataProvisionalProvenance, ...]] = (
    ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
    ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
    ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
)

#: The provenances that stand on a document. An AEAT-authorised percentage
#: (art. 105.Dos) has an authorisation; an inicio-de-actividades percentage
#: (art. 105.Tres via art. 111.Dos) has a proposal. Recording either without its
#: reference stores a percentage whose authority cannot be produced later.
REFERENCED_PROVENANCES: Final[frozenset[ProrrataProvisionalProvenance]] = frozenset(
    {
        ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
        ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
    }
)


class ProrrataElectionRefusal(StrEnum):
    """Why an election was refused, so a surface can say which input to fix."""

    PROVENANCE_NOT_ELECTABLE = "provenance_not_electable"
    REFERENCE_REQUIRED = "reference_required"
    REFERENCE_NOT_PERMITTED = "reference_not_permitted"


class ProrrataElectionError(ValueError):
    """Raised when a declared election does not satisfy art. 105.

    Carries the discriminated reason rather than only prose, so an interface
    can name the offending input instead of restating the whole rule.
    """

    def __init__(self, refusal: ProrrataElectionRefusal, message: str) -> None:
        """Record which rule refused the election."""
        super().__init__(message)
        self.refusal = refusal


def validate_prorrata_election(
    *,
    provenance: ProrrataProvisionalProvenance,
    reference: str | None,
) -> tuple[ProrrataProvisionalProvenance, str | None]:
    """Check one declared provenance and its reference against art. 105.

    Args:
        provenance: The provenance the operator declared.
        reference: The authorisation or proposal reference, when supplied.

    Returns:
        The provenance and reference as they should be recorded.

    Raises:
        ProrrataElectionError: When the provenance is computed rather than
            declarable, when a document-backed provenance carries no reference,
            or when a reference accompanies a provenance that has none.
    """
    if provenance not in ELECTABLE_PROVENANCES:
        accepted = ", ".join(member.value for member in ELECTABLE_PROVENANCES)
        raise ProrrataElectionError(
            ProrrataElectionRefusal.PROVENANCE_NOT_ELECTABLE,
            f"provenance {provenance.value!r} is computed rather than declarable; accepted: {accepted}",
        )
    referenced = provenance in REFERENCED_PROVENANCES
    if referenced and (reference is None or not reference.strip()):
        raise ProrrataElectionError(
            ProrrataElectionRefusal.REFERENCE_REQUIRED,
            f"provenance {provenance.value!r} stands on a document and requires its reference",
        )
    if not referenced and reference is not None:
        raise ProrrataElectionError(
            ProrrataElectionRefusal.REFERENCE_NOT_PERMITTED,
            f"provenance {provenance.value!r} carries no document, so a reference cannot be recorded against it",
        )
    return provenance, reference


__all__ = [
    "ELECTABLE_PROVENANCES",
    "REFERENCED_PROVENANCES",
    "ProrrataElectionError",
    "ProrrataElectionRefusal",
    "validate_prorrata_election",
]
