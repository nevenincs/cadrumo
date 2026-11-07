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
from typing import NamedTuple

import pytest
import yaml

from cadrumo.core.i18n.render import override_locales_root
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.modelo_localization import resolve_modelo_localization
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

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


#: The editions of a full-copy modelo are the last two supported years, and the catalogue
#: a test without a migrated chain writes names the last three.
_FULL_COPY_YEARS = filing_year_envelope().years[-2:]
_FULL_COPY_REVISION = str(_FULL_COPY_YEARS[-1])
_ENVELOPE_EDITIONS = tuple(str(year) for year in filing_year_envelope().years[-3:])


class _Chain(NamedTuple):
    """A migrated chain on disk with the ids of its three editions, oldest first."""

    root: Path
    first: str
    second: str
    third: str

    @property
    def editions(self) -> tuple[str, str, str]:
        return (self.first, self.second, self.third)


def _migrated(tmp_path: Path) -> _Chain:
    """Build the migrated chain and read its edition ids off the tree it wrote."""
    root = migrated_chain(tmp_path)
    first, second, third = sorted(entry.name for entry in (root / "revisions").iterdir())
    return _Chain(root, first, second, third)


def _full_copy_modelo(root: Path) -> Path:
    modelo_dir = staged_modelo(root)
    for year in _FULL_COPY_YEARS:
        revision_id = str(year)
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
def _authored_labels(first: str, second: str, third: str) -> dict[str, dict[str, str]]:
    return {
        f"modelo.schema.999.revision.{first}.casilla.0001.label": {
            "es": "Base imponible",
            "en": "Taxable base",
            "ca": "Base imposable",
            "hu": "Adóalap",
        },
        f"modelo.schema.999.revision.{first}.casilla.0002.label": {"es": "Cuota íntegra", "en": "Gross tax due"},
        f"modelo.schema.999.revision.{second}.casilla.0002.label": {"hu": "Kiigazított adó"},
        "modelo.schema.999.casilla.continuidad.cuota-integra.label": {
            "es": "Cuota íntegra",
            "en": "Gross tax (lineage)",
            "ca": "Quota íntegra",
        },
        f"modelo.schema.999.revision.{third}.casilla.0001.label": {"ca": f"Base imposable {third}"},
        f"modelo.schema.999.revision.{third}.casilla.0004.label": {
            "es": "Recargo",
            "en": "Surcharge",
            "ca": "Recàrrec",
            "hu": "Pótlék",
        },
    }


def _write_catalogue(locales_root: Path, editions: tuple[str, str, str]) -> None:
    locales_root.mkdir(parents=True)
    for locale in _LOCALES:
        tree: dict[str, object] = {}
        for dotted_key, texts in _authored_labels(*editions).items():
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


def _locale_roots(tmp_path: Path, editions: tuple[str, str, str] = _ENVELOPE_EDITIONS) -> dict[str, Path]:
    source = tmp_path / "locales-source"
    if not source.exists():
        _write_catalogue(source, editions)
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
    chain = _migrated(tmp_path)
    source = chain.root
    live = load_modelo_directory(source).revisions[chain.third]

    staged_root = stage_isolated_edition(
        source, tmp_path / "staged" / "999", revision=chain.third, **_locale_roots(tmp_path, chain.editions)
    ).modelo_root

    assert sorted(path.name for path in (staged_root / "revisions").iterdir()) == [chain.third]
    assert "predecessor" not in (staged_root / "revisions" / chain.third / "revision.toml").read_text(encoding="utf-8")
    staged_definition = load_modelo_directory(staged_root)
    assert tuple(staged_definition.revisions) == (chain.third,)
    staged = staged_definition.revisions[chain.third]
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
    chain = _migrated(tmp_path)
    source = chain.root
    roots = _locale_roots(tmp_path, chain.editions)
    live = load_modelo_directory(source).revisions[chain.third]

    staged = stage_isolated_edition(source, tmp_path / "staged" / "999", revision=chain.third, **roots)

    assert staged.locales_root == roots["staged_locales_root"]
    live_labels = _labels(live, roots["source_locales_root"])
    staged_labels = _labels(load_modelo_directory(staged.modelo_root).revisions[chain.third], staged.locales_root)
    assert staged_labels == live_labels
    assert all(text is not None for text in live_labels.values())
    # Each tier the live chain reaches is represented, so the parity above is not vacuous:
    # text carried two editions down, the adjacent predecessor's text, the lineage-wide
    # text, the row's own override, and a row the successor states itself.
    assert live_labels[("0001", "hu")] == "Adóalap"
    assert live_labels[("0002", "hu")] == "Kiigazított adó"
    assert live_labels[("0002", "en")] == "Gross tax (lineage)"
    assert live_labels[("0001", "ca")] == f"Base imposable {chain.third}"
    assert live_labels[("0004", "ca")] == "Recàrrec"


def test_an_edition_stating_every_row_resolves_labels_from_the_source_catalogue(tmp_path: Path) -> None:
    roots = _locale_roots(tmp_path)

    staged = stage_isolated_edition(
        _full_copy_modelo(tmp_path), tmp_path / "staged" / "999", revision=_FULL_COPY_REVISION, **roots
    )

    assert staged.locales_root == roots["source_locales_root"]
    assert not roots["staged_locales_root"].exists()


def test_a_staged_successor_equals_what_the_entry_point_materialises(tmp_path: Path) -> None:
    chain = _migrated(tmp_path)
    source = chain.root
    edition = materialise_edition(source, chain.third)

    staged_root = stage_isolated_edition(
        source, tmp_path / "staged" / "999", revision=chain.third, **_locale_roots(tmp_path, chain.editions)
    ).modelo_root

    assert edition.inherits_from == chain.second
    # Isolation prunes the sibling editions, so the continuity evolutions naming them go too.
    expected = {key: value for key, value in edition.table.items() if key != "casilla_continuidad_evolutions"}
    assert materialise_edition(staged_root, chain.third).table == expected
    assert materialise_edition(staged_root, chain.third).inherits_from is None


def test_a_staged_delta_whose_predecessor_was_removed_is_refused(tmp_path: Path) -> None:
    chain = _migrated(tmp_path)
    source = chain.root
    shutil.rmtree(source / "revisions" / chain.second)
    staged_root = tmp_path / "staged" / "999"

    with pytest.raises(RegistryLoadError, match=chain.second):
        stage_isolated_edition(source, staged_root, revision=chain.third, **_locale_roots(tmp_path, chain.editions))

    assert not staged_root.exists()


def test_pruning_without_materialising_leaves_a_successor_naming_a_deleted_predecessor(tmp_path: Path) -> None:
    """The defect materialising prevents: the pruned copy no longer loads as an edition at all."""
    chain = _migrated(tmp_path)
    pruned = tmp_path / "pruned" / "999"
    shutil.copytree(chain.root, pruned)
    for entry in (pruned / "revisions").iterdir():
        if entry.name != chain.third:
            shutil.rmtree(entry)

    with pytest.raises(RegistryLoadError, match=chain.second):
        load_modelo_directory(pruned)


def test_an_edition_stating_every_row_stages_as_an_unchanged_copy(tmp_path: Path) -> None:
    source = _full_copy_modelo(tmp_path)

    staged_root = stage_isolated_edition(
        source, tmp_path / "staged" / "999", revision=_FULL_COPY_REVISION, **_locale_roots(tmp_path)
    ).modelo_root

    assert sorted(path.name for path in (staged_root / "revisions").iterdir()) == [_FULL_COPY_REVISION]
    assert _tree_bytes(staged_root / "revisions" / _FULL_COPY_REVISION) == _tree_bytes(
        source / "revisions" / _FULL_COPY_REVISION
    )
    assert (staged_root / "manifest.toml").read_bytes() == (source / "manifest.toml").read_bytes()
    assert (
        load_modelo_directory(staged_root).revisions[_FULL_COPY_REVISION]
        == load_modelo_directory(source).revisions[_FULL_COPY_REVISION]
    )
