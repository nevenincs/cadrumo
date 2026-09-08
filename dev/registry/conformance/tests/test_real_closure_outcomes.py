"""Real-authority outcome proofs for the registry closure loader."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from functools import cache

import pytest
from pydantic import ValidationError

from cadrumo.core.modelo import Modelo
from cadrumo.domain.calculations.registry.authority import bundled_authority

from ..closure import load_registry_closure_report

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
_AS_OF = date(2026, 8, 24)


@cache
def _canonical_report():
    return load_registry_closure_report(as_of=_AS_OF, registry_authority=bundled_authority())


def test_real_below_grade_row_is_complete_without_filing_export() -> None:
    report = _canonical_report()
    row = next(item for item in report.rows if (item.modelo, item.revision) == (Modelo.M036, "2025-02-03-y-siguientes"))
    assert row.temporal_coverage.status == "validated"
    assert row.filing_export is not None
    assert (row.filing_export.outcome, row.filing_export.evidence, row.filing_export.refusal) == (
        "not_applicable",
        (),
        None,
    )
    assert row.predicate_outcome == "satisfied"
    assert row.refusals == ()
    assert report.satisfied_revision_count >= 1
    assert not report.release_eligible


def test_real_grade_scope_row_guards_bite_both_participation_mutations() -> None:
    report = _canonical_report()
    below_grade = next(
        item for item in report.rows if (item.modelo, item.revision) == (Modelo.M036, "2025-02-03-y-siguientes")
    )
    filing_grade = next(item for item in report.rows if (item.modelo, item.revision) == (Modelo.M100, "2025"))
    assert below_grade.filing_export is not None and filing_grade.filing_export is not None
    below_payload = _declared_row_fields(below_grade)
    below_payload["filing_export"] = filing_grade.filing_export.model_dump(mode="python")
    below_payload["filing_export"].update(modelo=below_grade.modelo, revision=below_grade.revision)
    with pytest.raises(ValidationError, match="below-filing temporal coverage requires"):
        below_grade.__class__.model_validate(below_payload)
    filing_payload = _declared_row_fields(filing_grade)
    filing_payload["filing_export"] = below_grade.filing_export.model_dump(mode="python")
    filing_payload["filing_export"].update(modelo=filing_grade.modelo, revision=filing_grade.revision)
    with pytest.raises(ValidationError, match="filing-grade temporal coverage requires"):
        filing_grade.__class__.model_validate(filing_payload)


def test_real_loader_reports_stale_layout_bytes_from_a_live_catalogue_mutation() -> None:
    authority = bundled_authority()
    modelo = authority.modelo(Modelo.M100)
    revision = modelo.revisions["2025"]
    source_id = next(
        ref
        for layout in revision.export_layouts
        for ref in layout.source_refs
        if authority.catalogues.sources[ref].evidence_tier == "layout_authority"
    )
    source = authority.catalogues.sources[source_id]
    catalogues = authority.catalogues.model_copy(
        update={"sources": {**authority.catalogues.sources, source_id: source.model_copy(update={"sha256": "0" * 64})}}
    )
    mutated = replace(authority, catalogues=catalogues, _snapshots={})
    report = load_registry_closure_report(as_of=_AS_OF, registry_authority=mutated)
    row = next(item for item in report.rows if (item.modelo, item.revision) == (Modelo.M100, "2025"))
    assert row.filing_export is not None
    assert row.filing_export.refusal is not None
    assert (row.filing_export.outcome, row.filing_export.refusal.reason) == ("refused", "stale_evidence")
    assert row.predicate_outcome == "refused"


def test_real_loader_reports_cross_limb_disagreement_from_divergent_authority_cache() -> None:
    authority = bundled_authority()
    modelo = authority.modelo(Modelo.M303)
    selected = modelo.revisions["2025"]
    selector = selected.period_selector.model_copy(update={"years": (2026,), "year_from": None, "year_to": None})
    divergent_revision = selected.model_copy(update={"period_selector": selector})
    divergent_modelo = modelo.model_copy(update={"revisions": {divergent_revision.id: divergent_revision}})
    mutated = replace(
        authority, _modelos_by_id={**authority._modelos_by_id, divergent_modelo.id: divergent_modelo}, _snapshots={}
    )
    report = load_registry_closure_report(as_of=_AS_OF, registry_authority=mutated)
    row = next(item for item in report.rows if (item.modelo, item.revision) == (Modelo.M303, "2026-y-siguientes"))
    assert row.temporal_coverage.failure_code == "selected_revision_mismatch"
    assert row.filing_export is not None
    assert row.filing_export.refusal is not None
    assert (row.filing_export.outcome, row.filing_export.refusal.reason) == ("refused", "cross_limb_disagreement")
    assert row.predicate_outcome == "refused"


def _declared_row_fields(row) -> dict[str, object]:
    return {name: getattr(row, name) for name in type(row).model_fields}
