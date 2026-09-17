"""Maritime worker IRPF exemption calculation engine.

Implements the legally distinct exemption pathways for trabajadores del mar
and the associated profile completeness gate. Each calculation returns a
:class:`CasillaObservation` whose amount parameter and provenance come from
the governed facts of the selected authority.

Active pathways:

  Art. 7.p) LIRPF (Ley 35/2006, BOE-A-2006-20764)
    Foreign-flagged vessel or international waters. The annual cap is the
    ``lirpf-art-7p-exemption-cap`` governed fact.
    Formula: min(annual_salary / 365 * qualifying_days, cap)

  REBECA exemption (Ley 19/1994, Arts. 73.2 73.3 75.1 75.3, BOE-A-1994-15794)
    Crew of REBECA-registered vessels or scheduled Canary Islands routes. The
    exempt fraction is the ``rebeca-maritime-exemption-fraction`` governed fact.

Inactive pathway:

  DA 41 LIRPF (Ley 35/2006 DA 41, added by Ley 26/2014 BOE-A-2014-12327)
    Tuna fleet crew. Requires EU state-aid clearance that has not been
    granted, so the engine refuses instead of silently applying it.

Profile completeness gate (not a calculation pathway):

  RETM mandatory filing (Ley 35/2006 Art. 96, BOE-A-2006-20764)
    RETMAR-registered workers must file IRPF regardless of income level.

The pathway selectors mirror the ``trabajador_del_mar`` exemption binding
category in the registry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.time.clock import today_madrid
from ..calculations.registry.authority import bundled_indexed_authority
from ..calculations.registry.bindings import CasillaObservation
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ..calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from ..calculations.registry.ids import LegalRefId
from ..calculations.registry.schema_base import DateAxis
from .errors import RentaError, RentaValidationError

# Modelo 100 renta exenta casilla both active pathways flow into; the registry
# formula ``renta-maritime-exempt-income-0525`` declares the same target.
RENTA_EXENTA_CASILLA: CasillaId = validated_casilla_id("0525", surface="RENTA_EXENTA_CASILLA")

_MARITIME_WORKER_CLASS: Final = "trabajador_del_mar"
_ELIGIBLE_VESSEL_REGISTRIES: Final = frozenset({"REBECA", "rebeca_eu_eea", "scheduled_canary_route"})
_DA41_BINDING_ID: Final = "da41-tuna-fleet-inactive"
_DA41_LEGAL_REF: Final[LegalRefId] = "ley-35-2006:da-41"
_RETMAR_LEGAL_REF: Final[LegalRefId] = "ley-35-2006:art-96"

_ART_7P_EXEMPTION_CAP_FACT_ID: Final = "lirpf-art-7p-exemption-cap"
_REBECA_EXEMPTION_FRACTION_FACT_ID: Final = "rebeca-maritime-exemption-fraction"
_DAYS_IN_YEAR: Final = 365


class MaritimeExemptionInactiveError(RentaError):
    """Raised when the DA 41 tuna-fleet selector resolves for a trabajador del mar.

    DA 41 LIRPF requires prior EU state-aid clearance that has not been
    granted, so the engine refuses rather than producing exempt income.
    """


class ProfileCompletenessError(RentaError):
    """Raised when a RETMAR-registered worker's profile is presented for filing.

    This is a profile-completeness gate only. It does not alter output values
    or formula execution paths.
    """


# ---------------------------------------------------------------------------
# Profile fact types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MaritimeWorkerFacts:
    """Resolved profile facts that gate maritime exemption pathway selection.

    All fields default to the non-triggering value so callers can construct
    partial profiles. A profile whose ``worker_class`` is not
    ``"trabajador_del_mar"`` is unaffected by every selector here.
    """

    worker_class: str | None = None
    vessel_flag: str | None = None
    waters_type: str | None = None
    vessel_registry: str | None = None
    tuna_fleet: bool = False
    pending_eu_clearance: bool = False
    retmar_registered: bool = False


# ---------------------------------------------------------------------------
# Binding selector predicates
# ---------------------------------------------------------------------------


def art_7p_eligible(facts: MaritimeWorkerFacts) -> bool:
    """Return whether Art. 7.p) LIRPF applies to the worker profile.

    A trabajador del mar on a foreign-flagged vessel or in international
    waters (Ley 35/2006 Art. 7.p), BOE-A-2006-20764).
    """
    if facts.worker_class != _MARITIME_WORKER_CLASS:
        return False
    return facts.vessel_flag == "foreign" or facts.waters_type == "international"


def rebeca_eligible(facts: MaritimeWorkerFacts) -> bool:
    """Return whether the REBECA exemption applies to the worker profile.

    A trabajador del mar on a REBECA vessel, a REBECA company vessel in another
    EU/EEA register, or a scheduled Canary Islands route (Ley 19/1994
    Arts. 73.2 73.3 75.1 75.3, BOE-A-1994-15794).
    """
    if facts.worker_class != _MARITIME_WORKER_CLASS:
        return False
    return facts.vessel_registry in _ELIGIBLE_VESSEL_REGISTRIES


def da41_eligible(facts: MaritimeWorkerFacts) -> bool:
    """Return whether the inactive DA 41 tuna-fleet selector resolves.

    Kept separate from :func:`guard_da41_inactive` so the selector is testable
    on its own (Ley 35/2006 DA 41 BOE-A-2006-20764).
    """
    if facts.worker_class != _MARITIME_WORKER_CLASS:
        return False
    return facts.tuna_fleet and facts.pending_eu_clearance


# ---------------------------------------------------------------------------
# Exemption calculations
# ---------------------------------------------------------------------------


def _with_authority[T](authority: GovernedFactSource | None, resolve: Callable[[GovernedFactSource], T]) -> T:
    """Resolve under the given authority, else the scoped one, else a published lease."""
    selected = authority or governed_facts_in_scope()
    if selected is not None:
        return resolve(selected)
    with bundled_indexed_authority().operation() as operation:
        return resolve(operation)


def _resolve_decimal_fact(
    authority: GovernedFactSource | None,
    *,
    fact_id: str,
    date_axis: DateAxis,
    effective_date: date,
) -> tuple[Decimal, ResolvedScalarFact]:
    """Resolve one decimal scalar fact and return its value with its provenance."""

    def resolve(source: GovernedFactSource) -> tuple[Decimal, ResolvedScalarFact]:
        resolved = source.resolve_governed_fact(
            ScalarFactQuery(fact_id=fact_id, date_axis=date_axis, effective_date=effective_date)
        )
        if not isinstance(resolved, ResolvedScalarFact) or not isinstance(resolved.payload.value, Decimal):
            raise RegistryValidationError(f"governed fact {fact_id!r} must resolve to a Decimal scalar")
        return resolved.payload.value, resolved

    return _with_authority(authority, resolve)


def _exempt_observation(value: Decimal, resolved: ResolvedScalarFact) -> CasillaObservation:
    return CasillaObservation(
        casilla_id=RENTA_EXENTA_CASILLA,
        value=value,
        legal_refs=resolved.legal_refs,
        source_refs=resolved.source_refs,
    )


def calculate_art_7p_exemption(
    *,
    annual_salary: Decimal,
    qualifying_days: int,
    facts: MaritimeWorkerFacts,
    authority: GovernedFactSource | None = None,
    filing_period: date | None = None,
) -> CasillaObservation:
    """Calculate the Art. 7.p) exempt amount.

    Formula (Ley 35/2006 Art. 7.p) BOE-A-2006-20764):
        exempt_amount = min(annual_salary / 365 * qualifying_days, cap)

    Args:
        annual_salary: Gross annual employment salary in EUR (Decimal).
        qualifying_days: Calendar days of work abroad in the tax year, within
            the ordinary calendar-day input range.
        facts: Resolved profile facts; :func:`art_7p_eligible` must hold.
        authority: Governed-fact authority. Defaults to the scoped authority,
            else the published one.
        filing_period: Filing-period coordinate for the cap; defaults to today.

    Returns:
        :class:`CasillaObservation` carrying the exempt amount and provenance.

    Raises:
        RentaValidationError: When eligibility predicate is not satisfied
            or when input values are out of range.
    """
    if not art_7p_eligible(facts):
        raise RentaValidationError("art_7p_eligible predicate is False; cannot calculate Art. 7.p) exemption")
    if not annual_salary.is_finite() or annual_salary <= Decimal("0"):
        raise RentaValidationError("annual_salary must be a positive finite Decimal")
    if not (1 <= qualifying_days <= _DAYS_IN_YEAR):
        raise RentaValidationError("qualifying_days must be within the ordinary calendar-day input range")
    cap, resolved_cap = _resolve_decimal_fact(
        authority,
        fact_id=_ART_7P_EXEMPTION_CAP_FACT_ID,
        date_axis=DateAxis.FILING_PERIOD,
        effective_date=filing_period or today_madrid(),
    )
    prorated = annual_salary / Decimal(_DAYS_IN_YEAR) * Decimal(qualifying_days)
    return _exempt_observation(min(prorated, cap), resolved_cap)


def calculate_rebeca_exemption(
    *,
    gross_navigation_income: Decimal,
    facts: MaritimeWorkerFacts,
    authority: GovernedFactSource | None = None,
    devengo_date: date | None = None,
) -> CasillaObservation:
    """Calculate the REBECA exempt amount.

    Formula (Ley 19/1994 Arts. 73-75 BOE-A-1994-15794):
        exempt_amount = gross_navigation_income * fraction

    Args:
        gross_navigation_income: Total gross employment income from navigation
            in EUR (Decimal). Must be positive.
        facts: Resolved profile facts; :func:`rebeca_eligible` must hold.
        authority: Governed-fact authority. Defaults to the scoped authority,
            else the published one.
        devengo_date: Devengo-date coordinate for the fraction; defaults to today.

    Returns:
        :class:`CasillaObservation` carrying the exempt amount and provenance.

    Raises:
        RentaValidationError: When eligibility predicate is not satisfied
            or when input values are out of range.
    """
    if not rebeca_eligible(facts):
        raise RentaValidationError("rebeca_eligible predicate is False; cannot calculate REBECA exemption")
    if not gross_navigation_income.is_finite() or gross_navigation_income <= Decimal("0"):
        raise RentaValidationError("gross_navigation_income must be a positive finite Decimal")
    fraction, resolved_fraction = _resolve_decimal_fact(
        authority,
        fact_id=_REBECA_EXEMPTION_FRACTION_FACT_ID,
        date_axis=DateAxis.DEVENGO_DATE,
        effective_date=devengo_date or today_madrid(),
    )
    return _exempt_observation(gross_navigation_income * fraction, resolved_fraction)


def guard_da41_inactive(facts: MaritimeWorkerFacts) -> None:
    """Refuse a DA 41 profile, whose exemption lacks EU state-aid clearance.

    Call before any path that could produce DA 41 exempt income; applying it
    silently would be legally incorrect output.

    Args:
        facts: Resolved MaritimeWorkerFacts.

    Raises:
        MaritimeExemptionInactiveError: When :func:`da41_eligible` holds.
    """
    if da41_eligible(facts):
        raise MaritimeExemptionInactiveError(
            "DA 41 LIRPF exemption is inactive: EU state-aid clearance has not been granted. "
            "Activate only after EU clearance is granted (Ley 35/2006 DA 41 BOE-A-2006-20764, "
            "added by Ley 26/2014 BOE-A-2014-12327).",
            context={
                "binding_id": _DA41_BINDING_ID,
                "legal_ref": _DA41_LEGAL_REF,
            },
        )


def check_retmar_mandatory_filing(facts: MaritimeWorkerFacts) -> None:
    """Raise ProfileCompletenessError for a RETMAR-registered worker.

    RETMAR-registered workers must file IRPF regardless of income level
    (Ley 35/2006 Art. 96, BOE-A-2006-20764). This is a completeness gate only;
    it must not suppress further processing or alter output values.

    Callers should catch ProfileCompletenessError, surface the message
    to the operator, and continue processing.

    Args:
        facts: Resolved MaritimeWorkerFacts.

    Raises:
        ProfileCompletenessError: When retmar_registered is True.
    """
    if facts.retmar_registered:
        raise ProfileCompletenessError(
            "RETMAR mandatory filing: workers registered in the maritime special Social Security "
            "regime must file an IRPF declaration regardless of income level "
            "(Ley 35/2006 Art. 96 BOE-A-2006-20764).",
            context={
                "legal_ref": _RETMAR_LEGAL_REF,
            },
        )


__all__ = [
    "RENTA_EXENTA_CASILLA",
    "MaritimeExemptionInactiveError",
    "MaritimeWorkerFacts",
    "ProfileCompletenessError",
    "art_7p_eligible",
    "calculate_art_7p_exemption",
    "calculate_rebeca_exemption",
    "check_retmar_mandatory_filing",
    "da41_eligible",
    "guard_da41_inactive",
    "rebeca_eligible",
]
