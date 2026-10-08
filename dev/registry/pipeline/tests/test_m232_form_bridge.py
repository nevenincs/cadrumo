"""Exact M232 source and separate form-owner cutover refusals."""

from __future__ import annotations

import os
import re
import shutil
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import override

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_form_layouts import FormLayoutSeedSource

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_registry_tree
from ...form_layout.generator import generate_revision_layout
from ...form_layout.serialization import render_form_layout_toml
from .. import cli, generated_form_bridge
from ..generated_form_bridge import GeneratedFormBridge, prepare_generated_form_bridge, registry_evidence_content_digest
from ..historical_static_repair import validated_historical_repair_source
from ..tree_publication_contracts import GeneratedExportPublicationJournal, GeneratedExportTransactionPaths
from ..tree_publication_journal import write_generated_export_publication_journal

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_historical_repair_refuses_another_target_or_old_manifest() -> None:
    for changed in ("modelo", "source", "year", "period", "manifest"):
        with pytest.raises(RegistryValidationError, match="exact reviewed M232/2016"):
            validated_historical_repair_source(
                modelo="233" if changed == "modelo" else "232",
                revision="2016-2017",
                source_ref="aeat-dr-232-2018" if changed == "source" else "aeat-dr-232-2016",
                filing_year=2018 if changed == "year" else 2016,
                period="1T" if changed == "period" else "0A",
                expected_manifest_sha256=(
                    "0" * 64
                    if changed == "manifest"
                    else "f4e1bb800af4c511c93e0d1df74520b70cc0ee986338b57f31c46c619582d6fa"
                ),
            )


def test_bridge_refuses_unreviewed_old_manifest_before_any_file_access(tmp_path: Path) -> None:
    with pytest.raises(RegistryValidationError, match="exact reviewed source and old target"):
        prepare_generated_form_bridge(
            registry_root=tmp_path / "absent-registry",
            candidate_root=tmp_path / "absent-candidate",
            modelo="232",
            revision="2016-2017",
            source_ref="aeat-dr-232-2016",
            source_sha256="fb6802dcf8746e69331b67873cb2e5cae90c3343c69b4f4d430aecde3c56b6ad",
            expected_manifest_sha256="0" * 64,
        )


def test_detached_candidate_form_reproduces_generator_without_the_live_fragment_name(tmp_path: Path) -> None:
    """An isolated generated companion reproduces under the detached edition's filename."""
    revision_id = "2018-y-siguientes"
    source_root = bundled_path()
    old_manifest = (
        source_root
        / "registry"
        / "aeat"
        / "modelos"
        / "232"
        / "revisions"
        / revision_id
        / "export"
        / "_generation.provenance.json"
    )
    prepared = cli.prepare_generated_tree_invocation(
        cli.GeneratedTreeInvocation(
            "232", revision_id, "aeat-dr-232-2018", 2022, "0A", sha256(old_manifest.read_bytes()).hexdigest()
        ),
        tmp_path,
        authority=compiled_bundled_authority(),
    )
    form_root = prepared.candidate_root / "modelos" / "232" / "revisions" / revision_id / "form_layouts"
    fragment = next(form_root.glob("*.toml"))
    authored_bytes = fragment.read_bytes()
    cli._render_candidate(prepared)
    assert fragment.read_bytes() == authored_bytes
    modelos, catalogues = load_registry_tree(prepared.candidate_root)
    revision = next(modelo for modelo in modelos if str(modelo.id) == "232").revisions[revision_id]
    assert revision.form_layouts[0].seed_source is FormLayoutSeedSource.AUTHORED
    with pytest.raises(RegistryValidationError, match="candidate form differs from its fresh canonical generation"):
        generated_form_bridge._candidate_generated_form_bytes(prepared.candidate_root, "232", revision_id, source_root)

    # The live authored form is preserved above. This detached harness supplies
    # its own generator-owned companion to exercise generated-byte verification.
    layout = generate_revision_layout("232", revision, sources=catalogues.sources, data_root=source_root).layout
    assert layout is not None
    fragment.write_text(render_form_layout_toml(revision_id, layout), encoding="utf-8", newline="\n")
    canonical_bytes = fragment.read_bytes()
    detached_fragment = fragment.with_name("0001-complete-edition.toml")
    if fragment != detached_fragment:
        assert not detached_fragment.exists()
        fragment.rename(detached_fragment)
    fragment = detached_fragment
    assert fragment.name == "0001-complete-edition.toml"
    generated = generated_form_bridge._candidate_generated_form_bytes(
        prepared.candidate_root, "232", revision_id, source_root
    )
    assert generated == canonical_bytes
    absent_fragment = tmp_path / "absent-form.toml"
    fragment.rename(absent_fragment)
    with pytest.raises(RegistryValidationError, match="no unique generated form fragment"):
        generated_form_bridge._candidate_generated_form_bytes(prepared.candidate_root, "232", revision_id, source_root)
    absent_fragment.rename(fragment)
    fragment.rename(form_root / "unreviewed-form.toml")
    with pytest.raises(RegistryValidationError, match="no unique generated form fragment"):
        generated_form_bridge._candidate_generated_form_bytes(prepared.candidate_root, "232", revision_id, source_root)
    (form_root / "unreviewed-form.toml").rename(fragment)
    (form_root / "unexpected.txt").write_text("extra staged form content", encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="no unique generated form fragment"):
        generated_form_bridge._candidate_generated_form_bytes(prepared.candidate_root, "232", revision_id, source_root)
    (form_root / "unexpected.txt").unlink()
    original = fragment.read_text(encoding="utf-8")
    changed, count = re.subn(
        r'(?m)^(source_state_digest = ")[0-9a-f]{64}(")$',
        lambda match: match.group(1) + "0" * 64 + match.group(2),
        original,
        count=1,
    )
    assert count == 1
    fragment.write_text(changed, encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="candidate form differs from its fresh canonical generation"):
        generated_form_bridge._candidate_generated_form_bytes(prepared.candidate_root, "232", revision_id, source_root)


def test_same_size_restored_time_corpus_edit_refuses_cutover(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    profile_root = source_root / "registry" / "cadrumo"
    profile_root.mkdir(parents=True)
    binary = source_root / "official-design.xls"
    binary.write_bytes(b"AB")
    first_stat = binary.stat()

    def evidence(_root: Path, *, use_cache: bool) -> tuple[tuple[str, int, int], ...]:
        assert not use_cache
        state = binary.stat()
        return ((str(binary), state.st_size, state.st_mtime_ns),)

    monkeypatch.setattr(generated_form_bridge, "collect_source_evidence_fingerprints", evidence)
    monkeypatch.setattr(generated_form_bridge, "generated_form_interpreting_input_digest", lambda _modelo: "unchanged")
    monkeypatch.setattr(generated_form_bridge, "bundled_path", lambda: source_root)
    digest_before = registry_evidence_content_digest(source_root)
    bridge = GeneratedFormBridge(
        modelo="232",
        old_manifest_sha256=sha256(b"old manifest").hexdigest(),
        revision="2016-2017",
        source_ref="aeat-dr-232-2016",
        source_sha256="fb6802dcf8746e69331b67873cb2e5cae90c3343c69b4f4d430aecde3c56b6ad",
        old_form_sha256=sha256(b"old form").hexdigest(),
        candidate_form_sha256=sha256(b"new form").hexdigest(),
        candidate_manifest_sha256=sha256(b"new manifest").hexdigest(),
        other_files={},
        interpreting_digest="unchanged",
        evidence_content_digest=digest_before,
        profile_schema_fingerprint=generated_form_bridge.fingerprint_tree(profile_root),
    )
    binary.write_bytes(b"CD")
    os.utime(binary, ns=(first_stat.st_atime_ns, first_stat.st_mtime_ns))
    assert binary.stat().st_size == first_stat.st_size
    assert binary.stat().st_mtime_ns == first_stat.st_mtime_ns
    assert registry_evidence_content_digest(source_root) != digest_before
    with pytest.raises(RegistryValidationError, match="inputs changed after prevalidation"):
        bridge.require_export_cutover(tmp_path / "not-live")


def test_form_owner_failure_after_export_commit_reports_incomplete(tmp_path: Path) -> None:
    """The separate export journal cannot imply complete source/currentness."""
    reached_full_live = False

    def full_live() -> None:
        nonlocal reached_full_live
        reached_full_live = True

    class RefusingOwner(GeneratedFormBridge):
        @override
        def finish_with_form_owner(self, registry_root: Path, source_root: Path) -> None:
            raise RegistryValidationError("selected form owner failed after export commit")

    bridge = RefusingOwner(
        modelo="232",
        old_manifest_sha256="0" * 64,
        revision="2016-2017",
        source_ref="aeat-dr-232-2016",
        source_sha256="fb6802dcf8746e69331b67873cb2e5cae90c3343c69b4f4d430aecde3c56b6ad",
        old_form_sha256="0" * 64,
        candidate_form_sha256="1" * 64,
        candidate_manifest_sha256="2" * 64,
        other_files={},
        interpreting_digest="test",
        evidence_content_digest="test",
        profile_schema_fingerprint=(),
    )
    with pytest.raises(
        RegistryValidationError, match="source was installed but companion/currentness closure is incomplete"
    ):
        cli._finish_form_republication(
            tmp_path,
            bridge,
            final_live_validator=full_live,
        )
    assert not reached_full_live


def test_only_active_journal_bound_old_backup_is_excluded_from_cutover_census(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry_root = tmp_path / "aeat"
    revision_root = registry_root / "modelos" / "232" / "revisions" / "2016-2017"
    export_root = revision_root / "export"
    export_root.mkdir(parents=True)
    old_bytes, new_bytes = b"old manifest", b"new manifest"
    manifest = export_root / "_generation.provenance.json"
    manifest.write_bytes(old_bytes)
    form = revision_root / "form_layouts" / "0001-form-layout.toml"
    form.parent.mkdir()
    form.write_bytes(b"old form")
    source_root = tmp_path / "source"
    profile_root = source_root / "registry" / "cadrumo"
    profile_root.mkdir(parents=True)
    reviewed = (
        "aeat-dr-232-2016",
        "fb6802dcf8746e69331b67873cb2e5cae90c3343c69b4f4d430aecde3c56b6ad",
        sha256(old_bytes).hexdigest(),
        sha256(b"old form").hexdigest(),
    )
    monkeypatch.setattr(generated_form_bridge, "_REVIEWED", {("232", "2016-2017"): reviewed})
    monkeypatch.setattr(generated_form_bridge, "bundled_path", lambda: source_root)
    monkeypatch.setattr(generated_form_bridge, "generated_form_interpreting_input_digest", lambda _modelo: "same")
    monkeypatch.setattr(generated_form_bridge, "registry_evidence_content_digest", lambda _source_root: "same")
    monkeypatch.setattr(
        generated_form_bridge,
        "verify_generated_export_package",
        lambda _root: SimpleNamespace(
            modelo="232", revision_id="2016-2017", source_ref=reviewed[0], source_sha256=reviewed[1]
        ),
    )
    bridge = GeneratedFormBridge(
        modelo="232",
        old_manifest_sha256=sha256(b"old manifest").hexdigest(),
        revision="2016-2017",
        source_ref=reviewed[0],
        source_sha256=reviewed[1],
        old_form_sha256=reviewed[3],
        candidate_form_sha256=sha256(b"new form").hexdigest(),
        candidate_manifest_sha256=sha256(new_bytes).hexdigest(),
        other_files=generated_form_bridge._other_files(registry_root, "232", "2016-2017"),
        interpreting_digest="same",
        evidence_content_digest="same",
        profile_schema_fingerprint=generated_form_bridge.fingerprint_tree(profile_root),
    )
    paths = GeneratedExportTransactionPaths(target_root=registry_root, modelo="232", revision_id="2016-2017")
    backup = registry_root / f"{paths.backup_prefix}reviewed"
    shutil.copytree(export_root, backup)
    manifest.write_bytes(new_bytes)
    journal = GeneratedExportPublicationJournal(
        schema_version=1,
        state="candidate_live",
        modelo="232",
        revision_id="2016-2017",
        candidate_export=str(registry_root / f"{paths.staging_prefix}consumed"),
        backup_export=str(backup),
        candidate_manifest_sha256=bridge.candidate_manifest_sha256,
    )
    write_generated_export_publication_journal(paths.journal, journal)
    bridge.require_export_cutover(registry_root)

    rogue = registry_root / f"{paths.backup_prefix}unreviewed"
    shutil.copytree(backup, rogue)
    with pytest.raises(RegistryValidationError, match="other source"):
        bridge.require_export_cutover(registry_root)
    shutil.rmtree(rogue)
    (backup / "_generation.provenance.json").write_bytes(b"changed old package")
    with pytest.raises(RegistryValidationError, match="reviewed old manifest"):
        bridge.require_export_cutover(registry_root)
    (backup / "_generation.provenance.json").write_bytes(old_bytes)

    paths.journal.unlink()
    with pytest.raises(RegistryValidationError, match="other source"):
        bridge.require_export_cutover(registry_root)
    shutil.rmtree(backup)
    bridge.require_export_cutover(registry_root)
