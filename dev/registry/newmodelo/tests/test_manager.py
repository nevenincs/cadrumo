"""Real-behaviour tests for NewModeloScaffoldManager scaffold/check against a real filesystem."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ..checklist import CHECKLIST, render_checklist
from ..manager import NewModeloError, NewModeloScaffoldManager, ScaffoldResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# A modelo id that is guaranteed to collide with no real registry entry
# (three digits, well above the highest AEAT modelo code currently modelled).
_THROWAWAY_MODELO_ID = "987"
_THROWAWAY_REVISION_ID = "2026-y-siguientes"


def test_scaffold_writes_full_skeleton_and_is_idempotent(tmp_path: Path) -> None:
    """scaffold() writes every planned file once; a second run is a no-op."""
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)

    first = manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID, title="Throwaway test modelo")
    assert isinstance(first, ScaffoldResult)
    assert first.written, "first scaffold run must write files"
    assert not first.already_present

    manifest_path = tmp_path / _THROWAWAY_MODELO_ID / "manifest.toml"
    revision_path = tmp_path / _THROWAWAY_MODELO_ID / "revisions" / _THROWAWAY_REVISION_ID / "revision.toml"
    assert manifest_path.is_file()
    assert revision_path.is_file()
    assert "987" in manifest_path.read_text(encoding="utf-8")

    for section in (
        "casillas",
        "formulas",
        "bindings",
        "completeness_manifest",
        "verification_expectations",
        "export_layouts",
        "extraction_profiles",
        "application_links",
    ):
        section_dir = tmp_path / _THROWAWAY_MODELO_ID / "revisions" / _THROWAWAY_REVISION_ID / section
        assert section_dir.is_dir(), f"missing scaffolded section directory: {section}"
        fragments = scan_directory(section_dir, pattern="*.toml")
        assert fragments, f"section {section} has no scaffolded fragment file"

    locales_dir = tmp_path / _THROWAWAY_MODELO_ID / "revisions" / _THROWAWAY_REVISION_ID / "locales"
    assert not locales_dir.exists(), "new Modelo scaffolding must not recreate legacy locale storage"

    # Second run: nothing new written, everything reported as already present.
    second = manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID, title="Throwaway test modelo")
    assert not second.written
    assert second.already_present
    assert set(second.already_present) == set(first.written)


def test_scaffold_force_overwrites_existing_placeholders(tmp_path: Path) -> None:
    """--force re-writes every planned file even when it already exists."""
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)

    manifest_path = tmp_path / _THROWAWAY_MODELO_ID / "manifest.toml"
    manifest_path.write_text("# hand-mutated\n", encoding="utf-8")

    forced = manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID, force=True)
    assert Path("manifest.toml") in forced.written
    assert "hand-mutated" not in manifest_path.read_text(encoding="utf-8")


def test_check_reports_missing_files_without_writing(tmp_path: Path) -> None:
    """check() reports drift and writes nothing, even when the tree is entirely absent."""
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)

    drift = manager.check(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)
    assert not drift.is_conformant
    assert not drift.already_present
    assert drift.missing
    assert not (tmp_path / _THROWAWAY_MODELO_ID).exists(), "check() must never write to disk"


def test_check_is_conformant_after_a_real_scaffold(tmp_path: Path) -> None:
    """check() reports zero drift immediately after scaffold() on the same ids."""
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)

    drift = manager.check(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)
    assert drift.is_conformant
    assert not drift.missing


def test_check_detects_partial_drift_after_manual_deletion(tmp_path: Path) -> None:
    """Deleting one scaffolded file causes check() to report exactly that file as missing."""
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)

    target = tmp_path / _THROWAWAY_MODELO_ID / "revisions" / _THROWAWAY_REVISION_ID / "casillas" / "0001-casillas.toml"
    assert target.is_file()
    target.unlink()

    drift = manager.check(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)
    assert not drift.is_conformant
    assert Path("revisions") / _THROWAWAY_REVISION_ID / "casillas" / "0001-casillas.toml" in drift.missing


def test_scaffold_rejects_malformed_modelo_id(tmp_path: Path) -> None:
    """A modelo id that is not exactly three digits is refused, matching ModeloId's pattern."""
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    for bad_modelo_id in ("", "AB", "12", "1234", "abc"):
        with pytest.raises(NewModeloError):
            manager.scaffold(bad_modelo_id, _THROWAWAY_REVISION_ID)
        assert not scan_directory(tmp_path), bad_modelo_id


def test_scaffold_rejects_malformed_revision_id(tmp_path: Path) -> None:
    """A revision id outside the registry ref pattern is refused before any write."""
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    for bad_revision_id in ("", "Bad Revision", "_leading-underscore", "trailing-"):
        with pytest.raises(NewModeloError):
            manager.scaffold(_THROWAWAY_MODELO_ID, bad_revision_id)
        assert not (tmp_path / _THROWAWAY_MODELO_ID).exists(), bad_revision_id


def test_scaffold_refuses_when_modelo_root_is_a_file(tmp_path: Path) -> None:
    """A pre-existing plain file at the modelo root path is refused, not silently replaced."""
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    (tmp_path / _THROWAWAY_MODELO_ID).write_text("not a directory", encoding="utf-8")

    with pytest.raises(NewModeloError):
        manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)


def test_scaffold_refuses_to_graft_a_revision_onto_a_real_foreign_modelo(tmp_path: Path) -> None:
    """A mistyped/colliding modelo id whose manifest is real registry content is refused.

    Regression for a defect caught by manual smoke-testing this scaffold against the
    real registry root: scaffolding modelo "100" (an already-modelled, real modelo)
    with a not-yet-existing revision id silently wrote 12 new placeholder files into
    modelo 100's live directory tree because only per-file existence was checked, not
    whether the modelo directory already belongs to real content. The guard refuses
    unless the existing manifest.toml carries this scaffold's own sentinel, or the
    caller passes force=True.
    """
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    foreign_modelo_dir = tmp_path / _THROWAWAY_MODELO_ID
    foreign_modelo_dir.mkdir(parents=True)
    (foreign_modelo_dir / "manifest.toml").write_text(
        '[modelo]\nid = "987"\ntitle = "Real, already-modelled modelo"\n',
        encoding="utf-8",
    )

    with pytest.raises(NewModeloError, match="refusing to add a revision skeleton"):
        manager.scaffold(_THROWAWAY_MODELO_ID, "2099-y-siguientes")

    # Confirm nothing was written into the foreign modelo's revisions tree.
    assert not (foreign_modelo_dir / "revisions" / "2099-y-siguientes").exists()


def test_scaffold_force_bypasses_the_foreign_manifest_guard(tmp_path: Path) -> None:
    """force=True explicitly bypasses the foreign-manifest guard, as documented."""
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    foreign_modelo_dir = tmp_path / _THROWAWAY_MODELO_ID
    foreign_modelo_dir.mkdir(parents=True)
    (foreign_modelo_dir / "manifest.toml").write_text(
        '[modelo]\nid = "987"\ntitle = "Real, already-modelled modelo"\n',
        encoding="utf-8",
    )

    result = manager.scaffold(_THROWAWAY_MODELO_ID, "2099-y-siguientes", force=True)
    assert (foreign_modelo_dir / "revisions" / "2099-y-siguientes" / "revision.toml").is_file()
    assert result.written


def test_scaffolded_tree_reaches_directory_mode_validation(tmp_path: Path) -> None:
    """The scaffolded skeleton reaches semantic registry validation.

    The real directory loader can read the generated on-disk structure, then rejects its
    deliberately incomplete TODO metadata. This proves the scaffold reaches semantic
    validation rather than failing earlier on a malformed directory layout.
    """
    from cadrumo.domain.calculations.registry.loader import load_modelo_directory

    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)

    # The placeholder manifest/revision content is intentionally incomplete
    # (TODO tax_domain, cadence, dates) and must not validate as-is: a scaffold
    # that "passes" the loader with all-TODO content would be a false green.
    modelo_root = tmp_path / _THROWAWAY_MODELO_ID
    with pytest.raises(RegistryLoadError):
        load_modelo_directory(modelo_root)


def test_scaffolded_toml_declares_only_fields_the_schema_knows(tmp_path: Path) -> None:
    """Every key the scaffold emits is a real schema field.

    The scaffold's load is expected to FAIL while its TODO placeholders stand,
    so the adjacent load test cannot tell "refused because tax_domain is TODO"
    apart from "refused because the key does not exist". A field the schema
    dropped therefore hides inside an expected failure, and the contributor
    meets it only after filling every TODO in. This asserts the structural
    property directly instead, and derives the permitted set from the models so
    it cannot drift from them the way a hand-listed set would.
    """
    import tomllib

    from cadrumo.domain.calculations.registry.schema import (
        ModeloDefinition,
        ModeloRevision,
    )

    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)
    modelo_root = tmp_path / _THROWAWAY_MODELO_ID

    manifest = tomllib.loads((modelo_root / "manifest.toml").read_text(encoding="utf-8"))
    declared_modelo = set(manifest["modelo"])
    unknown_modelo = sorted(declared_modelo - set(ModeloDefinition.model_fields))
    assert not unknown_modelo, (
        f"scaffolded manifest.toml declares [modelo] keys ModeloDefinition rejects: {unknown_modelo}. "
        "A scaffolded modelo must load once its TODOs are filled in."
    )

    revision_path = modelo_root / "revisions" / _THROWAWAY_REVISION_ID / "revision.toml"
    revision_doc = tomllib.loads(revision_path.read_text(encoding="utf-8"))
    declared_revision = set(revision_doc["revisions"][_THROWAWAY_REVISION_ID])
    unknown_revision = sorted(declared_revision - set(ModeloRevision.model_fields))
    assert not unknown_revision, (
        f"scaffolded revision.toml declares keys ModeloRevision rejects: {unknown_revision}. "
        "Presentation text belongs in the shared locale catalogues, not the revision fragment."
    )

    assert declared_modelo, "manifest fixture produced no [modelo] keys; the scaffold changed shape"
    assert declared_revision, "revision fixture produced no keys; the scaffold changed shape"


def test_render_checklist_contains_all_twelve_items() -> None:
    """The checklist module carries exactly the 12 contributor items #410 requires."""
    assert len(CHECKLIST) == 12
    rendered = render_checklist()
    for index, item in enumerate(CHECKLIST, start=1):
        assert item.title in rendered
        assert f"{index:>2}." in rendered
