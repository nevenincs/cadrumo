"""Oracle test for M322 2024 group-entity individual settlement casillas
grounded against the AEAT Manual practico IVA 2024's own worked example
(Cap. 6, "Los regimenes especiales en el IVA", "Regimen especial del grupo de
entidades").

Ground truth (bundled AEAT Manual practico IVA 2024):

    raw_evidence_locator: corpus/manuals/iva/2024/source.pdf#Pag.199-200

The manual's "Ejemplo" (pag. 199-200) states:

    "Las sociedades OMEGA, S.A. y DELTA, S.A. que cumplen todos los
    requisitos para aplicar el regimen especial de grupos de entidades, han
    ejercitado la opcion y cumplen los requisitos establecidos en la Ley del
    IVA para su aplicacion. La sociedad OMEGA, S.A. tiene una participacion
    del 60% del capital de la sociedad DELTA, S.A. El dia 19 de abril cada
    sociedad presenta su autoliquidacion individual en el modelo 322, con el
    siguiente resultado:

    Sociedad OMEGA, S.A.:
    IVA devengado: 6.000
    IVA deducible: 2.000
    Resultado autoliquidacion: 4.000

    Sociedad DELTA, S.A.:
    IVA devengado: 1.000
    IVA deducible: 2.000
    Resultado autoliquidacion: -1.000"

The manual states only the aggregate IVA devengado/deducible/resultado per
society (no base or rate-tier breakdown), and the example does not name a
specific calendar year (illustrative). This test grounds the two individual
Modelo 322 settlements against the manual's own printed totals, feeding each
society's devengado/deducible cuota to the registry as a single
:class:`IvaLedgerObservation` row per flow (aggregation ``sum`` is
associative, so one row carrying the manual's own printed aggregate resolves
identically to the underlying per-operation lines the manual does not
itemise). ``base_amount`` is undisclosed by the manual and plays no role in
the casillas graded here (``iva.cuota-devengada-total`` /
``iva.cuota-deducible-total`` / ``iva.resultado-regimen-general`` sum only
``iva_amount``); it is set to zero rather than fabricated from an assumed
rate.

Registry mapping (M322 2024-2025 revision):

    iva.cuota-devengada-total = repercutido.general (iva_amount) +
      repercutido.reducido (0) + repercutido.super-reducido (0) +
      autorepercutido.intracomunitaria (0) -> for OMEGA, 6.000 (the manual's
      own printed "IVA devengado: 6.000"); for DELTA, 1.000 (the manual's
      own printed "IVA devengado: 1.000").
    iva.cuota-deducible-total = soportado.interiores (iva_amount) +
      autorepercutido.intracomunitaria (0) -> for OMEGA, 2.000; for DELTA,
      2.000 (both match the manual's own printed "IVA deducible: 2.000").
    iva.resultado-regimen-general = cuota-devengada-total -
      cuota-deducible-total -> OMEGA 6.000-2.000=4.000, DELTA 1.000-2.000=
      -1.000, matching the manual's own printed "Resultado autoliquidacion"
      figures exactly (including DELTA's negative a-compensar result).

Anti-tautology: this test does not hand-compute 4.000 or -1.000 from the
registry's own devengada-minus-deducible formula under test; both operands
(devengada, deducible) and the result are independently quoted from the
manual's own printed figures, and the registry's own subtraction formula is
what is under test (a formula that used addition instead of subtraction, or
that dropped a term, would fail this check against the manual's own printed
resultado).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.iva_deduction_fact import IvaDeductionFactKind
from ....iva.flow import IvaFlowDirection
from ....iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ..authority import ValidatedRegistryAuthority, bundled_authority
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..ledger_iva_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
)
from ._ledger_iva_aggregation_support import _deduction_provenance

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_CASILLA_DEVENGADA: CasillaId = validated_casilla_id(
    "iva.cuota-devengada-total",
    surface="_CASILLA_DEVENGADA",
)
_CASILLA_DEDUCIBLE: CasillaId = validated_casilla_id(
    "iva.cuota-deducible-total",
    surface="_CASILLA_DEDUCIBLE",
)
_CASILLA_RESULTADO: CasillaId = validated_casilla_id(
    "iva.resultado-regimen-general",
    surface="_CASILLA_RESULTADO",
)

_FILING_YEAR = 2024
_PERIOD = "03"


def _calculate(*, devengado: Decimal, deducible: Decimal) -> RegistryCalculationResult:
    snapshot = bundled_authority().snapshot("322", filing_year=_FILING_YEAR, period=_PERIOD)
    observations = (
        IvaLedgerObservation(
            ledger_id="devengado-general",
            transaction_date=date(2024, 3, 15),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("0"),
            iva_amount=devengado,
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="deducible-general",
            transaction_date=date(2024, 3, 15),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("0"),
            iva_amount=deducible,
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_provenance=_deduction_provenance(
                IvaDeductionFactKind.DOMESTIC_CURRENT,
                source_locator="invoice:deducible-general",
            ),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
    )
    binding_values = dict(resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations))
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2024, 3, 31)},
    )


def test_m322_2024_omega_dominante_manual_worked_example() -> None:
    """OMEGA, S.A.: devengada/deducible/resultado = 6.000 / 2.000 / 4.000.

    Oracle: AEAT Manual practico IVA 2024, Cap. 6, pag. 199, "Sociedad OMEGA,
    S.A.: IVA devengado: 6.000 / IVA deducible: 2.000 / Resultado
    autoliquidacion: 4.000".
    """
    result = _calculate(devengado=Decimal("6000.00"), deducible=Decimal("2000.00"))

    assert result.values[_CASILLA_DEVENGADA] == Decimal("6000.00")
    assert result.values[_CASILLA_DEDUCIBLE] == Decimal("2000.00")
    assert result.values[_CASILLA_RESULTADO] == Decimal("4000.00")


def test_m322_2024_delta_dependiente_manual_worked_example() -> None:
    """DELTA, S.A.: devengada/deducible/resultado = 1.000 / 2.000 / -1.000.

    Oracle: AEAT Manual practico IVA 2024, Cap. 6, pag. 199, "Sociedad DELTA,
    S.A.: IVA devengado: 1.000 / IVA deducible: 2.000 / Resultado
    autoliquidacion: -1.000". Also proves the negative-resultado (a
    compensar) path, which the OMEGA scenario does not exercise.
    """
    result = _calculate(devengado=Decimal("1000.00"), deducible=Decimal("2000.00"))

    assert result.values[_CASILLA_DEVENGADA] == Decimal("1000.00")
    assert result.values[_CASILLA_DEDUCIBLE] == Decimal("2000.00")
    assert result.values[_CASILLA_RESULTADO] == Decimal("-1000.00")


def test_m322_2024_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The manual-oracle grounding of the three settlement totals is enrolled,
    not just computed.

    Mirrors the M303/M390 enrollment-honesty proofs (see
    ``test_external_oracle_grounding_enrolled.py`` for the shared
    registry-honesty gate this proves reaches the live, VALIDATED
    :class:`RegistryVerificationPolicy` fold for M322). Not tautological:
    the grounded set and the fraction are read from the registry's own
    declared+validated data, never hand-computed or asserted from a
    synthetic fixture.
    """
    authority = registry_authority
    snapshot = authority.snapshot("322", filing_year=_FILING_YEAR, period=_PERIOD)
    policy = snapshot.verification_policy()

    for casilla_id in (_CASILLA_DEVENGADA, _CASILLA_DEDUCIBLE, _CASILLA_RESULTADO):
        assert casilla_id in policy.externally_grounded_casilla_ids

    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids
    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )

    assert _CASILLA_RESULTADO in externally_grounded
    assert independently_grounded_fraction > 0.0
