"""Real-behaviour tests for the hand-authored layout type-column screen.

The detector case copies a real hand-authored revision's layouts to a scratch
root, unsigns one field the official design types signed, and requires the
screen to name it. The working tree is never touched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from cadrumo.core.toml import parse_toml, render_toml
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

from ..analysis.hand_authored_type_column import (
    Alignment,
    hand_authored_revisions,
    revision_findings,
    screen_authority,
)
from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


def _records(document: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for body in document.get("revisions", {}).values():
        for layout in body.get("export_layouts", []):
            records.extend(layout.get("records", []))
    return records


def _aligned_signed_field(authority: ValidatedRegistryAuthority) -> tuple[str, str, Path, str, str]:
    """Return a hand-authored field the screen aligns to its design and ships signed."""
    for modelo, revision, root in hand_authored_revisions(authority):
        alignments, _ = revision_findings(authority, modelo=modelo, revision=revision, revision_root=root)
        aligned = {(item.layout_file, item.record_id) for item in alignments if item.alignment is Alignment.ALIGNED}
        for layout_file in sorted((root / "export_layouts").glob("*.toml")):
            for record in _records(parse_toml(layout_file.read_text(encoding="utf-8"))):
                if (layout_file.name, str(record.get("id", ""))) not in aligned:
                    continue
                for field in record.get("fields", []):
                    if field.get("signed") and field.get("data_type") == "money":
                        return modelo, revision, root, layout_file.name, str(field["id"])
    raise AssertionError("no hand-authored aligned signed money field exists, so the detector has nothing to unsign")


def test_unsigning_a_design_signed_field_is_reported_as_a_contradiction(
    authority: ValidatedRegistryAuthority, tmp_path: Path
) -> None:
    modelo, revision, root, layout_name, field_id = _aligned_signed_field(authority)
    _, before = revision_findings(authority, modelo=modelo, revision=revision, revision_root=root)
    assert field_id not in {item.field_id for item in before}

    (tmp_path / "export_layouts").mkdir()
    for layout_file in sorted((root / "export_layouts").glob("*.toml")):
        document = parse_toml(layout_file.read_text(encoding="utf-8"))
        if layout_file.name == layout_name:
            for record in _records(document):
                for field in record.get("fields", []):
                    if str(field.get("id")) == field_id:
                        field["signed"] = False
        (tmp_path / "export_layouts" / layout_file.name).write_text(render_toml(document), encoding="utf-8")

    _, after = revision_findings(authority, modelo=modelo, revision=revision, revision_root=tmp_path)

    unsigned = [item for item in after if item.field_id == field_id]
    assert len(unsigned) == 1
    assert unsigned[0].blocked_reason is None


def test_the_screen_reports_findings_that_name_their_modelo_and_revision(
    authority: ValidatedRegistryAuthority,
) -> None:
    alignments, contradictions = screen_authority(authority)

    assert alignments, "no hand-authored record was examined, so the screen measured nothing"
    for finding in (*alignments, *contradictions):
        assert finding.revision in authority.modelo(finding.modelo).revisions
