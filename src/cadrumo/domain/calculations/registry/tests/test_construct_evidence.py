"""Real-registry tests for revision-level legal/source construct evidence."""

from __future__ import annotations

from collections import Counter
from datetime import date

import pytest
from pydantic import ValidationError

from .....core.resources.bundled_data import bundled_path
from .....tests.registry_snapshot import build_snapshot
from ..authority import bundled_authority
from ..coverage import (
    ConstructEvidenceLedger,
    ConstructEvidenceRow,
    audit_registry_construct_evidence,
    build_construct_evidence_ledger,
)
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_construct_evidence_audit_enumerates_every_declared_construct_and_selector() -> None:
    """The evidence ledger has one exact row for each real revision declaration."""
    authority = bundled_authority()
    modelos = authority.modelos
    audit = audit_registry_construct_evidence(authority)

    ledgers_by_coordinate = {(ledger.modelo, ledger.revision): ledger for ledger in audit.ledgers}
    expected_ledger_coordinates = {
        (modelo.id, revision.id) for modelo in modelos for revision in modelo.revisions.values()
    }
    assert set(ledgers_by_coordinate) == expected_ledger_coordinates
    assert len(audit.ledgers) == len(expected_ledger_coordinates)
    assert audit.ok
    assert audit.filing_gaps == ()
    assert audit.inspection_gaps

    expected_inspection_gap_coordinates = set()
    actual_inspection_gap_coordinates = set()

    for modelo in modelos:
        for revision in modelo.revisions.values():
            ledger = ledgers_by_coordinate[(modelo.id, revision.id)]
            by_coordinate = {(row.kind, row.construct_id): row for row in ledger.rows}
            expected_coordinates = {
                (kind, declaration.id)
                for kind, declarations in (
                    ("formula", revision.formulas),
                    ("parameter", revision.parameters),
                    ("binding", revision.bindings),
                    ("relation", revision.relations),
                )
                for declaration in declarations
            }
            expected_coordinates.update(("selector", binding.id) for binding in revision.bindings)
            assert set(by_coordinate) == expected_coordinates
            assert Counter(row.kind for row in ledger.rows) == Counter(
                coordinate[0] for coordinate in expected_coordinates
            )

            inspection_gap_coordinates = {(row.kind, row.construct_id) for row in ledger.gaps}
            if ledger.filing_eligible:
                assert not inspection_gap_coordinates
            else:
                assert inspection_gap_coordinates == expected_coordinates
                expected_inspection_gap_coordinates.update(
                    (ledger.modelo, ledger.revision, *coordinate) for coordinate in expected_coordinates
                )
                actual_inspection_gap_coordinates.update(
                    (ledger.modelo, ledger.revision, *coordinate) for coordinate in inspection_gap_coordinates
                )

            for kind, declarations in (
                ("formula", revision.formulas),
                ("parameter", revision.parameters),
                ("binding", revision.bindings),
                ("relation", revision.relations),
            ):
                for declaration in declarations:
                    row = by_coordinate[(kind, declaration.id)]
                    expected_status = "grounded" if ledger.filing_eligible else "unvalidated"
                    assert row.status == expected_status
                    assert row.authority_checked is ledger.filing_eligible
                    assert row.legal_refs == declaration.legal_refs
                    assert row.source_refs == declaration.source_refs

            for binding in revision.bindings:
                row = by_coordinate[("selector", binding.id)]
                assert row.binding_id == binding.id
                expected_status = "inherited" if ledger.filing_eligible else "unvalidated"
                assert row.status == expected_status
                assert row.authority_checked is ledger.filing_eligible
                assert row.legal_refs == binding.legal_refs
                assert row.source_refs == binding.source_refs
                expected_reason = "inherited" if ledger.filing_eligible else "no validated registry authority"
                assert expected_reason in row.reason

    assert actual_inspection_gap_coordinates == expected_inspection_gap_coordinates

    m038 = {modelo.id: modelo for modelo in modelos}["038"]
    m038_revisions = tuple(sorted(m038.revisions.values(), key=lambda revision: revision.id))
    assert {
        revision.id: (
            revision.valid_from,
            revision.valid_to,
            revision.period_selector.years,
            revision.period_selector.year_from,
            revision.period_selector.year_to,
            revision.period_selector.periods,
        )
        for revision in m038_revisions
    } == {
        "2024-desde-06": (
            date(2024, 6, 1),
            date(2024, 12, 31),
            (2024,),
            None,
            None,
            ("06", "07", "08", "09", "10", "11", "12"),
        ),
        "2025-y-siguientes": (
            date(2025, 1, 1),
            None,
            (),
            2025,
            None,
            ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"),
        ),
    }

    for m038_revision in m038_revisions:
        m038_ledger = ledgers_by_coordinate[(m038.id, m038_revision.id)]
        assert not (
            m038_revision.formulas or m038_revision.parameters or m038_revision.bindings or m038_revision.relations
        )
        assert m038_ledger.authority_scope == "inspection_only"
        assert m038_ledger.rows == ()
        assert m038_ledger.gaps == ()


def test_construct_evidence_rows_keep_incomplete_refs_explicit() -> None:
    """A partial declaration is unresolved rather than reported as grounded."""
    row = ConstructEvidenceRow(
        kind="formula",
        construct_id="formula-without-source",
        status="unresolved",
        legal_refs=("ley-35-2006:art-1",),
        reason="source declaration is absent",
    )

    assert row.status == "unresolved"
    assert row.legal_refs == ("ley-35-2006:art-1",)
    assert row.source_refs == ()

    with pytest.raises(ValidationError, match="grounded construct evidence"):
        ConstructEvidenceRow(
            kind="formula",
            construct_id="formula-without-source",
            status="grounded",
            legal_refs=("ley-35-2006:art-1",),
            reason="incomplete evidence",
        )


def test_complete_construct_evidence_requires_the_authority_check_marker() -> None:
    """Reference presence alone cannot claim corpus-reconciled evidence."""
    with pytest.raises(ValidationError, match="authority-checked registry validation boundary"):
        ConstructEvidenceRow(
            kind="formula",
            construct_id="formula-without-authority-check",
            status="grounded",
            legal_refs=("ley-35-2006:art-1",),
            source_refs=("aeat-source-1",),
            reason="refs are present",
        )


def test_public_construct_ledger_keeps_reference_presence_unvalidated() -> None:
    """The public snapshot projection cannot manufacture validated authority."""
    modelo, catalogues = _committed_modelo("130")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )
    ledger = build_construct_evidence_ledger(snapshot)

    assert ledger.gaps
    assert any(row.status == "unvalidated" for row in ledger.rows)
    assert all(not row.authority_checked for row in ledger.rows)


def test_construct_evidence_ledger_rejects_duplicate_kind_and_identity() -> None:
    """The ledger cannot hide two rows behind one construct coordinate."""
    row = ConstructEvidenceRow(
        kind="formula",
        construct_id="formula-1",
        status="unresolved",
        reason="duplicate coordinate test",
    )

    with pytest.raises(ValidationError, match="unique kind/id coordinates"):
        ConstructEvidenceLedger(modelo="100", revision="2025", rows=(row, row))
