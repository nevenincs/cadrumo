"""IS-1 regression: the M200←M202 pagos-fraccionados fold-in credits BOTH modalidades.

A taxpayer filing Modelo 202 under modalidad cuota (art. 40.2 LIS) reports the pago
fraccionado in casilla 03; modalidad base imponible (art. 40.3 LIS) reports it in
casilla 34. The two are mutually exclusive per filing. The Modelo 200 fold-in must
credit whichever modality the taxpayer used. Before the fix it read only casilla 34,
so a 40.2 filer's instalments folded in as 0 — the annual cuota diferencial omitted
payments already made (over-payment). This verifies each modality's relation resolves
to the persisted M202 quarterly amounts, against an external oracle (the sum the test
persists), not the formula under test.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....tests.secure_sql import isolated_runtime_profile
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REL_40_2 = "modelo-200-2024-rel-202-pagos-fraccionados-40-2"
_REL_40_3 = "modelo-200-2024-rel-202-pagos-fraccionados"


def _m202_observation(
    *, filing_year: int, period: str, casilla_03: Decimal, casilla_34: Decimal
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="202",
        filing_year=filing_year,
        period=period,
        observations=(
            CasillaObservation(casilla_id="03", value=casilla_03),
            CasillaObservation(casilla_id="34", value=casilla_34),
        ),
    )


def _resolve_m200_pagos_fraccionados(repository: CalculationObservationRepository) -> dict[str, Decimal]:
    snapshot = resources().modelos.authority.snapshot("200", filing_year=2024, period="0A")
    relation_vals = resolve_relations_from_local_store(snapshot, repository=repository)
    return {rv.relation: rv.value for rv in relation_vals.values if rv.value is not None}


def test_m200_fold_in_credits_modalidad_40_2_instalments(tmp_path: Path) -> None:
    """A modalidad-cuota (40.2) filer's instalments (casilla 03) are credited."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        amounts = {"1P": Decimal("300.00"), "2P": Decimal("450.00"), "3P": Decimal("250.00")}
        repository = CalculationObservationRepository()
        for period, amount in amounts.items():
            repository.save_observation(
                _m202_observation(filing_year=2024, period=period, casilla_03=amount, casilla_34=Decimal("0")),
                source_kind="app_filing",
            )
        values = _resolve_m200_pagos_fraccionados(repository)
        # The 40.2 relation captures the modalidad-cuota instalments: 300 + 450 + 250.
        assert values.get(_REL_40_2) == Decimal("1000.00")
        # The 40.3 relation is 0 for a 40.2 filer (casilla 34 = 0 every quarter).
        assert values.get(_REL_40_3) == Decimal("0")


def test_m200_fold_in_credits_modalidad_40_3_instalments(tmp_path: Path) -> None:
    """Control: a modalidad-base-imponible (40.3) filer's instalments (casilla 34) still
    fold in unchanged — the fix did not regress the pre-existing path."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        amounts = {"1P": Decimal("100.00"), "2P": Decimal("200.00"), "3P": Decimal("150.00")}
        repository = CalculationObservationRepository()
        for period, amount in amounts.items():
            repository.save_observation(
                _m202_observation(filing_year=2024, period=period, casilla_03=Decimal("0"), casilla_34=amount),
                source_kind="app_filing",
            )
        values = _resolve_m200_pagos_fraccionados(repository)
        assert values.get(_REL_40_3) == Decimal("450.00")
        assert values.get(_REL_40_2) == Decimal("0")
