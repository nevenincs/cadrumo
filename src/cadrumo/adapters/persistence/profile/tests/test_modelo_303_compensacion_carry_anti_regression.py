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
engine-_produced from the parametrised primitive credit; the assertion
compares engine outputs across two engine runs, not against any
hand-computed expectation derived from the formula under test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.application.calculations.binding_prefill import resolve_bindings_from_local_store
from cadrumo.application.calculations.observations_repository import ResultDispositionProjection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.tests.registry_observations import revision_id_for_observation
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from .modelo_303_carry_support import calculate_303, registry_observation
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "303"
_YEAR_N = 2025
_YEAR_N_PLUS_1 = 2026

_CASILLA_110: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
    surface="test_modelo_303_compensacion_carry_anti_regression:_CASILLA_110",
)
_SALDO_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-disponible-fin-periodo",
    surface="test_modelo_303_compensacion_carry_anti_regression:_SALDO_CASILLA",
)

_CLOCK = datetime(2026, 5, 1, 9, 0, 0, tzinfo=UTC)


def _resolve_carry_from_local_store(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository,
    operation: PinnedAuthorityOperation,
) -> dict[str, Decimal]:
    """Resolve the previous-filing carry binding the way the calculate path does."""
    prefill = resolve_bindings_from_local_store(
        snapshot,
        repository=repository,
        captured_at=_CLOCK,
        iva_history_repository=IvaCompensationHistoryRepository(objects=repository.secure_object_repository),
        operation=operation,
    )
    return {str(binding_id): value for binding_id, value in prefill.binding_values.items()}


def _run_carry_chain(
    *,
    tmp_path: Path,
    devengada_cuota: Decimal,
    deducible_cuota: Decimal,
    operation: PinnedAuthorityOperation,
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

        result_n = calculate_303(
            filing_year=_YEAR_N,
            period="4T",
            cuota_binding_overrides=year_n_4t_inputs,
            relation_values={},
        )
        carried_saldo = result_n.values[_SALDO_CASILLA]
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                registry_observation(filing_year=_YEAR_N, period="4T", result=result_n),
                source_kind="app_filing",
                result_disposition=ResultDispositionProjection(
                    disposition=ResultDisposition.COMPENSACION,
                    provenance_kind="app_filing",
                    provenance_locator="test-local-filing:compensacion-carry",
                ),
                captured_at=_CLOCK,
                stamped_revision_id=revision_id_for_observation(
                    registry_observation(filing_year=_YEAR_N, period="4T", result=result_n)
                ),
            )
        )

        snapshot_n1 = published_authority_operation().snapshot(_MODELO, filing_year=_YEAR_N_PLUS_1, period="1T")
        resolved = _resolve_carry_from_local_store(snapshot_n1, repository=obs_repo, operation=operation)
        result_n1 = calculate_303(
            filing_year=_YEAR_N_PLUS_1,
            period="1T",
            cuota_binding_overrides={**year_n_plus_1_1t_inputs, **resolved},
            relation_values={},
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
    tmp_path: Path, devengada_cuota: Decimal, deducible_cuota: Decimal, *, operation: PinnedAuthorityOperation
) -> None:
    """1T/N+1 casilla 110 equals the engine-_produced 4T/N saldo at every credit magnitude.

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
        operation=operation,
    )

    assert carried_saldo > Decimal("0")
    assert casilla_110 == carried_saldo
