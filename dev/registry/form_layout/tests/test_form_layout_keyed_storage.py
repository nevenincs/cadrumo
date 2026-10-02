"""A layout keyed against its family baseline keeps working with the generator and the converter.

The converter stores a successor's layout as a delta against its family
baseline's, so the edition states no fragment of its own. The generator must
judge such a layout by what it hydrates to, and when it writes a layout whole
again the edition must still mean the same and key afresh through the
converter. Every rewrite happens in a temporary copy of a modelo.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ...compiler.loader import load_modelo_directory, load_registry_tree
from ...edition_family_delta import collapse_keyed_families
from ...record_design_labels import DATA_ROOT
from ..cli import REGISTRY_ROOT, _is_current, _write_layout
from ..generator import generate_modelo_layouts
from ..serialization import form_layout_fragment_path, render_form_layout_toml

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FAMILY = "form_layouts"


@cache
def _registry() -> tuple[Mapping[str, ModeloDefinition], Mapping[str, SourceReference]]:
    modelos, catalogues = load_registry_tree(REGISTRY_ROOT)
    return {str(modelo.id): modelo for modelo in modelos}, catalogues.sources


def _keyed(modelo: ModeloDefinition) -> list[str]:
    return sorted(
        str(revision_id) for revision_id, revision in modelo.revisions.items() if _FAMILY in revision.scoped_families
    )


@cache
def _smallest_keyed_modelo() -> str:
    """The keyed modelo with the least source on disk, so the copies below stay cheap."""
    modelos, _sources = _registry()
    keyed = [modelo_id for modelo_id, modelo in modelos.items() if _keyed(modelo)]
    assert keyed, "no modelo stores a form layout keyed against its family baseline"
    return min(
        keyed,
        key=lambda modelo_id: sum(
            path.stat().st_size for path in (REGISTRY_ROOT / "modelos" / modelo_id).rglob("*") if path.is_file()
        ),
    )


def test_a_keyed_layout_is_judged_by_the_layout_it_hydrates_to() -> None:
    modelos, sources = _registry()
    modelo = modelos[_smallest_keyed_modelo()]
    outcomes = generate_modelo_layouts(modelo, sources=sources, data_root=DATA_ROOT)
    for revision_id in _keyed(modelo):
        revision = modelo.revisions[revision_id]
        layout = outcomes[revision_id].layout
        assert layout is not None
        path = form_layout_fragment_path(REGISTRY_ROOT / "modelos" / str(modelo.id) / "revisions" / revision_id)
        assert not path.is_file()
        assert _is_current(path, revision_id, revision, layout)
        drifted = layout.model_copy(update={"source_state_digest": "0" * 64})
        assert not _is_current(path, revision_id, revision, drifted)


def test_a_layout_written_whole_over_a_keyed_edition_keeps_its_meaning_and_keys_again(tmp_path: Path) -> None:
    modelo_id = _smallest_keyed_modelo()
    source = REGISTRY_ROOT / "modelos" / modelo_id
    copy = tmp_path / modelo_id
    shutil.copytree(source, copy)
    before = load_modelo_directory(source)
    keyed = _keyed(before)

    for revision_id in keyed:
        _write_layout(
            form_layout_fragment_path(copy / "revisions" / revision_id),
            revision_id,
            before.revisions[revision_id].form_layouts[0],
        )
    restated = load_modelo_directory(copy)
    for revision_id, revision in before.revisions.items():
        assert restated.revisions[revision_id].form_layouts == revision.form_layouts
    for revision_id in keyed:
        stated = restated.revisions[revision_id]
        assert _FAMILY not in stated.scoped_families
        assert all(operation.family != _FAMILY for operation in stated.family_overrides)
        assert form_layout_fragment_path(copy / "revisions" / revision_id).read_text(
            encoding="utf-8"
        ) == render_form_layout_toml(revision_id, stated.form_layouts[0])

    candidate = tmp_path / "candidate"
    collapse_keyed_families(copy, candidate)
    rekeyed = load_modelo_directory(candidate)
    for revision_id, revision in before.revisions.items():
        assert rekeyed.revisions[revision_id].form_layouts == revision.form_layouts
    for revision_id in keyed:
        assert not form_layout_fragment_path(candidate / "revisions" / revision_id).is_file()
        assert _FAMILY in rekeyed.revisions[revision_id].scoped_families
