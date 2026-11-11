"""The Modelo 100 projection reads its boxes and quarter count from the published authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.config import override_settings
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ....domain.calculations.registry.schema_base import DateAxis
from ...operations.error_detail import build_operation_error_detail
from ..projection import ModeloProjectResultUnresolvedError, m100_projection_result, source_quarter_count
from ..projection_declaration import projection_declaration_from, registry_projection_declaration

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SUPPORTED_YEARS = (2022, 2023, 2024, 2025, 2026)


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_the_published_fact_declares_the_modelo_130_and_100_boxes(year: int) -> None:
    with bundled_indexed_authority().operation() as operation:
        declaration = registry_projection_declaration(year, operation=operation)
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
        declaration.cuota_liquida_estatal,
        declaration.cuota_liquida_autonomica,
        declaration.cuota_resultante,
        declaration.pagos_fraccionados,
    ) == ("0171", "0505", "0545", "0546", "0570", "0571", "0595", "0604")

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
        declaration = registry_projection_declaration(year, operation=operation)
        count = source_quarter_count(
            declaration,
            year=year,
            period=Period.from_year_and_code(year, "2T"),
            operation=operation,
        )

    assert count == 4


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_the_projection_reports_the_quotas_and_not_the_withholding_boxes(year: int) -> None:
    with bundled_indexed_authority().operation() as operation:
        declaration = registry_projection_declaration(year, operation=operation)
    # Distinct figures per box, so a mapping onto the wrong box changes the result.
    values = {
        validated_casilla_id(box, surface="test"): Decimal(figure)
        for box, figure in {
            "0505": "48000.00",
            "0545": "6203.50",
            "0546": "5608.09",
            "0570": "6203.51",
            "0571": "5608.10",
            "0595": "11811.61",
            "0596": "1000.00",
            "0597": "200.00",
            "0604": "9600.00",
        }.items()
    }

    projection = m100_projection_result(values, declaration=declaration)

    assert projection.cuota_liquida_estatal == Decimal("6203.51")
    assert projection.cuota_liquida_autonomica == Decimal("5608.10")
    assert projection.cuota_resultante == Decimal("11811.61")


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
        projection_declaration_from(resolved.model_copy(update={"payload": payload}))


def test_a_figure_the_annual_return_left_without_a_value_is_refused_and_its_boxes_named() -> None:
    with bundled_indexed_authority().operation() as operation:
        declaration = registry_projection_declaration(2025, operation=operation)
    left_out = (declaration.cuota_integra_estatal, declaration.cuota_resultante)
    values = {
        box: Decimal("1.00")
        for box in (
            declaration.base_liquidable_general,
            declaration.pagos_fraccionados,
            declaration.cuota_integra_estatal,
            declaration.cuota_integra_autonomica,
            declaration.cuota_liquida_estatal,
            declaration.cuota_liquida_autonomica,
            declaration.cuota_resultante,
        )
        if box not in left_out
    }

    with pytest.raises(ModeloProjectResultUnresolvedError) as refused:
        m100_projection_result(values, declaration=declaration)

    sentences: set[str] = set()
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            detail = build_operation_error_detail(refused.value)
        assert detail is not None and detail.refusal_words is not None
        assert detail.refusal_words_language is OutputLanguage(language)
        assert detail.error_code == "REFUSED_MODELO_PROJECT_RESULT_UNRESOLVED"
        # Only the boxes without a value are named, and no step is offered for what the quarters cannot supply.
        assert all(box in detail.refusal_words for box in left_out)
        assert declaration.base_liquidable_general not in detail.refusal_words
        assert detail.next_step is None
        sentences.add(detail.refusal_words)
    assert len(sentences) == len(SUPPORTED_OUTPUT_LANGUAGES)
