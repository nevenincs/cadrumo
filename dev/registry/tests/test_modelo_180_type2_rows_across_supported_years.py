"""Modelo 180 type-2 perceptor rows in every year of the support envelope.

The annual summary emits one type-2 record per recipient, modality, accrual
year and property, and counts those records in the type-1 "número total de
perceptores". Every record design selected inside the envelope lays out that
record and states that count rule, so the row bindings, the repeated export
record, the count fact, the declaration-PDF extraction profile and the
application wiring are authored once and hydrate in each supported year. Each
year's expectation is read from the record design its own edition cites rather
than restated here.
"""

from __future__ import annotations

from decimal import Decimal
from functools import cache

import pytest

from cadrumo.application.aggregation.retenciones import (
    Modelo180PropertyEvidence,
    Modelo180StructuredAddress,
    Modelo180Type2Row,
    RetencionesAggregation,
    RetencionPerceptorRollup,
)
from cadrumo.core.aggregation import BindingSourceKind, RetencionScheme
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.export import (
    derive_export_layouts_from_bindings,
    row_binding_casilla_ids_by_field,
)
from cadrumo.domain.calculations.registry.retenciones_bindings import (
    resolve_retenciones_aggregation_binding_row_values,
    resolve_retenciones_aggregation_binding_values,
)
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "180"
_PERIOD = "0A"
_COUNT_CASILLA = "decl.total-perceptores"
_REPEATED_RECORD = "perceptor"
# The design's own statement of what the type-1 count counts.
_COUNT_RULE = "(Número de registros de tipo 2)"


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


@cache
def _edition(year: int) -> ModeloRevision:
    return compiled_bundled_authority().snapshot(_MODELO, filing_year=year, period=_PERIOD).revision


def _record_design_text(revision: ModeloRevision) -> str:
    """Return the extracted text of the record design the edition's export layout cites."""
    sources = compiled_bundled_authority().catalogues.sources
    designs = {
        ref for layout in revision.export_layouts for ref in layout.source_refs if sources[ref].kind == "record_design"
    }
    assert len(designs) == 1, f"edition {revision.id} cites record designs {sorted(designs)}"
    (design,) = designs
    corpus_path = bundled_path() / sources[design].corpus_path
    return corpus_path.with_name(f"{corpus_path.name}.extracted.md").read_text(encoding="utf-8")


def _row_wiring_problems(revision: ModeloRevision) -> list[str]:
    """Name every way the edition fails to emit repeated type-2 rows from its bindings."""
    problems: list[str] = []
    records = [
        record
        for layout in revision.export_layouts
        for record in layout.records
        if record.record_type == _REPEATED_RECORD
    ]
    if len(records) != 1:
        return [f"{revision.id}: expected one {_REPEATED_RECORD} record, found {len(records)}"]
    (record,) = records
    if record.repeat != "binding_rows" or record.binding_record != _REPEATED_RECORD:
        problems.append(f"{revision.id}: {record.id} is not a repeated binding-row record")
    if not record.row_field_casilla_ids:
        problems.append(f"{revision.id}: {record.id} maps no row field to a casilla")
    row_bindings: dict[str, BindingDefinition] = {}
    for binding in revision.bindings:
        provider = binding.provider.model_dump(mode="python")
        if provider.get("fact") == "row_field" and provider.get("record") == _REPEATED_RECORD:
            row_bindings[str(provider["row_field"])] = binding
    for row_field, casilla_id in record.row_field_casilla_ids.items():
        binding = row_bindings.get(str(row_field))
        if binding is None:
            problems.append(f"{revision.id}: no row binding fills {row_field} ({casilla_id})")
        elif binding.provider.model_dump(mode="python").get("target_casilla_id") != casilla_id:
            problems.append(f"{revision.id}: row binding {binding.id} does not target {casilla_id}")
    derived = row_binding_casilla_ids_by_field(revision, derive_export_layouts_from_bindings(revision)[0])
    if set(derived.values()) != set(record.row_field_casilla_ids.values()):
        missing = sorted(set(record.row_field_casilla_ids.values()) - set(derived.values()))
        problems.append(f"{revision.id}: export derivation leaves {missing} without a row binding slot")
    return problems


@pytest.mark.parametrize("year", _supported_years())
def test_each_supported_year_emits_repeated_type2_rows_from_its_bindings(year: int) -> None:
    revision = _edition(year)
    design = _record_design_text(revision)

    assert "REGISTRO DE TIPO 2: REGISTRO DE PERCEPTOR" in design
    assert _row_wiring_problems(revision) == []


def test_row_wiring_check_detects_an_edition_that_emits_one_template_record() -> None:
    """A perceptor record that is not a repeated binding-row record is reported, not passed."""
    revision = _edition(min(_supported_years()))
    layouts = []
    for layout in revision.export_layouts:
        records = tuple(
            record.model_copy(update={"repeat": None, "binding_record": None, "row_field_casilla_ids": {}})
            if record.record_type == _REPEATED_RECORD
            else record
            for record in layout.records
        )
        layouts.append(layout.model_copy(update={"records": records}))
    single_record = revision.model_copy(update={"export_layouts": tuple(layouts)})

    problems = _row_wiring_problems(single_record)

    assert any("is not a repeated binding-row record" in problem for problem in problems)
    assert any("maps no row field" in problem for problem in problems)


@pytest.mark.parametrize("year", _supported_years())
def test_each_supported_year_counts_type2_records_as_its_design_directs(year: int) -> None:
    revision = _edition(year)
    assert _COUNT_RULE in _record_design_text(revision)

    count_binding = next(
        binding
        for binding in revision.bindings
        if binding.provider.model_dump(mode="python").get("target_casilla_id") == _COUNT_CASILLA
    )
    aggregation = _one_recipient_two_properties(year)

    scalar = resolve_retenciones_aggregation_binding_values(revision, aggregation)
    row_values = resolve_retenciones_aggregation_binding_row_values(revision, aggregation)

    # One recipient letting two properties files two type-2 records and counts both.
    assert scalar[count_binding.id] == Decimal(2)
    assert {row_index for _binding_id, row_index in row_values} == {1, 2}


@pytest.mark.parametrize("year", _supported_years())
def test_row_bindings_cite_the_record_design_their_edition_selects(year: int) -> None:
    """Moving the rows to the earliest edition keeps each year's own design as their authority."""
    revision = _edition(year)
    layout_designs = {ref for layout in revision.export_layouts for ref in layout.source_refs}
    row_bindings = [
        binding
        for binding in revision.bindings
        if binding.provider.model_dump(mode="python").get("fact") == "row_field"
    ]

    assert row_bindings
    for binding in row_bindings:
        assert layout_designs <= set(binding.source_refs), binding.id
        assert set(binding.legal_refs) <= set(revision.legal_refs), binding.id


def test_declaration_pdf_profile_and_application_wiring_are_one_member_across_the_envelope() -> None:
    """The same edition-free members serve every supported year; no year lacks them."""
    editions = {year: _edition(year) for year in _supported_years()}
    profiles = {
        year: {str(p.id) for p in rev.extraction_profiles if p.surface == "declaracion_pdf"}
        for year, rev in editions.items()
    }
    links = {year: {(str(link.id), link.surface) for link in rev.application_links} for year, rev in editions.items()}
    xrefs = {year: {str(ref.id) for ref in rev.live_cross_references} for year, rev in editions.items()}

    assert all(profiles.values()), profiles
    assert len({frozenset(value) for value in profiles.values()}) == 1, profiles
    assert len({frozenset(value) for value in links.values()}) == 1, links
    assert len({frozenset(value) for value in xrefs.values()}) == 1, xrefs
    for year, revision in editions.items():
        construct = revision.constructs[0]
        declared = {str(link.id) for link in revision.application_links}
        assert set(construct.application_links) <= declared, year
        assert set(construct.live_cross_references) <= xrefs[year], year


def _one_recipient_two_properties(year: int) -> RetencionesAggregation:
    """One landlord letting two properties: one distinct recipient, two type-2 rows."""
    nif = "11111111H"
    rows = tuple(
        Modelo180Type2Row(
            filing_year=year,
            perceptor_nif=nif,
            perceptor_name="ARRENDADOR EJEMPLO",
            property_detail=Modelo180PropertyEvidence(
                property_key=key,
                situation="1",
                cadastral_reference=f"{key.upper()}REF",
                address=Modelo180StructuredAddress(
                    province_code="28",
                    municipality_code="079",
                    municipality="Madrid",
                    locality="Madrid",
                    postal_code="28001",
                    street_type="CL",
                    street_name="Ejemplo",
                    number_type="NUM",
                    house_number=number,
                ),
                recipient_province_code="28",
                modality="1",
                accrual_year=year,
                withholding_percentage=Decimal("19.00"),
            ),
            observations_count=1,
            taxable_base=Decimal("1000.00"),
            retencion_amount=Decimal("190.00"),
            withholding_percentage=Decimal("19.00"),
        )
        for key, number in (("property-a", "1"), ("property-b", "2"))
    )
    return RetencionesAggregation(
        modelo=_MODELO,
        period=Period.from_year_and_code(year, _PERIOD),
        rollups=(
            RetencionPerceptorRollup(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                perceptor_nif=nif,
                perceptor_name="ARRENDADOR EJEMPLO",
                scheme=RetencionScheme("arrendamiento_urbano"),
                observations_count=2,
                total_taxable_base=Decimal("2000.00"),
                total_retencion=Decimal("380.00"),
            ),
        ),
        total_perceptors=1,
        total_taxable_base=Decimal("2000.00"),
        total_retencion=Decimal("380.00"),
        type2_rows=rows,
        type2_record_count=len(rows),
    )
