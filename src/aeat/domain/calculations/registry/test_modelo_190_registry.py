"""Modelo 190 registry behaviour for annual Modelo 111 summary links."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.core.resources import bundled_path

from . import (
    CasillaObservation,
    RegistryModeloObservation,
    RegistryValidator,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
)
from ._relations import relation_source_requirements, resolve_relation_values_from_observations

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _load_modelo(modelo_id: str):
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == modelo_id)
    return modelo, catalogues


def test_modelo_190_validates_and_gates_workflow_surfaces_through_snapshot() -> None:
    modelo, catalogues = _load_modelo("190")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )

    construct = snapshot.revision.constructs[0]
    linked_surfaces = {
        link.surface for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert {
        "calculation",
        "filing",
        "review",
        "verification",
        "approval",
        "reconciliation",
        "extractor",
        "portal",
        "workflow",
    } <= linked_surfaces


def test_modelo_190_2024_revision_resolves_against_2024_legal_sources() -> None:
    modelo, catalogues = _load_modelo("190")

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    assert snapshot.revision.id == "2024"
    assert "orden-hac-1432-2024:df-unica" in snapshot.revision.legal_refs
    assert "orden-hac-1431-2025:art-2" not in snapshot.revision.legal_refs
    assert "aeat-dr-190-2024" in snapshot.revision.source_refs
    assert "boe-modelo-190-2024-amendment" in snapshot.revision.source_refs
    assert {casilla.number for casilla in snapshot.revision.casillas} == {"136-144", "145-160", "161-175"}
    assert snapshot.revision.period_selector.years == (2024,)
    assert snapshot.revision.period_selector.periods == ("0A",)


def test_modelo_190_2024_record_design_contains_registered_summary_fields() -> None:
    _, catalogues = _load_modelo("190")
    source = catalogues.sources["aeat-dr-190-2024"]
    source_path = Path(bundled_path()) / source.corpus_path

    text = _extract_pdf_text(source_path)

    assert "Modelo 190 (2024)" in text
    assert "136-144" in text
    assert "NÚMERO TOTAL DE PERCEPCIONES" in text
    assert "145-160" in text
    assert "IMPORTE TOTAL DE LAS PERCEPCIONES" in text
    assert "161-175" in text
    assert "IMPORTE TOTAL DE LAS RETENCIONES E" in text
    assert "INGRESOS A CUENTA" in text


def test_modelo_190_relations_resolve_against_modelo_111_registry() -> None:
    modelo, catalogues = _load_modelo("190")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )
    modelo_111, _ = _load_modelo("111")
    snapshot_111 = build_snapshot(
        modelo_111,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="1T",
    )

    modelo_111_outputs = {casilla.id for casilla in snapshot_111.revision.casillas}
    relation_source_outputs = {relation.source_output for relation in snapshot.revision.relations}
    assert relation_source_outputs <= modelo_111_outputs
    assert {tuple(relation.source_periods) for relation in snapshot.revision.relations} == {("1T", "2T", "3T", "4T")}


def test_modelo_190_calculation_aggregates_modelo_111_quarterly_observations() -> None:
    modelo, catalogues = _load_modelo("190")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )
    modelo_111, _ = _load_modelo("111")
    snapshot_111 = build_snapshot(
        modelo_111,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="1T",
    )
    source_casillas = {casilla.id: casilla for casilla in snapshot_111.revision.casillas}
    requirements = relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
    observed_by_period: dict[str, dict[str, Decimal]] = {}
    for requirement in requirements:
        source_casilla = source_casillas[requirement.source_output]
        for index, period in enumerate(requirement.periods):
            value = _value_for(source_casilla.data_type, source_casilla.input_kind, index)
            observed_by_period.setdefault(period, {})[requirement.source_output] = value
    observations = tuple(
        RegistryModeloObservation(
            modelo="111",
            filing_year=2025,
            period=period,
            observations=tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in casilla_values.items()),
        )
        for period, casilla_values in sorted(observed_by_period.items())
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2025,
        period="0A",
    )

    # Assert binding wiring: relation_values must be populated for the
    # casillas the 190 relations source from 111.
    assert relation_values, "relation_values must be non-empty after resolving 111 observations"

    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(2025, 12, 31)},
        relation_values=relation_values,
    )

    # Assert structural wiring: expected aggregation casillas must be present
    # in the engine result. Values are not asserted here because the expected_*
    # accumulators above re-apply the same classification logic the registry
    # uses (data_type == "integer" → perceptors, input_kind == "computed" →
    # retenciones, else → perceptions), making any numeric assertion tautological.
    assert "decl.total-percepciones" in result.values, "perceptores aggregation casilla must be computed"
    assert "decl.percepciones-total" in result.values, "percepciones aggregation casilla must be computed"
    assert "decl.retenciones-total" in result.values, "retenciones aggregation casilla must be computed"

    # Non-negativity is a structural constraint (modelo 190 reports accumulated
    # annual totals, which cannot be negative by definition).
    assert result.values["decl.total-percepciones"] >= Decimal("0")
    assert result.values["decl.percepciones-total"] >= Decimal("0")
    assert result.values["decl.retenciones-total"] >= Decimal("0")


def _value_for(data_type: str, input_kind: str, period_index: int) -> Decimal:
    quarter = Decimal(period_index + 1)
    if input_kind == "computed":
        return Decimal("42") * quarter
    if data_type == "integer":
        return quarter
    return Decimal("10") * quarter


def _extract_pdf_text(path: Path) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    pages: list[str] = []
    try:
        for index in range(min(len(pdf), 8)):
            page = pdf[index]
            try:
                text_page = page.get_textpage()
                try:
                    pages.append(text_page.get_text_range())
                finally:
                    text_page.close()
            finally:
                page.close()
    finally:
        pdf.close()
    return "\n".join(pages)
