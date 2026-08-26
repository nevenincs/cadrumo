"""Oracle test for M353 2024 group-entity aggregated settlement casillas
grounded against the AEAT Manual practico IVA 2024's own worked example
(Cap. 6, "Los regimenes especiales en el IVA", "Regimen especial del grupo de
entidades").

Ground truth (bundled AEAT Manual practico IVA 2024):

    raw_evidence_locator: corpus/manuals/iva/2024/source.pdf#Pag.199-200

The manual's "Ejemplo" (pag. 199-200), continuing from the OMEGA/DELTA
individual Modelo 322 settlements (see
test_m322_2024_grupo_entidades_manual_worked_example.py), states:

    "El dia 20 de abril, la entidad dominante, presentara una
    autoliquidacion mensual en el modelo agregado 353, en la que integrara
    los resultados de las autoliquidaciones anteriores, de la siguiente
    forma:

    Sociedad OMEGA, S.A. (dominante). Resultado (modelo 322): 4.000
    Sociedad DELTA, S.A. (dependiente). Resultado (modelo 322): -1.000

    Resultado autoliquidacion: 3.000"

This is the manual's own printed AGGREGATE for the group's Modelo 353. This
test grounds the group's combined ledger-direct devengada/deducible/resultado
totals by summing the manual's own printed per-member IVA devengado/deducible
figures (OMEGA "IVA devengado: 6.000" / "IVA deducible: 2.000"; DELTA "IVA
devengado: 1.000" / "IVA deducible: 2.000" - see the M322 module docstring)
into the group's combined cuota (6.000+1.000=7.000 devengada; 2.000+2.000=
4.000 deducible - simple arithmetic over the manual's own printed figures,
never a hand-run of the registry formula under test), fed to the registry as
:class:`IvaLedgerObservation` rows exactly as the M303/M322 grounding tests
do. ``base_amount`` is undisclosed by the manual and plays no role in the
casillas graded here; it is set to zero rather than fabricated.

Registry mapping (M353 2008-2025 revision):

    iva.cuota-devengada-total = repercutido.general (iva_amount=7.000) +
      repercutido.reducido (0) + repercutido.super-reducido (0) +
      autorepercutido.intracomunitaria (0) = 7.000.
    iva.cuota-deducible-total = soportado.interiores (iva_amount=4.000) +
      autorepercutido.intracomunitaria (0) = 4.000.
    iva.resultado-regimen-general = 7.000-4.000 = 3.000 -> matches the
      manual's own printed "Resultado autoliquidacion: 3.000" exactly.

This test grounds the LEDGER-DIRECT computed casillas
(``iva.cuota-devengada-total`` / ``iva.cuota-deducible-total`` /
``iva.resultado-regimen-general``, ``input_kind = "computed"``), not the
cross-modelo reconciliation casillas (``iva.reconciliacion.*``,
``input_kind = "bound"`` to ``per_grupo_member`` ``previous_filing``
bindings) - the latter are pinned to zero here and are out of scope of this
grounding (they require simulating filed Modelo 322 declarations, exercised
elsewhere, e.g. test_modelo_353_grupo_aggregation_continuity.py).

Anti-tautology: this test does not hand-compute 3.000 from the registry's own
devengada-minus-deducible formula under test; both operands (the group's
combined devengada, deducible) are independently derived by simple addition
over the manual's own printed per-member figures, and the manual itself
prints the resulting aggregate ("Resultado autoliquidacion: 3.000") the
registry's subtraction formula is graded against.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.ledger_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
)

from .....core import CasillaId, IvaDeductionFactKind, validated_casilla_id
from ....iva import IvaCategory, IvaFlowDirection, IvaLedgerObservationRole, IvaRateKind
from ..authority import bundled_authority
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

# The three cross-modelo reconciliation bindings (per_grupo_member
# previous_filing) are outside this grounding's scope; every bound casilla
# still needs a resolved fact, so these are pinned to zero.
_RECONCILIATION_BINDING_IDS = (
    "modelo-353-prev-322-cuota-devengada-total",
    "modelo-353-prev-322-cuota-deducible-total",
    "modelo-353-prev-322-resultado-regimen-general",
)


def _calculate() -> object:
    snapshot = bundled_authority().snapshot("353", filing_year=_FILING_YEAR, period=_PERIOD)
    observations = (
        IvaLedgerObservation(
            ledger_id="grupo-devengado-general",
            transaction_date=date(2024, 3, 15),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("0"),
            # OMEGA 6.000 + DELTA 1.000 (manual's own printed per-member
            # "IVA devengado" figures, pag. 199).
            iva_amount=Decimal("7000.00"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="grupo-deducible-general",
            transaction_date=date(2024, 3, 15),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("0"),
            # OMEGA 2.000 + DELTA 2.000 (manual's own printed per-member
            # "IVA deducible" figures, pag. 199).
            iva_amount=Decimal("4000.00"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_provenance=_deduction_provenance(
                IvaDeductionFactKind.DOMESTIC_CURRENT,
                source_locator="invoice:grupo-deducible-general",
            ),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
    )
    binding_values: dict[str, Decimal] = {binding_id: Decimal("0") for binding_id in _RECONCILIATION_BINDING_IDS}
    binding_values.update(resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations))
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2024, 3, 31)},
    )


def test_m353_2024_grupo_omega_delta_manual_worked_example() -> None:
    """Grupo devengada/deducible/resultado = 7.000 / 4.000 / 3.000.

    Oracle: AEAT Manual practico IVA 2024, Cap. 6, pag. 199-200. The
    devengada (7.000) and deducible (4.000) operands are the sum of the
    manual's own printed per-member OMEGA/DELTA totals; the graded resultado
    (3.000) matches the manual's own printed "Resultado autoliquidacion:
    3.000" for the aggregated Modelo 353 exactly.
    """
    result: Any = _calculate()

    assert result.values[_CASILLA_DEVENGADA] == Decimal("7000.00")
    assert result.values[_CASILLA_DEDUCIBLE] == Decimal("4000.00")
    assert result.values[_CASILLA_RESULTADO] == Decimal("3000.00")


def test_m353_2024_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The manual-oracle grounding of the three aggregated totals is
    enrolled, not just computed.

    Mirrors the M303/M390/M322 enrollment-honesty proofs (see
    ``test_external_oracle_grounding_enrolled.py`` for the shared
    registry-honesty gate this proves reaches the live, VALIDATED
    :class:`RegistryVerificationPolicy` fold for M353). Not tautological:
    the grounded set and the fraction are read from the registry's own
    declared+validated data, never hand-computed or asserted from a
    synthetic fixture.
    """
    authority = registry_authority
    snapshot = authority.snapshot("353", filing_year=_FILING_YEAR, period=_PERIOD)
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
