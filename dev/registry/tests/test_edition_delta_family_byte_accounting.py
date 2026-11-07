"""Physical family-byte accounting follows the canonical fragment grammar."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from dev.registry.compiler.loader import load_modelo_directory
from dev.registry.edition_delta_assessment import MigrationAssessment, assess_migration_state
from dev.registry.tests.synthetic_delta_edition_support import write_sectioned_edition
from dev.registry.tests.test_edition_family_delta import (
    casillas,
    edition_family_delta_layout,
    edition_family_delta_modelo,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PREDECESSOR = str(filing_year_envelope().horizon - 1)
_SUCCESSOR = str(filing_year_envelope().horizon)


def _row(assessment: MigrationAssessment, revision: str, family: str) -> dict[str, object]:
    return dict(
        next(row for row in assessment.by_revision_family if row["revision"] == revision and row["family"] == family)
    )


def _file_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def test_generated_full_export_and_empty_successor_are_attributed_once(tmp_path: Path) -> None:
    modelo = edition_family_delta_modelo(tmp_path)
    full = write_sectioned_edition(
        modelo, _PREDECESSOR, sections={"export": edition_family_delta_layout(_PREDECESSOR, "cabecera")}
    )
    (full / "export" / "_generation.provenance.json").write_text("{}\n", encoding="utf-8")
    empty = write_sectioned_edition(
        modelo,
        _SUCCESSOR,
        manifest_extra=f'family_storage_baseline = "{_PREDECESSOR}"\nscoped_families = ["export_layouts"]\n',
        sections={"export": f'[revisions."{_SUCCESSOR}"]\nexport_layouts = []\n'},
    )
    # The loader skips this sidecar; accounting must still charge its physical
    # bytes to the export family. This fixture does not attest valid provenance.
    (empty / "export" / "_generation.provenance.json").write_text("{}\n", encoding="utf-8")

    loaded = load_modelo_directory(modelo)
    assert loaded.revisions[_PREDECESSOR].export_layouts == loaded.revisions[_SUCCESSOR].export_layouts
    assessment = assess_migration_state(modelo)
    full_export = _row(assessment, _PREDECESSOR, "export_layouts")
    empty_export = _row(assessment, _SUCCESSOR, "export_layouts")

    assert full_export["physical_bytes"] == _file_bytes(full / "export")
    assert isinstance(full_export["authored_payload_fields"], int)
    assert full_export["authored_payload_fields"] > 0
    assert empty_export["physical_bytes"] == _file_bytes(empty / "export")
    empty_physical_bytes = empty_export["physical_bytes"]
    assert isinstance(empty_physical_bytes, int)
    assert empty_physical_bytes > 0
    assert empty_export.get("authored_payload_fields", 0) == 0
    assert _row(assessment, _PREDECESSOR, "$scalars")["physical_bytes"] == (full / "revision.toml").stat().st_size
    assert _row(assessment, _SUCCESSOR, "$scalars")["physical_bytes"] == (empty / "revision.toml").stat().st_size
    assert assessment.physical_bytes == _file_bytes(modelo)


def test_authored_export_and_other_family_keep_their_own_bytes(tmp_path: Path) -> None:
    modelo = edition_family_delta_modelo(tmp_path)
    revision = write_sectioned_edition(
        modelo,
        _PREDECESSOR,
        sections={
            "casillas": casillas(_PREDECESSOR),
            "export_layouts": edition_family_delta_layout(_PREDECESSOR, "cabecera"),
        },
    )

    assessment = assess_migration_state(modelo)

    assert _row(assessment, _PREDECESSOR, "export_layouts")["physical_bytes"] == _file_bytes(
        revision / "export_layouts"
    )
    assert _row(assessment, _PREDECESSOR, "casillas")["physical_bytes"] == _file_bytes(revision / "casillas")
    assert _row(assessment, _PREDECESSOR, "$scalars")["physical_bytes"] == (revision / "revision.toml").stat().st_size
    assert assessment.physical_bytes == _file_bytes(modelo)
