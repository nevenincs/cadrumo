"""Derive the art. 23.2 LIRPF reduction facts of a Modelo 100 from the profile's leases.

The registry's casilla 0150 formula reads two engine-owned profile paths: whether
the reduction reaches the ejercicio's lease, and the regime or tier that sets its
rate. This module computes them from the lease rows of the profile and the dated
registry data, through :func:`~cadrumo.domain.renta.rental_reduction_derivation.derive_rental_reduction`.

The two paths are always decided here. Where the derivation refuses, both stay
absent so the box is unresolved rather than reduced by a guessed rate, and a
diagnostic names the reason and the door that records the missing lease fact.
Without a lease in the ejercicio and without declared rental income there is
nothing to reduce, and no diagnostic is raised.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final

from ...core.aggregation import BindingSourceKind
from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...domain.calculations.registry.rental_reduction import (
    resolve_rental_reduction_art232_rules,
    resolve_rental_reduction_art232_tier_catalogue,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.contribuyente.inmueble_facts import arrendamientos_from_facts
from ...domain.renta.rental_reduction_derivation import (
    RentalReductionDerivation,
    RentalReductionRefusal,
    derive_rental_reduction,
    leases_active_in,
)
from ...domain.user_profile.registry_contract import profile_binding_selectors
from ...domain.user_profile.values import UserProfileFactValue
from ..aggregation.source_mesh import CalculationSourceDiagnostic

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = [
    "RENTAL_REDUCTION_APLICABLE_PATH",
    "RENTAL_REDUCTION_TIER_PATH",
    "RentalReductionFacts",
    "inject_derived_rental_reduction_facts",
]

RENTAL_REDUCTION_APLICABLE_PATH: Final = "renta_capital_inmobiliario.reduccion_art_23_2_aplicable"
RENTAL_REDUCTION_TIER_PATH: Final = "renta_capital_inmobiliario.reduccion_art_23_2_tier"
_DERIVED_PATHS: Final = (RENTAL_REDUCTION_APLICABLE_PATH, RENTAL_REDUCTION_TIER_PATH)
_INCOME_CATEGORIES_PATH: Final = "taxpayer_type.irpf_income_categories"
_RENTAL_INCOME_CATEGORY: Final = "capital_inmobiliario"
_REDUCTION_CASILLA: Final = "0150"
_LEASE_DOOR: Final = "aeat config profile arrendamiento edit"
_LEASE_ADD_DOOR: Final = "aeat config profile arrendamiento add"

_REFUSAL_MESSAGES: Final[Mapping[RentalReductionRefusal, str]] = {
    RentalReductionRefusal.NO_LEASE: (
        "the profile declares rental income but records no lease active in the ejercicio, "
        "so the art. 23.2 reduction cannot be derived"
    ),
    RentalReductionRefusal.SEVERAL_LEASES: (
        "more than one lease is active in the ejercicio; the art. 23.2 reduction is derived per contract "
        "and this return computes it for one lease only"
    ),
    RentalReductionRefusal.LEASE_UNREADABLE: "a lease row of the profile does not cohere as a lease",
    RentalReductionRefusal.USO_VIVIENDA_UNSTATED: "the lease does not state whether it lets a dwelling",
    RentalReductionRefusal.ZONA_TENSIONADA_UNSTATED: (
        "the lease does not state whether the dwelling is in a tensioned residential-market zone"
    ),
    RentalReductionRefusal.LAU_17_6_UNSTATED: (
        "the lease is in a tensioned residential-market zone and does not state whether it breaches "
        "art. 17.6 of the Ley de Arrendamientos Urbanos"
    ),
    RentalReductionRefusal.MIXED_TENANT_AGES: (
        "only some of the lease's tenants are aged 18 to 35; the 70 per cent reduction then reaches only "
        "their proportional share of the income, which no recorded fact gives"
    ),
}


@dataclass(frozen=True, slots=True)
class RentalReductionFacts:
    """The derived paths this injector decided and the diagnostics it raised."""

    decided_paths: tuple[str, ...] = ()
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()


def _declares_rental_income(fact_index: Mapping[str, UserProfileFactValue]) -> bool:
    raw = str(fact_index.get(_INCOME_CATEGORIES_PATH, ""))
    return _RENTAL_INCOME_CATEGORY in {token.strip() for token in raw.split(",")}


def _consuming_binding_id(snapshot: RegistrySnapshot) -> str | None:
    for binding in snapshot.revision.bindings:
        if binding.source is BindingSourceKind.PROFILE and RENTAL_REDUCTION_TIER_PATH in profile_binding_selectors(
            binding.provider
        ):
            return binding.id
    return None


def _refusal_diagnostic(
    refusal: RentalReductionRefusal,
    *,
    lease: int | None,
    snapshot: RegistrySnapshot,
    bucket_id: str,
    resolver_id: str,
) -> CalculationSourceDiagnostic:
    message = _REFUSAL_MESSAGES[refusal]
    if lease is not None:
        message = f"lease {lease}: {message}"
    binding_id = _consuming_binding_id(snapshot)
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=BindingSourceKind.PROFILE.value,
        resolver_id=resolver_id,
        binding_id=binding_id,
        casilla_id=_REDUCTION_CASILLA,
        source_ref=f"profile:{bucket_id}:binding:{binding_id or RENTAL_REDUCTION_TIER_PATH}",
        message=message,
        remedy=_LEASE_ADD_DOOR if refusal is RentalReductionRefusal.NO_LEASE else _LEASE_DOOR,
    )


def _derive(
    fact_index: Mapping[str, UserProfileFactValue],
    *,
    snapshot: RegistrySnapshot,
    devengo: date,
    operation: PinnedAuthorityOperation,
) -> RentalReductionDerivation | None:
    try:
        leases = arrendamientos_from_facts(fact_index)
    except ProfileAnswerTypeError:
        return RentalReductionDerivation(aplicable=None, refusal=RentalReductionRefusal.LEASE_UNREADABLE)
    active = leases_active_in(leases, year=devengo.year)
    if not active and not _declares_rental_income(fact_index):
        return None
    rules = resolve_rental_reduction_art232_rules(
        revision_id=snapshot.revision.id,
        devengo=devengo,
        operation=operation,
    )
    outcome = derive_rental_reduction(active, devengo=devengo, rules=rules)
    if outcome.tier is not None and outcome.tier != rules.legacy_tier:
        resolve_rental_reduction_art232_tier_catalogue(effective_date=devengo, authority=operation).require(
            outcome.tier
        )
    return outcome


def inject_derived_rental_reduction_facts(
    fact_index: dict[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    declared_selectors: frozenset[str],
    *,
    bucket_id: str,
    resolver_id: str,
    operation: PinnedAuthorityOperation,
) -> RentalReductionFacts:
    """Write the reduction's applicability and tier for the snapshot's ejercicio into ``fact_index``.

    Runs only where the revision declares a binding on either path. A stored
    value at either path is engine-owned, so it is discarded before deriving.
    """
    if not any(path in declared_selectors for path in _DERIVED_PATHS):
        return RentalReductionFacts()
    for path in _DERIVED_PATHS:
        fact_index.pop(path, None)
    outcome = _derive(
        fact_index,
        snapshot=snapshot,
        devengo=date(snapshot.filing_year, 12, 31),
        operation=operation,
    )
    if outcome is None:
        return RentalReductionFacts(decided_paths=_DERIVED_PATHS)
    if outcome.refusal is not None:
        diagnostic = _refusal_diagnostic(
            outcome.refusal, lease=outcome.lease, snapshot=snapshot, bucket_id=bucket_id, resolver_id=resolver_id
        )
        return RentalReductionFacts(decided_paths=_DERIVED_PATHS, diagnostics=(diagnostic,))
    if outcome.aplicable is not None:
        fact_index[RENTAL_REDUCTION_APLICABLE_PATH] = outcome.aplicable
    if outcome.tier is not None:
        fact_index[RENTAL_REDUCTION_TIER_PATH] = str(outcome.tier)
    return RentalReductionFacts(decided_paths=_DERIVED_PATHS)
