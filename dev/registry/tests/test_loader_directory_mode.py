"""Layout tests for the directory-mode modelo loader.

A modelo source is a ``modelos/<id>/`` directory carrying ``manifest.toml``
plus one ``revisions/<id>/`` fragment tree per revision. Nothing else is a
modelo source: a ``modelos/<id>.toml`` file and a ``revisions/<id>.toml``
file are both refused at discovery, naming the path and the expected layout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import (
    RegistryFailureCondition,
    RegistryLoadError,
    RegistryValidationError,
)

from ..compiler.loader import (
    load_catalogue_file,
    load_modelo_directory,
    load_modelo_source,
    load_registry_tree,
    load_shared_catalogues,
)
from ..compiler.loader_cache import ModeloSource, discover_modelo_sources
from ..compiler.loader_fingerprints import clear_fingerprint_cache
from ..conformance.loader_directory_mode_support import (
    MAX_TOML_FRAGMENT_LINES as _MAX_TOML_FRAGMENT_LINES,
)
from ..conformance.loader_directory_mode_support import (
    MAX_TOML_ROW_CHARS as _MAX_TOML_ROW_CHARS,
)
from ..conformance.loader_directory_mode_support import (
    committed_modelo as _committed_modelo,
)
from ..conformance.loader_directory_mode_support import (
    committed_modelo_sources as _committed_modelo_sources,
)
from ..conformance.loader_directory_mode_support import (
    committed_modelo_sources_by_id as _committed_modelo_sources_by_id,
)
from ..conformance.loader_directory_mode_support import (
    committed_modelo_toml_paths as _committed_modelo_toml_paths,
)
from ..conformance.loader_directory_mode_support import (
    committed_modelos_dir as _committed_modelos_dir,
)
from ..conformance.loader_directory_mode_support import (
    committed_registry_modelos as _committed_registry_modelos,
)
from ..conformance.loader_directory_mode_support import (
    committed_toml_paths_by_fragment_revision as _committed_toml_paths_by_fragment_revision,
)
from ..conformance.loader_directory_mode_support import (
    committed_toml_paths_by_modelo_id as _committed_toml_paths_by_modelo_id,
)
from ..conformance.loader_directory_mode_support import (
    minimal_fragment_revision_layout as _minimal_fragment_revision_layout,
)
from ..conformance.loader_directory_mode_support import (
    standard_manifest_text as _standard_manifest_text,
)
from ..conformance.loader_directory_mode_support import (
    standard_revision_preamble_text as _standard_revision_preamble_text,
)
from ..conformance.loader_directory_mode_support import (
    write_fragmented_modelo as _write_fragmented_modelo,
)
from ..conformance.loader_directory_mode_support import (
    write_fragmented_revision as _write_fragmented_revision,
)
from ..conformance.loader_directory_mode_support import (
    write_minimal_shared_catalogues,
)
from ..conformance.loader_directory_mode_support import (
    write_standard_manifest as _write_standard_manifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_directory_mode_rejects_manifest_with_revisions_table(tmp_path: Path) -> None:
    """The manifest must not declare [revisions] — that lives in revisions/*.toml."""

    target = tmp_path / "bad_manifest"
    target.mkdir()
    (target / "manifest.toml").write_text(
        '[modelo]\nid = "999"\ntax_domain = "iva"\n[revisions."2025"]\n',
        encoding="utf-8",
    )
    (target / "revisions").mkdir()
    with pytest.raises(RegistryLoadError, match="manifest must not declare \\[revisions\\]"):
        load_modelo_directory(target)


def test_directory_mode_rejects_inline_section_in_revision_manifest(tmp_path: Path) -> None:
    """A fragment-directory revision.toml must not carry an inline section table.

    Sections (bindings, formulas, casillas, …) live in per-section fragment
    subdirectories; an inline array-of-tables in revision.toml is a loud load
    error naming the fragmented layout it belongs in.
    """

    target = tmp_path / "inline_section_manifest"
    revision_dir = _minimal_fragment_revision_layout(target)
    (revision_dir / "revision.toml").write_text(
        '[revisions."2025"]\n'
        "valid_from = 2025-01-01\n"
        '[[revisions."2025".bindings]]\n'
        'id = "inline-binding"\n'
        'source = "previous_filing"\n',
        encoding="utf-8",
    )
    with pytest.raises(RegistryLoadError, match="'bindings' section must live in a 'bindings/' fragment subdirectory"):
        load_modelo_directory(target)


def test_directory_mode_rejects_inline_formulas_section_in_revision_manifest(tmp_path: Path) -> None:
    """The manifest refusal covers every section field, including formulas."""

    target = tmp_path / "inline_formulas_manifest"
    revision_dir = _minimal_fragment_revision_layout(target)
    (revision_dir / "revision.toml").write_text(
        '[revisions."2025"]\n'
        "valid_from = 2025-01-01\n"
        '[[revisions."2025".formulas]]\n'
        'id = "inline-formula"\n'
        'target_casilla_id = "01"\n',
        encoding="utf-8",
    )
    with pytest.raises(RegistryLoadError, match="'formulas' section must live in a 'formulas/' fragment subdirectory"):
        load_modelo_directory(target)


def test_directory_mode_rejects_malformed_casilla_id_before_locale_key_authority(tmp_path: Path) -> None:
    """Raw TOML casilla ids must be validated before they seed loader authority sets."""

    target = _write_fragmented_modelo(
        tmp_path / "malformed_casilla_id",
        manifest_text=_standard_manifest_text("Malformed casilla id test"),
        revisions={
            "2025": _standard_revision_preamble_text()
            + """

[[revisions."2025".casillas]]
id = "bad key"
number = "1"
section = ["liquidacion"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        },
    )

    with pytest.raises(RegistryLoadError, match=r"casillas\.0\.id"):
        load_modelo_directory(target)


def test_directory_mode_rejects_ambiguous_casilla_identity_during_load(tmp_path: Path) -> None:
    target = _write_fragmented_modelo(
        tmp_path / "999",
        manifest_text=_standard_manifest_text("Ambiguous casilla identity test"),
        revisions={
            "2025": _standard_revision_preamble_text()
            + """

[[revisions."2025".casillas]]
id = "01"
number = "99"
section = ["test"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".casillas]]
id = "DPX:01"
number = "01"
segmento = "DPX"
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
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\ntax_domain = "iva"\n', encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="no revisions found"):
        load_modelo_directory(target)


def test_committed_registry_tree_loads_directory_modelos() -> None:
    """Registry discovery must load every committed directory-form modelo."""

    sources = _committed_modelo_sources()
    modelos = _committed_registry_modelos()
    loaded_ids = {modelo.id for modelo in modelos}

    assert loaded_ids == {source.modelo_id for source in sources}
    assert {_committed_modelo(source.modelo_id).id for source in sources} == loaded_ids
    assert sources


def test_catalogue_rejects_the_retired_global_parameters_section(tmp_path: Path) -> None:
    """The shared legal loader must not silently revive the retired provider."""

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
review_status = "pending_review"
reviewed_at = 2026-06-28
reviewed_by = "registry-test"
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match=r"retired global \[parameters\] catalogue section is forbidden"):
        load_catalogue_file(legal_dir / "parameters.toml")


def test_shared_catalogues_reject_duplicate_legal_ids_across_fragments(tmp_path: Path) -> None:
    """The cycle-safe loader must preserve the full catalogue's unique legal authority."""

    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    first_fragment = """
[legal."ley-test:art-1"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/test/first.html#art-1"
document_id = "BOE-FIRST"
article = "1"
permalink = "https://example.com/first"
effective_from = 2026-01-01
review_status = "agent_reviewed"
reviewed_at = 2026-06-28
reviewed_by = "registry-test"
required_text = ["first provision"]
""".lstrip()
    second_fragment = first_fragment.replace("first", "second").replace("BOE-FIRST", "BOE-SECOND")
    (legal_dir / "a.toml").write_text(first_fragment, encoding="utf-8")
    (legal_dir / "b.toml").write_text(second_fragment, encoding="utf-8")

    with pytest.raises(
        RegistryLoadError,
        match=r"duplicate catalogue ids legal=\['ley-test:art-1'\] sources=\[\]",
    ):
        load_shared_catalogues(tmp_path)


def test_shared_catalogues_reject_noncanonical_parameter_key(tmp_path: Path) -> None:
    """The TOML map key must pass the canonical ParameterId boundary."""

    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    (legal_dir / "parameters.toml").write_text(
        """
[parameters."bad id with spaces"]
evidence_tier = "legal_authority"
value = "0.21"
unit = "fraction"
applies_to = "test-case"
legal_refs = ["ley-test:art-1"]
review_status = "pending_review"
reviewed_at = 2026-06-28
reviewed_by = "registry-test"
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(
        RegistryLoadError,
        match=r"invalid legal parameter 'bad id with spaces'",
    ):
        load_shared_catalogues(tmp_path)


def test_shared_catalogues_preserves_valid_parameter_key_identity(tmp_path: Path) -> None:
    """A valid TOML key is the identity of the loaded typed parameter."""

    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    (legal_dir / "catalogue.toml").write_text(
        """
[legal."ley-test:art-1"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/test/ley-test.html#art-1"
document_id = "BOE-TEST-001"
article = "1"
permalink = "https://example.com/ley-test"
effective_from = 2026-01-01
review_status = "agent_reviewed"
reviewed_at = 2026-06-28
reviewed_by = "registry-test"
required_text = ["test provision"]

[parameters."test-rate"]
evidence_tier = "legal_authority"
value = "0.21"
unit = "fraction"
applies_to = "test-case"
legal_refs = ["ley-test:art-1"]
review_status = "pending_review"
reviewed_at = 2026-06-28
reviewed_by = "registry-test"
""".lstrip(),
        encoding="utf-8",
    )
    write_minimal_shared_catalogues(legal_dir, years=(2026,))

    parameters = load_shared_catalogues(tmp_path).parameters

    assert tuple(parameters) == ("test-rate",)
    assert parameters["test-rate"].id == "test-rate"


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
review_status = "pending_review"
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

        assert source.path.name == modelo_id
        assert modelo.id == modelo_id
        assert source.revision_sources
        assert {revision_source.revision_id for revision_source in source.revision_sources} == set(modelo.revisions)


def test_registry_tree_cache_invalidates_when_a_revision_directory_is_added_inside_ttl(tmp_path: Path) -> None:
    """A structural change to a modelo tree must not reuse the previous registry-tree fingerprint."""

    registry_root = tmp_path / "registry" / "aeat"
    modelos_dir = registry_root / "modelos"
    legal_dir = registry_root / "legal"
    legal_dir.mkdir(parents=True)
    (legal_dir / "supported-filing-years.toml").write_text(
        "[supported_filing_years]\nyears = [2025]\n\n"
        "[sociedades_annual_manual_coverage]\n"
        'dispositions = [{ year = 2025, status = "unpublished", '
        'official_locator = "https://example.com/manuals", observed_at = 2026-09-10, '
        'acquisition_condition_key = "application.registry.manuals.coverage.recheck_aeat_publication" }]\n',
        encoding="utf-8",
        newline="\n",
    )
    modelos_dir.mkdir()

    modelo_dir = _write_fragmented_modelo(
        modelos_dir / "999",
        manifest_text=_standard_manifest_text("Cache invalidation before"),
        revisions={"2025": _standard_revision_preamble_text(source_ref="cache-before")},
    )

    clear_fingerprint_cache()
    first_modelos, first_catalogues = load_registry_tree(registry_root)
    first_by_id = {modelo.id: modelo for modelo in first_modelos}
    assert set(first_by_id["999"].revisions) == {"2025"}
    assert first_by_id["999"].revisions["2025"].source_refs == ("cache-before",)
    assert first_catalogues.supported_filing_years is not None
    assert first_catalogues.supported_filing_years.years == (2025,)

    _write_fragmented_revision(
        modelo_dir / "revisions" / "2026",
        _standard_revision_preamble_text(source_ref="cache-after").replace('"2025"', '"2026"'),
    )

    second_modelos, _second_catalogues = load_registry_tree(registry_root)
    second_by_id = {modelo.id: modelo for modelo in second_modelos}
    assert set(second_by_id["999"].revisions) == {"2025", "2026"}
    assert second_by_id["999"].revisions["2026"].source_refs == ("cache-after",)


def test_stale_discovered_source_reports_typed_disappearance(tmp_path: Path) -> None:
    """A source removed after discovery raises RegistryLoadError, not bare FileNotFoundError."""

    source_path = tmp_path / "parameters.toml"
    source_path.write_text('[legal.ley-58-2003]\ntitle = "Ley General Tributaria"\n', encoding="utf-8")

    source_path.unlink()

    with pytest.raises(RegistryLoadError, match="registry TOML could not be fingerprinted") as exc_info:
        load_catalogue_file(source_path)

    message = str(exc_info.value)
    assert str(source_path) in message
    failure = exc_info.value.registry_failure
    assert failure is not None
    assert failure.condition is RegistryFailureCondition.TREE_QUIESCENT
    assert failure.facts == {
        "path": str(source_path),
        "registry_tree_quiescent": False,
        "operation": "toml_stat",
    }
    assert "retry after concurrent registry writes settle" not in message


def test_stable_malformed_modelo_toml_remains_invalid_registry_data(tmp_path: Path) -> None:
    """Malformed TOML that does not change during load remains a real parse error."""

    registry_root = tmp_path / "registry" / "aeat"
    modelos_dir = registry_root / "modelos"
    (registry_root / "legal").mkdir(parents=True)
    modelos_dir.mkdir()
    bad_modelo_dir = modelos_dir / "999"
    bad_modelo_dir.mkdir()
    bad_path = bad_modelo_dir / "manifest.toml"
    bad_path.write_text("[modelo]\nid = ", encoding="utf-8")

    clear_fingerprint_cache()
    with pytest.raises(RegistryLoadError, match="invalid TOML") as exc_info:
        load_registry_tree(registry_root)

    message = str(exc_info.value)
    assert str(bad_path) in message
    assert "changed during load" not in message


def test_fragmented_revision_directories_are_schema_owned() -> None:
    """Every committed revision fragment directory has a schema manifest and loads."""

    checked: list[str] = []
    for source in _committed_modelo_sources():
        modelo = _committed_modelo(source.modelo_id)
        for revision_source in source.revision_sources:
            checked.append(f"{source.modelo_id}/{revision_source.revision_id}")
            assert (revision_source.path / "revision.toml").is_file()
            assert revision_source.revision_id in modelo.revisions
            assert not (source.path / "revisions" / f"{revision_source.revision_id}.toml").exists()

    assert checked, "at least one committed revision must use fragment-directory layout"


def test_committed_directory_source_inventory_lists_every_revision_fragment_toml() -> None:
    """Discovery exposes all TOML fragments that participate in a directory revision."""

    checked: list[str] = []
    paths_by_modelo_id = _committed_toml_paths_by_modelo_id()
    paths_by_fragment_revision = _committed_toml_paths_by_fragment_revision()
    for source in _committed_modelo_sources():
        expected_paths = set(paths_by_modelo_id.get(source.modelo_id, ()))
        discovered_paths: set[Path] = set()
        for revision_source in source.revision_sources:
            expected_revision_paths = paths_by_fragment_revision[(source.modelo_id, revision_source.revision_id)]
            assert tuple(sorted(revision_source.fragment_paths)) == expected_revision_paths
            discovered_paths.update(revision_source.fragment_paths)
            checked.append(f"{source.modelo_id}/{revision_source.revision_id}")
        assert discovered_paths == expected_paths

    assert checked, "at least one committed directory revision must be discovered"


def test_committed_registry_toml_files_stay_reviewable() -> None:
    """Registry TOML files must not regress toward monolithic artifacts."""

    oversized_fragments: list[str] = []
    oversized_rows: list[str] = []

    modelos_dir = _committed_modelos_dir()
    for path in _committed_modelo_toml_paths():
        relative_path = path.relative_to(modelos_dir).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > _MAX_TOML_FRAGMENT_LINES:
            oversized_fragments.append(f"{relative_path}: {len(lines)} lines > {_MAX_TOML_FRAGMENT_LINES}")
        for line_number, line in enumerate(lines, start=1):
            if len(line) <= _MAX_TOML_ROW_CHARS:
                continue
            oversized_rows.append(f"{relative_path}:{line_number}: {len(line)} chars > {_MAX_TOML_ROW_CHARS}")

    assert oversized_fragments == []
    assert oversized_rows == []


def test_discovery_refuses_a_single_file_modelo(tmp_path: Path) -> None:
    """``modelos/<id>.toml`` is no longer a modelo source."""

    modelos_dir = tmp_path / "modelos"
    modelos_dir.mkdir()
    single_file = modelos_dir / "999.toml"
    single_file.write_text(
        _standard_manifest_text("Retired single-file layout") + "\n" + _standard_revision_preamble_text(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="single-file modelos are not a supported layout") as exc_info:
        discover_modelo_sources(modelos_dir)

    message = str(exc_info.value)
    assert str(single_file) in message
    assert "modelos/<id>/ directory containing manifest.toml" in message


def test_load_modelo_source_refuses_a_single_file_modelo(tmp_path: Path) -> None:
    """The compile path refuses a modelo file even if one reaches it directly."""

    single_file = tmp_path / "999.toml"
    single_file.write_text(
        _standard_manifest_text("Retired single-file layout") + "\n" + _standard_revision_preamble_text(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="modelo directory does not exist"):
        load_modelo_source(ModeloSource(modelo_id="999", path=single_file, manifest_path=single_file))


def test_directory_mode_refuses_a_revision_file(tmp_path: Path) -> None:
    """``revisions/<id>.toml`` is no longer a revision source."""

    target = tmp_path / "999"
    (target / "revisions").mkdir(parents=True)
    _write_standard_manifest(target, "Retired revision-file layout")
    revision_file = target / "revisions" / "2025.toml"
    revision_file.write_text(_standard_revision_preamble_text(), encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="revision files are not a supported layout") as exc_info:
        load_modelo_directory(target)

    message = str(exc_info.value)
    assert str(revision_file) in message
    assert "revisions/<id>/ directory containing revision.toml" in message


def test_discovery_refuses_a_revision_file(tmp_path: Path) -> None:
    """Source discovery refuses the retired revision-file layout too."""

    modelos_dir = tmp_path / "modelos"
    target = modelos_dir / "999"
    (target / "revisions").mkdir(parents=True)
    _write_standard_manifest(target, "Retired revision-file layout")
    revision_file = target / "revisions" / "2025.toml"
    revision_file.write_text(_standard_revision_preamble_text(), encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="revision files are not a supported layout"):
        discover_modelo_sources(modelos_dir)
