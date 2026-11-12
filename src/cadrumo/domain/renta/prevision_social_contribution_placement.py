"""The Modelo 100 casilla a pension contribution record reaches in one revision, or why it reaches none.

The answer is read from the revision's placement rows, which quote the Modelo
345 design and the Modelo 100 text for each clave and subclave. Nothing here
names a casilla or a year: a refusal is a closed reason, and the caller serves
its words and the door to enter the box as an operator value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.casilla_id import CasillaId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.prevision_social import PrevisionSocialBeneficiario, PrevisionSocialPlacementRefusal
from ..calculations.registry.errors import RegistryValidationError

if TYPE_CHECKING:
    from ..calculations.registry.schema import ModeloRevision
    from .prevision_social_contribution import PrevisionSocialContribution

__all__ = ["ContributionPlacement", "ContributionPlacementRefused", "place_contribution"]


class ContributionPlacement(BaseModel):
    """The casilla a record reaches, with the placement row that says so."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    placement_id: str


class ContributionPlacementRefused(BaseModel):
    """Why a record reaches no casilla; the operator enters the box instead."""

    model_config = STRICT_FROZEN_CONFIG

    reason: PrevisionSocialPlacementRefusal


def place_contribution(
    revision: ModeloRevision,
    record: PrevisionSocialContribution,
) -> ContributionPlacement | ContributionPlacementRefused:
    """Return the casilla ``record`` reaches in ``revision``, or the reason it reaches none.

    ``revision`` is the :class:`ModeloRevision` the record's ejercicio is
    calculated against. A revision that declares no placement at all has no
    Modelo 345 design behind it. A pair the revision does not declare is not
    defined by its design, and is refused as unplaced.
    """
    if record.beneficiary is not PrevisionSocialBeneficiario.TAXPAYER:
        return ContributionPlacementRefused(reason=PrevisionSocialPlacementRefusal.BENEFICIARY_OUT_OF_SCOPE)
    rows = revision.prevision_social_placements
    if not rows:
        return ContributionPlacementRefused(reason=PrevisionSocialPlacementRefusal.DESIGN_NOT_BUNDLED)
    matching = tuple(row for row in rows if row.clave is record.clave and row.subclave is record.subclave)
    if not matching:
        return ContributionPlacementRefused(reason=PrevisionSocialPlacementRefusal.UNPLACED_CLAVE)
    split = tuple(row for row in matching if row.employer_contributed_to_same_plan is not None)
    if split:
        if record.employer_contributed_to_same_plan is None:
            return ContributionPlacementRefused(reason=PrevisionSocialPlacementRefusal.SAME_PLAN_SPLIT_UNSTATED)
        matching = tuple(
            row for row in split if row.employer_contributed_to_same_plan is record.employer_contributed_to_same_plan
        )
    (row,) = matching
    if row.refusal is not None:
        return ContributionPlacementRefused(reason=row.refusal)
    if row.casilla_id is None:
        raise RegistryValidationError(f"placement {row.id!r} declares neither a casilla nor a refusal")
    return ContributionPlacement(casilla_id=row.casilla_id, placement_id=row.id)
