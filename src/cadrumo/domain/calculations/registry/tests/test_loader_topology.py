"""Fail-closed filesystem topology gates for registry authoring sources."""

from pathlib import Path

import pytest

from ..errors import RegistryLoadError
from ..loader import load_legal_parameters_only, load_modelo_directory, load_registry_tree
from ..loader_cache import discover_modelo_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _write_fragment_modelo(root: Path, fragment_relative_path: str, fragment_text: str) -> Path:
    modelo = root / "999"
    revision = modelo / "revisions" / "2025"
    fragment = revision / fragment_relative_path
    fragment.parent.mkdir(parents=True)
    (modelo / "manifest.toml").write_text(
        '[modelo]\nid = "999"\ntax_domain = "iva"\ncadence = "annual"\n'
        'jurisdiction = "ES-AEAT"\nlegal_refs = ["law"]\nsource_refs = ["source"]\n',
        encoding="utf-8",
    )
    (revision / "revision.toml").write_text(
        '[revisions."2025"]\nvalid_from = 2025-01-01\n'
        'period_selector = { years = [2025], periods = ["0A"] }\n'
        'legal_refs = ["law"]\nsource_refs = ["source"]\n',
        encoding="utf-8",
    )
    fragment.write_text(fragment_text, encoding="utf-8")
    return modelo


@pytest.mark.parametrize("name", ["999.tom", "notes.txt"])
def test_modelo_discovery_rejects_wrong_suffix_files(tmp_path: Path, name: str) -> None:
    modelos = tmp_path / "modelos"
    modelos.mkdir()
    (modelos / name).write_text("plausible ignored source", encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="unrecognized modelos file"):
        discover_modelo_sources(modelos)


def test_modelo_discovery_rejects_orphan_modelo_directory(tmp_path: Path) -> None:
    modelos = tmp_path / "modelos"
    (modelos / "999").mkdir(parents=True)

    with pytest.raises(RegistryLoadError, match="orphan modelo directory"):
        discover_modelo_sources(modelos)


def test_modelo_directory_rejects_unknown_child(tmp_path: Path) -> None:
    modelo = _write_fragment_modelo(
        tmp_path,
        "bindings/0001-valid.toml",
        '[revisions."2025"]\nbindings = []\n',
    )
    (modelo / "generated").mkdir()

    with pytest.raises(RegistryLoadError, match="unrecognized modelo source directory"):
        load_modelo_directory(modelo)


@pytest.mark.parametrize("entry_kind", ["file", "directory"])
def test_modelo_directory_rejects_non_toml_or_nested_locale_entry(tmp_path: Path, entry_kind: str) -> None:
    modelo = _write_fragment_modelo(
        tmp_path,
        "bindings/0001-valid.toml",
        '[revisions."2025"]\nbindings = []\n',
    )
    locales_entry = modelo / "locales" / ("notes.txt" if entry_kind == "file" else "nested")
    if entry_kind == "file":
        locales_entry.parent.mkdir()
        locales_entry.write_text("ignored", encoding="utf-8")
    else:
        locales_entry.mkdir(parents=True)

    with pytest.raises(RegistryLoadError, match="unrecognized modelo locale entry"):
        load_modelo_directory(modelo)


def test_registry_tree_rejects_nested_legal_directory(tmp_path: Path) -> None:
    (tmp_path / "modelos").mkdir()
    (tmp_path / "legal" / "nested").mkdir(parents=True)
    (tmp_path / "legal" / "nested" / "catalogue.toml").write_text("", encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="unrecognized legal directory"):
        load_registry_tree(tmp_path)


def test_registry_tree_rejects_wrong_suffix_legal_file(tmp_path: Path) -> None:
    (tmp_path / "modelos").mkdir()
    (tmp_path / "legal").mkdir()
    (tmp_path / "legal" / "catalogue.tom").write_text("", encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="unrecognized legal catalogue file"):
        load_registry_tree(tmp_path)


@pytest.mark.parametrize("entry_kind", ["wrong_suffix", "nested"])
def test_legal_parameters_only_rejects_non_flat_toml_tree(tmp_path: Path, entry_kind: str) -> None:
    legal = tmp_path / "legal"
    legal.mkdir()
    if entry_kind == "wrong_suffix":
        (legal / "catalogue.json").write_text("{}\n", encoding="utf-8")
        match = "unrecognized legal catalogue file"
    else:
        (legal / "nested").mkdir()
        match = "unrecognized legal directory"

    with pytest.raises(RegistryLoadError, match=match):
        load_legal_parameters_only(tmp_path)


def test_fragment_folder_may_declare_only_its_owned_section(tmp_path: Path) -> None:
    modelo = _write_fragment_modelo(
        tmp_path,
        "bindings/0001-wrong.toml",
        '[[revisions."2025".formulas]]\nid = "wrong-owner"\n',
    )

    with pytest.raises(RegistryLoadError, match=r"folder 'bindings'.*found 'formulas'"):
        load_modelo_directory(modelo)


def test_revision_fragment_rejects_empty_revision_table(tmp_path: Path) -> None:
    modelo = _write_fragment_modelo(tmp_path, "bindings/0001-empty.toml", '[revisions."2025"]\n')

    with pytest.raises(RegistryLoadError, match="declares no section fields"):
        load_modelo_directory(modelo)


def test_revision_fragment_rejects_wrong_suffix_file(tmp_path: Path) -> None:
    modelo = _write_fragment_modelo(tmp_path, "bindings/0001-valid.toml", '[revisions."2025"]\nbindings = []\n')
    (modelo / "revisions" / "2025" / "bindings" / "ignored.tom").write_text("", encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="unrecognized revision fragment file"):
        load_modelo_directory(modelo)


def test_revision_root_rejects_stray_wrong_suffix_file(tmp_path: Path) -> None:
    modelo = _write_fragment_modelo(
        tmp_path,
        "bindings/0001-valid.toml",
        '[revisions."2025"]\nbindings = []\n',
    )
    (modelo / "revisions" / "notes.txt").write_text("ignored", encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="unrecognized revision file"):
        load_modelo_directory(modelo)


def test_revision_root_rejects_special_entry(tmp_path: Path) -> None:
    modelo = _write_fragment_modelo(
        tmp_path,
        "bindings/0001-valid.toml",
        '[revisions."2025"]\nbindings = []\n',
    )
    special = modelo / "revisions" / "dangling"
    special.symlink_to(modelo / "missing-revision")

    with pytest.raises(RegistryLoadError, match="unrecognized revisions entry"):
        load_modelo_directory(modelo)


def test_revision_tree_rejects_top_level_fragment_file(tmp_path: Path) -> None:
    modelo = _write_fragment_modelo(
        tmp_path,
        "bindings/0001-valid.toml",
        '[revisions."2025"]\nbindings = []\n',
    )
    (modelo / "revisions" / "2025" / "stray.toml").write_text(
        '[revisions."2025"]\nbindings = []\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="must live in its owned section subdirectory"):
        load_modelo_directory(modelo)


def test_revision_fragment_rejects_nested_section_directory(tmp_path: Path) -> None:
    _write_fragment_modelo(
        tmp_path,
        "bindings/nested/0001-valid.toml",
        '[revisions."2025"]\nbindings = []\n',
    )

    with pytest.raises(RegistryLoadError, match="nested revision section directories are not allowed"):
        discover_modelo_sources(tmp_path)


def test_revision_section_directory_rejects_no_toml_fragments(tmp_path: Path) -> None:
    modelo = _write_fragment_modelo(tmp_path, "bindings/0001-valid.toml", '[revisions."2025"]\nbindings = []\n')
    (modelo / "revisions" / "2025" / "formulas").mkdir()

    with pytest.raises(RegistryLoadError, match="contains no TOML fragments"):
        load_modelo_directory(modelo)


@pytest.mark.parametrize(
    ("relative_path", "error_match"),
    [
        ("bindings/bindings.toml", "invalid numbered administrative"),
        ("bindings/0001-binding_rows.toml", "invalid numbered administrative"),
        ("bindings/0001-binding@rows.toml", "invalid numbered administrative"),
        ("bindings/0001-binding-.toml", "invalid numbered administrative"),
        ("bindings/0001-binding..rows.toml", "invalid numbered administrative"),
        ("casillas/c0001@c0002.toml", "invalid casilla source-native"),
        (
            "casilla_continuidad_evolutions/0001-unsafe_name.toml",
            "invalid casilla continuity source-native",
        ),
    ],
)
def test_revision_fragment_rejects_noncanonical_filename(
    tmp_path: Path,
    relative_path: str,
    error_match: str,
) -> None:
    _write_fragment_modelo(tmp_path, relative_path, '[revisions."2025"]\nbindings = []\n')

    with pytest.raises(RegistryLoadError, match=error_match):
        discover_modelo_sources(tmp_path)


def test_administrative_fragment_rejects_duplicate_numeric_prefix(tmp_path: Path) -> None:
    modelo = _write_fragment_modelo(
        tmp_path,
        "bindings/0001-first.toml",
        '[revisions."2025"]\nbindings = []\n',
    )
    (modelo / "revisions" / "2025" / "bindings" / "0001-second.toml").write_text(
        '[revisions."2025"]\nbindings = []\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="duplicate administrative fragment prefix '0001'"):
        discover_modelo_sources(tmp_path)


@pytest.mark.parametrize(
    "relative_path",
    [
        "casillas/cDP200011+00547__c00548.toml",
        "casilla_continuidad_evolutions/0063-2024-2025-legal-refs-evolved.toml",
    ],
)
def test_source_native_fragment_filename_grammar_accepts_canonical_names(
    tmp_path: Path,
    relative_path: str,
) -> None:
    _write_fragment_modelo(tmp_path, relative_path, '[revisions."2025"]\nbindings = []\n')

    sources = discover_modelo_sources(tmp_path)

    assert len(sources) == 1
