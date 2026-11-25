"""A copy of the shipped Modelo 296 tree with its perceptor record's second field re-declared."""

from __future__ import annotations

import shutil
from pathlib import Path

from cadrumo.core.toml import load_toml, render_toml
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions

from ..conformance.stamp import bundled_registry_root

_LAYOUT_REVISION = next(
    revision
    for revision in authored_revisions("296")
    if revision.valid_to is not None and revision.valid_to.year > revision.valid_from.year
)
"""The one closed Modelo 296 revision that spans several exercises and carries the perceptor record."""

REVISION = str(_LAYOUT_REVISION.id)
PERCEPTOR_RECORD = Path("revisions") / REVISION / "export" / "0002-record-m296-perceptor.toml"


def modelo_296_with_second_field_length(tmp_path: Path, *, length: int) -> Path:
    """Copy the shipped Modelo 296 tree, re-declaring one field's position count."""
    modelo_dir = tmp_path / "296"
    shutil.copytree(bundled_registry_root() / "modelos" / "296", modelo_dir)
    record = modelo_dir / PERCEPTOR_RECORD
    document = load_toml(record)
    export_layouts = document["revisions"][REVISION]["export_layouts"]
    perceptor = next(item for layout in export_layouts for item in layout["records"] if item["id"] == "m296-perceptor")
    second_field = next(
        field
        for field in perceptor["fields"]
        if field["id"] == f"m296-{_LAYOUT_REVISION.valid_from.year}.perceptor.f002"
    )
    assert (second_field["offset"], second_field["length"]) == (2, 3)
    second_field["length"] = length
    record.write_text(render_toml(document), encoding="utf-8", newline="\n")
    return modelo_dir
