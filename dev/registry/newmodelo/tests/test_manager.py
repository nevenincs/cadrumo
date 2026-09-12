"""Real-behaviour tests for NewModeloScaffoldManager scaffold/check against a real filesystem."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ...conformance.manager import load_locale_coverage_index
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


def test_scaffold_invalidates_the_conformance_snapshot_cache_only_when_it_writes(tmp_path: Path) -> None:
    """A write must drop the conformance snapshot cache; a pure no-op must not.

    The cache is keyed only on ``validate``, never on registry source state
    (see :func:`dev.registry.conformance.manager.reset_conformance_cache`), so
    nothing notices this scaffold's write on its own. A scaffold-then-audit
    call chain in one process would otherwise see the pre-scaffold profile.
    """
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)

    # The memoised read returns the SAME object until something clears it, so
    # object identity across calls is the cache state itself -- no seam to stub.
    primed = load_locale_coverage_index()
    assert load_locale_coverage_index() is primed, "a live cache must serve the identical object"

    first = manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID, title="Throwaway test modelo")
    assert first.written
    after_write = load_locale_coverage_index()
    assert after_write is not primed, "a scaffold that wrote must have dropped the conformance snapshot cache"

    second = manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID, title="Throwaway test modelo")
    assert not second.written
    assert load_locale_coverage_index() is after_write, "a no-op scaffold must leave the cache intact"


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
        with pytest.raises(NewModeloError, match="modelo id must be exactly three digits"):
            manager.scaffold(bad_modelo_id, _THROWAWAY_REVISION_ID)
        assert not scan_directory(tmp_path), bad_modelo_id


def test_scaffold_rejects_malformed_revision_id(tmp_path: Path) -> None:
    """A revision id outside the registry ref pattern is refused before any write."""
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    for bad_revision_id in ("", "Bad Revision", "_leading-underscore", "trailing-"):
        with pytest.raises(NewModeloError, match="revision id must be a lowercase kebab-style ref"):
            manager.scaffold(_THROWAWAY_MODELO_ID, bad_revision_id)
        assert not (tmp_path / _THROWAWAY_MODELO_ID).exists(), bad_revision_id


def test_scaffold_refuses_when_modelo_root_is_a_file(tmp_path: Path) -> None:
    """A pre-existing plain file at the modelo root path is refused, not silently replaced."""
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    (tmp_path / _THROWAWAY_MODELO_ID).write_text("not a directory", encoding="utf-8")

    with pytest.raises(NewModeloError, match="exists and is not a directory"):
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


def test_scaffolded_tree_is_refused_by_the_directory_mode_loader(tmp_path: Path) -> None:
    """The scaffolded skeleton never passes as a loadable modelo tree.

    Measured, not assumed. A bare ``pytest.raises(RegistryLoadError)`` here once
    let a docstring claim the refusal came from semantic ``ModeloDefinition``
    validation of the manifest's TODO fields; against a real scaffolded tree it
    does not. Every non-``casillas`` section fragment (formulas, bindings,
    completeness_manifest, verification_expectations,
    extraction_profiles, application_links) is scaffolded as guidance that is
    entirely commented out, so ``_read_single_revision_table`` refuses the
    first such fragment it reads for declaring no ``[revisions.<id>]`` table at
    all -- a structural refusal, before the merged tree ever reaches the
    manifest's own TODO placeholders. The ``match=`` pins that structural
    reason directly so a change that made the scaffold reach semantic
    validation instead -- or one that broke it in a third, new way -- would be
    visible here rather than passing under a docstring that no longer
    describes what fires.
    """
    from ...compiler.loader import load_modelo_directory

    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)

    modelo_root = tmp_path / _THROWAWAY_MODELO_ID
    with pytest.raises(RegistryLoadError, match=r"revision fragment must declare \[revisions\.<id>\]"):
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


def test_render_checklist_renders_every_item() -> None:
    """Every checklist item reaches the rendered report, numbered in order.

    The item count is deliberately not asserted. It is not the contract, and
    pinning it made adding a required authoring step fail three tests that were
    not about the new step at all.
    """
    assert CHECKLIST
    rendered = render_checklist()
    for index, item in enumerate(CHECKLIST, start=1):
        assert item.title in rendered
        assert f"{index:>2}." in rendered


def _write_edition(modelos_root: Path, modelo_id: str, revision_id: str, valid_from: str) -> None:
    """Write a minimal real edition on disk for the predecessor scan to read."""
    revision_root = modelos_root / modelo_id / "revisions" / revision_id
    revision_root.mkdir(parents=True, exist_ok=True)
    (revision_root / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\nvalid_from = {valid_from}\n',
        encoding="utf-8",
    )


def test_a_first_edition_declares_no_predecessor_key_at_all(tmp_path: Path) -> None:
    """Absence is the grounded statement; a placeholder naming nothing is not.

    A modelo with no earlier edition on disk states every row itself, and the
    schema reads a missing key as exactly that. Emitting the key with an empty
    or TODO value instead would be a predecessor claim the scaffold cannot make.
    """
    import tomllib

    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)

    revision_path = tmp_path / _THROWAWAY_MODELO_ID / "revisions" / _THROWAWAY_REVISION_ID / "revision.toml"
    declared = tomllib.loads(revision_path.read_text(encoding="utf-8"))["revisions"][_THROWAWAY_REVISION_ID]
    assert "predecessor" not in declared


def test_a_successor_edition_declares_the_latest_existing_edition_as_predecessor(tmp_path: Path) -> None:
    """The newest edition BY DECLARED valid_from is offered, not the last one by name.

    Directory order and edition order disagree in the real corpus: modelo 303
    carries `2024-desde-09-y-3t` and `2024-hasta-08-y-2t`, where the edition
    that sorts first is the one that takes effect second. A scaffold that read
    the directory listing would hand a new edition the wrong predecessor, and
    the delta would then be measured against a form it does not succeed.
    """
    import tomllib

    _write_edition(tmp_path, _THROWAWAY_MODELO_ID, "2024-hasta-08-y-2t", "2024-01-01")
    _write_edition(tmp_path, _THROWAWAY_MODELO_ID, "2024-desde-09-y-3t", "2024-09-01")
    (tmp_path / _THROWAWAY_MODELO_ID / "manifest.toml").write_text(
        "# Scaffolded modelo manifest — test fixture\n",
        encoding="utf-8",
    )

    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    manager.scaffold(_THROWAWAY_MODELO_ID, "2025")

    revision_path = tmp_path / _THROWAWAY_MODELO_ID / "revisions" / "2025" / "revision.toml"
    declared = tomllib.loads(revision_path.read_text(encoding="utf-8"))["revisions"]["2025"]
    assert declared["predecessor"] == "2024-desde-09-y-3t"


def test_a_rescaffolded_edition_is_never_offered_its_own_name_as_predecessor(tmp_path: Path) -> None:
    """Re-running the scaffold over a written edition must not make it its own predecessor.

    The edition being scaffolded is on disk from the first run, so a scan that
    did not exclude it would name it -- a self-edge the predecessor forest
    refuses, discovered only once the tree is loaded.
    """
    import tomllib

    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)
    manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID, force=True)

    revision_path = tmp_path / _THROWAWAY_MODELO_ID / "revisions" / _THROWAWAY_REVISION_ID / "revision.toml"
    declared = tomllib.loads(revision_path.read_text(encoding="utf-8"))["revisions"][_THROWAWAY_REVISION_ID]
    assert declared.get("predecessor") != _THROWAWAY_REVISION_ID


def test_the_revision_manifest_declares_the_editions_casilla_source_default(tmp_path: Path) -> None:
    """casilla_source_refs is declared once on the edition, so no row has to restate it."""
    import tomllib

    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)

    revision_path = tmp_path / _THROWAWAY_MODELO_ID / "revisions" / _THROWAWAY_REVISION_ID / "revision.toml"
    declared = tomllib.loads(revision_path.read_text(encoding="utf-8"))["revisions"][_THROWAWAY_REVISION_ID]
    assert "casilla_source_refs" in declared


def test_the_casillas_fragment_proposes_no_restated_row_field(tmp_path: Path) -> None:
    """The exemplar row names only delta-shaped keys.

    The three restatements this excludes -- a row's own source_refs, its own
    legal_refs, and an edition year inside an identifier -- are each
    individually valid TOML the loader accepts, so nothing downstream would
    report them. The scaffold is where they are not proposed in the first place.
    """
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID)

    fragment = (
        tmp_path / _THROWAWAY_MODELO_ID / "revisions" / _THROWAWAY_REVISION_ID / "casillas" / "0001-casillas.toml"
    ).read_text(encoding="utf-8")
    proposed = [
        line.removeprefix("# ").strip()
        for line in fragment.splitlines()
        if line.startswith("# ") and "=" in line and not line.startswith("# [")
    ]
    keys = [line.split("=", 1)[0].strip() for line in proposed]

    assert "additional_source_refs" in keys, "the exemplar must show how a row adds to the edition default"
    assert "source_refs" not in keys, "a scaffolded row must not restate the edition's casilla_source_refs"
    assert "legal_refs" not in keys, "a scaffolded row must not restate the edition's orden_aplicabilidad"
    for line in proposed:
        assert _THROWAWAY_REVISION_ID not in line, f"an exemplar identifier carries the edition year: {line}"


def test_the_scaffold_does_not_create_the_hand_authored_export_directory(tmp_path: Path) -> None:
    """Generation is the supported path, so transcription is not the default.

    A scaffolded `export_layouts/` directory made hand-transcribing the official
    record design the path of least resistance, and the authored export surface
    grew back one new revision at a time. The directory is not forbidden -- a
    revision may still declare it as an exception -- but the scaffold no longer
    proposes it, so choosing it is a decision someone records rather than the
    default nobody notices.
    """
    manager = NewModeloScaffoldManager(registry_modelos_root=tmp_path)
    manager.scaffold(_THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID, title="Throwaway test modelo")

    revision_root = tmp_path / _THROWAWAY_MODELO_ID / "revisions" / _THROWAWAY_REVISION_ID

    assert not (revision_root / "export_layouts").exists()
    assert (revision_root / "casillas").is_dir(), "the scaffold still writes the sections it owns"
