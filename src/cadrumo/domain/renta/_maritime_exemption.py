"""Maritime worker IRPF exemption calculation engine.

Implements the three legally distinct exemption pathways for trabajadores
del mar and the associated profile completeness gate. Each calculation
function returns a :class:`CasillaObservation` carrying the exempt amount
and its full legal provenance.

Active exemption axes (2024/2025):

  Art. 7.p) LIRPF (Ley 35/2006, BOE-A-2006-20764)
    Conditions: foreign-flagged vessel OR international waters; foreign
    entity receiving services; territory with CDI or equivalent income
    tax. Annual cap: 60,100 EUR.
    Formula: min(annual_salary / 365 * qualifying_days, 60_100)

  REBECA 50% exemption (Ley 19/1994, Arts. 73.2 73.3 75.1 75.3, BOE-A-1994-15794)
    Crew of REBECA-registered vessels or scheduled Canary Islands routes.
    Exempt 50% is excluded from the Modelo 111 withholding base by employer.

Inactive axis (future variant):

  DA 41 LIRPF (Ley 35/2006 DA 41, added by Ley 26/2014 BOE-A-2014-12327)
    50% exemption for tuna fleet crew. Requires EU state-aid clearance
    not granted as of 2024/2025. Engine raises MaritimeExemptionInactiveError
    when the selector resolves True so it is never silently applied.

Profile completeness gate (not a calculation axis):

  RETM mandatory filing (Ley 35/2006 Art. 96, BOE-A-2006-20764)
    Since January 2023 all RETMAR-registered workers must file IRPF
    regardless of income level. Raises ProfileCompletenessError; it
    does not alter casilla values.

Provisions outside scope:
  The transitional withholding rule from January 2015 (a different
  disposicion adicional with no maritime content) must not be cited as a
  maritime exemption anchor in any registry or code artefact.
  Art. 17.1.d) / Art. 9 RIRPF daily allowance caps apply generically;
  TEAC narrowed their scope for crew whose ordinary workplace is the vessel
  (STS 954/2020, STS 3185/2021). No special per-diem exists in any currently
  applicable LIRPF provision for these workers.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from ...core import CasillaId, validated_casilla_id
from ...core.external_constants import ART_7P_EXEMPTION_CAP_EUR, REBECA_MARITIME_EXEMPTION_FRACTION
from ..calculations.registry.bindings import CasillaObservation
from ..calculations.registry.ids import LegalRefId, SourceRefId
from .errors import RentaError, RentaValidationError

# Casilla in Modelo 100 that receives exempt income (renta exenta section).
# Art. 7.p) and REBECA both flow through the existing renta exenta casilla
# for base liquidable general (0525). No new casilla identifiers exist for
# maritime workers; the existing renta exenta casilla is the only target.
# Source: aeat-dr-100-2024-dictionary (semantic_role irpf_rentas_exentas_base_general).
RENTA_EXENTA_CASILLA: CasillaId = validated_casilla_id("0525", surface="RENTA_EXENTA_CASILLA")

# Legal references carried through every observation — sourced from the
# trabajador_del_mar.toml binding entries.
_ART_7P_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-35-2006:art-7",)
_REBECA_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-19-1994:art-75",)
_DA41_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-35-2006:da-41",)
_RETMAR_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-35-2006:art-96",)

_ART_7P_SOURCE_REFS: tuple[SourceRefId, ...] = ("boe-lirpf-art-7-authority",)
_REBECA_SOURCE_REFS: tuple[SourceRefId, ...] = ("boe-ley-19-1994-art-75-authority",)


class MaritimeExemptionInactiveError(RentaError):
    """Raised when the DA 41 selector resolves True for a trabajador del mar.

    DA 41 LIRPF requires prior EU state-aid clearance under TFEU rules.
    That clearance has not been granted as of 2024/2025. The engine raises
    this error instead of silently producing an exempt-income observation,
    which would be legally incorrect output.

    Once EU clearance is granted a follow-up task must flip the binding
    status in trabajador_del_mar.toml and add oracle-backed tests; no
    code change in this module is required.

    Legal authority: Ley 35/2006 DA 41 BOE-A-2006-20764 (as amended by
    Ley 26/2014 BOE-A-2014-12327).
    """


class ProfileCompletenessError(RentaError):
    """Raised when a RETMAR-registered worker's profile is presented for filing.

    Since 2023, all workers registered in the maritime special Social
    Security regime must file an IRPF declaration regardless of income
    level (Ley 35/2006 art. 96, BOE-A-2006-20764).
    This is a profile completeness gate — it does not alter casilla values
    or formula execution paths.

    Callers should surface the mandatory-filing status to the operator in
    CLI JSON output; the warning must not suppress further processing.
    """


# ---------------------------------------------------------------------------
# Profile fact types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MaritimeWorkerFacts:
    """Resolved profile facts that gate maritime exemption pathway selection.

    All fields are optional and default to the non-triggering value so that
    callers building partial profiles do not require every fact to be present.
    A profile without worker_class = "trabajador_del_mar" is unaffected by
    any predicate in this module.

    Attributes:
        worker_class: Must be ``"trabajador_del_mar"`` to activate any
            maritime exemption pathway.
        vessel_flag: ``"ES"`` (Spanish-flagged) or ``"foreign"``.
        waters_type: ``"national"`` or ``"international"``.
        vessel_registry: One of ``"REBECA"``, ``"rebeca_eu_eea"``,
            ``"scheduled_canary_route"``, or ``None``.
        tuna_fleet: Whether the vessel is a qualifying tuna fleet vessel
            (DA 41 selector; currently always inactive).
        pending_eu_clearance: Mirrors the DA 41 TOML selector field.
            Must be True alongside tuna_fleet to trigger the inactive gate.
        retmar_registered: Whether the taxpayer is in the RETMAR register.
            Drives the mandatory-filing completeness check only.
    """

    worker_class: str | None = None
    vessel_flag: Literal["ES", "foreign"] | None = None
    waters_type: Literal["national", "international"] | None = None
    vessel_registry: Literal["REBECA", "rebeca_eu_eea", "scheduled_canary_route"] | None = None
    tuna_fleet: bool = False
    pending_eu_clearance: bool = False
    retmar_registered: bool = False


# ---------------------------------------------------------------------------
# Binding selector predicates
# ---------------------------------------------------------------------------


def art_7p_eligible(facts: MaritimeWorkerFacts) -> bool:
    """Return True when Art. 7.p) LIRPF applies to the worker profile.

    Conditions (conjunctive):
    - worker_class == "trabajador_del_mar"
    - vessel_flag == "foreign" OR waters_type == "international"

    International waters qualify for foreign-flagged
    vessels per AEAT accepted practice, confirmed by TEAR Galicia
    December 2024 for Galician fishing crew and by Supreme Court doctrine
    extended April 2025 to military Navy in NATO/UN sea operations.

    Legal authority: Ley 35/2006 Art. 7.p) BOE-A-2006-20764.
    """
    if facts.worker_class != "trabajador_del_mar":
        return False
    return facts.vessel_flag == "foreign" or facts.waters_type == "international"


def rebeca_eligible(facts: MaritimeWorkerFacts) -> bool:
    """Return True when the REBECA 50% exemption applies to the worker profile.

    Conditions:
    - worker_class == "trabajador_del_mar"
    - vessel_registry in {"REBECA", "rebeca_eu_eea", "scheduled_canary_route"}

    The "rebeca_eu_eea" value covers the 2021 extension to crews of
    REBECA-registered company vessels enrolled in other EU/EEA member state
    registries (Ley 19/1994 Art. 75.1).

    Legal authority: Ley 19/1994 Arts. 73.2 73.3 75.1 75.3 BOE-A-1994-15794.
    """
    if facts.worker_class != "trabajador_del_mar":
        return False
    return facts.vessel_registry in {"REBECA", "rebeca_eu_eea", "scheduled_canary_route"}


def da41_eligible(facts: MaritimeWorkerFacts) -> bool:
    """Return True when the DA 41 tuna-fleet selector resolves.

    DA 41 requires:
    - worker_class == "trabajador_del_mar"
    - tuna_fleet == True
    - pending_eu_clearance == True

    The binding is currently inactive_pending_eu_clearance. Callers must
    check the return value and raise MaritimeExemptionInactiveError when
    True; this predicate is deliberately separated from the error-raising
    path so it can be tested independently.

    Legal authority: Ley 35/2006 DA 41 BOE-A-2006-20764 (as amended by
    Ley 26/2014 BOE-A-2014-12327).
    """
    if facts.worker_class != "trabajador_del_mar":
        return False
    return facts.tuna_fleet and facts.pending_eu_clearance


# ---------------------------------------------------------------------------
# Exemption calculations
# ---------------------------------------------------------------------------


def calculate_art_7p_exemption(
    *,
    annual_salary: Decimal,
    qualifying_days: int,
    facts: MaritimeWorkerFacts,
) -> CasillaObservation:
    """Calculate the Art. 7.p) exempt amount and return a :class:`CasillaObservation`.

    Formula (Ley 35/2006 Art. 7.p) BOE-A-2006-20764):
        exempt_amount = min(annual_salary / 365 * qualifying_days, 60_100)

    The observation carries legal_refs and source_refs from the registry
    binding entry so the provenance is traceable from calculation to CLI emit.

    Args:
        annual_salary: Gross annual employment salary in EUR (Decimal).
        qualifying_days: Calendar days of work effectively performed outside
            Spanish territory within the tax year. Must be in [1, 365].
        facts: Resolved MaritimeWorkerFacts. art_7p_eligible must be True;
            raises RentaValidationError otherwise.

    Returns:
        :class:`CasillaObservation` for the renta exenta casilla with the exempt
        amount and full legal provenance.

    Raises:
        RentaValidationError: When eligibility predicate is not satisfied
            or when input values are out of range.
    """
    if not art_7p_eligible(facts):
        raise RentaValidationError("art_7p_eligible predicate is False; cannot calculate Art. 7.p) exemption")
    if not annual_salary.is_finite() or annual_salary <= Decimal("0"):
        raise RentaValidationError("annual_salary must be a positive finite Decimal")
    if not (1 <= qualifying_days <= 365):
        raise RentaValidationError("qualifying_days must be in [1, 365]")

    raw_exempt = annual_salary / Decimal("365") * Decimal(qualifying_days)
    exempt_amount = min(raw_exempt, ART_7P_EXEMPTION_CAP_EUR)

    return CasillaObservation(
        casilla_id=RENTA_EXENTA_CASILLA,
        value=exempt_amount,
        formula_id=None,
        op=None,
        operand_refs=(),
        operand_casilla_refs=(),
        operand_values=(),
        legal_refs=_ART_7P_LEGAL_REFS,
        source_refs=_ART_7P_SOURCE_REFS,
        absent_by_design=False,
    )


def calculate_rebeca_exemption(
    *,
    gross_navigation_income: Decimal,
    facts: MaritimeWorkerFacts,
) -> CasillaObservation:
    """Calculate the REBECA 50% exempt amount and return a typed CasillaObservation.

    Formula (Ley 19/1994 Arts. 73-75 BOE-A-1994-15794):
        exempt_amount = gross_navigation_income * 0.50

    The 50% fraction is statutory and not variable by election.

    Args:
        gross_navigation_income: Total gross employment income from navigation
            in EUR (Decimal). Must be positive.
        facts: Resolved MaritimeWorkerFacts. rebeca_eligible must be True;
            raises RentaValidationError otherwise.

    Returns:
        :class:`CasillaObservation` for the renta exenta casilla with the exempt
        amount and full legal provenance.

    Raises:
        RentaValidationError: When eligibility predicate is not satisfied
            or when input values are out of range.
    """
    if not rebeca_eligible(facts):
        raise RentaValidationError("rebeca_eligible predicate is False; cannot calculate REBECA exemption")
    if not gross_navigation_income.is_finite() or gross_navigation_income <= Decimal("0"):
        raise RentaValidationError("gross_navigation_income must be a positive finite Decimal")

    exempt_amount = gross_navigation_income * REBECA_MARITIME_EXEMPTION_FRACTION

    return CasillaObservation(
        casilla_id=RENTA_EXENTA_CASILLA,
        value=exempt_amount,
        formula_id=None,
        op=None,
        operand_refs=(),
        operand_casilla_refs=(),
        operand_values=(),
        legal_refs=_REBECA_LEGAL_REFS,
        source_refs=_REBECA_SOURCE_REFS,
        absent_by_design=False,
    )


def guard_da41_inactive(facts: MaritimeWorkerFacts) -> None:
    """Raise MaritimeExemptionInactiveError if DA 41 selector resolves True.

    This function must be called before any code path that would produce
    DA 41 exempt-income output. DA 41 requires EU state-aid clearance not
    granted as of 2024/2025; silently producing an exempt amount would be
    legally incorrect.

    Args:
        facts: Resolved MaritimeWorkerFacts.

    Raises:
        MaritimeExemptionInactiveError: When da41_eligible returns True.
    """
    if da41_eligible(facts):
        raise MaritimeExemptionInactiveError(
            "DA 41 LIRPF exemption is inactive: EU state-aid clearance has not been granted "
            "as of 2024/2025. AEAT confirms non-applicability in official 2024 guidance. "
            "Activate only after EU clearance is granted (Ley 35/2006 DA 41 BOE-A-2006-20764, "
            "added by Ley 26/2014 BOE-A-2014-12327).",
            context={
                "binding_id": "da41-tuna-fleet-inactive",
                "legal_ref": _DA41_LEGAL_REFS[0],
            },
        )


def check_retmar_mandatory_filing(facts: MaritimeWorkerFacts) -> None:
    """Raise ProfileCompletenessError when retmar_registered is True.

    Since 2023, all workers registered in the maritime special Social
    Security regime must file an IRPF declaration regardless of income
    level (Ley 35/2006 art. 96, BOE-A-2006-20764).
    This is a completeness gate only — it must not suppress further
    processing or alter casilla values.

    Callers should catch ProfileCompletenessError, surface the message
    to the operator, and continue processing.

    Args:
        facts: Resolved MaritimeWorkerFacts.

    Raises:
        ProfileCompletenessError: When retmar_registered is True.
    """
    if facts.retmar_registered:
        raise ProfileCompletenessError(
            "RETMAR mandatory filing: this worker is registered in RETMAR. "
            "Since 2023, workers registered in the maritime special Social Security "
            "regime must file an IRPF "
            "declaration regardless of income level "
            "(Ley 35/2006 Art. 96 BOE-A-2006-20764).",
            context={
                "legal_ref": _RETMAR_LEGAL_REFS[0],
            },
        )


__all__ = [
    "ART_7P_EXEMPTION_CAP_EUR",
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
