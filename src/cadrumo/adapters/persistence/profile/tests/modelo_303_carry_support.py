"""Modelo 303 carry-chain calculation helpers shared by the cross-period carry tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from .....domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    resolve_available_bound_inputs_by_casilla_id,
)
from .....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from .....domain.calculations.registry.ids import RelationId
from .....domain.calculations.registry.tests.relation_fixture import relation_prefill_values_as_binding_values
from .published_authority_support import published_authority_operation

__all__ = [
    "AUTOCONSUMO_PROMOTOR_BASE_BINDING",
    "CARRY_BINDING",
    "LEDGER_CUOTA_BINDINGS",
    "MODELO",
    "STATE_ATTRIBUTION_RATIO_BINDING",
    "calculate_303",
    "registry_observation",
]

MODELO = "303"
CARRY_BINDING = "modelo-303-compensacion-pendiente-anteriores"

#: Profile-gap workaround bindings: the direct-calculate path does not run the
#: profile resolver, so each is supplied explicitly. Zero autoconsumo del promotor
#: (LIVA art. 9.1.c / 79.4) and a 100 state attribution ratio model a standard
#: (non-foral) filer (LIVA art. 115, Ley 12/2002 art. 29). This is a registry-gap
#: workaround, not a fix of the registry file.
AUTOCONSUMO_PROMOTOR_BASE_BINDING = "modelo-303-autoconsumo-promotor-base"
STATE_ATTRIBUTION_RATIO_BINDING = "modelo-303-profile-state-attribution-ratio"

#: The ``ledger_iva_aggregation`` cuota bindings whose bound casillas the engine
#: requires a fact for. The carry scenarios drive the result through manual
#: section totals, so each is supplied as zero unless a test overrides it.
LEDGER_CUOTA_BINDINGS = (
    "modelo-303-iva-repercutido-general-cuota",
    "modelo-303-iva-repercutido-reducido-cuota",
    "modelo-303-iva-repercutido-super-reducido-cuota",
    "modelo-303-iva-soportado-interiores-cuota",
    "modelo-303-iva-soportado-importaciones-cuota",
    "modelo-303-iva-autorepercutido-intracomunitaria-cuota",
    "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base",
    "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota",
    "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota",
    "modelo-303-iva-autorepercutido-interior-devengado-cuota",
    "modelo-303-iva-autorepercutido-interior-deducible-cuota",
    "modelo-303-casilla-59-entregas-intracomunitarias-base",
    "modelo-303-casilla-60-exportaciones-base",
    "modelo-303-casilla-120-no-sujetas-localizacion-base",
    "modelo-303-casilla-122-inversion-sujeto-pasivo-base",
    "modelo-303-iva-repercutido-general-base",
    "modelo-303-iva-repercutido-reducido-base",
    "modelo-303-iva-repercutido-reducido-transitorio-base",
    "modelo-303-iva-repercutido-reducido-transitorio-cuota",
    "modelo-303-iva-repercutido-super-reducido-base",
    "modelo-303-iva-repercutido-super-reducido-transitorio-base",
    "modelo-303-iva-repercutido-super-reducido-transitorio-cuota",
    "modelo-303-iva-soportado-interiores-base",
    "modelo-303-recargo-equivalencia-general-cuota",
    "modelo-303-recargo-equivalencia-reducido-cuota",
    "modelo-303-recargo-equivalencia-super-reducido-cuota",
    # Criterio-de-caja informational bindings (LIVA arts. 163 decies ff.) for
    # casillas 62/63/74/75; zero when the fixture has no cash-accounting rows.
    "modelo-303-criterio-caja-entregas-art75-base",
    "modelo-303-criterio-caja-entregas-art75-cuota",
    "modelo-303-criterio-caja-adquisiciones-base",
    "modelo-303-criterio-caja-adquisiciones-cuota",
)


def calculate_303(
    *,
    filing_year: int,
    period: str,
    cuota_binding_overrides: Mapping[str, Decimal],
    relation_values: Mapping[RelationId, Decimal],
) -> RegistryCalculationResult:
    snapshot = published_authority_operation().snapshot(MODELO, filing_year=filing_year, period=period)
    relation_binding_values = relation_prefill_values_as_binding_values(
        snapshot.revision,
        dict(relation_values),
        period=period,
    )
    binding_values = {
        CARRY_BINDING: Decimal("0"),
        AUTOCONSUMO_PROMOTOR_BASE_BINDING: Decimal("0"),
        STATE_ATTRIBUTION_RATIO_BINDING: Decimal("100"),
        **{binding: Decimal("0") for binding in LEDGER_CUOTA_BINDINGS},
        **cuota_binding_overrides,
        **relation_binding_values,
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        relation_values=dict(relation_values),
        date_context={"filing_period": date(filing_year, 12, 31)},
    )


def registry_observation(
    *,
    filing_year: int,
    period: str,
    result: RegistryCalculationResult,
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo=MODELO,
        filing_year=filing_year,
        period=period,
        observations=result.observations,
    )
