"""Modelo 840 IAE net-turnover exemption semantics.

See Also:
    :data:`~core.external_constants.MODELO_840_IAE_CIFRA_NEGOCIOS_EXEMPTION_THRESHOLD_EUR`
        Legal threshold constant for the strict art. 82.1.c INCN gate.
    :mod:`~application.calculations.tests.test_modelo_840_iae_continuity`
        Multi-year enrollment proof that persists two annual assessments through
        the real calculation observation store.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from ...core.external_constants import MODELO_840_IAE_CIFRA_NEGOCIOS_EXEMPTION_THRESHOLD_EUR
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG


class Modelo840IaeExemptionStatus(StrEnum):
    """Turnover-based IAE exemption status under TRLRHL art. 82.1.c."""

    EXEMPT = "exempt"
    NOT_EXEMPT = "not_exempt"


class Modelo840IaeExemptionAssessment(BaseModel):
    """One annual Modelo 840 IAE turnover-threshold assessment.

    The assessment covers only the art. 82.1.c ``importe neto de la cifra de
    negocios`` exemption. Other art. 82 exemptions, such as the natural-person
    and first-two-period exemptions, are separate legal pathways.

    See Also:
        :class:`Modelo840IaeExemptionStatus`
            Closed status vocabulary carried by each annual assessment.
    """

    model_config = STRICT_FROZEN_CONFIG

    filing_year: FilingYear
    importe_neto_cifra_negocios_eur: Decimal = Field(ge=Decimal("0"))
    threshold_eur: Decimal = Field(
        default=MODELO_840_IAE_CIFRA_NEGOCIOS_EXEMPTION_THRESHOLD_EUR,
        gt=Decimal("0"),
    )
    status: Modelo840IaeExemptionStatus
    legal_refs: tuple[str, ...] = ("rdl-2-2004:art-82", "rdl-2-2004:art-90")

    @property
    def is_exempt(self) -> bool:
        """Return whether the annual INCN is within the art. 82.1.c exemption."""
        return self.status is Modelo840IaeExemptionStatus.EXEMPT


def assess_modelo_840_iae_cifra_negocios_exemption(
    *,
    filing_year: int,
    importe_neto_cifra_negocios_eur: Decimal,
) -> Modelo840IaeExemptionAssessment:
    """Assess the strict Modelo 840 IAE art. 82.1.c turnover exemption.

    TRLRHL art. 82.1.c exempts the covered entities only when their net turnover
    is below 1,000,000 EUR. Equality is outside the exemption.

    See Also:
        :class:`Modelo840IaeExemptionAssessment`
            Frozen result carrier returned by this assessment helper.
    """
    status = (
        Modelo840IaeExemptionStatus.EXEMPT
        if importe_neto_cifra_negocios_eur < MODELO_840_IAE_CIFRA_NEGOCIOS_EXEMPTION_THRESHOLD_EUR
        else Modelo840IaeExemptionStatus.NOT_EXEMPT
    )
    return Modelo840IaeExemptionAssessment(
        filing_year=filing_year,
        importe_neto_cifra_negocios_eur=importe_neto_cifra_negocios_eur,
        status=status,
    )


__all__ = [
    "Modelo840IaeExemptionAssessment",
    "Modelo840IaeExemptionStatus",
    "assess_modelo_840_iae_cifra_negocios_exemption",
]
