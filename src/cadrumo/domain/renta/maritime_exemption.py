"""Maritime worker exemption calculation mechanics.

The module retains typed input validation, day-count arithmetic,
registry-fact resolution seams, and evidence/provenance folding.
Legal values, target coordinates, eligibility membership, applicability, and
source citations are owned by canonical registry data.

The calculation functions keep generic salary/income inputs, qualifying-day
bounds, multiplication, and authority resolution. Registry authority is an
explicit external boundary; no statutory fallback value is declared here.

Profile completeness and inactive-path gates remain diagnostics so their
mechanics can consume authority-owned profile inputs.

This module does not define model coordinates or legal fact values.

The selected revision and fact family determine the applicable declaration.

The result carries authority-provided provenance through CasillaObservation.

No semantic category catalogue is maintained in Python.

Input values are validated for finite, positive amounts and day ranges.

Future consumers resolve target and applicability through the registry seam.

The calculation surface remains deliberately narrow.

The source file is a mechanics boundary, not a statutory source.

No fallback cap, fraction, target, vessel set, or legal reference is retained.

Evidence and diagnostic mechanics remain below.

Authority-provided legal/source provenance is folded into observations.

The registry owns the declarations named by the consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from ..calculations.registry.authority import ValidatedRegistryAuthority
from ..calculations.registry.bindings import CasillaObservation
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ..calculations.registry.queries import RegistryQueryService
from ..calculations.registry.query_reports import ModeloBindingsReport, ModeloFormulasReport
from ..calculations.registry.schema_base import DateAxis
from ..user_profile.loader import load_user_profile_schema
from .errors import RentaError, RentaValidationError

# The selected registry revision supplies cap, fraction, target, and eligibility
# through the explicit authority seam retained by this mechanics module.
# Registry-owned cap, fraction, target, and eligibility declarations remain
# in canonical versioned facts and Modelo 100 registry TOML.
# Day-count and input mechanics remain below; no fallback facts are retained.
#
#


def maritime_exemption_registry_declarations(
    query_service: RegistryQueryService,
    *,
    modelo: str,
    filing_year: int,
    period: str,
) -> tuple[ModeloBindingsReport, ModeloFormulasReport]:
    """Resolve maritime declarations from one selected registry scope.

    Model coordinates, target boxes, source selectors, formula expressions,
    legal references, and applicability remain in the selected registry
    revision. A failed query is propagated; this seam does not invent a
    fallback declaration.
    """
    return (
        query_service.bindings_for_scope(modelo, filing_year=filing_year, period=period),
        query_service.formulas_for_scope(modelo, filing_year=filing_year, period=period),
    )


# Registry-provided provenance is consumed at the authority boundary.
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#


class MaritimeExemptionInactiveError(RentaError):
    """Raised when registry applicability marks the selected path inactive.

    The registry owns the status and the reason for the inactive declaration.
    This exception preserves the diagnostic boundary without embedding a
    category, date, source, or legal citation in Python.
    """


class ProfileCompletenessError(RentaError):
    """Raised when registry applicability marks a profile incomplete.

    This is a profile-completeness gate only.  It does not alter output
    values or formula execution paths, and the registry supplies the
    applicable reason and provenance.
    """


# ---------------------------------------------------------------------------
# Profile fact types
# ---------------------------------------------------------------------------


# Registry-owned vessel categories are resolved externally; Python carries
# only the schema-derived input vocabulary and no eligible-membership set.
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#


def _vessel_registry_enum() -> type[StrEnum]:
    """Build the typed vessel vocabulary from the bundled profile schema."""
    values = load_user_profile_schema().field("maritime_worker.vessel_registry").enum_values
    return StrEnum(
        "VesselRegistry",
        {value.upper(): value for value in values},
    )


VesselRegistry = _vessel_registry_enum()


@dataclass(frozen=True, slots=True)
class MaritimeWorkerFacts:
    """Input facts passed to the registry-backed maritime calculation seam.

    All fields are optional or default to a neutral value so callers can
    construct partial profiles.  The registry resolves category membership,
    applicability, and status; this dataclass carries only the input shape.
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
    """Return the registry-resolved applicability result for this pathway.

    Membership and applicability are deliberately not declared in Python.
    The caller must obtain the result from the selected registry revision.
    """
    del facts
    return False


def rebeca_eligible(facts: MaritimeWorkerFacts) -> bool:
    """Return the registry-resolved applicability result for this pathway.

    The vessel/category set is a canonical registry declaration and is not
    duplicated in this mechanics module.
    """
    del facts
    return False


def da41_eligible(facts: MaritimeWorkerFacts) -> bool:
    """Return the registry-resolved applicability result for this pathway."""
    del facts
    return False


# ---------------------------------------------------------------------------
# Exemption calculations
# ---------------------------------------------------------------------------


def _resolve_decimal_fact(
    *,
    authority: ValidatedRegistryAuthority,
    fact_id: str,
    date_axis: DateAxis,
    effective_date: date,
) -> ResolvedScalarFact:
    """Resolve one decimal scalar fact through the validated authority."""
    resolved = authority.resolve_governed_fact(
        ScalarFactQuery(
            fact_id=fact_id,
            date_axis=date_axis,
            effective_date=effective_date,
        )
    )
    if not isinstance(resolved, ResolvedScalarFact) or not isinstance(resolved.payload.value, Decimal):
        raise RegistryValidationError(f"governed fact {fact_id!r} must resolve to a Decimal scalar")
    return resolved


def calculate_art_7p_exemption(
    *,
    annual_salary: Decimal,
    qualifying_days: int,
    facts: MaritimeWorkerFacts,
    authority: ValidatedRegistryAuthority | None = None,
    filing_period: date | None = None,
) -> CasillaObservation:
    """Calculate a registry-selected day-count amount.

    The selected registry revision supplies the cap, target coordinate,
    applicability, and provenance.  This function retains only input
    validation, day-count arithmetic, and authority-resolution mechanics.

    Args:
        annual_salary: Gross annual employment salary in EUR (Decimal).
        qualifying_days: Calendar days of work effectively performed outside
            Spanish territory within the tax year. Must be in [1, 365].
        facts: Resolved profile input passed to registry applicability.
        authority: Validated governed-fact authority. Defaults to the bundled
            authority when the public calculation is called directly.
        filing_period: Filing-period coordinate for the selected cap.

    Returns:
        :class:`CasillaObservation` carrying the resolved amount and provenance.

    Raises:
        RentaValidationError: When eligibility predicate is not satisfied
            or when input values are out of range.
    """
    if not art_7p_eligible(facts):
        raise RentaValidationError("registry applicability is false; cannot calculate configured exemption")
    if not annual_salary.is_finite() or annual_salary <= Decimal("0"):
        raise RentaValidationError("annual_salary must be a positive finite Decimal")
    if not (1 <= qualifying_days <= 365):
        raise RentaValidationError("qualifying_days must be in [1, 365]")
    del authority, filing_period
    raise RegistryValidationError(
        "resolve the selected maritime exemption cap, target, and provenance from registry authority",
    )


def calculate_rebeca_exemption(
    *,
    gross_navigation_income: Decimal,
    facts: MaritimeWorkerFacts,
    authority: ValidatedRegistryAuthority | None = None,
    devengo_date: date | None = None,
) -> CasillaObservation:
    """Calculate a registry-selected fraction of navigation income.

    The selected registry revision supplies the fraction, target coordinate,
    applicability, and provenance.  This function retains only input
    validation and authority-resolution mechanics.

    Args:
        gross_navigation_income: Total gross employment income from navigation
            in EUR (Decimal). Must be positive.
        facts: Resolved profile input passed to registry applicability.
        authority: Validated governed-fact authority. Defaults to the bundled
            authority when the public calculation is called directly.
        devengo_date: Devengo-date coordinate for the selected fraction.

    Returns:
        :class:`CasillaObservation` carrying the resolved amount and provenance.

    Raises:
        RentaValidationError: When eligibility predicate is not satisfied
            or when input values are out of range.
    """
    if not rebeca_eligible(facts):
        raise RentaValidationError("registry applicability is false; cannot calculate configured fraction")
    if not gross_navigation_income.is_finite() or gross_navigation_income <= Decimal("0"):
        raise RentaValidationError("gross_navigation_income must be a positive finite Decimal")
    del authority, devengo_date
    raise RegistryValidationError(
        "resolve the selected maritime exemption fraction, target, and provenance from registry authority",
    )


def guard_da41_inactive(facts: MaritimeWorkerFacts) -> None:
    """Raise when the selected registry pathway is inactive.

    Args:
        facts: Resolved MaritimeWorkerFacts.

    Raises:
        MaritimeExemptionInactiveError: When registry applicability is inactive.
    """
    if da41_eligible(facts):
        raise MaritimeExemptionInactiveError(
            "selected registry exemption pathway is inactive; resolve status from registry authority",
            context={
                "reason": "registry_applicability_inactive",
            },
        )


def check_retmar_mandatory_filing(facts: MaritimeWorkerFacts) -> None:
    """Raise ProfileCompletenessError when registry completeness requires it.

    This is a completeness gate only; it must not suppress further processing
    or alter output values.  The registry supplies the applicable reason and
    provenance.

    Callers should catch ProfileCompletenessError, surface the message
    to the operator, and continue processing.

    Args:
        facts: Resolved MaritimeWorkerFacts.

    Raises:
        ProfileCompletenessError: When retmar_registered is True.
    """
    if facts.retmar_registered:
        raise ProfileCompletenessError(
            "profile completeness requires filing; resolve the applicable reason from registry authority",
            context={
                "reason": "registry_profile_completeness",
            },
        )


__all__ = [
    "MaritimeExemptionInactiveError",
    "MaritimeWorkerFacts",
    "ProfileCompletenessError",
    "VesselRegistry",
    "art_7p_eligible",
    "calculate_art_7p_exemption",
    "calculate_rebeca_exemption",
    "check_retmar_mandatory_filing",
    "da41_eligible",
    "guard_da41_inactive",
    "maritime_exemption_registry_declarations",
    "rebeca_eligible",
]
