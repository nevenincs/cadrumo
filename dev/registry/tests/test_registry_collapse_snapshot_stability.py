"""Detector teeth for collapse verifier snapshot input stability."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema import SupportedFilingYearsCatalogue

from .. import registry_collapse_run as collapse_run
from ..registry_collapse_fingerprints import fingerprint_optional_tree, fingerprint_tree
from ..registry_collapse_inputs import _source_dependency_paths
from ..registry_collapse_models import CheckStatus

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _prepare_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    registry_root = tmp_path / "registry" / "aeat"
    registry_root.mkdir(parents=True)
    (registry_root / "registry.toml").write_text("value = 'A'\n", encoding="utf-8")
    source_root = tmp_path / "data"
    source_file = source_root / "legal" / "source.toml"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("value = 'A'\n", encoding="utf-8")
    monkeypatch.setattr(collapse_run, "_source_dependency_paths", lambda _root: (source_file,))
    monkeypatch.setattr(collapse_run, "_tool_fingerprints", lambda _root: ())
    monkeypatch.setattr(collapse_run, "_selected_sources", lambda _root, _modelos: ((), 0))
    support = SupportedFilingYearsCatalogue(floor=2024, horizon=2025, hard_ceiling=2025)
    monkeypatch.setattr(collapse_run, "_run_support", lambda _root: (support, 2025))
    return registry_root, source_root, source_file, tmp_path / "publication"


def _prepare(
    tmp_path: Path,
    registry_root: Path,
    source_root: Path,
    publication_root: Path,
) -> collapse_run._RunContext:
    return collapse_run._prepare_run_context(
        registry_root,
        source_root,
        tmp_path / "verification-work",
        publication_root,
        (),
    )


def test_unchanged_copy_matches_all_captured_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_root, source_root, _source_file, publication_root = _prepare_fixture(monkeypatch, tmp_path)
    context = _prepare(tmp_path, registry_root, source_root, publication_root)

    assert context.live_registry_before == fingerprint_tree(context.snapshot_registry)
    assert context.live_registry_before == fingerprint_tree(context.registry_candidate)
    assert context.source_dependencies_before == fingerprint_optional_tree(context.snapshot_source_root)
    assert context.live_registry_before == fingerprint_tree(registry_root)
    assert context.source_dependencies_before == fingerprint_optional_tree(source_root)


def test_all_live_input_manifests_are_captured_before_first_copy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_root, source_root, _source_file, publication_root = _prepare_fixture(monkeypatch, tmp_path)
    events: list[str] = []
    original_fingerprint_tree = collapse_run.fingerprint_tree
    original_fingerprint_paths = collapse_run.fingerprint_paths
    original_fingerprint_optional_tree = collapse_run.fingerprint_optional_tree
    original_copy = collapse_run._copy_registry_snapshots

    def tracked_tree(path: Path) -> tuple[collapse_run.FingerprintEntry, ...]:
        if path == registry_root:
            events.append("registry")
        return original_fingerprint_tree(path)

    def tracked_tools(_root: Path) -> tuple[collapse_run.FingerprintEntry, ...]:
        events.append("tools")
        return ()

    def tracked_paths(paths: tuple[Path, ...], *, relative_to: Path) -> tuple[collapse_run.FingerprintEntry, ...]:
        if relative_to == source_root:
            events.append("dependencies")
        return original_fingerprint_paths(paths, relative_to=relative_to)

    def tracked_optional(path: Path) -> tuple[collapse_run.FingerprintEntry, ...]:
        if path == publication_root:
            events.append("publication")
        return original_fingerprint_optional_tree(path)

    def tracked_copy(source: Path, snapshot: Path, candidate: Path) -> None:
        assert events == ["registry", "tools", "dependencies", "publication"]
        original_copy(source, snapshot, candidate)

    monkeypatch.setattr(collapse_run, "fingerprint_tree", tracked_tree)
    monkeypatch.setattr(collapse_run, "_tool_fingerprints", tracked_tools)
    monkeypatch.setattr(collapse_run, "fingerprint_paths", tracked_paths)
    monkeypatch.setattr(collapse_run, "fingerprint_optional_tree", tracked_optional)
    monkeypatch.setattr(collapse_run, "_copy_registry_snapshots", tracked_copy)

    _prepare(tmp_path, registry_root, source_root, publication_root)
    assert events[:4] == ["registry", "tools", "dependencies", "publication"]


@pytest.mark.parametrize("restore_live", [False, True])
def test_registry_change_during_copy_refuses_even_if_live_restored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, restore_live: bool
) -> None:
    registry_root, source_root, _source_file, publication_root = _prepare_fixture(monkeypatch, tmp_path)
    registry_file = registry_root / "registry.toml"
    original_copy = collapse_run._copy_registry_snapshots

    def torn_copy(source: Path, snapshot: Path, candidate: Path) -> None:
        registry_file.write_text("value = 'B'\n", encoding="utf-8")
        original_copy(source, snapshot, candidate)
        if restore_live:
            registry_file.write_text("value = 'A'\n", encoding="utf-8")

    monkeypatch.setattr(collapse_run, "_copy_registry_snapshots", torn_copy)

    with pytest.raises(RuntimeError, match="registry source snapshot differs"):
        _prepare(tmp_path, registry_root, source_root, publication_root)
    assert registry_file.read_text(encoding="utf-8") == ("value = 'A'\n" if restore_live else "value = 'B'\n")


def test_source_dependency_change_and_restore_during_copy_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_root, source_root, source_file, publication_root = _prepare_fixture(monkeypatch, tmp_path)
    original_copy = collapse_run._copy_source_dependencies

    def torn_copy(paths: tuple[Path, ...], *, source_root: Path, destination: Path) -> None:
        source_file.write_text("value = 'B'\n", encoding="utf-8")
        original_copy(paths, source_root=source_root, destination=destination)
        source_file.write_text("value = 'A'\n", encoding="utf-8")

    monkeypatch.setattr(collapse_run, "_copy_source_dependencies", torn_copy)

    with pytest.raises(RuntimeError, match="source dependency snapshot differs"):
        _prepare(tmp_path, registry_root, source_root, publication_root)
    assert source_file.read_text(encoding="utf-8") == "value = 'A'\n"


def test_candidate_copy_corruption_refuses_before_verification(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_root, source_root, _source_file, publication_root = _prepare_fixture(monkeypatch, tmp_path)
    original_copy = collapse_run._copy_registry_snapshots

    def torn_copy(source: Path, snapshot: Path, candidate: Path) -> None:
        original_copy(source, snapshot, candidate)
        (candidate / "registry.toml").write_text("value = 'B'\n", encoding="utf-8")

    monkeypatch.setattr(collapse_run, "_copy_registry_snapshots", torn_copy)

    with pytest.raises(RuntimeError, match="registry candidate snapshot differs"):
        _prepare(tmp_path, registry_root, source_root, publication_root)


@pytest.mark.parametrize("family", ["corpus", "manual_corpus_text"])
def test_new_source_evidence_file_changes_final_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, family: str
) -> None:
    registry_root, source_root, _source_file, publication_root = _prepare_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(collapse_run, "_source_dependency_paths", _source_dependency_paths)
    evidence_root = source_root / family
    evidence_root.mkdir()
    (evidence_root / "base.txt").write_text("base\n", encoding="utf-8")
    context = _prepare(tmp_path, registry_root, source_root, publication_root)

    registry_after, tools_after, dependencies_after, _published_after = collapse_run._fingerprint_run_inputs(context)
    assert dependencies_after == context.source_dependencies_before
    assert collapse_run._inputs_stable(context, registry_after, tools_after, dependencies_after)

    (evidence_root / "added.txt").write_text("added\n", encoding="utf-8")
    registry_after, tools_after, dependencies_after, _published_after = collapse_run._fingerprint_run_inputs(context)
    assert f"{family}/added.txt" in {entry.path for entry in dependencies_after}
    assert not collapse_run._inputs_stable(context, registry_after, tools_after, dependencies_after)


@pytest.mark.parametrize("change", ["same_size_mutation", "removed"])
def test_changed_or_removed_source_evidence_changes_final_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, change: str
) -> None:
    registry_root, source_root, _source_file, publication_root = _prepare_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(collapse_run, "_source_dependency_paths", _source_dependency_paths)
    evidence_root = source_root / "manual_corpus_text"
    evidence_root.mkdir()
    existing = evidence_root / "base.txt"
    existing.write_text("A\n", encoding="utf-8")
    context = _prepare(tmp_path, registry_root, source_root, publication_root)

    if change == "removed":
        existing.unlink()
    else:
        existing.write_text("B\n", encoding="utf-8")
    registry_after, tools_after, dependencies_after, _published_after = collapse_run._fingerprint_run_inputs(context)

    assert dependencies_after != context.source_dependencies_before
    assert not collapse_run._inputs_stable(context, registry_after, tools_after, dependencies_after)


def test_published_authority_change_refuses_complete_rollout_with_stable_source_inputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry_root, source_root, _source_file, publication_root = _prepare_fixture(monkeypatch, tmp_path)
    publication_root.mkdir()
    publication_file = publication_root / "authority.current.json"
    publication_file.write_text('{"generation":"A"}\n', encoding="utf-8")
    context = _prepare(tmp_path, registry_root, source_root, publication_root)
    authority = {"publication_readiness": CheckStatus.PASSED}

    registry_after, tools_after, dependencies_after, published_after = collapse_run._fingerprint_run_inputs(context)
    inputs_stable = collapse_run._inputs_stable(context, registry_after, tools_after, dependencies_after)
    no_live_mutation = collapse_run._no_live_mutation(context, registry_after, published_after)
    assert inputs_stable
    assert no_live_mutation
    stable = collapse_run._run_summary(context, (), authority, inputs_stable, no_live_mutation)
    assert stable["complete"] is True
    assert stable["registry_rollout"] == "complete"

    publication_file.write_text('{"generation":"B"}\n', encoding="utf-8")
    registry_after, tools_after, dependencies_after, published_after = collapse_run._fingerprint_run_inputs(context)
    inputs_stable = collapse_run._inputs_stable(context, registry_after, tools_after, dependencies_after)
    no_live_mutation = collapse_run._no_live_mutation(context, registry_after, published_after)
    assert inputs_stable
    assert not no_live_mutation
    changed = collapse_run._run_summary(context, (), authority, inputs_stable, no_live_mutation)
    assert changed["no_live_mutation"] is False
    assert changed["complete"] is False
    assert changed["registry_rollout"] == "incomplete"
