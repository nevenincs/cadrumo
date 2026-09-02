"""Detector teeth for disposable object-name rehearsal and receipts."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from cadrumo.core.hashing import canonical_json_bytes

from ...audit.object_names import ObjectNameAuditResult, scan, to_json
from .. import object_name_graph as graph_module
from .. import object_name_rehearsal as rehearsal_module
from ..object_name_graph import build_manifest_components
from ..object_name_manifest import ObjectNameRenameManifest, object_name_manifest_digest
from ..object_name_rehearsal import ObjectNameRehearsalError, rehearse_object_name_component

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(autouse=True)
def _unbind_host_worktree_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let graph discovery bind imports to each disposable test repository."""
    monkeypatch.delitem(sys.modules, "cadrumo", raising=False)
    monkeypatch.delitem(sys.modules, "dev", raising=False)
    monkeypatch.setattr(graph_module, "_FIRST_PARTY_ROOTS", ("example",))


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(("git", *args), cwd=repo_root, check=True, capture_output=True)  # noqa: S603,S607


def _write(repo_root: Path, relative: str, payload: bytes) -> None:
    path = repo_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _live_bytes(repo_root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(repo_root).as_posix(): path.read_bytes()
        for root in (repo_root / "src", repo_root / "dev")
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def _fixture(
    repo_root: Path,
    *,
    gate: tuple[str, ...] | None = None,
    reference_classes: tuple[str, ...] = ("definition",),
    generator_commands: tuple[tuple[str, ...], ...] = (),
) -> tuple[ObjectNameAuditResult, ObjectNameRenameManifest, Any]:
    repo_root.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init", "-q")
    _write(repo_root, "src/example/__init__.py", b"")
    _write(repo_root, "src/example/contracts.py", b"class Placeholder:\n    pass\n")
    _write(repo_root, "dev/tracked.txt", b"committed\n")
    _write(
        repo_root,
        ".gitignore",
        b".pytest_cache/\n__pycache__/\n.mypy_cache/\n.ruff_cache/\n.tox/\n.venv/\nnode_modules/\nignored.log\n",
    )
    _git(repo_root, "add", ".gitignore", "src/example/__init__.py", "src/example/contracts.py", "dev/tracked.txt")
    _write(repo_root, "src/example/contracts.py", b"class Widgets:\n    pass\n")
    _write(repo_root, "dev/tracked.txt", b"dirty tracked bytes\n")
    _write(repo_root, "dev/untracked.txt", b"untracked bytes\n")
    _write(repo_root, ".pytest_cache/ignored.bin", b"cache\n")
    _write(repo_root, "dev/__pycache__/ignored.pyc", b"cache\n")
    for directory in (".mypy_cache", ".ruff_cache", ".tox", ".venv", "node_modules"):
        _write(repo_root, f"{directory}/ignored.bin", b"cache\n")
    _write(repo_root, "ignored.log", b"ignored\n")
    inventory = scan((repo_root / "src", repo_root / "dev"), repo_root)
    declaration = next(item for item in inventory.declarations if item.name == "Widgets")
    finding = next(item for item in inventory.findings if item.name == "Widgets")
    operation = {
        "operation_id": "rename-widgets",
        "finding_id": finding.id,
        "operation_kind": "symbol-rename",
        "disposition": "lexical-singular",
        "lifecycle": "reviewed",
        "old_locator": declaration.qualified_locator,
        "old_path": declaration.path,
        "new_locator": replace(declaration, name="Widget").qualified_locator,
        "new_path": declaration.path,
        "owner": "dev-quality",
        "rationale": "Use the exact singular object name.",
        "preconditions": ({"path": declaration.path, "sha256": declaration.source_hash},),
        "expected_reference_classes": reference_classes,
        "moves": (),
        "changed_paths": (declaration.path,),
        "generator_commands": generator_commands,
        "focused_gates": (
            gate
            or (
                sys.executable,
                "-c",
                "from pathlib import Path; assert b'class Widget:' in Path('src/example/contracts.py').read_bytes()",
            ),
        ),
    }
    manifest = ObjectNameRenameManifest.model_validate(
        {
            "schema_version": 1,
            "inventory_digest": to_json(inventory)["inventory_digest"],
            "operations": (operation,),
        }
    )
    component = build_manifest_components(manifest, inventory=inventory)[0]  # ty: ignore[invalid-argument-type]
    return inventory, manifest, component


def test_rehearsal_captures_dirty_and_untracked_bytes_but_excludes_git_and_caches(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    before = _live_bytes(repo)

    receipt = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    baseline = dict(receipt.baseline_files)
    assert baseline["dev/tracked.txt"] == _digest(b"dirty tracked bytes\n")
    assert baseline["dev/untracked.txt"] == _digest(b"untracked bytes\n")
    assert not any(".git" in Path(path).parts or "__pycache__" in Path(path).parts for path in baseline)
    assert not any(".pytest_cache" in Path(path).parts or path.endswith(".pyc") for path in baseline)
    assert not any(
        set(Path(path).parts).intersection({".mypy_cache", ".ruff_cache", ".tox", ".venv", "node_modules"})
        or path == "ignored.log"
        for path in baseline
    )
    assert receipt.manifest_digest == object_name_manifest_digest(manifest)
    assert receipt.inventory_digest == manifest.inventory_digest
    assert receipt.component_id == component.component_id
    assert receipt.operation_ids == component.operation_ids
    assert receipt.changed_paths == ("src/example/contracts.py",)
    assert receipt.baseline_tree_digest == _digest(
        canonical_json_bytes({"schema_version": 1, "files": list(receipt.baseline_files)})
    )
    assert receipt.changed_path_digest == _digest(canonical_json_bytes(list(receipt.changed_paths)))
    assert receipt.input_file_digests == (("src/example/contracts.py", _digest(b"class Widgets:\n    pass\n")),)
    assert receipt.proposed_file_digests == (("src/example/contracts.py", _digest(b"class Widget:\n    pass\n")),)
    assert {name for name, _version in receipt.tool_versions} == {
        "git",
        "libcst",
        "python",
        "rehearsal",
        "runtime-environment",
        "uv",
    }
    assert all(value for _name, value in receipt.tool_versions)
    assert receipt.gate_outcomes[0].argv == manifest.operations[0].focused_gates[0]
    assert receipt.gate_outcomes[0].return_code == 0
    assert receipt.gate_outcomes[0].stdout_sha256 == _digest(b"")
    assert receipt.gate_outcomes[0].stderr_sha256 == _digest(b"")
    assert receipt.generator_outcomes == ()
    assert receipt.finding_delta.before_count == len(inventory.enforced_findings)
    assert receipt.finding_delta.after_count == len(inventory.enforced_findings) - 1
    assert receipt.finding_delta.resolved_ids == (manifest.operations[0].finding_id,)
    assert receipt.finding_delta.introduced_ids == ()
    assert receipt.finding_delta.introduced_signatures == ()
    assert receipt.receipt_id.startswith("sha256:") and receipt.receipt_id != _digest(b"")
    assert receipt.evidence_digest.startswith("sha256:") and receipt.evidence_digest != _digest(b"")
    assert receipt.source_tree_unchanged
    assert _live_bytes(repo) == before
    assert Path(receipt.rehearsal_root).is_relative_to(Path(rehearsal_module.tempfile.gettempdir()).resolve())


def test_receipt_is_deterministic_after_normalizing_root_and_output_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)

    first = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)
    second = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    assert first == second
    assert first.receipt_id == second.receipt_id
    assert first.evidence_digest == second.evidence_digest
    assert first.rehearsal_root != second.rehearsal_root


def test_failed_gate_reports_exit_and_output_digests_and_retains_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    gate = (sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)")
    inventory, manifest, component = _fixture(repo, gate=gate)
    before = _live_bytes(repo)

    with pytest.raises(ObjectNameRehearsalError) as raised:
        rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    message = str(raised.value)
    assert "return_code=7" in message
    assert f"stdout_sha256={_digest(b'out' + os.linesep.encode())}" in message
    assert f"stderr_sha256={_digest(b'err' + os.linesep.encode())}" in message
    retained = Path(message.rsplit("retained rehearsal root: ", 1)[1])
    assert retained.is_dir()
    assert _live_bytes(repo) == before


@pytest.mark.parametrize(
    "stage",
    ["copy", "inventory-scan", "transform", "materialise", "command", "temporary-paths", "tool-version"],
)
def test_post_allocation_failures_retain_root_and_live_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    before = _live_bytes(repo)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise ObjectNameRehearsalError(f"injected {stage} failure")

    target = {
        "copy": "_copy_snapshot",
        "inventory-scan": "scan",
        "transform": "plan_object_name_transformation",
        "materialise": "_materialise",
        "command": "_run_command",
        "temporary-paths": "_temporary_paths",
        "tool-version": "_tool_version",
    }[stage]
    monkeypatch.setattr(rehearsal_module, target, fail)

    with pytest.raises(ObjectNameRehearsalError, match=r"retained rehearsal root: .+") as raised:
        rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    assert Path(str(raised.value).rsplit("retained rehearsal root: ", 1)[1]).is_dir()
    assert _live_bytes(repo) == before


def test_transformation_changed_paths_must_exactly_equal_component_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    before = _live_bytes(repo)
    monkeypatch.setattr(
        rehearsal_module,
        "plan_object_name_transformation",
        lambda *_args, **_kwargs: SimpleNamespace(changed_paths=("dev/unreviewed.py",)),
    )

    with pytest.raises(ObjectNameRehearsalError, match="paths differ from the reviewed allowlist") as raised:
        rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    assert "retained rehearsal root:" in str(raised.value)
    assert _live_bytes(repo) == before


def test_post_gate_filesystem_side_effect_must_equal_allowlist(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    gate = (sys.executable, "-c", "from pathlib import Path; Path('dev/extra.py').write_text('value = 1\\n')")
    inventory, manifest, component = _fixture(repo, gate=gate)
    before = _live_bytes(repo)

    with pytest.raises(ObjectNameRehearsalError, match="materialised changed paths differ") as raised:
        rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    assert "retained rehearsal root:" in str(raised.value)
    assert _live_bytes(repo) == before


@pytest.mark.parametrize("return_code", [0, 7])
def test_live_tree_mutation_during_gate_is_refused_and_retains_root(tmp_path: Path, return_code: int) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    live_path = repo / "dev/tracked.txt"
    original = live_path.read_bytes()
    gate = (
        sys.executable,
        "-c",
        f"from pathlib import Path; Path({str(live_path)!r}).write_bytes(b'mutated'); raise SystemExit({return_code})",
    )
    operation = manifest.operations[0].model_copy(update={"focused_gates": (gate,)})
    mutated_manifest = manifest.model_copy(update={"operations": (operation,)})

    try:
        with pytest.raises(ObjectNameRehearsalError, match=r"source tree changed.*retained rehearsal root") as raised:
            rehearse_object_name_component(
                mutated_manifest,
                inventory=inventory,
                component=component,
                repo_root=repo,
            )
        assert Path(str(raised.value).rsplit("retained rehearsal root: ", 1)[1]).is_dir()
    finally:
        live_path.write_bytes(original)


def test_unsafe_system_temp_and_escaped_allocation_are_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    monkeypatch.setattr(rehearsal_module.tempfile, "gettempdir", lambda: str(repo / "dev"))
    with pytest.raises(ObjectNameRehearsalError, match="system temporary root is unsafe"):
        rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    safe_temp = tmp_path / "safe-temp"
    safe_temp.mkdir()
    escaped = tmp_path / "escaped"
    escaped.mkdir()
    monkeypatch.setattr(rehearsal_module.tempfile, "gettempdir", lambda: str(safe_temp))
    monkeypatch.setattr(rehearsal_module.tempfile, "mkdtemp", lambda **_kwargs: str(escaped))
    with pytest.raises(
        ObjectNameRehearsalError, match=r"allocated rehearsal parent is unsafe.*retained rehearsal root"
    ):
        rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)


def test_link_like_system_temp_root_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    real_temp = tmp_path / "real-temp"
    real_temp.mkdir()
    linked_temp = tmp_path / "linked-temp"
    try:
        linked_temp.symlink_to(real_temp, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    monkeypatch.setattr(rehearsal_module.tempfile, "gettempdir", lambda: str(linked_temp))

    with pytest.raises(ObjectNameRehearsalError, match="system temporary root is unsafe"):
        rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)


def test_rehearsal_writes_and_replaces_only_below_allocated_temporary_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    original_write_bytes = Path.write_bytes
    original_mkdir = Path.mkdir
    original_unlink = Path.unlink
    original_replace = os.replace
    original_copyfile = shutil.copyfile

    def guarded_write(path: Path, payload: bytes) -> int:
        assert not path.resolve().is_relative_to(repo.resolve())
        return original_write_bytes(path, payload)

    def guarded_replace(source: Any, target: Any) -> None:
        assert not Path(target).resolve().is_relative_to(repo.resolve())
        original_replace(source, target)

    def guarded_mkdir(path: Path, *args: Any, **kwargs: Any) -> None:
        assert not path.resolve().is_relative_to(repo.resolve())
        original_mkdir(path, *args, **kwargs)

    def guarded_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        assert not path.resolve().is_relative_to(repo.resolve())
        original_unlink(path, *args, **kwargs)

    def guarded_copyfile(source: Any, target: Any, **kwargs: Any) -> Any:
        assert not Path(target).resolve().is_relative_to(repo.resolve())
        return original_copyfile(source, target, **kwargs)

    monkeypatch.setattr(Path, "write_bytes", guarded_write)
    monkeypatch.setattr(Path, "mkdir", guarded_mkdir)
    monkeypatch.setattr(Path, "unlink", guarded_unlink)
    monkeypatch.setattr(os, "replace", guarded_replace)
    monkeypatch.setattr(shutil, "copyfile", guarded_copyfile)

    receipt = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    assert receipt.source_tree_unchanged


def test_empty_snapshot_and_link_input_are_refused(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    _git(empty, "init", "-q")
    with pytest.raises(ObjectNameRehearsalError, match="inventory is empty"):
        rehearsal_module._git_snapshot_paths(empty)

    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    target = repo / "outside.py"
    target.write_bytes(b"value = 1\n")
    link = repo / "dev/link.py"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    _git(repo, "add", "dev/link.py")

    with pytest.raises(ObjectNameRehearsalError, match="link-like component"):
        rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)


@pytest.mark.parametrize(
    ("reference_class", "message"),
    [
        ("dynamic-target", r"cannot reconstruct.*reference classes differ"),
        ("generated-artifact", r"bounded transformation refused.*unsupported reference classes"),
    ],
)
def test_generated_or_dynamic_reference_manifest_is_refused_before_rehearsal(
    tmp_path: Path, reference_class: str, message: str
) -> None:
    repo = tmp_path / "repo"
    command = ((sys.executable, "-c", "raise SystemExit(0)"),)
    inventory, manifest, component = _fixture(repo)
    operation = manifest.operations[0].model_copy(
        update={
            "expected_reference_classes": ("definition", reference_class),
            "generator_commands": command if reference_class == "generated-artifact" else (),
        }
    )
    unsupported = manifest.model_copy(update={"operations": (operation,)})

    with pytest.raises(ObjectNameRehearsalError, match=message):
        rehearse_object_name_component(unsupported, inventory=inventory, component=component, repo_root=repo)
