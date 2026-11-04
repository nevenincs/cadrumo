"""A relation whose source periods all precede the activity start is positively not applicable.

A taxpayer whose activity starts in the year after the filing year had no
pagos-fraccionados obligation in the filing year, so the Modelo 130 fed relation
of a Modelo 100 contributes an explicit zero rather than staying unresolved. An
undeclared activity start is unknown applicability and keeps the relation
unresolved, as does an activity start inside the source year.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.calculations.relation_prefill import resolve_relations_from_local_store
from .....application.storage.calc_sheets.records import RelationValue
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.modelo import Modelo
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.calculations.registry.relations import relation_source_requirements
from .....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_MODELO = str(Modelo("130"))


def _horizon() -> int:
    supported = published_supported_filing_years()
    assert supported is not None, "the bundled registry declares no supported filing years"
    return supported.horizon


def _renta_relations(*, activity_start_date: date | None, tmp_path: Path) -> dict[str, RelationValue]:
    """Resolve the Modelo 100 relations for the year before the horizon with an empty store."""
    snapshot = published_authority_operation().snapshot(
        "100", filing_year=_horizon() - 1, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )
    with isolated_runtime_profile(tmp_path=tmp_path), bundled_indexed_authority().operation() as operation:
        values = resolve_relations_from_local_store(
            snapshot,
            operation=operation,
            repository=CalculationObservationRepository(),
            activity_start_date=activity_start_date,
        )
    return {item.relation: item for item in values.values}


def _pagos_fraccionados_relation_ids() -> frozenset[str]:
    snapshot = published_authority_operation().snapshot(
        "100", filing_year=_horizon() - 1, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )
    return frozenset(
        binding_id
        for requirement in relation_source_requirements(
            snapshot.revision, filing_year=snapshot.filing_year, period=snapshot.period
        )
        if requirement.source_modelo == _SOURCE_MODELO
        for binding_id in requirement.target_bindings
    )


def test_precondition_modelo_100_declares_a_modelo_130_fed_relation() -> None:
    assert _pagos_fraccionados_relation_ids(), "Modelo 100 must declare a Modelo 130 fed relation"


def test_activity_starting_after_the_source_year_resolves_the_relation_to_not_applicable_zero(tmp_path: Path) -> None:
    relations = _renta_relations(activity_start_date=date(_horizon(), 1, 1), tmp_path=tmp_path)

    for relation_id in _pagos_fraccionados_relation_ids():
        item = relations[relation_id]
        assert item.value == Decimal("0"), f"{relation_id} must be a not-applicable zero"
        assert item.note is not None
        assert "not applicable" in item.note
        assert item.source_modelo == _SOURCE_MODELO
        assert item.source_periods, "the not-applicable zero keeps the source periods it covers"


def test_unknown_activity_start_keeps_the_relation_unresolved(tmp_path: Path) -> None:
    relations = _renta_relations(activity_start_date=None, tmp_path=tmp_path)

    for relation_id in _pagos_fraccionados_relation_ids():
        assert relations[relation_id].value is None


def test_activity_start_inside_the_source_year_keeps_the_relation_unresolved(tmp_path: Path) -> None:
    relations = _renta_relations(activity_start_date=date(_horizon() - 1, 1, 1), tmp_path=tmp_path)

    for relation_id in _pagos_fraccionados_relation_ids():
        assert relations[relation_id].value is None
