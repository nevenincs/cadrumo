"""Restatement dropping reads each family's storage baseline, not only a named predecessor.

An edition can declare an explicit no-predecessor root and still store a family
against an earlier edition's payload through ``casilla_storage_baseline`` or
``family_storage_baseline``. Such an edition inherits from that baseline, so a
member it restates byte for byte is a restatement the drop must find; reading
only the string ``predecessor`` skipped the edition as a root and left every
restatement in place.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import tomlkit

from cadrumo.core.resources.bundled_data import bundled_path

from .. import edition_delta_migration as migration

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "322"
_SECTION = "casillas"


def _storage_rooted_edition(modelo_dir: Path) -> tuple[str, str]:
    """An edition declaring a no-predecessor root while storing casillas against a baseline."""
    for revision_dir in sorted((modelo_dir / "revisions").iterdir()):
        manifest = migration._read_edition(modelo_dir, revision_dir.name).manifest
        baseline = manifest.get("casilla_storage_baseline")
        if migration._declared_predecessor(manifest) is None and isinstance(baseline, str):
            return revision_dir.name, baseline
    raise LookupError(f"modelo {_MODELO} has no storage-rooted edition")


def _family() -> migration._DroppableFamily:
    return next(family for family in migration._DROPPABLE_FAMILIES if family.section == _SECTION)


def _copied_modelo(tmp_path: Path) -> Path:
    target = tmp_path / "modelos" / _MODELO
    shutil.copytree(bundled_path("registry", "aeat", "modelos", _MODELO), target)
    return target


def test_a_storage_rooted_edition_is_assessed_rather_than_skipped_as_a_root(tmp_path: Path) -> None:
    modelo_dir = _copied_modelo(tmp_path)
    revision_id, _baseline = _storage_rooted_edition(modelo_dir)

    drop = migration._plan_edition_drop(modelo_dir, revision_id, families=migration._DROPPABLE_FAMILIES)

    assert drop.skipped is None
    assert all(not family.dropped for family in drop.families)


def test_a_member_restated_from_the_storage_baseline_is_planned_as_dropped(tmp_path: Path) -> None:
    modelo_dir = _copied_modelo(tmp_path)
    revision_id, _baseline = _storage_rooted_edition(modelo_dir)
    family = _family()
    stated = {
        migration._identity_of(block.row, family)
        for fragment in migration._read_family_fragments(modelo_dir / "revisions" / revision_id, _SECTION)
        for block in fragment.blocks
    }
    inherited = [
        member
        for member in migration._materialised_members(migration._read_edition(modelo_dir, revision_id).table, _SECTION)
        if migration._identity_of(member, family) not in stated
    ]
    member = inherited[0]
    (fragment, *_rest) = migration._read_family_fragments(modelo_dir / "revisions" / revision_id, _SECTION)
    document = tomlkit.parse(fragment.path.read_text(encoding="utf-8"))
    document["revisions"][revision_id][_SECTION].append(member)
    fragment.path.write_text(tomlkit.dumps(document), encoding="utf-8")

    drop = migration._plan_edition_drop(modelo_dir, revision_id, families=migration._DROPPABLE_FAMILIES)

    (casillas,) = [planned for planned in drop.families if planned.section == _SECTION]
    assert migration._identity_of(member, family) in casillas.dropped
