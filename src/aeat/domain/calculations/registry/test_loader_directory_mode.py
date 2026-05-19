"""Equivalence tests for the directory-mode modelo loader.

The single-file ``modelos/<id>.toml`` layout and the directory-mode
``modelos/<id>/{manifest.toml, revisions/*.toml}`` layout must produce
byte-identical ``ModeloDefinition`` objects from the same TOML data.

This is the safety net for the segmentation migration: by exercising
the round trip
``load_modelo_file(file) == load_modelo_directory(dir-built-from-file)``
on every realistic shape (multi-revision, single-revision, with /
without manifest-level metadata), the migration of any modelo from
single-file to directory layout can be done without behavioral risk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.core.resources import bundled_path

from ._errors import RegistryLoadError
from ._loader import (
    discover_modelo_sources,
    load_modelo_directory,
    load_modelo_file,
    load_modelo_source,
    load_registry_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _build_directory_layout(
    target_dir: Path,
    *,
    manifest_text: str,
    revision_files: dict[str, str],
) -> None:
    """Materialise a directory-mode modelo at ``target_dir``."""

    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "manifest.toml").write_text(manifest_text, encoding="utf-8")
    revisions_dir = target_dir / "revisions"
    revisions_dir.mkdir(exist_ok=True)
    for filename, content in revision_files.items():
        (revisions_dir / filename).write_text(content, encoding="utf-8")


@pytest.mark.parametrize(
    "modelo_filename",
    ["130.toml", "184.toml", "190.toml", "193.toml", "303.toml", "390.toml"],
)
def test_directory_mode_round_trip_matches_single_file_for_real_modelo(tmp_path: Path, modelo_filename: str) -> None:
    """Existing single-file modelos load byte-identically in directory mode.

    For each real modelo TOML in registry/aeat/modelos/, this test:
      1. Reads the file's text.
      2. Splits it into manifest (everything before the first
         [revisions table) + a single revisions/single.toml.
      3. Builds a directory-mode layout in tmp_path.
      4. Asserts ``load_modelo_directory(tmp_dir) ==
         load_modelo_file(original)``.

    Equivalence is at the ``ModeloDefinition`` level — pydantic
    structural equality. Any divergence between the two loaders is a
    blocker for migrating modelos to directory mode.
    """

    single_file_path = bundled_path("registry", "aeat", "modelos") / modelo_filename
    if not single_file_path.is_file():
        pytest.skip(f"{modelo_filename} not present")
    expected = load_modelo_file(single_file_path)

    text = single_file_path.read_text(encoding="utf-8")
    manifest_lines: list[str] = []
    revision_lines: list[str] = []
    in_revision = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("[revisions") or stripped.startswith("[[revisions"):
            in_revision = True
        if in_revision:
            revision_lines.append(line)
        else:
            manifest_lines.append(line)

    target = tmp_path / "modelo_dir"
    _build_directory_layout(
        target,
        manifest_text="".join(manifest_lines),
        revision_files={"all.toml": "".join(revision_lines)},
    )
    actual = load_modelo_directory(target)
    assert actual == expected


def test_directory_mode_rejects_manifest_with_revisions_table(tmp_path: Path) -> None:
    """The manifest must not declare [revisions] — that lives in revisions/*.toml."""

    target = tmp_path / "bad_manifest"
    target.mkdir()
    (target / "manifest.toml").write_text(
        '[modelo]\nid = "999"\nlabel = "test"\n[revisions."2025"]\n',
        encoding="utf-8",
    )
    (target / "revisions").mkdir()
    with pytest.raises(RegistryLoadError, match="manifest must not declare \\[revisions\\]"):
        load_modelo_directory(target)


def test_directory_mode_rejects_revision_file_with_modelo_table(tmp_path: Path) -> None:
    """A revision file must not redeclare [modelo] — that's manifest-only."""

    target = tmp_path / "bad_revision"
    target.mkdir()
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\nlabel = "test"\n', encoding="utf-8")
    (target / "revisions").mkdir()
    (target / "revisions" / "2025.toml").write_text(
        '[modelo]\nid = "999"\n[revisions."2025"]\n',
        encoding="utf-8",
    )
    with pytest.raises(RegistryLoadError, match="must not declare \\[modelo\\]"):
        load_modelo_directory(target)


def test_directory_mode_rejects_duplicate_revision_ids_across_files(tmp_path: Path) -> None:
    """Two revision files cannot both declare the same revision id."""

    target = tmp_path / "duplicate_rev"
    target.mkdir()
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\nlabel = "test"\n', encoding="utf-8")
    (target / "revisions").mkdir()
    rev_text = '[revisions."2025"]\n[[revisions."2025".casillas]]\nid = "0001"\n'
    (target / "revisions" / "a.toml").write_text(rev_text, encoding="utf-8")
    (target / "revisions" / "b.toml").write_text(rev_text, encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="already declared in another revisions"):
        load_modelo_directory(target)


def test_directory_mode_rejects_duplicate_revision_id_across_file_and_fragment_dir(tmp_path: Path) -> None:
    """A revision id cannot be owned by both ``revisions/<id>.toml`` and ``revisions/<id>/``."""

    target = tmp_path / "duplicate_rev_file_and_dir"
    target.mkdir()
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\ntitle = "test"\n', encoding="utf-8")
    revisions_dir = target / "revisions"
    revisions_dir.mkdir()
    (revisions_dir / "2025.toml").write_text('[revisions."2025"]\nvalid_from = 2025-01-01\n', encoding="utf-8")
    (revisions_dir / "2025").mkdir()
    (revisions_dir / "2025" / "revision.toml").write_text(
        '[revisions."2025"]\nvalid_from = 2025-01-01\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="already declared"):
        load_modelo_directory(target)


def test_directory_mode_loads_fragmented_revision_layout(tmp_path: Path) -> None:
    """A ``revisions/<id>/`` fragment tree compiles to the same object shape."""

    single_file = tmp_path / "999.toml"
    single_file.write_text(
        """
[modelo]
id = "999"
title = "Fragment test"
official_name = "Fragment test"
tax_domain = "test"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".casillas]]
id = "0001"
number = "1"
label = "Base"
section = ["liquidacion"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".export_layouts]]
id = "modelo-999-layout"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".export_layouts.records]]
id = "modelo-999-record"
record_type = "1"
order = 0
encoding = "latin-1"
line_ending = "crlf"
required = true
""".lstrip(),
        encoding="utf-8",
    )
    expected = load_modelo_file(single_file)

    target = tmp_path / "999"
    (target / "revisions" / "2025" / "casillas").mkdir(parents=True)
    (target / "revisions" / "2025" / "export").mkdir()
    (target / "manifest.toml").write_text(
        """
[modelo]
id = "999"
title = "Fragment test"
official_name = "Fragment test"
tax_domain = "test"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "revision.toml").write_text(
        """
[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "casillas" / "liquidacion.toml").write_text(
        """
[[revisions."2025".casillas]]
id = "0001"
number = "1"
label = "Base"
section = ["liquidacion"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "export" / "manifest.toml").write_text(
        """
[[revisions."2025".export_layouts]]
id = "modelo-999-layout"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "export" / "record-001.toml").write_text(
        """
[[revisions."2025".export_layouts]]
id = "modelo-999-layout"

[[revisions."2025".export_layouts.records]]
id = "modelo-999-record"
record_type = "1"
order = 0
encoding = "latin-1"
line_ending = "crlf"
required = true
""".lstrip(),
        encoding="utf-8",
    )

    actual = load_modelo_directory(target)
    assert actual == expected


def test_directory_mode_rejects_fragment_revision_id_mismatch(tmp_path: Path) -> None:
    """Fragments under ``revisions/<id>/`` must declare the same revision id."""

    target = tmp_path / "999"
    (target / "revisions" / "2025").mkdir(parents=True)
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\ntitle = "x"\n', encoding="utf-8")
    (target / "revisions" / "2025" / "revision.toml").write_text(
        '[revisions."2024"]\nvalid_from = 2024-01-01\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="expected '2025'"):
        load_modelo_directory(target)


def test_directory_mode_rejects_fragment_scalar_redeclaration(tmp_path: Path) -> None:
    """A fragmented revision has one owner for each scalar revision field."""

    target = tmp_path / "999"
    (target / "revisions" / "2025").mkdir(parents=True)
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\ntitle = "x"\n', encoding="utf-8")
    (target / "revisions" / "2025" / "revision.toml").write_text(
        '[revisions."2025"]\nlabel = "one"\n',
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "extra.toml").write_text(
        '[revisions."2025"]\nlabel = "two"\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="redeclares scalar field 'label'"):
        load_modelo_directory(target)


def test_directory_mode_rejects_missing_manifest(tmp_path: Path) -> None:
    """Directory-mode requires manifest.toml at the root of the modelo dir."""

    target = tmp_path / "no_manifest"
    target.mkdir()
    with pytest.raises(RegistryLoadError, match=r"missing manifest\.toml"):
        load_modelo_directory(target)


def test_directory_mode_rejects_no_revisions(tmp_path: Path) -> None:
    """A directory-mode modelo must have at least one revision file."""

    target = tmp_path / "no_revs"
    target.mkdir()
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\nlabel = "test"\n', encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="no revisions found"):
        load_modelo_directory(target)


def test_committed_registry_tree_loads_single_file_and_directory_modelos() -> None:
    """Registry discovery must include both supported modelo layouts."""

    registry_root = bundled_path("registry", "aeat")
    modelos_dir = registry_root / "modelos"
    sources = discover_modelo_sources(modelos_dir)
    modelos, _catalogues = load_registry_tree(registry_root)
    loaded_ids = {modelo.id for modelo in modelos}

    assert loaded_ids == {source.modelo_id for source in sources}
    assert {load_modelo_source(source).id for source in sources} == loaded_ids
    assert any(source.layout == "directory" for source in sources)
    assert any(source.layout == "single_file" for source in sources)


def test_fragmented_modelos_do_not_keep_stale_single_file_siblings() -> None:
    """A fragmented modelo cannot also keep ``modelos/<id>.toml``."""

    modelos_dir = bundled_path("registry", "aeat", "modelos")
    sources = discover_modelo_sources(modelos_dir)
    offenders = [
        source.modelo_id
        for source in sources
        if source.layout == "directory" and (modelos_dir / f"{source.modelo_id}.toml").exists()
    ]

    assert offenders == []


def test_fragmented_revision_directories_are_schema_owned() -> None:
    """Every committed revision fragment directory has a schema manifest and loads."""

    modelos_dir = bundled_path("registry", "aeat", "modelos")
    checked: list[str] = []
    for source in discover_modelo_sources(modelos_dir):
        if source.layout != "directory":
            continue
        modelo = load_modelo_source(source)
        for revision_source in source.revision_sources:
            if revision_source.layout != "fragment_directory":
                continue
            checked.append(f"{source.modelo_id}/{revision_source.revision_id}")
            assert (revision_source.path / "revision.toml").is_file()
            assert revision_source.revision_id in modelo.revisions
            assert not (source.path / "revisions" / f"{revision_source.revision_id}.toml").exists()

    assert checked, "at least one committed revision must use fragment-directory layout"
