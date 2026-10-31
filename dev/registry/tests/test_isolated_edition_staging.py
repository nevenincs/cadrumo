"""Isolated staging of one edition for the published-layout witness.

The witness is a copy of the modelo holding only the target edition. Pruning
the sibling editions is what isolates it, and it deletes precisely the chain an
edition naming a predecessor inherits from. These tests drive the real staging
function and the real directory loader over on-disk trees: a delta edition must
stage as the complete edition it stands for, a delta whose predecessor is gone
must be refused, and an edition stating every row must stage byte-for-byte as
the copy it always was. Labels travel with the rows: every casilla of a staged
delta resolves the same text in every shipped locale as the live edition.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from cadrumo.core.i18n.render import override_locales_root
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.modelo_localization import resolve_modelo_localization
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.edition_materialisation import materialise_edition
from ..compiler.loader import load_modelo_directory
from ..pipeline.published_edition_staging import stage_isolated_edition
from .edition_staging_tree_support import (
    edition_casilla,
    migrated_chain,
    staged_modelo,
    write_edition,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _full_copy_modelo(root: Path) -> Path:
    modelo_dir = staged_modelo(root)
    for revision_id, year in (("2024", 2024), ("2025", 2025)):
        write_edition(
            modelo_dir,
            revision_id,
            year=year,
            casillas=(
                edition_casilla(revision_id, "0001", number="1", lineage="base-imponible")
                + edition_casilla(revision_id, "0002", number="2", lineage="cuota-integra")
            ),
        )
    return modelo_dir


_LOCALES = ("es", "en", "ca", "hu")

#: Labels authored per edition, as the shipped catalogue carries them. Each
#: inherited row's text lives under the edition that last stated it; the
#: successor authors a label only where it states a row, plus one Catalan
#: override for an inherited row so the row's own key is shown to win.
_AUTHORED_LABELS: dict[str, dict[str, str]] = {
    "modelo.schema.999.revision.2023.casilla.0001.label": {
        "es": "Base imponible",
        "en": "Taxable base",
        "ca": "Base imposable",
        "hu": "Adóalap",
    },
    "modelo.schema.999.revision.2023.casilla.0002.label": {"es": "Cuota íntegra", "en": "Gross tax due"},
    "modelo.schema.999.revision.2024.casilla.0002.label": {"hu": "Kiigazított adó"},
    "modelo.schema.999.casilla.continuidad.cuota-integra.label": {
        "es": "Cuota íntegra",
        "en": "Gross tax (lineage)",
        "ca": "Quota íntegra",
    },
    "modelo.schema.999.revision.2025.casilla.0001.label": {"ca": "Base imposable 2025"},
    "modelo.schema.999.revision.2025.casilla.0004.label": {
        "es": "Recargo",
        "en": "Surcharge",
        "ca": "Recàrrec",
        "hu": "Pótlék",
    },
}


def _write_catalogue(locales_root: Path) -> None:
    locales_root.mkdir(parents=True)
    for locale in _LOCALES:
        tree: dict[str, object] = {}
        for dotted_key, texts in _AUTHORED_LABELS.items():
            if locale not in texts:
                continue
            *parents, leaf = dotted_key.split(".")
            cursor = tree
            for part in parents:
                child = cursor.setdefault(part, {})
                assert isinstance(child, dict)
                cursor = child
            cursor[leaf] = texts[locale]
        (locales_root / f"{locale}.yml").write_text(
            yaml.safe_dump(tree, allow_unicode=True, sort_keys=True),
            encoding="utf-8",
            newline="\n",
        )


def _locale_roots(tmp_path: Path) -> dict[str, Path]:
    source = tmp_path / "locales-source"
    if not source.exists():
        _write_catalogue(source)
    return {"source_locales_root": source, "staged_locales_root": tmp_path / "locales-staged"}


def _labels(revision: ModeloRevision, locales_root: Path) -> dict[tuple[str, str], str | None]:
    with override_locales_root(locales_root):
        return {
            (casilla.id, locale): resolve_modelo_localization(casilla.localization_keys, locale=locale)
            for casilla in revision.casillas
            for locale in _LOCALES
        }


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _without_label_origin_fallback(revision: ModeloRevision) -> ModeloRevision:
    """Drop what the live load derives for rows it inherited, which no staged full copy can author.

    That is the origin edition's locale key and the loader-owned ``inherited_from``
    marker: a full copy states every row itself, so neither exists for it.
    """
    return revision.model_copy(
        update={
            "casillas": tuple(
                casilla.model_copy(
                    update={
                        "localization_keys": casilla.localization_keys[:1] + casilla.localization_keys[2:],
                        "inherited_from": None,
                    }
                )
                if casilla.id != "0004"
                else casilla
                for casilla in revision.casillas
            ),
        },
    )


def test_a_migrated_successor_stages_as_the_complete_edition_it_stands_for(tmp_path: Path) -> None:
    source = migrated_chain(tmp_path)
    live = load_modelo_directory(source).revisions["2025"]

    staged_root = stage_isolated_edition(
        source, tmp_path / "staged" / "999", revision="2025", **_locale_roots(tmp_path)
    ).modelo_root

    assert sorted(path.name for path in (staged_root / "revisions").iterdir()) == ["2025"]
    assert "predecessor" not in (staged_root / "revisions" / "2025" / "revision.toml").read_text(encoding="utf-8")
    staged_definition = load_modelo_directory(staged_root)
    assert tuple(staged_definition.revisions) == ("2025",)
    staged = staged_definition.revisions["2025"]
    assert staged.predecessor is None
    assert [(row.id, row.number, row.continuidad_id) for row in staged.casillas] == [
        ("0001", "1", "base-imponible"),
        ("0002", "22", "cuota-integra"),
        ("0004", "4", "recargo-nuevo"),
    ]
    # Isolation prunes the sibling editions, so the continuity evolutions naming them go too.
    expected = _without_label_origin_fallback(live).model_copy(update={"casilla_continuidad_evolutions": ()})
    assert staged.model_copy(update={"predecessor": live.predecessor}) == expected


def test_a_staged_successor_resolves_every_label_the_live_edition_resolves(tmp_path: Path) -> None:
    source = migrated_chain(tmp_path)
    roots = _locale_roots(tmp_path)
    live = load_modelo_directory(source).revisions["2025"]

    staged = stage_isolated_edition(source, tmp_path / "staged" / "999", revision="2025", **roots)

    assert staged.locales_root == roots["staged_locales_root"]
    live_labels = _labels(live, roots["source_locales_root"])
    staged_labels = _labels(load_modelo_directory(staged.modelo_root).revisions["2025"], staged.locales_root)
    assert staged_labels == live_labels
    assert all(text is not None for text in live_labels.values())
    # Each tier the live chain reaches is represented, so the parity above is not vacuous:
    # text carried two editions down, the adjacent predecessor's text, the lineage-wide
    # text, the row's own override, and a row the successor states itself.
    assert live_labels[("0001", "hu")] == "Adóalap"
    assert live_labels[("0002", "hu")] == "Kiigazított adó"
    assert live_labels[("0002", "en")] == "Gross tax (lineage)"
    assert live_labels[("0001", "ca")] == "Base imposable 2025"
    assert live_labels[("0004", "ca")] == "Recàrrec"


def test_an_edition_stating_every_row_resolves_labels_from_the_source_catalogue(tmp_path: Path) -> None:
    roots = _locale_roots(tmp_path)

    staged = stage_isolated_edition(_full_copy_modelo(tmp_path), tmp_path / "staged" / "999", revision="2025", **roots)

    assert staged.locales_root == roots["source_locales_root"]
    assert not roots["staged_locales_root"].exists()


def test_a_staged_successor_equals_what_the_entry_point_materialises(tmp_path: Path) -> None:
    source = migrated_chain(tmp_path)
    edition = materialise_edition(source, "2025")

    staged_root = stage_isolated_edition(
        source, tmp_path / "staged" / "999", revision="2025", **_locale_roots(tmp_path)
    ).modelo_root

    assert edition.inherits_from == "2024"
    # Isolation prunes the sibling editions, so the continuity evolutions naming them go too.
    expected = {key: value for key, value in edition.table.items() if key != "casilla_continuidad_evolutions"}
    assert materialise_edition(staged_root, "2025").table == expected
    assert materialise_edition(staged_root, "2025").inherits_from is None


def test_a_staged_delta_whose_predecessor_was_removed_is_refused(tmp_path: Path) -> None:
    source = migrated_chain(tmp_path)
    shutil.rmtree(source / "revisions" / "2024")
    staged_root = tmp_path / "staged" / "999"

    with pytest.raises(RegistryLoadError, match="2024"):
        stage_isolated_edition(source, staged_root, revision="2025", **_locale_roots(tmp_path))

    assert not staged_root.exists()


def test_pruning_without_materialising_leaves_a_successor_naming_a_deleted_predecessor(tmp_path: Path) -> None:
    """The defect materialising prevents: the pruned copy no longer loads as an edition at all."""
    source = migrated_chain(tmp_path)
    pruned = tmp_path / "pruned" / "999"
    shutil.copytree(source, pruned)
    for entry in (pruned / "revisions").iterdir():
        if entry.name != "2025":
            shutil.rmtree(entry)

    with pytest.raises(RegistryLoadError, match="2024"):
        load_modelo_directory(pruned)


def test_an_edition_stating_every_row_stages_as_an_unchanged_copy(tmp_path: Path) -> None:
    source = _full_copy_modelo(tmp_path)

    staged_root = stage_isolated_edition(
        source, tmp_path / "staged" / "999", revision="2025", **_locale_roots(tmp_path)
    ).modelo_root

    assert sorted(path.name for path in (staged_root / "revisions").iterdir()) == ["2025"]
    assert _tree_bytes(staged_root / "revisions" / "2025") == _tree_bytes(source / "revisions" / "2025")
    assert (staged_root / "manifest.toml").read_bytes() == (source / "manifest.toml").read_bytes()
    assert load_modelo_directory(staged_root).revisions["2025"] == load_modelo_directory(source).revisions["2025"]
