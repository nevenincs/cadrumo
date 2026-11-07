"""The attestation census separates a checkable citation from an unfalsifiable one."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    revision_covering,
)

from ..analysis.export_derivation_attestation import (
    DerivationAttestation,
    shipped_export_attestation,
)
from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Modelo 309's edition serving the support floor, and its oldest authored edition.
_FLOOR_EDITION = str(revision_covering("309", filing_year_envelope().floor).id)
_OLDEST_EDITION = str(authored_revisions("309")[0].id)


def _definitions(*modelo_ids: str) -> tuple[ModeloDefinition, ...]:
    authority = compiled_bundled_authority()
    return tuple(authority.modelo(modelo_id) for modelo_id in modelo_ids)


def _generated(root: Path, modelo: str, revision: str, fields: int) -> None:
    export = root / modelo / "revisions" / revision / "export"
    export.mkdir(parents=True)
    (export / "_generation.provenance.json").write_text(
        json.dumps({"field_derivations": [{"field": {"id": f"f{n}"}} for n in range(fields)]}),
        encoding="utf-8",
    )


def test_a_generated_revision_is_checkable(tmp_path: Path) -> None:
    """A manifest pairs each field with its design row, so the citation can be read back."""
    _generated(tmp_path, "309", _FLOOR_EDITION, fields=3)

    rows = {row.revision: row for row in shipped_export_attestation(_definitions("309"), tmp_path)}

    assert rows[_FLOOR_EDITION].attestation is DerivationAttestation.ATTESTED
    assert rows[_FLOOR_EDITION].is_checkable
    assert rows[_FLOOR_EDITION].field_count == 3


def test_an_authored_revision_is_reported_as_cited_only(tmp_path: Path) -> None:
    """Citing a design without recording a derivation from it is not the same as agreeing with it."""
    rows = {row.revision: row for row in shipped_export_attestation(_definitions("309"), tmp_path)}

    assert {row.attestation for row in rows.values()} == {DerivationAttestation.CITED_ONLY}
    assert not rows[_FLOOR_EDITION].is_checkable
    assert rows[_FLOOR_EDITION].field_count == 78


def test_the_census_counts_both_populations(tmp_path: Path) -> None:
    """The ratio is the finding, so neither side may go missing from the denominator."""
    _generated(tmp_path, "309", _FLOOR_EDITION, fields=5)

    rows = {row.revision: row for row in shipped_export_attestation(_definitions("309"), tmp_path)}

    assert rows[_FLOOR_EDITION].attestation is DerivationAttestation.ATTESTED
    assert rows[_OLDEST_EDITION].attestation is DerivationAttestation.CITED_ONLY
    assert (rows[_FLOOR_EDITION].field_count, rows[_OLDEST_EDITION].field_count) == (5, 64)


def test_a_revision_inheriting_its_layout_is_counted_not_omitted(tmp_path: Path) -> None:
    """Modelo 100's later editions declare no export_layouts directory yet ship their predecessor's layout."""
    revisions_root = bundled_path("registry", "aeat", "modelos", "100", "revisions")
    authored = {str(revision.id) for revision in authored_revisions("100")}
    inheriting = {
        revision_id for revision_id in authored if not (revisions_root / revision_id / "export_layouts").exists()
    }
    assert inheriting

    revisions = {row.revision for row in shipped_export_attestation(_definitions("100"), tmp_path)}

    assert authored <= revisions


def test_the_shipped_corpus_reports_both_halves() -> None:
    """A census that saw only one half would report a checkable share that is fiction."""
    rows = tuple(shipped_export_attestation())

    assert any(row.is_checkable for row in rows)
    assert any(not row.is_checkable for row in rows), "the authored surface is not visible to this census"
