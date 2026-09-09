"""The attestation census separates a checkable citation from an unfalsifiable one."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..analysis.export_derivation_attestation import (
    DerivationAttestation,
    shipped_export_attestation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _generated(root: Path, modelo: str, revision: str, fields: int) -> None:
    export = root / modelo / "revisions" / revision / "export"
    export.mkdir(parents=True)
    (export / "_generation.provenance.json").write_text(
        json.dumps({"field_derivations": [{"field": {"id": f"f{n}"}} for n in range(fields)]}),
        encoding="utf-8",
    )


def _authored(root: Path, modelo: str, revision: str, fields: int) -> None:
    layouts = root / modelo / "revisions" / revision / "export_layouts"
    layouts.mkdir(parents=True)
    (layouts / "0001-layout.toml").write_text(
        "\n".join(f"offset = {n}" for n in range(fields)),
        encoding="utf-8",
    )


def test_a_generated_revision_is_checkable(tmp_path: Path) -> None:
    """A manifest pairs each field with its design row, so the citation can be read back."""
    _generated(tmp_path, "999", "2026", fields=3)

    row = next(iter(shipped_export_attestation(tmp_path)))

    assert row.attestation is DerivationAttestation.ATTESTED
    assert row.is_checkable
    assert row.field_count == 3


def test_an_authored_revision_is_reported_as_cited_only(tmp_path: Path) -> None:
    """Citing a design without recording a derivation from it is not the same as agreeing with it."""
    _authored(tmp_path, "999", "2026", fields=4)

    row = next(iter(shipped_export_attestation(tmp_path)))

    assert row.attestation is DerivationAttestation.CITED_ONLY
    assert not row.is_checkable
    assert row.field_count == 4


def test_the_census_counts_both_populations(tmp_path: Path) -> None:
    """The ratio is the finding, so neither side may go missing from the denominator."""
    _generated(tmp_path, "998", "2026", fields=5)
    _authored(tmp_path, "999", "2026", fields=7)

    rows = tuple(shipped_export_attestation(tmp_path))

    assert {row.attestation for row in rows} == {
        DerivationAttestation.ATTESTED,
        DerivationAttestation.CITED_ONLY,
    }
    assert sum(row.field_count for row in rows) == 12


def test_the_shipped_corpus_reports_both_halves() -> None:
    """A census that saw only one half would report a checkable share that is fiction."""
    rows = tuple(shipped_export_attestation())

    assert any(row.is_checkable for row in rows)
    assert any(not row.is_checkable for row in rows), "the authored surface is not visible to this census"
