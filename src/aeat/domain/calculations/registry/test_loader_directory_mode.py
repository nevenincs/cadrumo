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
from ._loader import load_modelo_directory, load_modelo_file, load_registry_tree

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


def test_modelo_100_does_not_coexist_in_both_layouts() -> None:
    """**HARD INVARIANT**: modelo 100 must live in exactly one layout.

    modelo 100 is stored in directory mode at
    ``registry/aeat/modelos/100/``. The single-file
    ``registry/aeat/modelos/100.toml`` must NOT coexist alongside it.

    The runtime loader rejects dual layouts at load time, but git
    accepts re-introduction of ``100.toml`` silently because main
    does not track that path. This test is the static safety net:
    it fails loudly if the dual layout is ever introduced.

    Recovery procedure when this test fires:
      1. Run ``scripts/split_modelo_100.py`` to migrate the
         re-introduced ``100.toml`` content into the directory
         layout, preserving any local edits.
      2. Verify the round-trip equivalence test still passes for
         the single-file modelos used as the migration-safety
         reference (130, 184, 190, 193, 303, 390).
      3. Delete ``100.toml`` and commit the merged directory state.
    """

    single_file = bundled_path("registry", "aeat", "modelos", "100.toml")
    directory = bundled_path("registry", "aeat", "modelos", "100")
    if single_file.is_file() and directory.is_dir():
        raise AssertionError(
            "modelo 100 exists in BOTH single-file and directory layouts:\n"
            f"  - {single_file}\n"
            f"  - {directory}/manifest.toml\n"
            "This is forbidden — the loader rejects dual layouts at "
            "load time. An in-flight agent likely re-introduced "
            "100.toml from a pre-migration checkout. Run "
            "scripts/split_modelo_100.py to merge the re-introduced "
            "content into the directory layout, then delete 100.toml."
        )


def test_modelo_100_directory_layout_loads_with_expected_revisions() -> None:
    """Schema-level integrity check on the live modelo 100 directory.

    Loads ``registry/aeat/modelos/100/`` via the directory loader and
    asserts the in-memory ``ModeloDefinition`` shape matches the
    expected revision set. This catches:
      - A revision file accidentally deleted
      - A revision file's content corrupted to the point that pydantic
        validation drops it
      - A new revision added without an ADR / planning document
        (forces a deliberate update to this expectation)
      - Manifest.toml's [modelo] table corrupted

    The expected set lists the revisions present in the directory
    today. Future revisions (e.g. when AEAT publishes the 2026 form)
    update this list as part of the same commit that adds the new
    revision file under ``revisions/``.
    """

    directory = bundled_path("registry", "aeat", "modelos", "100")
    if not (directory / "manifest.toml").is_file():
        pytest.skip("modelo 100 not in directory layout")
    modelo = load_modelo_directory(directory)
    assert modelo.id == "100"
    expected_revisions = {"2020", "2021", "2022", "2023", "2024", "2025"}
    actual_revisions = set(modelo.revisions)
    assert actual_revisions == expected_revisions


def test_modelo_100_revision_schema_is_fragment_directory_backed() -> None:
    """Modelo 100 revisions are now authoritative fragment directories.

    This guards the M100 schema rollout specifically: every revision
    must live at ``revisions/<year>/revision.toml`` so future schema
    work exercises the same revision-fragment path as the large modelos.
    """

    directory = bundled_path("registry", "aeat", "modelos", "100")
    revisions_dir = directory / "revisions"
    assert (directory / "manifest.toml").is_file()
    assert not tuple(revisions_dir.glob("*.toml"))
    for revision_id in {"2020", "2021", "2022", "2023", "2024", "2025"}:
        revision_dir = revisions_dir / revision_id
        assert revision_dir.is_dir(), f"missing M100 revision directory {revision_dir}"
        assert (revision_dir / "revision.toml").is_file(), f"missing M100 revision manifest {revision_dir}"


def test_committed_registry_tree_loads_single_file_and_directory_modelos() -> None:
    """Registry discovery must include both supported modelo layouts."""

    registry_root = bundled_path("registry", "aeat")
    modelos_dir = registry_root / "modelos"
    modelos, _catalogues = load_registry_tree(registry_root)
    loaded_ids = {modelo.id for modelo in modelos}
    single_file_ids = {path.stem for path in modelos_dir.glob("*.toml")}
    directory_ids = {
        entry.name
        for entry in modelos_dir.iterdir()
        if entry.is_dir() and (entry / "manifest.toml").is_file()
    }

    assert loaded_ids == single_file_ids | directory_ids
    assert {"100", "180", "200", "202", "232"}.issubset(directory_ids)


def test_fragmented_modelos_do_not_keep_stale_single_file_siblings() -> None:
    """A fragmented modelo cannot also keep ``modelos/<id>.toml``."""

    modelos_dir = bundled_path("registry", "aeat", "modelos")
    offenders = [
        entry.name
        for entry in sorted(modelos_dir.iterdir())
        if entry.is_dir()
        and (entry / "manifest.toml").is_file()
        and (modelos_dir / f"{entry.name}.toml").exists()
    ]

    assert offenders == []
