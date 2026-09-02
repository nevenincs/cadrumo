from __future__ import annotations

import pytest

from ..analysis import m200_2024_full_reconciliation as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def rows():
    return subject.reconcile_bundled_m200_2024()


def test_full_reconciliation_surfaces_966_967_and_protects_unmapped_declarations(rows) -> None:
    by_id = {row.casilla_id: row for row in rows}

    assert len(rows) == 3329
    assert sum(row.origin == "restoration_candidate" for row in rows) == 156
    for casilla_id in ("00966", "00967"):
        row = by_id[casilla_id]
        assert row.source_ref_state == "mechanical_rebind"
        assert row.mechanical_source_refs_proposal is not None
        assert "aeat-dr-200-2024" in row.mechanical_source_refs_proposal
        assert "aeat-dr-200-2025" not in row.mechanical_source_refs_proposal
        assert row.export_reachability == "mapped_current_2024"
        assert row.fields
        assert all(field.printed_number == casilla_id for field in row.fields)

    unmapped = tuple(row for row in rows if row.export_reachability == "unmapped_calculation_only")
    assert len(unmapped) == 15
    assert all(row.source_ref_state == "unmapped_no_rebind" for row in unmapped)
    assert all(row.mechanical_source_refs_proposal is None for row in unmapped)


def test_reconciliation_report_is_deterministic_and_source_sha_bound(rows) -> None:
    first = subject.render_reconciliation_toml(rows)
    second = subject.render_reconciliation_toml(rows)

    assert first == second
    assert 'source_ref = "aeat-dr-200-2024"' in first or "source_ref = 'aeat-dr-200-2024'" in first
    assert "source_sha256" in first
    assert "mechanical_source_refs_proposal" in first
    assert "cross_revision_proposal_non_authoritative" in first
