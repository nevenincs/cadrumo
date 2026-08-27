"""DT 12ª LIRPF plan-de-pensiones capital-rescate reducción.

The 40% reducción on the part of a plan-de-pensiones capital rescate attributable
to contributions made on or before 31-12-2006 (LIRPF Disposición Transitoria 12ª).
:func:`compute_dt12_reduccion_plan_pensiones` accepts :class:`~decimal.Decimal`
amounts, applies :data:`~cadrumo.core.external_constants.DT12_RESCATE_REDUCCION_RATE`,
rounds with :func:`cadrumo.core.money.round_to_cents`, and raises
:class:`PensionReduccionError` for invalid preconditions.

DT 12ª apartado 3 (added by Ley 26/2014, ``BOE-A-2014-12327``) restricts the whole
transitional régimen — and therefore the 40% reducción — to prestaciones percibidas
within a time window measured from the contingencia year.
:func:`dt12_regime_window_eligibility` is the pure predicate implementing the three
verbatim apartado-3 branches; it is consumed by the calculate-shortcut path to
fact-gate the injection (withhold the reducción when the declared years prove the
window closed), never by forking the core compute.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from ...core.external_constants import (
    DT12_CLIFF_LAST_YEAR,
    DT12_GENERAL_WINDOW_FOLLOWING_YEARS,
    DT12_RESCATE_REDUCCION_RATE,
    DT12_TRANSITIONAL_CONTINGENCIA_FIRST_YEAR,
    DT12_TRANSITIONAL_CONTINGENCIA_LAST_YEAR,
    DT12_TRANSITIONAL_WINDOW_FOLLOWING_YEARS,
)
from ...core.money import round_to_cents
from .errors import PensionReduccionError


def compute_dt12_reduccion_plan_pensiones(
    *,
    gross_rescate: Decimal,
    aportaciones_pre_2007: Decimal,
    aportaciones_totales: Decimal,
) -> Decimal:
    """Compute the DT 12ª LIRPF 40% reducción for a plan-de-pensiones capital rescate.

    Formula (LIRPF DT 12ª): ``pre_2007 / totales * gross_rescate * 40%``. The result
    is rounded to 2 decimal places (money-2 per the registry convention).

    Raises:
        PensionReduccionError: When ``aportaciones_totales`` is zero or negative
            (division-by-zero guard), when any input is negative, or when
            ``aportaciones_pre_2007`` exceeds ``aportaciones_totales`` (DT 12ª
            apartado 2 scopes the reduced part to contributions made up to
            31-12-2006, a subset of the total, so its share cannot exceed 1).
    """
    if aportaciones_totales <= Decimal(0):
        raise PensionReduccionError(
            f"aportaciones_totales must be positive; got {aportaciones_totales}",
            context={"field": "aportaciones_totales", "value": str(aportaciones_totales)},
        )
    if gross_rescate < Decimal(0):
        raise PensionReduccionError(
            f"gross_rescate must be non-negative; got {gross_rescate}",
            context={"field": "gross_rescate", "value": str(gross_rescate)},
        )
    if aportaciones_pre_2007 < Decimal(0):
        raise PensionReduccionError(
            f"aportaciones_pre_2007 must be non-negative; got {aportaciones_pre_2007}",
            context={"field": "aportaciones_pre_2007", "value": str(aportaciones_pre_2007)},
        )
    if aportaciones_pre_2007 > aportaciones_totales:
        raise PensionReduccionError(
            "aportaciones_pre_2007 must not exceed aportaciones_totales "
            f"(DT 12ª apartado 2: the pre-2007 part is a subset of total contributions); "
            f"got pre_2007={aportaciones_pre_2007}, totales={aportaciones_totales}",
            context={
                "field": "aportaciones_pre_2007",
                "value": str(aportaciones_pre_2007),
                "aportaciones_totales": str(aportaciones_totales),
            },
        )

    reduccion = (aportaciones_pre_2007 / aportaciones_totales) * gross_rescate * DT12_RESCATE_REDUCCION_RATE
    return round_to_cents(reduccion)


class Dt12WindowBranch(StrEnum):
    """Which LIRPF DT 12ª apartado-3 branch governs a rescate's eligibility window.

    Attributes:
        GENERAL: Contingencia in 2015 or later — the general rule: eligible in
            the ejercicio the contingencia occurs plus the two following.
        TRANSITIONAL_2011_2014: Contingencia in 2011–2014 — eligible through the
            end of the eighth following ejercicio.
        CLIFF_2010_OR_EARLIER: Contingencia in 2010 or earlier — eligible only
            through the 31-12-2018 cliff.
    """

    GENERAL = "general"
    TRANSITIONAL_2011_2014 = "transitional_2011_2014"
    CLIFF_2010_OR_EARLIER = "cliff_2010_or_earlier"


@dataclass(frozen=True, slots=True)
class Dt12WindowEligibility:
    """Typed verdict of the LIRPF DT 12ª apartado-3 time-window predicate.

    Attributes:
        contingencia_year: The year the contingencia (retirement, disability,
            death) occurred, as declared by the operator.
        rescate_year: The year the prestación is percibida (normally the filing
            year).
        branch: The :class:`Dt12WindowBranch` the contingencia year selects.
        eligible: Whether the rescate falls inside the apartado-3 window and may
            therefore apply the 40% reducción.
        eligible_through_year: The last ejercicio in which a rescate for this
            contingencia year may still apply the régimen.
    """

    contingencia_year: int
    rescate_year: int
    branch: Dt12WindowBranch
    eligible: bool
    eligible_through_year: int


def dt12_regime_window_eligibility(
    *,
    contingencia_year: int,
    rescate_year: int,
) -> Dt12WindowEligibility:
    """Evaluate the LIRPF DT 12ª apartado-3 time-window eligibility (pure predicate).

    Apartado 4 (added by Ley 26/2014 art. 1.85, ``BOE-A-2014-12327``) restricts
    the transitional régimen — and therefore the 40% reducción — to prestaciones
    percibidas within a window measured from the contingencia year:

    - Contingencia in 2015 or later (general rule): eligible in the ejercicio the
      contingencia occurs "o en los dos ejercicios siguientes", i.e.
      ``contingencia_year <= rescate_year <= contingencia_year + 2``.
    - Contingencia in 2011–2014: eligible "hasta la finalización del octavo
      ejercicio siguiente", i.e.
      ``contingencia_year <= rescate_year <= contingencia_year + 8``.
    - Contingencia in 2010 or earlier: eligible "hasta el 31 de diciembre de
      2018", i.e. ``contingencia_year <= rescate_year <= 2018``.

    A rescate percibida before the contingencia year (``rescate_year <
    contingencia_year``) is never eligible: the window opens with the
    contingency.

    Args:
        contingencia_year: The year the contingencia occurred.
        rescate_year: The year the prestación is percibida.

    Returns:
        A :class:`Dt12WindowEligibility` verdict carrying the governing branch,
        the eligibility flag, and the last eligible ejercicio.

    Raises:
        PensionReduccionError: When either year is not a positive four-digit-era
            year (a defensive guard against transposed or unset inputs).
    """
    for field_name, value in (("contingencia_year", contingencia_year), ("rescate_year", rescate_year)):
        if value < 1900 or value > 2200:
            raise PensionReduccionError(
                f"{field_name} must be a plausible calendar year (1900–2200); got {value}",
                context={"field": field_name, "value": str(value)},
            )

    if contingencia_year <= 2010:
        branch = Dt12WindowBranch.CLIFF_2010_OR_EARLIER
        eligible_through_year = DT12_CLIFF_LAST_YEAR
    elif DT12_TRANSITIONAL_CONTINGENCIA_FIRST_YEAR <= contingencia_year <= DT12_TRANSITIONAL_CONTINGENCIA_LAST_YEAR:
        branch = Dt12WindowBranch.TRANSITIONAL_2011_2014
        eligible_through_year = contingencia_year + DT12_TRANSITIONAL_WINDOW_FOLLOWING_YEARS
    else:
        branch = Dt12WindowBranch.GENERAL
        eligible_through_year = contingencia_year + DT12_GENERAL_WINDOW_FOLLOWING_YEARS

    eligible = contingencia_year <= rescate_year <= eligible_through_year
    return Dt12WindowEligibility(
        contingencia_year=contingencia_year,
        rescate_year=rescate_year,
        branch=branch,
        eligible=eligible,
        eligible_through_year=eligible_through_year,
    )
