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
from ..object_name_graph import HardEdge, ReferenceKind, build_manifest_components
from ..object_name_manifest import ObjectNameGateCommand, ObjectNameRenameManifest, object_name_manifest_digest
from ..object_name_rehearsal import ObjectNameRehearsalError, rehearse_object_name_component

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TEST_MANDATORY_GATES = tuple(
    ObjectNameGateCommand(family=family, argv=(sys.executable, "-c", "pass"))
    for family in ("parsing-import", "architecture", "semantic-overlap", "clone", "type-lint")
)


def test_snapshot_records_a_file_deleted_between_stat_and_hash_as_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "dev/concurrent_helper.py"
    source.parent.mkdir()
    source.write_text("def concurrent_helper() -> None:\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(
        rehearsal_module,
        "sha256_file",
        lambda _path: (_ for _ in ()).throw(FileNotFoundError(source)),
    )

    assert rehearsal_module._snapshot(tmp_path, ("dev/concurrent_helper.py",)) == (("dev/concurrent_helper.py", None),)


@pytest.fixture(autouse=True)
def _unbind_host_worktree_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let graph discovery bind imports to each disposable test repository."""
    monkeypatch.delitem(sys.modules, "cadrumo", raising=False)
    monkeypatch.delitem(sys.modules, "dev", raising=False)
    monkeypatch.setattr(graph_module, "_FIRST_PARTY_ROOTS", ("example",))
    monkeypatch.setattr(rehearsal_module, "MANDATORY_OBJECT_NAME_GATES", _TEST_MANDATORY_GATES)


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
    _write(repo_root, "dev/deleted.txt", b"tracked then deleted\n")
    _write(
        repo_root,
        ".gitignore",
        b".pytest_cache/\n__pycache__/\n.mypy_cache/\n.ruff_cache/\n.tox/\n.venv/\nnode_modules/\nignored.log\n",
    )
    _git(
        repo_root,
        "add",
        ".gitignore",
        "src/example/__init__.py",
        "src/example/contracts.py",
        "dev/tracked.txt",
        "dev/deleted.txt",
    )
    _write(repo_root, "src/example/contracts.py", b"class Widgets:\n    pass\n")
    _write(repo_root, "dev/tracked.txt", b"dirty tracked bytes\n")
    _write(repo_root, "dev/untracked.txt", b"untracked bytes\n")
    (repo_root / "dev/deleted.txt").unlink()
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


def test_rehearsal_receipt_binds_only_declared_component_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    before = _live_bytes(repo)
    original_components = rehearsal_module.canonical_object_name_component_set
    canonical_roots: list[Path] = []

    def observe_canonical_root(*args: Any, repo_root: Path, **kwargs: Any) -> Any:
        canonical_roots.append(repo_root)
        return original_components(*args, repo_root=repo_root, **kwargs)

    monkeypatch.setattr(rehearsal_module, "canonical_object_name_component_set", observe_canonical_root)

    receipt = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    baseline = dict(receipt.baseline_files)
    assert baseline == {"src/example/contracts.py": _digest(before["src/example/contracts.py"])}
    assert receipt.manifest_digest == object_name_manifest_digest(manifest)
    assert receipt.inventory_digest == manifest.inventory_digest
    assert receipt.component_id == component.component_id
    assert receipt.operation_ids == component.operation_ids
    assert receipt.changed_paths == ("src/example/contracts.py",)
    assert canonical_roots == [Path(receipt.rehearsal_root)]
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
    assert {outcome.family for outcome in receipt.gate_outcomes} == {
        "parsing-import",
        "architecture",
        "semantic-overlap",
        "clone",
        "type-lint",
        "focused",
    }
    focused_outcome = next(outcome for outcome in receipt.gate_outcomes if outcome.family == "focused")
    assert focused_outcome.argv == manifest.operations[0].focused_gates[0]
    assert focused_outcome.return_code == 0
    assert focused_outcome.stdout_sha256 == _digest(b"")
    assert focused_outcome.stderr_sha256 == _digest(b"")
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
    retained_root = Path(receipt.rehearsal_root)
    assert retained_root.is_relative_to(Path(rehearsal_module.tempfile.gettempdir()).resolve())
    assert (retained_root / "dev/tracked.txt").read_bytes() == b"dirty tracked bytes\n"
    assert (retained_root / "dev/untracked.txt").read_bytes() == b"untracked bytes\n"
    assert not (retained_root / "dev/deleted.txt").exists()
    assert (retained_root / "src/example/contracts.py").read_bytes() == b"class Widget:\n    pass\n"


def test_incremental_allowed_path_inventory_matches_full_rescan(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    before, _manifest, _component = _fixture(repo)
    (repo / "src/example/contracts.py").write_bytes(b"class Widget:\n    pass\n")

    incremental = rehearsal_module._inventory_after_allowed_changes(
        before,
        repo_root=repo,
        changed_paths=("src/example/contracts.py",),
    )
    full = scan((repo / "src", repo / "dev"), repo)

    assert incremental == full


def test_receipt_is_deterministic_after_normalizing_root_and_output_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)

    first = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)
    second = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    assert first == second
    assert first.receipt_id == second.receipt_id
    assert first.evidence_digest == second.evidence_digest
    assert first.rehearsal_root != second.rehearsal_root


def test_receipt_identity_binds_stable_fields_but_only_evidence_binds_command_output(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    receipt = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    def recompute(candidate: Any) -> tuple[str, str]:
        provisional = replace(candidate, receipt_id="", evidence_digest="")
        receipt_id = _digest(
            canonical_json_bytes(rehearsal_module._receipt_payload(provisional, include_output_evidence=False))
        )
        stable = replace(provisional, receipt_id=receipt_id)
        evidence_digest = _digest(
            canonical_json_bytes(rehearsal_module._receipt_payload(stable, include_output_evidence=True))
        )
        return receipt_id, evidence_digest

    assert recompute(receipt) == (receipt.receipt_id, receipt.evidence_digest)
    stable_mutations = (
        replace(receipt, manifest_digest=_digest(b"other manifest")),
        replace(receipt, inventory_digest=_digest(b"other inventory")),
        replace(receipt, component_id=_digest(b"other component")),
        replace(receipt, operation_ids=("other-operation",)),
        replace(receipt, baseline_tree_digest=_digest(b"other tree")),
        replace(receipt, input_file_digests=(("src/example/contracts.py", _digest(b"other input")),)),
        replace(receipt, proposed_file_digests=(("src/example/contracts.py", _digest(b"other output")),)),
        replace(receipt, changed_paths=("src/example/other.py",)),
        replace(receipt, changed_path_digest=_digest(b"other allowlist")),
        replace(receipt, finding_delta=replace(receipt.finding_delta, after_count=99)),
        replace(receipt, tool_versions=(*receipt.tool_versions, ("probe", "1"))),
        replace(
            receipt,
            gate_outcomes=(
                replace(receipt.gate_outcomes[0], argv=(sys.executable, "--version")),
                *receipt.gate_outcomes[1:],
            ),
        ),
        replace(receipt, source_tree_unchanged=False),
    )
    assert all(recompute(candidate)[0] != receipt.receipt_id for candidate in stable_mutations)

    volatile = replace(
        receipt,
        gate_outcomes=(
            replace(
                receipt.gate_outcomes[0],
                stdout_sha256=_digest(b"volatile output"),
                stdout_bytes=len(b"volatile output"),
            ),
            *receipt.gate_outcomes[1:],
        ),
    )
    volatile_receipt_id, volatile_evidence_digest = recompute(volatile)
    assert volatile_receipt_id == receipt.receipt_id
    assert volatile_evidence_digest != receipt.evidence_digest


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


def test_gate_runs_in_isolated_copy_with_bound_runtime_environment(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    gate = (
        sys.executable,
        "-c",
        "import os, sys; from pathlib import Path; "
        "assert Path.cwd() != Path(sys.argv[1]); "
        "assert Path.cwd().name == 'repository'; "
        "assert os.environ['VIRTUAL_ENV'] == sys.prefix; "
        "assert os.environ['UV_PROJECT_ENVIRONMENT'] == sys.prefix; "
        "assert str(Path.cwd() / 'src') in os.environ['PYTHONPATH'].split(os.pathsep)",
        str(repo.resolve()),
    )
    inventory, manifest, component = _fixture(repo, gate=gate)

    receipt = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    focused = next(outcome for outcome in receipt.gate_outcomes if outcome.family == "focused")
    assert focused.argv == gate
    assert focused.return_code == 0


def test_gate_argv_metacharacters_are_passed_literally_without_shell_interpretation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    sentinel = repo / "shell-interpreted.txt"
    metacharacter_argument = f"literal & echo shell > {sentinel}"
    gate = (
        sys.executable,
        "-c",
        "import sys; assert sys.argv[1] == sys.argv[2]",
        metacharacter_argument,
        metacharacter_argument,
    )
    inventory, manifest, component = _fixture(repo, gate=gate)

    receipt = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    assert next(outcome for outcome in receipt.gate_outcomes if outcome.family == "focused").argv == gate
    assert not sentinel.exists()


def test_timed_out_gate_fails_closed_and_retains_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    gate = (sys.executable, "-c", "import time; time.sleep(5)")
    inventory, manifest, component = _fixture(repo, gate=gate)
    monkeypatch.setattr(rehearsal_module, "_COMMAND_TIMEOUT_SECONDS", 0.01)

    with pytest.raises(
        ObjectNameRehearsalError, match=r"cannot execute declared command.*retained rehearsal root"
    ) as raised:
        rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    assert Path(str(raised.value).rsplit("retained rehearsal root: ", 1)[1]).is_dir()


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


def test_post_copy_byte_corruption_is_detected_by_snapshot_hash_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    original_copyfile = shutil.copyfile

    def corrupting_copyfile(source: Any, target: Any, **kwargs: Any) -> Any:
        result = original_copyfile(source, target, **kwargs)
        if Path(target).as_posix().endswith("src/example/contracts.py"):
            Path(target).write_bytes(b"corrupted after copy\n")
        return result

    monkeypatch.setattr(shutil, "copyfile", corrupting_copyfile)

    with pytest.raises(
        ObjectNameRehearsalError, match=r"temporary copy hash differs.*retained rehearsal root"
    ) as raised:
        rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)

    assert Path(str(raised.value).rsplit("retained rehearsal root: ", 1)[1]).is_dir()


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


def test_selected_component_cannot_be_replaced_by_an_otherwise_valid_component(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, _component = _fixture(repo)
    _write(repo, "src/example/reports.py", b"class Reports:\n    pass\n")
    inventory = scan((repo / "src", repo / "dev"), repo)
    report_declaration = next(item for item in inventory.declarations if item.name == "Reports")
    report_finding = next(item for item in inventory.findings if item.name == "Reports")
    report_operation = manifest.operations[0].model_copy(
        update={
            "operation_id": "rename-reports",
            "finding_id": report_finding.id,
            "old_locator": report_declaration.qualified_locator,
            "old_path": report_declaration.path,
            "new_locator": replace(report_declaration, name="Report").qualified_locator,
            "new_path": report_declaration.path,
            "preconditions": (
                manifest.operations[0]
                .preconditions[0]
                .model_copy(update={"path": report_declaration.path, "sha256": report_declaration.source_hash}),
            ),
            "changed_paths": (report_declaration.path,),
        }
    )
    manifest = manifest.model_copy(
        update={
            "inventory_digest": to_json(inventory)["inventory_digest"],
            "operations": (manifest.operations[0], report_operation),
        }
    )
    components = build_manifest_components(manifest, inventory=inventory)  # ty: ignore[invalid-argument-type]
    selected = next(item for item in components if item.operation_ids == ("rename-widgets",))
    other = next(item for item in components if item.operation_ids == ("rename-reports",))

    with pytest.raises(ObjectNameRehearsalError, match="copied repository graph differs from the reviewed component"):
        rehearse_object_name_component(
            manifest,
            inventory=inventory,
            component=replace(selected, affected_paths=other.affected_paths),
            repo_root=repo,
        )

    receipt = rehearse_object_name_component(manifest, inventory=inventory, component=selected, repo_root=repo)
    assert receipt.operation_ids == ("rename-widgets",)
    assert receipt.changed_paths == ("src/example/contracts.py",)
    assert (Path(receipt.rehearsal_root) / "src/example/reports.py").read_bytes() == b"class Reports:\n    pass\n"


def test_shared_hard_edge_makes_two_operations_indivisible(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, _component = _fixture(repo)
    _write(repo, "src/example/reports.py", b"class Reports:\n    pass\n")
    consumer_path = "src/example/consumer.py"
    _write(
        repo,
        consumer_path,
        b"from example.contracts import Widgets\nfrom example.reports import Reports\n",
    )
    inventory = scan((repo / "src", repo / "dev"), repo)
    widget_declaration = next(item for item in inventory.declarations if item.name == "Widgets")
    report_declaration = next(item for item in inventory.declarations if item.name == "Reports")
    report_finding = next(item for item in inventory.findings if item.name == "Reports")
    consumer_precondition = (
        manifest.operations[0]
        .preconditions[0]
        .model_copy(update={"path": consumer_path, "sha256": _digest((repo / consumer_path).read_bytes())})
    )
    widget_operation = manifest.operations[0].model_copy(
        update={
            "expected_reference_classes": ("definition", "shared-consumer", "static-import"),
            "changed_paths": (widget_declaration.path, consumer_path),
            "preconditions": (*manifest.operations[0].preconditions, consumer_precondition),
        }
    )
    report_operation = widget_operation.model_copy(
        update={
            "operation_id": "rename-reports",
            "finding_id": report_finding.id,
            "old_locator": report_declaration.qualified_locator,
            "old_path": report_declaration.path,
            "new_locator": replace(report_declaration, name="Report").qualified_locator,
            "new_path": report_declaration.path,
            "preconditions": (
                widget_operation.preconditions[0].model_copy(
                    update={"path": report_declaration.path, "sha256": report_declaration.source_hash}
                ),
                consumer_precondition,
            ),
            "changed_paths": (report_declaration.path, consumer_path),
        }
    )
    manifest = manifest.model_copy(
        update={
            "inventory_digest": to_json(inventory)["inventory_digest"],
            "operations": (widget_operation, report_operation),
        }
    )
    shared_edges = (
        HardEdge("rename-widgets", consumer_path, ReferenceKind.SYMBOL_IMPORT),
        HardEdge("rename-reports", consumer_path, ReferenceKind.SYMBOL_IMPORT),
    )
    component = build_manifest_components(manifest, inventory=inventory, hard_edges=shared_edges)[0]  # ty: ignore[invalid-argument-type]
    assert component.operation_ids == ("rename-reports", "rename-widgets")
    assert component.affected_paths.count(consumer_path) == 1

    partial = replace(component, operation_ids=("rename-widgets",))
    with pytest.raises(ObjectNameRehearsalError, match="copied repository graph differs from the reviewed component"):
        rehearse_object_name_component(manifest, inventory=inventory, component=partial, repo_root=repo)


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
    live_path = repo / "src/example/contracts.py"
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


def test_unrelated_live_tree_mutation_does_not_stale_selected_component(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    live_path = repo / "dev/tracked.txt"
    original = live_path.read_bytes()
    gate = (
        sys.executable,
        "-c",
        f"from pathlib import Path; Path({str(live_path)!r}).write_bytes(b'unrelated peer edit')",
    )
    operation = manifest.operations[0].model_copy(update={"focused_gates": (gate,)})
    mutated_manifest = manifest.model_copy(update={"operations": (operation,)})

    try:
        receipt = rehearse_object_name_component(
            mutated_manifest,
            inventory=inventory,
            component=component,
            repo_root=repo,
        )
        assert receipt.source_tree_unchanged
    finally:
        live_path.write_bytes(original)


def test_copy_race_that_adds_selected_reference_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    consumer = repo / "src/example/consumer.py"
    consumer.write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "src/example/consumer.py")
    original_copy = rehearsal_module._copy_snapshot

    def copy_then_add_reference(*args: Any, **kwargs: Any) -> None:
        original_copy(*args, **kwargs)
        target_root = args[1]
        (target_root / "src/example/consumer.py").write_text(
            "from example.contracts import Widgets\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(rehearsal_module, "_copy_snapshot", copy_then_add_reference)

    with pytest.raises(ObjectNameRehearsalError, match=r"hard reference .* is outside the changed-path allowlist"):
        rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)


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


def test_dynamic_reference_manifest_is_refused_before_rehearsal(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    operation = manifest.operations[0].model_copy(
        update={"expected_reference_classes": ("definition", "dynamic-target")}
    )
    unsupported = manifest.model_copy(update={"operations": (operation,)})

    with pytest.raises(ObjectNameRehearsalError, match=r"cannot reconstruct.*reference classes differ"):
        rehearse_object_name_component(unsupported, inventory=inventory, component=component, repo_root=repo)


def test_generated_owner_runs_and_forged_generated_edge_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    generated_path = "dev/generated.txt"
    command = (
        (
            sys.executable,
            "-c",
            "from pathlib import Path; Path('dev/generated.txt').write_bytes(b'generated Widget\\n')",
        ),
    )
    inventory, manifest, _component = _fixture(repo)
    _write(repo, generated_path, b"generated Widgets\n")
    inventory = scan((repo / "src", repo / "dev"), repo)
    operation = manifest.operations[0].model_copy(
        update={
            "expected_reference_classes": ("definition", "generated-artifact"),
            "changed_paths": ("src/example/contracts.py", generated_path),
            "generator_commands": command,
            "preconditions": (
                *manifest.operations[0].preconditions,
                manifest.operations[0]
                .preconditions[0]
                .model_copy(update={"path": generated_path, "sha256": _digest(b"generated Widgets\n")}),
            ),
        }
    )
    manifest = manifest.model_copy(
        update={"inventory_digest": to_json(inventory)["inventory_digest"], "operations": (operation,)}
    )
    owner = canonical_json_bytes(command).decode("utf-8")
    edge = HardEdge("rename-widgets", generated_path, ReferenceKind.GENERATED_ARTIFACT, generator_owner=owner)
    component = build_manifest_components(manifest, inventory=inventory, hard_edges=(edge,))[0]  # ty: ignore[invalid-argument-type]
    forged_edge = replace(edge, generator_owner='[["forged-generator"]]')
    forged = build_manifest_components(manifest, inventory=inventory, hard_edges=(forged_edge,))[0]  # ty: ignore[invalid-argument-type]

    with pytest.raises(ObjectNameRehearsalError, match="copied repository graph differs from the reviewed component"):
        rehearse_object_name_component(manifest, inventory=inventory, component=forged, repo_root=repo)

    receipt = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)
    assert receipt.changed_paths == (generated_path, "src/example/contracts.py")
    assert receipt.generator_outcomes[0].argv == command[0]
    assert receipt.generator_outcomes[0].return_code == 0
    assert (Path(receipt.rehearsal_root) / generated_path).read_bytes() == b"generated Widget\n"
