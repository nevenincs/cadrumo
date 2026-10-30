"""The Modelo 100 projection reads its boxes and quarter count from the published authority."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ....domain.calculations.registry.schema_base import DateAxis
from ..projection import _projection_declaration_from, _registry_projection_declaration, _source_quarter_count

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SUPPORTED_YEARS = (2022, 2023, 2024, 2025, 2026)


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_the_published_fact_declares_the_modelo_130_and_100_boxes(year: int) -> None:
    with bundled_indexed_authority().operation() as operation:
        declaration = _registry_projection_declaration(year, operation=operation)
        source = operation.revision_for_context(declaration.source_modelo, filing_year=year, period="1T")
        target = operation.revision_for_context(
            declaration.target_modelo, filing_year=year, period=declaration.target_period
        )

    # Independently read from the AEAT Modelo 130 and Modelo 100 forms.
    assert (declaration.source_modelo, declaration.target_modelo, declaration.target_period) == ("130", "100", "0A")
    assert (
        declaration.ingresos,
        declaration.gastos,
        declaration.rendimiento_neto,
        declaration.resultado_final,
    ) == ("01", "02", "03", "19")
    assert (
        declaration.rendimiento_neto_projected,
        declaration.base_liquidable_general,
        declaration.cuota_integra_estatal,
        declaration.cuota_integra_autonomica,
        declaration.pagos_fraccionados,
    ) == ("0171", "0505", "0545", "0546", "0604")

    source_ids = {casilla.id for casilla in source.casillas}
    target_ids = {casilla.id for casilla in target.casillas}
    assert {declaration.ingresos, declaration.gastos, declaration.rendimiento_neto, declaration.resultado_final} <= (
        source_ids
    )
    assert {
        declaration.rendimiento_neto_projected,
        declaration.base_liquidable_general,
        declaration.cuota_integra_estatal,
        declaration.cuota_integra_autonomica,
        declaration.cuota_liquida_estatal,
        declaration.cuota_liquida_autonomica,
        declaration.cuota_resultante,
        declaration.pagos_fraccionados,
    } <= target_ids


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_the_modelo_130_revision_serves_four_quarters(year: int) -> None:
    with bundled_indexed_authority().operation() as operation:
        declaration = _registry_projection_declaration(year, operation=operation)
        count = _source_quarter_count(
            declaration,
            year=year,
            period=Period.from_year_and_code(year, "2T"),
            operation=operation,
        )

    assert count == 4


def test_a_mapping_without_a_required_key_is_refused() -> None:
    with bundled_indexed_authority().operation() as operation:
        resolved = operation.resolve_governed_fact(
            MappingFactQuery(
                fact_id="modelo-100-m130-projection-mapping",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(2025, 12, 31),
            ),
        )
    assert isinstance(resolved, ResolvedMappingFact)
    payload = resolved.payload.model_copy(
        update={"entries": tuple(entry for entry in resolved.payload.entries if entry.key != "source.casilla.ingresos")}
    )

    with pytest.raises(RegistryValidationError, match=r"source\.casilla\.ingresos"):
        _projection_declaration_from(resolved.model_copy(update={"payload": payload}))
