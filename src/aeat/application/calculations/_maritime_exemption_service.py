"""Application-layer service for maritime worker IRPF exemption resolution.

Bridges the domain-layer maritime exemption calculation functions with the
application-layer observation pipeline. Accepts resolved MaritimeWorkerFacts
and income inputs, routes to the appropriate domain calculation function, and
returns typed :class:`CasillaObservation` rows alongside a flat casilla_values
mapping.

The flat mapping is for human readability; the typed observation list is the
canonical contract per aeat-calculation-grounding.

Calling conventions::

  result = resolve_maritime_exemption(
      facts=MaritimeWorkerFacts(
          worker_class="trabajador_del_mar",
          vessel_flag="foreign",
          waters_type="international",
      ),
      annual_salary=Decimal("36500"),
      qualifying_days=180,
  )
  # result.observations: tuple of CasillaObservation with legal_refs
  # result.casilla_values: {casilla_id: Decimal} derived view

Error handling::

  MaritimeExemptionInactiveError  — DA 41 selector resolved True (inactive)
  ProfileCompletenessError      — RETMAR mandatory filing gate triggered
  RentaValidationError            — input validation failed

Callers are responsible for catching ProfileCompletenessError, surfacing
its message to the operator, and continuing processing. It is not a blocking
error.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ...domain.calculations.registry import CasillaObservation
from ...domain.renta._errors import RentaValidationError
from ...domain.renta._maritime_exemption import (
    MaritimeWorkerFacts,
    art_7p_eligible,
    calculate_art_7p_exemption,
    calculate_rebeca_exemption,
    check_retmar_mandatory_filing,
    guard_da41_inactive,
    rebeca_eligible,
)


class MaritimeExemptionResult(BaseModel):
    """Typed result for a maritime worker exemption resolution.

    Carries the ordered tuple of CasillaObservation rows with full
    provenance and a derived flat mapping for human readability.
    The observations field is the canonical contract; callers must not
    persist or transmit only the flat casilla_values view.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    observations: tuple[CasillaObservation, ...] = Field(default_factory=tuple)
    retmar_mandatory_filing: bool = False

    @property
    def casilla_values(self) -> Mapping[str, Decimal]:
        """Derived flat view: casilla_id -> Decimal.

        Provided for human readability only. The canonical storage is
        ``observations``; this view must not be used for persistence or
        wire payloads.
        """
        return {obs.casilla_id: obs.value for obs in self.observations}


def resolve_maritime_exemption(
    *,
    facts: MaritimeWorkerFacts,
    annual_salary: Decimal | None = None,
    qualifying_days: int | None = None,
    gross_navigation_income: Decimal | None = None,
) -> MaritimeExemptionResult:
    """Resolve the applicable maritime exemption pathway and produce typed observations.

    Evaluates the binding selector predicates for Art. 7.p) and REBECA in
    order. For each eligible pathway the corresponding domain calculation
    function is called and its CasillaObservation is appended to the result.

    The DA 41 inactive guard runs before any calculation — if the DA 41
    selector resolves True (which it currently always will when tuna_fleet +
    pending_eu_clearance are both set on a trabajador del mar profile),
    MaritimeExemptionInactiveError is raised and no observations are produced.

    The RETMAR mandatory-filing gate is checked independently. When
    retmar_registered is True, ProfileCompletenessError is raised. Callers
    should catch it, surface the message to the operator, and continue
    processing. The gate does not suppress exemption calculations.

    Args:
        facts: Resolved MaritimeWorkerFacts from the user profile.
        annual_salary: Gross annual salary in EUR. Required when Art. 7.p)
            is potentially eligible.
        qualifying_days: Days of work outside Spain in the tax year. Required
            when Art. 7.p) is potentially eligible.
        gross_navigation_income: Total gross navigation income in EUR.
            Required when REBECA is potentially eligible.

    Returns:
        :class:`MaritimeExemptionResult` with typed observations and flat view.

    Raises:
        RentaValidationError: Eligibility predicate mismatch or invalid input.
            The DA 41 inactive guard and RETMAR completeness gate (described
            above) raise their own exceptions from the called guards.
    """
    # DA 41 inactive guard runs first — must not silently produce output.
    guard_da41_inactive(facts)

    # RETMAR completeness gate — callers catch and surface to operator.
    check_retmar_mandatory_filing(facts)

    observations: list[CasillaObservation] = []

    if art_7p_eligible(facts):
        if annual_salary is None or qualifying_days is None:
            raise RentaValidationError(
                "annual_salary and qualifying_days are required when Art. 7.p) eligibility applies",
            )
        obs = calculate_art_7p_exemption(
            annual_salary=annual_salary,
            qualifying_days=qualifying_days,
            facts=facts,
        )
        observations.append(obs)

    if rebeca_eligible(facts):
        if gross_navigation_income is None:
            raise RentaValidationError("gross_navigation_income is required when REBECA eligibility applies")
        obs = calculate_rebeca_exemption(
            gross_navigation_income=gross_navigation_income,
            facts=facts,
        )
        observations.append(obs)

    return MaritimeExemptionResult(
        observations=tuple(observations),
        retmar_mandatory_filing=facts.retmar_registered,
    )


__all__ = [
    "MaritimeExemptionResult",
    "resolve_maritime_exemption",
]
