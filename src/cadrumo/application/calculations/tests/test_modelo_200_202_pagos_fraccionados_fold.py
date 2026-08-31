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

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import RelationId
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._relation_prefill import resolve_relations_from_local_store
from ..observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REL_40_2: RelationId = "modelo-200-2024-rel-202-pagos-fraccionados-40-2"
_REL_40_3: RelationId = "modelo-200-2024-rel-202-pagos-fraccionados"


_M202_MODALIDAD_CUOTA_PAGO_CASILLA: CasillaId = validated_casilla_id("03")
_M202_MODALIDAD_BASE_PAGO_CASILLA: CasillaId = validated_casilla_id("34")


def _m202_observation(
    *, filing_year: int, period: str, casilla_03: Decimal, casilla_34: Decimal
) -> RegistryModeloObservation:
    return registry_grounded_modelo_observation(
        modelo="202",
        filing_year=filing_year,
        period=period,
        casilla_values={
            _M202_MODALIDAD_CUOTA_PAGO_CASILLA: casilla_03,
            _M202_MODALIDAD_BASE_PAGO_CASILLA: casilla_34,
        },
    )


def _resolve_m200_pagos_fraccionados(repository: CalculationObservationRepository) -> dict[RelationId, Decimal]:
    snapshot = bundled_authority().snapshot(
        "200", filing_year=2025, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )
    relation_vals = resolve_relations_from_local_store(snapshot, repository=repository)
    return {rv.relation: rv.value for rv in relation_vals.values if rv.value is not None}


def test_m200_fold_in_credits_modalidad_40_2_instalments(tmp_path: Path) -> None:
    """A modalidad-cuota (40.2) filer's instalments (casilla 03) are credited."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        amounts = {"1P": Decimal("300.00"), "2P": Decimal("450.00"), "3P": Decimal("250.00")}
        repository = CalculationObservationRepository()
        for period, amount in amounts.items():
            repository.save(
                repository.prepare_observation_envelope(
                    _m202_observation(filing_year=2025, period=period, casilla_03=amount, casilla_34=Decimal("0")),
                    source_kind="app_filing",
                )
            )
        values = _resolve_m200_pagos_fraccionados(repository)
        # The 40.2 relation captures the modalidad-cuota instalments — the sum of the
        # quarterly casilla-03 values the relation aggregated (computed from the inputs,
        # not a hand-summed literal, so the assertion proves the aggregation wiring).
        assert values.get(_REL_40_2) == sum(amounts.values(), Decimal("0"))
        # The 40.3 relation is 0 for a 40.2 filer (casilla 34 = 0 every quarter).
        assert values.get(_REL_40_3) == Decimal("0")


def test_m200_fold_in_credits_modalidad_40_3_instalments(tmp_path: Path) -> None:
    """Control: a modalidad-base-imponible (40.3) filer's instalments (casilla 34) still
    fold in unchanged — the fix did not regress the pre-existing path."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        amounts = {"1P": Decimal("100.00"), "2P": Decimal("200.00"), "3P": Decimal("150.00")}
        repository = CalculationObservationRepository()
        for period, amount in amounts.items():
            repository.save(
                repository.prepare_observation_envelope(
                    _m202_observation(filing_year=2025, period=period, casilla_03=Decimal("0"), casilla_34=amount),
                    source_kind="app_filing",
                )
            )
        values = _resolve_m200_pagos_fraccionados(repository)
        assert values.get(_REL_40_3) == sum(amounts.values(), Decimal("0"))
        assert values.get(_REL_40_2) == Decimal("0")


def _all_m202_relation_values(
    repository: CalculationObservationRepository,
    *,
    first_year_cuota: bool,
) -> dict[RelationId, Decimal | None]:
    snapshot = bundled_authority().snapshot(
        "200", filing_year=2025, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )
    relation_vals = resolve_relations_from_local_store(
        snapshot,
        repository=repository,
        modelo_202_first_year_cuota=first_year_cuota,
    )
    return {rv.relation: rv.value for rv in relation_vals.values}


def test_is3_first_year_cuota_resolves_unfiled_m202_relations_to_zero(tmp_path: Path) -> None:
    """A first-year modalidad-cuota filer (no M202 filed) resolves the M202 fold-in
    relations to 0 instead of None, so the cuota-diferencial formula computes (no draft-build
    crash) rather than refusing on an unsupplied relation."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()  # no M202 observations persisted
        values = _all_m202_relation_values(repository, first_year_cuota=True)
        assert values.get(_REL_40_3) == Decimal("0")
        assert values.get(_REL_40_2) == Decimal("0")


def test_is3_flag_off_leaves_unfiled_m202_relations_unresolved(tmp_path: Path) -> None:
    """Control: without the first-year-cuota flag, an unfiled M202 relation stays None
    (the pre-IS-3 behaviour is unchanged for every non-first-year-cuota path)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        values = _all_m202_relation_values(repository, first_year_cuota=False)
        assert values.get(_REL_40_3) is None
        assert values.get(_REL_40_2) is None


def test_is3_first_year_flag_never_overrides_a_filed_m202_value(tmp_path: Path) -> None:
    """Fail-closed: even with the first-year-cuota flag set, a genuinely-filed M202 value is
    folded in unchanged — the flag only resolves an OTHERWISE-UNRESOLVED M202 relation to 0,
    so real pagos fraccionados are never dropped to 0 (no under-declaration)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        amounts = {"1P": Decimal("300.00"), "2P": Decimal("450.00"), "3P": Decimal("250.00")}
        repository = CalculationObservationRepository()
        for period, amount in amounts.items():
            repository.save(
                repository.prepare_observation_envelope(
                    _m202_observation(filing_year=2025, period=period, casilla_03=amount, casilla_34=Decimal("0")),
                    source_kind="app_filing",
                )
            )
        values = _all_m202_relation_values(repository, first_year_cuota=True)
        # filed value preserved (the sum of the quarterly casilla-03 inputs), NOT zeroed
        assert values.get(_REL_40_2) == sum(amounts.values(), Decimal("0"))
        assert values.get(_REL_40_3) == Decimal("0")  # casilla 34 = 0 each quarter (genuinely 0)
