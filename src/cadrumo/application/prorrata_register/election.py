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

from ...core.prorrata_register import ProrrataProvisionalProvenance
from ...domain.calculations.registry.prorrata_register_catalogue import (
    prorrata_electable_provenances,
    prorrata_referenced_provenances,
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
    electable = prorrata_electable_provenances()
    if provenance not in electable:
        accepted = ", ".join(member.value for member in electable)
        raise ProrrataElectionError(
            ProrrataElectionRefusal.PROVENANCE_NOT_ELECTABLE,
            f"provenance {provenance.value!r} is computed rather than declarable; accepted: {accepted}",
        )
    referenced = provenance in prorrata_referenced_provenances()
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
    "ProrrataElectionError",
    "ProrrataElectionRefusal",
    "validate_prorrata_election",
]
