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

from .._errors import RegistryLoadError, RegistryValidationError
from .._loader import (
    discover_modelo_sources,
    load_legal_parameters_only,
    load_modelo_directory,
    load_modelo_file,
    load_registry_tree,
)
from ._loader_directory_mode_support import (
    _COMPLETENESS_CASILLA_0001,
    _COMPLETENESS_CASILLA_0002,
    _MAX_SINGLE_FILE_MODELO_LINES,
    _MAX_TOML_FRAGMENT_LINES,
    _MAX_TOML_ROW_CHARS,
    _build_directory_layout,
    _committed_modelo,
    _committed_modelo_sources,
    _committed_modelo_sources_by_id,
    _committed_modelo_toml_paths,
    _committed_modelos_dir,
    _committed_non_locale_toml_paths_by_fragment_revision,
    _committed_non_locale_toml_paths_by_modelo_id,
    _committed_registry_modelos,
    _minimal_fragment_revision_layout,
    _split_single_file_modelo_text,
    _standard_manifest_text,
    _standard_revision_preamble_text,
    _write_locale_fragment,
    _write_minimal_localized_modelo,
    _write_standard_manifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_directory_mode_round_trip_matches_every_single_file_modelo(tmp_path: Path) -> None:
    """Every single-file modelo loads byte-identically in directory mode.

    For each real single-file modelo TOML in registry/aeat/modelos/,
    this test builds a temporary directory layout with one revision
    file carrying the original revision tables, then checks it produces
    the same ``ModeloDefinition`` object as the source file.

    Equivalence is at the ``ModeloDefinition`` level — pydantic
    structural equality. Any divergence between the two loaders is a
    blocker for migrating modelos to directory mode.
    """

    modelos_dir = _committed_modelos_dir()
    checked: list[str] = []
    for source in _committed_modelo_sources():
        if source.layout != "single_file":
            continue
        checked.append(source.modelo_id)
        expected = _committed_modelo(source.modelo_id)
        manifest_text, revision_text, _revision_text_by_id = _split_single_file_modelo_text(
            source.path.read_text(encoding="utf-8"),
        )

        target = tmp_path / f"modelo_dir_{source.modelo_id}"
        _build_directory_layout(
            target,
            manifest_text=manifest_text,
            revision_files={"all.toml": revision_text},
        )
        actual = load_modelo_directory(target)
        assert actual == expected, source.modelo_id

    if not checked:
        assert list(modelos_dir.glob("*.toml")) == []


def test_fragment_directory_round_trip_matches_every_single_file_modelo(tmp_path: Path) -> None:
    """Every single-file modelo can be represented as revision fragment directories."""

    modelos_dir = _committed_modelos_dir()
    checked: list[str] = []
    for source in _committed_modelo_sources():
        if source.layout != "single_file":
            continue
        checked.append(source.modelo_id)
        expected = _committed_modelo(source.modelo_id)
        manifest_text, _revision_text, revision_text_by_id = _split_single_file_modelo_text(
            source.path.read_text(encoding="utf-8"),
        )

        target = tmp_path / f"fragmented_modelo_{source.modelo_id}"
        (target / "revisions").mkdir(parents=True)
        (target / "manifest.toml").write_text(manifest_text, encoding="utf-8")
        for revision_id, revision_text in revision_text_by_id.items():
            revision_dir = target / "revisions" / revision_id
            revision_dir.mkdir()
            (revision_dir / "revision.toml").write_text(revision_text, encoding="utf-8")

        actual = load_modelo_directory(target)
        assert actual == expected, source.modelo_id

    if not checked:
        assert list(modelos_dir.glob("*.toml")) == []


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
    revision_dir = _minimal_fragment_revision_layout(target)
    revisions_dir = revision_dir.parent
    (revisions_dir / "2025.toml").write_text('[revisions."2025"]\nvalid_from = 2025-01-01\n', encoding="utf-8")
    (revisions_dir / "2025" / "revision.toml").write_text(
        '[revisions."2025"]\nvalid_from = 2025-01-01\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="already declared"):
        load_modelo_directory(target)


def test_directory_mode_loads_plain_revision_file_layout(tmp_path: Path) -> None:
    """A directory modelo can carry a normal ``revisions/<id>.toml`` revision file."""

    single_file = tmp_path / "999.toml"
    single_file.write_text(
        _standard_manifest_text("Revision-file test")
        + "\n"
        + _standard_revision_preamble_text()
        + """

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
    expected = load_modelo_file(single_file)

    target = tmp_path / "999"
    (target / "revisions").mkdir(parents=True)
    _write_standard_manifest(target, "Revision-file test")
    (target / "revisions" / "2025.toml").write_text(
        _standard_revision_preamble_text()
        + """

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

    actual = load_modelo_directory(target)
    assert actual == expected


def test_directory_mode_rejects_malformed_casilla_id_before_locale_key_authority(tmp_path: Path) -> None:
    """Raw TOML casilla ids must be validated before they seed loader authority sets."""

    target = tmp_path / "malformed_casilla_id"
    (target / "revisions").mkdir(parents=True)
    _write_standard_manifest(target, "Malformed casilla id test")
    (target / "revisions" / "2025.toml").write_text(
        _standard_revision_preamble_text()
        + """

[[revisions."2025".casillas]]
id = "bad key"
number = "1"
label = "Base"
section = ["liquidacion"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError, match=r"Invalid casilla id 'bad key'.*canonical casilla\.id"):
        load_modelo_directory(target)


def test_single_file_mode_rejects_ambiguous_casilla_identity_during_load(tmp_path: Path) -> None:
    source = tmp_path / "999.toml"
    source.write_text(
        """
[modelo]
id = "999"
title = "Ambiguous casilla identity test"
official_name = "Ambiguous casilla identity test"
tax_domain = "iva"
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
id = "01"
number = "99"
label = "Canonical owner"
section = ["test"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".casillas]]
id = "DPX:01"
number = "01"
segmento = "DPX"
label = "Colliding display token"
section = ["test"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError, match="casilla reference token '01' is ambiguous"):
        load_modelo_file(source)


def test_directory_mode_rejects_ambiguous_casilla_identity_during_load(tmp_path: Path) -> None:
    target = tmp_path / "999"
    _build_directory_layout(
        target,
        manifest_text=_standard_manifest_text("Ambiguous casilla identity test"),
        revision_files={
            "2025.toml": _standard_revision_preamble_text()
            + """

[[revisions."2025".casillas]]
id = "01"
number = "99"
label = "Canonical owner"
section = ["test"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".casillas]]
id = "DPX:01"
number = "01"
segmento = "DPX"
label = "Colliding display token"
section = ["test"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        },
    )

    with pytest.raises(RegistryValidationError, match="casilla reference token '01' is ambiguous"):
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


def test_committed_registry_tree_loads_directory_modelos() -> None:
    """Registry discovery must load every committed directory-form modelo."""

    sources = _committed_modelo_sources()
    modelos = _committed_registry_modelos()
    loaded_ids = {modelo.id for modelo in modelos}

    assert loaded_ids == {source.modelo_id for source in sources}
    assert {_committed_modelo(source.modelo_id).id for source in sources} == loaded_ids
    assert any(source.layout == "directory" for source in sources)
    assert all(source.layout == "directory" for source in sources)


def test_legal_parameters_only_rejects_unknown_legal_refs(tmp_path: Path) -> None:
    """The cycle-safe parameter loader must not return ungrounded legal refs."""

    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    (legal_dir / "parameters.toml").write_text(
        """
[parameters."test-rate"]
evidence_tier = "legal_authority"
value = "0.21"
unit = "fraction"
applies_to = "test-case"
legal_refs = ["ley-test:art-1"]
review_status = "reviewed"
reviewed_at = 2026-06-28
reviewed_by = "registry-test"
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(
        RegistryLoadError,
        match=r"legal parameter 'test-rate' references unknown legal id 'ley-test:art-1'",
    ):
        load_legal_parameters_only(tmp_path)


def test_registry_tree_rejects_parameter_unknown_legal_refs(tmp_path: Path) -> None:
    """The full registry merge validates legal-parameter legal refs before returning."""

    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    (tmp_path / "modelos").mkdir()
    (legal_dir / "parameters.toml").write_text(
        """
[parameters."test-rate"]
evidence_tier = "legal_authority"
value = "0.21"
unit = "fraction"
applies_to = "test-case"
legal_refs = ["ley-test:art-1"]
review_status = "reviewed"
reviewed_at = 2026-06-28
reviewed_by = "registry-test"
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(
        RegistryLoadError,
        match=r"legal parameter 'test-rate' references unknown legal id 'ley-test:art-1'",
    ):
        load_registry_tree(tmp_path)


def test_committed_key_modelos_load_through_generic_fragment_sources() -> None:
    """Key committed modelos use the same generic directory-source contract."""

    sources = _committed_modelo_sources_by_id()

    for modelo_id in ("036", "100", "200", "303"):
        source = sources[modelo_id]
        modelo = _committed_modelo(modelo_id)

        assert source.layout == "directory"
        assert source.path.name == modelo_id
        assert modelo.id == modelo_id
        assert source.revision_sources
        assert all(revision_source.layout == "fragment_directory" for revision_source in source.revision_sources)
        assert {revision_source.revision_id for revision_source in source.revision_sources} == set(modelo.revisions)


def test_discovery_rejects_single_file_and_directory_layout_collision(tmp_path: Path) -> None:
    """A modelo id cannot be declared by both supported layouts."""

    modelos_dir = tmp_path / "modelos"
    modelos_dir.mkdir()
    single_file = modelos_dir / "999.toml"
    single_file.write_text(
        """
[modelo]
id = "999"
title = "Collision test"
official_name = "Collision test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    directory = modelos_dir / "999"
    (directory / "revisions").mkdir(parents=True)
    (directory / "manifest.toml").write_text(
        """
[modelo]
id = "999"
title = "Collision test"
official_name = "Collision test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (directory / "revisions" / "2025.toml").write_text(
        """
[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="also declared"):
        discover_modelo_sources(modelos_dir)


def test_fragmented_modelos_do_not_keep_stale_single_file_siblings() -> None:
    """A fragmented modelo cannot also keep ``modelos/<id>.toml``."""

    modelos_dir = _committed_modelos_dir()
    sources = _committed_modelo_sources()
    offenders = [
        source.modelo_id
        for source in sources
        if source.layout == "directory" and (modelos_dir / f"{source.modelo_id}.toml").exists()
    ]

    assert offenders == []


def test_multi_revision_modelos_do_not_use_single_file_layout() -> None:
    """Multi-revision modelos must use directory layout, not inline copy-per-revision TOML."""

    offenders: list[str] = []
    for source in _committed_modelo_sources():
        if source.layout != "single_file":
            continue
        modelo = _committed_modelo(source.modelo_id)
        if len(modelo.revisions) <= 1:
            continue
        offenders.append(f"{source.modelo_id}: {len(modelo.revisions)} revisions in {source.path.name}")

    assert offenders == []


def test_fragmented_revision_directories_are_schema_owned() -> None:
    """Every committed revision fragment directory has a schema manifest and loads."""

    checked: list[str] = []
    for source in _committed_modelo_sources():
        if source.layout != "directory":
            continue
        modelo = _committed_modelo(source.modelo_id)
        for revision_source in source.revision_sources:
            if revision_source.layout != "fragment_directory":
                continue
            checked.append(f"{source.modelo_id}/{revision_source.revision_id}")
            assert (revision_source.path / "revision.toml").is_file()
            assert revision_source.revision_id in modelo.revisions
            assert not (source.path / "revisions" / f"{revision_source.revision_id}.toml").exists()

    assert checked, "at least one committed revision must use fragment-directory layout"


def test_committed_directory_source_inventory_lists_every_revision_fragment_toml() -> None:
    """Discovery exposes all TOML fragments that participate in a directory revision."""

    checked: list[str] = []
    paths_by_modelo_id = _committed_non_locale_toml_paths_by_modelo_id()
    paths_by_fragment_revision = _committed_non_locale_toml_paths_by_fragment_revision()
    for source in _committed_modelo_sources():
        if source.layout != "directory":
            continue
        expected_paths = set(paths_by_modelo_id.get(source.modelo_id, ()))
        discovered_paths: set[Path] = set()
        for revision_source in source.revision_sources:
            if revision_source.layout == "revision_file":
                assert revision_source.fragment_paths == (revision_source.path,)
            else:
                expected_revision_paths = paths_by_fragment_revision[(source.modelo_id, revision_source.revision_id)]
                assert tuple(sorted(revision_source.fragment_paths)) == expected_revision_paths
            discovered_paths.update(revision_source.fragment_paths)
            checked.append(f"{source.modelo_id}/{revision_source.revision_id}")
        assert discovered_paths == expected_paths

    assert checked, "at least one committed directory revision must be discovered"


def test_locale_translation_fragments_merge_by_language_directory(tmp_path: Path) -> None:
    """Locale directories allow large reviewable language fragments."""

    revision_dir = _write_minimal_localized_modelo(tmp_path / "localized", ("0001", "0002"))
    locales_dir = revision_dir / "locales"
    _write_locale_fragment(locales_dir, "en", "001-labels.toml", '[labels]\n"0001" = "One"\n')
    _write_locale_fragment(locales_dir, "en", "002-help.toml", '[help]\n"0002" = "Two help"\n')

    modelo = load_modelo_directory(tmp_path / "localized")
    casillas = {casilla.id: casilla for casilla in modelo.revisions["2025"].casillas}

    assert casillas[_COMPLETENESS_CASILLA_0001].localized_labels == {"en": "One"}
    assert casillas[_COMPLETENESS_CASILLA_0002].localized_help == {"en": "Two help"}


def test_locale_translation_fragments_reject_duplicate_keys(tmp_path: Path) -> None:
    """Fragmented locale tables must remain unambiguous."""

    revision_dir = _write_minimal_localized_modelo(tmp_path / "localized", ("0001",))
    locales_dir = revision_dir / "locales"
    _write_locale_fragment(locales_dir, "en", "001-labels.toml", '[labels]\n"0001" = "One"\n')
    _write_locale_fragment(locales_dir, "en", "002-labels.toml", '[labels]\n"0001" = "Uno"\n')

    with pytest.raises(RegistryValidationError, match="Duplicate 'en' locale translation keys"):
        load_modelo_directory(tmp_path / "localized")


def test_committed_registry_toml_files_stay_reviewable() -> None:
    """Registry TOML files must not regress toward monolithic artifacts."""

    oversized_single_file_modelos: list[str] = []
    oversized_fragments: list[str] = []
    oversized_rows: list[str] = []

    modelos_dir = _committed_modelos_dir()
    for path in _committed_modelo_toml_paths():
        relative_path = path.relative_to(modelos_dir).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        if path.parent == modelos_dir and len(lines) > _MAX_SINGLE_FILE_MODELO_LINES:
            oversized_single_file_modelos.append(
                f"{relative_path}: {len(lines)} lines > {_MAX_SINGLE_FILE_MODELO_LINES}",
            )
        if len(lines) > _MAX_TOML_FRAGMENT_LINES:
            oversized_fragments.append(f"{relative_path}: {len(lines)} lines > {_MAX_TOML_FRAGMENT_LINES}")
        for line_number, line in enumerate(lines, start=1):
            if len(line) <= _MAX_TOML_ROW_CHARS:
                continue
            oversized_rows.append(f"{relative_path}:{line_number}: {len(line)} chars > {_MAX_TOML_ROW_CHARS}")

    assert oversized_single_file_modelos == []
    assert oversized_fragments == []
    assert oversized_rows == []
