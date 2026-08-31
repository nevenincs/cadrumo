"""Modelo 193 registry behaviour for annual Modelo 123 summary links."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId
from .....core.resources.bundled_data import bundled_path
from .....domain.deadlines.festivos import shift_deadline
from .....tests.registry_observations import registry_grounded_modelo_observation
from .._validate import RegistryValidator
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..formula_runtime import calculate_registry_snapshot
from ..relations import relation_source_requirements, resolve_relation_values_from_observations
from ..snapshot import build_snapshot
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_193_guidance_and_layout_sources_are_separated() -> None:
    modelo, catalogues = _committed_modelo("193")
    note = catalogues.sources["aeat-modelo-193-296-note-2025"]

    assert "aeat-modelo-193-296-note-2025" in modelo.source_refs
    assert note.evidence_tier == "official_source_guidance"
    assert note.authority == "aeat"
    assert note.kind == "manual_pdf"
    assert (bundled_path() / note.corpus_path).is_file()
    record_design = catalogues.sources["aeat-dr-193-2025"]
    assert record_design.evidence_tier == "layout_authority"
    assert "2025" in record_design.source_url
    assert catalogues.sources["boe-modelo-193-2011-form"].evidence_tier == "layout_authority"
    # The revision whose workbook parity ref names the 2025 design, which is what
    # the assertions below check. The id was stale -- modelo 193 declares "2024"
    # and "2025-y-siguientes", never "2024-y-siguientes" -- so this raised a
    # KeyError on the lookup and no assertion past this line had ever run.
    revision = modelo.revisions["2025-y-siguientes"]
    assert revision.workbook_parity_refs[0].id == "modelo-193-dr-pdf-2025"
    assert revision.workbook_parity_refs[0].workbook_source == "aeat-dr-193-2025"
    for formula in revision.formulas:
        for citation in formula.source_citations:
            assert catalogues.sources[citation.source_ref].evidence_tier == "official_source_guidance"
    for binding in revision.bindings:
        for citation in binding.source_citations:
            assert catalogues.sources[citation.source_ref].evidence_tier == "official_source_guidance"


def test_modelo_193_validates_and_gates_workflow_surfaces_through_snapshot() -> None:
    modelo, catalogues = _committed_modelo("193")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )

    assert snapshot.revision.orden_aplicabilidad == ("orden-eha-3377-2011:art-1",)
    construct = snapshot.revision.constructs[0]
    linked_surfaces = {
        link.surface for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert {
        "calculation",
        "filing",
        "review",
        "approval",
        "reconciliation",
        "extractor",
        "portal",
        "workflow",
    } <= linked_surfaces


def test_modelo_193_annual_deadline_is_grounded_to_current_revision() -> None:
    modelo, catalogues = _committed_modelo("193")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="0A",
    )
    revision = snapshot.revision
    construct = revision.constructs[0]
    windows = {window.id: window for window in revision.deadline_windows}
    schedule = next(item for item in revision.filing_schedules if item.id == "modelo-193-anual")
    deadline_link = next(item for item in revision.application_links if item.id == "modelo-193-deadline")

    assert deadline_link.surface == "deadline"
    assert deadline_link.consumer == "cadrumo.domain.deadlines"
    assert deadline_link.requires_snapshot is True
    assert catalogues.legal["orden-eha-3377-2011:art-1"].evidence_tier == "legal_authority"
    assert catalogues.legal["rd-439-2007:art-108"].evidence_tier == "legal_authority"
    assert catalogues.sources["aeat-modelo-193-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-193-2011-form"].evidence_tier == "layout_authority"

    assert "modelo-193-deadline" in construct.application_links
    # This revision owns the 2025 ejercicio, so it enumerates the 2025 window
    # only. It previously listed the 2024 window too, and modelo 193's 2024
    # revision listed the 2025 one -- each revision carried the other's window
    # as well as its own. The authority collects deadline windows across ALL
    # revisions of a modelo without deduplicating, so that duplication returned
    # the same annual deadline twice to an operator asking for the year.
    # A window belongs to the revision covering its PERIOD year, not its
    # filing_year: "2025 0A" is filed in January 2026 and is still the 2025
    # ejercicio.
    assert construct.deadline_windows == ("modelo-193-2025-0a",)
    assert construct.filing_schedules == ("modelo-193-anual",)
    assert schedule.period_kind == "annual"
    assert schedule.periods == ("0A",)
    assert len(schedule.profile_conditions) == 1
    assert schedule.profile_conditions[0].field == "pays_capital_income_with_retencion"

    # The 2024 window moved to the revision that owns the 2024 ejercicio; this
    # snapshot is the 2025-y-siguientes revision and carries its own only.
    expected_windows = {
        # The window stores the NOMINAL statutory close from
        # orden-eha-3377-2011 art. 5, the month-end the plazo names, never AEAT's
        # published operational date. 31 January 2026 is a Saturday, so the
        # operational date IS 2 February -- but that is derived on read by
        # shift_deadline and asserted below beside the stored value. Storing the
        # shifted date instead reports shifted=False / business_day, which states
        # that no shift occurred and discards the statutory date; the two forms
        # are indistinguishable on the operator-facing date alone, which is why
        # both halves are asserted.
        "modelo-193-2025-0a": (2025, "2025 0A", date(2026, 1, 1), date(2026, 1, 31)),
    }
    assert set(windows) == set(expected_windows)
    for window_id, (filing_year, period, opens_on, closes_on) in expected_windows.items():
        window = windows[window_id]
        assert window.filing_year == filing_year
        assert str(window.period) == period
        assert window.period_kind == "annual"
        assert window.opens_on == opens_on
        assert window.closes_on == closes_on
        assert len(window.applicability_conditions) == 1
        assert window.applicability_conditions[0].field == "pays_capital_income_with_retencion"
        # Grounded on art. 5, which establishes the plazo, rather than art. 1,
        # which approves the modelo.
        assert window.legal_refs == ("orden-eha-3377-2011:art-5",)
        shift = shift_deadline(window.closes_on, modelo="193", ccaa_code=None)
        assert (shift.adjusted_close_date, shift.shifted, shift.shift_reason) == (
            date(2026, 2, 2),
            True,
            "sabado",
        )


@pytest.mark.parametrize(
    ("revision_id", "filing_year", "opens_on", "closes_on"),
    [
        ("2024", 2024, date(2025, 1, 1), date(2025, 1, 31)),
        ("2025-y-siguientes", 2025, date(2026, 1, 1), date(2026, 1, 31)),
    ],
)
def test_modelo_193_deadline_identity_is_the_tax_year(
    revision_id: str,
    filing_year: int,
    opens_on: date,
    closes_on: date,
) -> None:
    modelo, _catalogues = _committed_modelo("193")
    (window,) = modelo.revisions[revision_id].deadline_windows

    assert window.filing_year == window.period.filing_year == filing_year
    assert str(window.period) == f"{filing_year} 0A"
    assert window.opens_on == opens_on
    assert window.closes_on == closes_on
    assert window.legal_refs == ("orden-eha-3377-2011:art-5",)
    expected_calendar_ref = (
        "aeat-calendario-contribuyente-2025"
        if filing_year == 2024
        else "aeat-calendario-contribuyente-2026-hasta-2-febrero"
    )
    assert expected_calendar_ref in window.source_refs


def test_modelo_193_relations_resolve_against_modelo_123_registry() -> None:
    snapshot = _committed_snapshot("193", 2025, "0A")
    snapshot_123 = _committed_snapshot("123", 2025, "1T")

    modelo_123_outputs = {casilla.id for casilla in snapshot_123.revision.casillas}
    relation_source_casilla_ids = {relation.source_casilla_id for relation in snapshot.revision.relations}
    assert relation_source_casilla_ids <= modelo_123_outputs
    assert {tuple(relation.source_periods) for relation in snapshot.revision.relations} == {("1T", "2T", "3T", "4T")}


def test_modelo_193_calculation_aggregates_modelo_123_quarterly_observations() -> None:
    snapshot = _committed_snapshot("193", 2025, "0A")
    snapshot_123 = _committed_snapshot("123", 2025, "1T")
    source_casilla_ids = {casilla.id: casilla for casilla in snapshot_123.revision.casillas}
    requirements = relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
    observed_by_period: dict[str, dict[CasillaId, Decimal]] = {}
    for requirement in requirements:
        source_casilla_id = requirement.source_casilla_ids[0]
        source_casilla = source_casilla_ids[source_casilla_id]
        for index, period in enumerate(requirement.periods):
            value = _value_for(source_casilla.data_type, index)
            observed_by_period.setdefault(period, {})[source_casilla_id] = value
    observations = tuple(
        registry_grounded_modelo_observation(
            modelo="123",
            filing_year=2025,
            period=period,
            casilla_values=casilla_values,
        )
        for period, casilla_values in sorted(observed_by_period.items())
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2025,
        period="0A",
    )
    binding_values = {"modelo-193-123-perceptores-anual": Decimal("2")}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        date_context={"filing_period": date(2025, 12, 31)},
        binding_values=binding_values,
        relation_values=relation_values,
    )

    entries_by_target = {entry.target_casilla_id: entry for entry in result.entries}
    assert "decl.total-perceptores" not in entries_by_target
    assert result.values["decl.total-perceptores"] == Decimal("2")
    assert "modelo-193-rel-123-base-anual" in entries_by_target["decl.base-total"].operand_refs
    assert "modelo-193-rel-123-retenciones-anual" in entries_by_target["decl.retenciones-total"].operand_refs


def _value_for(data_type: str, period_index: int) -> Decimal:
    quarter = Decimal(period_index + 1)
    if data_type == "integer":
        return quarter
    return Decimal("10") * quarter
