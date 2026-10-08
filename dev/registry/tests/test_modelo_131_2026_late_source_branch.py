"""The September 2026 La Palma release changes only Modelo 131's late quarters."""

from __future__ import annotations

from datetime import date
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.temporal import select_revision
from dev.registry.compiler.legal_grounding import verify_legal_reference_grounding
from dev.registry.compiler.loader import load_modelo_directory, load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _modelo():
    return load_modelo_directory(bundled_path("registry", "aeat", "modelos", "131"))


@pytest.mark.parametrize(
    ("period", "on", "expected"),
    (
        ("1T", date(2026, 4, 1), "2026"),
        ("2T", date(2026, 7, 1), "2026"),
        ("3T", date(2026, 10, 1), "2026-3t-4t"),
        ("4T", date(2027, 1, 1), "2026-3t-4t"),
    ),
)
def test_actual_2026_filing_window_selects_its_own_source_branch(period: str, on: date, expected: str) -> None:
    selected = select_revision(_modelo(), filing_year=2026, period=period, on=on)
    assert str(selected.id) == expected
    assert selected.filing_schedules[0].periods == (("1T", "2T") if expected == "2026" else ("3T", "4T"))
    assert {window.period.code for window in selected.deadline_windows} == set(selected.filing_schedules[0].periods)
    assert {str(ref) for ref in selected.constructs[0].deadline_windows} == {
        str(window.id) for window in selected.deadline_windows
    }


def test_late_hydrated_delta_rekeys_only_four_source_changed_binding_slots() -> None:
    early = _modelo().revisions["2026"]
    late = _modelo().revisions["2026-3t-4t"]
    early_by_offset = {
        (binding.provider.record, binding.provider.offset): binding
        for binding in early.bindings
        if hasattr(binding.provider, "record") and hasattr(binding.provider, "offset")
    }
    late_by_offset = {
        (binding.provider.record, binding.provider.offset): binding
        for binding in late.bindings
        if hasattr(binding.provider, "record") and hasattr(binding.provider, "offset")
    }
    assert early_by_offset.keys() == late_by_offset.keys()
    changed = {
        coordinate
        for coordinate, binding in late_by_offset.items()
        if binding.model_dump(mode="json", exclude={"inherited_from"})
        != early_by_offset[coordinate].model_dump(mode="json", exclude={"inherited_from"})
    }
    assert changed == {("page_1", 359), ("page_1", 448), ("page_1", 458), ("DPA", 29)}
    for coordinate in changed:
        binding = late_by_offset[coordinate]
        assert str(binding.id).endswith("-ceuta-melilla-la-palma")
        assert binding.provider.field.endswith("-ceuta-melilla-la-palma")
        assert "real-decreto-ley-23-2026:art-1" in binding.legal_refs
        assert "aeat-dr-131-2026-late" in binding.source_refs
        assert "aeat-modelo-131-instructions-2026-late" in binding.source_refs
    assert [item.model_dump(exclude={"inherited_from", "continuidad_origin"}) for item in early.casillas] == [
        item.model_dump(exclude={"inherited_from", "continuidad_origin"}) for item in late.casillas
    ]
    assert [item.model_dump(exclude={"inherited_from"}) for item in early.formulas] == [
        item.model_dump(exclude={"inherited_from"}) for item in late.formulas
    ]
    assert str(late.export_layouts[0].source_refs[0]) == "aeat-dr-131-2026-late"
    assert str(late.workbook_parity_refs[0].workbook_source) == "aeat-dr-131-2026-late"
    assert str(late.completeness_manifest.source_ref) == "aeat-dr-131-2026-late"
    late_rate = next(
        parameter
        for parameter in late.parameters
        if str(parameter.id) == "irpf.objective_la_palma_fractional_payment_multiplier"
    )
    assert str(late_rate.values[0].value) == "0.4"
    assert late_rate.values[0].valid_from == date(2026, 7, 1)
    assert late_rate.values[0].valid_to == date(2026, 12, 31)
    assert not any(str(item.id) == str(late_rate.id) for item in early.parameters)
    assert len(late.form_layouts) == 1
    design_sources = {str(source.source_ref) for source in late.form_layouts[0].design_sources}
    assert {ref for ref in design_sources if ref.startswith("aeat-dr-")} == {"aeat-dr-131-2026-late"}
    assert design_sources - {"aeat-dr-131-2026-late"} == {"boe-2015-1656-modelos-130-131-form"}
    assert "aeat-dr-131-2026-late" in late.constructs[0].source_refs
    assert "aeat-modelo-131-instructions-2026-late" in late.constructs[0].source_refs


def test_late_evidence_is_new_and_early_captures_remain_pinned() -> None:
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    new_design = catalogues.sources["aeat-dr-131-2026-late"]
    old_design = catalogues.sources["aeat-dr-131-2026"]
    new_guidance = catalogues.sources["aeat-modelo-131-instructions-2026-late"]
    old_guidance = catalogues.sources["aeat-modelo-131-instructions-2026-04-01"]
    assert new_design.sha256 == "b394370ae16d303a3ed7e192ca34ba1ff49dbbbea49e4d2bbe220085cc53600f"
    assert old_design.sha256 == "6d7704aa438c30dd538dbba471ac68f28d22e478bcd679ba8b49b2776a6c964a"
    assert new_guidance.sha256 == "a1f8370ac01d628910fd95ace2704c3e9e991b7265c943c0e4b4619dbf101b27"
    assert old_guidance.sha256 == "ff50d8e986968d3c2dd01f7146caa2084406cd083f4041b007b439c4493b9eac"
    assert new_design.period_selector is not None
    assert new_design.period_selector.periods == ("3T", "4T")
    verify_legal_reference_grounding(catalogues.legal["real-decreto-ley-23-2026:art-1"], source_root=bundled_path())
