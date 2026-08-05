"""Real-registry tests for revision-level legal/source construct evidence."""

from __future__ import annotations

from collections import Counter

import pytest
from pydantic import ValidationError

from .....core.resources import bundled_path
from .._coverage import (
    ConstructEvidenceLedger,
    ConstructEvidenceRow,
    audit_registry_construct_evidence,
    build_construct_evidence_ledger,
)
from ._catalogue_verification_support import _registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_construct_evidence_audit_enumerates_every_declared_construct_and_selector() -> None:
    """The evidence ledger has one exact row for each real revision declaration."""
    modelos, catalogues = _registry_tree()

    audit = audit_registry_construct_evidence(modelos, catalogues, source_root=bundled_path())

    ledgers_by_coordinate = {(ledger.modelo, ledger.revision): ledger for ledger in audit.ledgers}
    assert len(audit.ledgers) == sum(len(modelo.revisions) for modelo in modelos)
    assert audit.ok
    assert audit.gaps == ()
    assert all(row.authority_checked for ledger in audit.ledgers for row in ledger.rows)

    for modelo in modelos:
        for revision in modelo.revisions.values():
            ledger = ledgers_by_coordinate[(modelo.id, revision.id)]
            by_coordinate = {(row.kind, row.construct_id): row for row in ledger.rows}
            assert Counter(row.kind for row in ledger.rows) == Counter(
                {
                    "formula": len(revision.formulas),
                    "parameter": len(revision.parameters),
                    "binding": len(revision.bindings),
                    "relation": len(revision.relations),
                    "selector": len(revision.bindings),
                },
            )

            for kind, declarations in (
                ("formula", revision.formulas),
                ("parameter", revision.parameters),
                ("binding", revision.bindings),
                ("relation", revision.relations),
            ):
                for declaration in declarations:
                    row = by_coordinate[(kind, declaration.id)]
                    assert row.status == "grounded"
                    assert row.legal_refs == declaration.legal_refs
                    assert row.source_refs == declaration.source_refs

            for binding in revision.bindings:
                row = by_coordinate[("selector", binding.id)]
                assert row.binding_id == binding.id
                assert row.status == "inherited"
                assert row.legal_refs == binding.legal_refs
                assert row.source_refs == binding.source_refs
                assert "inherited" in row.reason


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
    from .._authority import bundled_authority

    snapshot = bundled_authority().snapshot("130", filing_year=2026, period="1T")
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
