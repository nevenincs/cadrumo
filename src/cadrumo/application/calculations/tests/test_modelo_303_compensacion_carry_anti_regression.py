"""Cross-period anti-regression: M303 4T/N saldo magnitude propagates to 1T/N+1 casilla 110.

The companion module ``test_modelo_303_compensacion_carry_forward_continuity``
asserts the cross-renta wiring invariant on a single credit scenario. This
module is the anti-regression contract authorised by
`cross-period-carry-continuity`: it varies the
primitive credit magnitude in 4T/N and asserts that 1T/N+1's casilla 110
auto-resolves proportionally — the contract that would have caught the
regression hidden by the primitive-encoding commit (`6e5a316a6`) had it
existed before that commit landed.

The in-period verification chain (`test_verification_chain_part*.py`) is
necessary but not sufficient: it does not exercise the
cross-period saldo carry. The 47/47 in-period greens stayed green while
the cross-period saldo magnitude collapsed silently between periods.
This anti-regression contract closes that hole permanently. Any future
structural change to the per-rate primitive distribution MUST keep this
test green; the only way to keep it green is to preserve the saldo
magnitude across the 4T/N -> 1T/N+1 wrap, not just the per-period totals
(devengada-total / deducible-total) the v2 spec already pins.

Grounding: LIVA art. 99 (compensación de cuotas), arts. 115-116 (saldo a
compensar / devolución), RD 1624/1992 arts. 29-30 (procedure).
Non-tautological: both the year-N saldo and the year-N+1 casilla 110 are
engine-produced from the parametrised primitive credit; the assertion
compares engine outputs across two engine runs, not against any
hand-computed expectation derived from the formula under test.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    resolve_available_bound_inputs_by_casilla_id,
)
from ....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ....domain.calculations.registry.ids import RelationId
from ....domain.calculations.registry.relations import materialize_relation_binding_values
from ....tests.secure_sql import isolated_runtime_profile
from .._relation_prefill import resolve_relations_from_local_store
from ..observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "303"
_YEAR_N = 2025
_YEAR_N_PLUS_1 = 2026

_CARRY_BINDING = "modelo-303-compensacion-pendiente-anteriores"
_CASILLA_110: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
    surface="test_modelo_303_compensacion_carry_anti_regression:_CASILLA_110",
)
_SALDO_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-disponible-fin-periodo",
    surface="test_modelo_303_compensacion_carry_anti_regression:_SALDO_CASILLA",
)

#: Profile-gap workaround bindings (mirror the companion module; contract-pinned
#: as MUST-NOT-mutate to mask the diagnostic).
_AUTOCONSUMO_PROMOTOR_BASE_BINDING = "modelo-303-autoconsumo-promotor-base"
_STATE_ATTRIBUTION_RATIO_BINDING = "modelo-303-profile-state-attribution-ratio"
_LEDGER_CUOTA_BINDINGS = (
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

_CLOCK = datetime(2026, 5, 1, 9, 0, 0, tzinfo=UTC)


def _calculate_303(
    *,
    filing_year: int,
    period: str,
    cuota_binding_overrides: Mapping[str, Decimal],
    relation_values: Mapping[RelationId, Decimal],
) -> RegistryCalculationResult:
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=filing_year, period=period)
    relation_binding_values = materialize_relation_binding_values(
        snapshot.revision,
        dict(relation_values),
        period=period,
    )
    binding_values = {
        _CARRY_BINDING: Decimal("0"),
        _AUTOCONSUMO_PROMOTOR_BASE_BINDING: Decimal("0"),
        _STATE_ATTRIBUTION_RATIO_BINDING: Decimal("100"),
        **{binding: Decimal("0") for binding in _LEDGER_CUOTA_BINDINGS},
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


def _registry_observation(
    *,
    filing_year: int,
    period: str,
    result: RegistryCalculationResult,
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=filing_year,
        period=period,
        observations=result.observations,
    )


def _run_carry_chain(
    *,
    tmp_path: Path,
    devengada_cuota: Decimal,
    deducible_cuota: Decimal,
) -> tuple[Decimal, Decimal]:
    """Drive the full 4T/N -> 1T/N+1 carry; return (year-N saldo, year-N+1 casilla 110)."""

    year_n_4t_inputs = {
        "modelo-303-iva-repercutido-general-cuota": devengada_cuota,
        "modelo-303-iva-soportado-interiores-cuota": deducible_cuota,
    }
    year_n_plus_1_1t_inputs = {
        "modelo-303-iva-repercutido-general-cuota": Decimal("50.00"),
    }

    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()

        result_n = _calculate_303(
            filing_year=_YEAR_N,
            period="4T",
            cuota_binding_overrides=year_n_4t_inputs,
            relation_values={},
        )
        carried_saldo = result_n.values[_SALDO_CASILLA]
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                _registry_observation(filing_year=_YEAR_N, period="4T", result=result_n),
                source_kind="app_filing",
                captured_at=_CLOCK,
            )
        )

        snapshot_n1 = bundled_authority().snapshot(_MODELO, filing_year=_YEAR_N_PLUS_1, period="1T")
        relation_values = resolve_relations_from_local_store(snapshot_n1, repository=obs_repo)
        resolved: dict[RelationId, Decimal] = {
            item.relation: item.value for item in relation_values.values if item.value is not None
        }
        result_n1 = _calculate_303(
            filing_year=_YEAR_N_PLUS_1,
            period="1T",
            cuota_binding_overrides=year_n_plus_1_1t_inputs,
            relation_values=resolved,
        )

    return carried_saldo, result_n1.values[_CASILLA_110]


@pytest.mark.parametrize(
    ("devengada_cuota", "deducible_cuota"),
    [
        (Decimal("21.00"), Decimal("63.00")),
        (Decimal("10.00"), Decimal("100.00")),
        (Decimal("0.00"), Decimal("42.00")),
        (Decimal("100.00"), Decimal("250.00")),
    ],
    ids=["baseline-42", "credit-90", "pure-credit-42", "credit-150"],
)
def test_carry_in_tracks_prior_period_saldo_magnitude(
    tmp_path: Path,
    devengada_cuota: Decimal,
    deducible_cuota: Decimal,
) -> None:
    """1T/N+1 casilla 110 equals the engine-produced 4T/N saldo at every credit magnitude.

    The contract: vary the primitive credit input in 4T/N, run the full
    cross-renta wrap, and assert the carry-in lands on the prior-period
    saldo bit-for-bit. Both values are engine outputs from a real
    registry-authority + encrypted-SQLite observation-repo round trip; no
    hand-computed expectation participates in the assertion.

    This is the proportional-tracking gate the
    ``m303-cross-period-carry-continuity`` contract mandated as the durable
    anti-regression against future shifts in the per-rate primitive
    distribution. If a future primitive-encoding change preserves the
    in-period totals (devengada-total / deducible-total) but collapses
    the cross-period saldo (as happened pre-`c2e05f644`), this test
    fires and the in-period 47/47 gate does not.
    """

    carried_saldo, casilla_110 = _run_carry_chain(
        tmp_path=tmp_path,
        devengada_cuota=devengada_cuota,
        deducible_cuota=deducible_cuota,
    )

    assert carried_saldo > Decimal("0")
    assert casilla_110 == carried_saldo
