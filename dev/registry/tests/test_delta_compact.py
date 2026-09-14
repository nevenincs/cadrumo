"""Source delta reduction uses real typed construction, without granting filing authority."""

import json
from pathlib import Path

import pytest

from cadrumo.core.i18n.render import override_locales_root
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
)
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from dev.registry.compact import fingerprint
from dev.registry.compiler.loader import load_modelo_directory
from dev.registry.delta_compact import compact_deltas, differences

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def tree(tmp_path: Path) -> Path:
    directory = tmp_path / "999"
    directory.mkdir()
    (directory / "manifest.toml").write_text(
        '[modelo]\nid = "999"\ntax_domain = "iva"\ncadence = "annual"\njurisdiction = "ES-AEAT"\n'
        'legal_refs = ["ley-58-2003:art-29"]\nsource_refs = ["aeat-manual"]\n',
        encoding="utf-8",
    )
    for year in (2024, 2025):
        edition = directory / "revisions" / str(year)
        section = edition / "bindings"
        section.mkdir(parents=True)
        (edition / "revision.toml").write_text(
            f'[revisions."{year}"]\nvalid_from = {year}-01-01\nvalid_to = {year}-12-31\n'
            + ('predecessor = "2024"\n' if year == 2025 else "")
            + f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
            + 'legal_refs = ["ley-58-2003:art-29"]\nsource_refs = ["aeat-manual"]\n',
            encoding="utf-8",
        )
        (section / "0001-declarations.toml").write_text(
            f'[[revisions."{year}".bindings]]\nid = "fixture-input" # original evidence note\n'
            'provider = { kind = "manual_input", record = "page_1", field = "campo-1", '
            'offset = 1, length = 1, data_type = "text" }\n'
            'value = { data_type = "text", channel = "text" }\n'
            'legal_refs = ["ley-58-2003:art-29"]\nsource_refs = ["aeat-manual"]\n',
            encoding="utf-8",
        )
    return directory


def test_rehearsal_does_not_change_source(tmp_path: Path) -> None:
    directory = tree(tmp_path)
    before = fingerprint(directory)
    receipt = compact_deltas(directory, tmp_path / "work")
    assert receipt["dropped_members"] == 1
    assert receipt["applied"] is False
    assert fingerprint(directory) == before


def test_apply_preserves_every_typed_field_and_comment_then_is_minimal(tmp_path: Path) -> None:
    directory = tree(tmp_path)
    before = load_modelo_directory(directory)
    receipt = compact_deltas(directory, tmp_path / "work", apply=True)
    assert receipt["dropped_members"] == 1
    assert differences(before, load_modelo_directory(directory)) == []
    assert not (directory / "revisions" / "2025" / "bindings").exists()
    manifest = directory / "revisions" / "2025" / "revision.toml"
    assert "fixture-input commentary: # original evidence note" in manifest.read_text(encoding="utf-8")
    again = compact_deltas(directory, tmp_path / "again")
    assert again["dropped_members"] == 0


def test_changed_binding_is_never_dropped(tmp_path: Path) -> None:
    directory = tree(tmp_path)
    path = directory / "revisions" / "2025" / "bindings" / "0001-declarations.toml"
    path.write_text(path.read_text(encoding="utf-8").replace("offset = 1", "offset = 2"), encoding="utf-8")
    receipt = compact_deltas(directory, tmp_path / "work", apply=True)
    assert receipt["dropped_members"] == 0
    assert path.exists()


@pytest.mark.parametrize("changed_field", ["label", "help"])
def test_ancestor_fallback_may_move_only_when_resolved_text_stays_equal(tmp_path: Path, changed_field: str) -> None:
    definition = load_modelo_directory(tree(tmp_path))
    own = casilla_occurrence_locale_key("999", "2025", "0001", ModeloLocalizationFieldKind.LABEL)
    fallback = casilla_occurrence_locale_key("999", "2024", "0001", ModeloLocalizationFieldKind.LABEL)
    row = CasillaDefinition.model_validate(
        {
            "id": "0001",
            "number": "1",
            "section": ("test",),
            "data_type": "money",
            "localization_keys": (own,),
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
        }
    )
    revision = definition.revisions["2025"].model_copy(update={"casillas": (row,)})
    before = definition.model_copy(update={"revisions": {**definition.revisions, "2025": revision}})
    inherited = row.model_copy(update={"localization_keys": (own, fallback), "inherited_from": "2024"})
    after = definition.model_copy(
        update={"revisions": {**definition.revisions, "2025": revision.model_copy(update={"casillas": (inherited,)})}}
    )
    locales = tmp_path / "translations"
    locales.mkdir()
    (locales / "es.yml").write_text(json.dumps({own: "same", fallback: "same"}), encoding="utf-8")
    with override_locales_root(locales):
        assert differences(before, after) == []
    changed = (
        {own: None, fallback: "different"}
        if changed_field == "label"
        else {
            own: "same",
            fallback: "same",
            own.removesuffix(".label") + ".help": None,
            fallback.removesuffix(".label") + ".help": "different help",
        }
    )
    (locales / "es.yml").write_text(json.dumps(changed), encoding="utf-8")
    with override_locales_root(locales):
        assert any("resolved_" in item for item in differences(before, after))
