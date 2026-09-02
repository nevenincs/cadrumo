"""Detector teeth for receipt-bound object-name replay transactions."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from cadrumo.core.hashing import canonical_json_bytes

from ...audit.object_names import scan, to_json
from .. import object_name_graph as graph_module
from .. import object_name_replay as replay_module
from ..object_name_graph import (
    HardEdge,
    ReferenceKind,
    build_manifest_components,
    collect_import_edges,
    operation_locators,
)
from ..object_name_manifest import ObjectNameRenameManifest
from ..object_name_rehearsal import ObjectNameRehearsalReceipt, rehearse_object_name_component
from ..object_name_replay import ObjectNameReplayError, replay_object_name_component
from .test_object_name_rehearsal import _digest, _fixture, _git, _live_bytes, _write

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(autouse=True)
def _bind_disposable_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "cadrumo", raising=False)
    monkeypatch.delitem(sys.modules, "dev", raising=False)
    monkeypatch.setattr(graph_module, "_FIRST_PARTY_ROOTS", ("example",))


def _case(tmp_path: Path) -> tuple[Path, Any, Any, Any, ObjectNameRehearsalReceipt]:
    repo = tmp_path / "repo"
    inventory, manifest, component = _fixture(repo)
    receipt = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)
    return repo, inventory, manifest, component, receipt


def _retag(receipt: ObjectNameRehearsalReceipt) -> ObjectNameRehearsalReceipt:
    identified = replace(receipt, receipt_id=replay_module._receipt_digest(receipt, evidence=False))
    return replace(identified, evidence_digest=replay_module._receipt_digest(identified, evidence=True))


def _module_case(tmp_path: Path) -> tuple[Path, Any, Any, Any, ObjectNameRehearsalReceipt]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "dev").mkdir()
    _write(repo, "src/example/__init__.py", b"")
    _write(repo, "src/example/widgets.py", b"VALUE = 1\n")
    _write(repo, "src/example/consumer.py", b"import example.widgets\n")
    _git(repo, "add", "src/example/__init__.py", "src/example/widgets.py", "src/example/consumer.py")
    inventory = scan((repo / "src", repo / "dev"), repo)
    declaration = next(item for item in inventory.declarations if item.path == "src/example/widgets.py")
    finding = next(item for item in inventory.findings if item.name == "widgets")
    target_path = "src/example/widget.py"
    operation = {
        "operation_id": "rename-widgets-module",
        "finding_id": finding.id,
        "operation_kind": "module-rename",
        "disposition": "lexical-singular",
        "lifecycle": "reviewed",
        "old_locator": declaration.qualified_locator,
        "old_path": declaration.path,
        "new_locator": replace(declaration, name="widget", path=target_path).qualified_locator,
        "new_path": target_path,
        "owner": "dev-quality",
        "rationale": "Use the singular module name.",
        "preconditions": (
            {
                "path": "src/example/consumer.py",
                "sha256": _digest((repo / "src/example/consumer.py").read_bytes()),
            },
            {"path": declaration.path, "sha256": declaration.source_hash},
        ),
        "expected_reference_classes": ("definition", "static-import"),
        "moves": ({"source": declaration.path, "target": target_path},),
        "changed_paths": ("src/example/consumer.py", target_path, declaration.path),
        "generator_commands": (),
        "focused_gates": (
            (
                sys.executable,
                "-c",
                "from pathlib import Path; assert Path('src/example/widget.py').read_bytes() == b'VALUE = 1\\n'",
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
    edges = collect_import_edges(
        operation_locators(manifest),  # ty: ignore[invalid-argument-type]
        repo_root=repo,
    )
    component = build_manifest_components(
        manifest,  # ty: ignore[invalid-argument-type]
        inventory=inventory,  # ty: ignore[invalid-argument-type]
        hard_edges=edges,
    )[0]
    receipt = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)
    return repo, inventory, manifest, component, receipt


def _generated_case(tmp_path: Path) -> tuple[Path, Any, Any, Any, ObjectNameRehearsalReceipt]:
    repo = tmp_path / "repo"
    inventory, manifest, _component = _fixture(repo)
    generated_path = "dev/generated.txt"
    generated_before = b"generated Widgets\n"
    _write(repo, generated_path, generated_before)
    inventory = scan((repo / "src", repo / "dev"), repo)
    command = (
        (
            sys.executable,
            "-c",
            "from pathlib import Path; Path('dev/generated.txt').write_bytes(b'generated Widget\\n')",
        ),
    )
    operation = manifest.operations[0].model_copy(
        update={
            "expected_reference_classes": ("definition", "generated-artifact"),
            "changed_paths": ("src/example/contracts.py", generated_path),
            "generator_commands": command,
            "preconditions": (
                *manifest.operations[0].preconditions,
                manifest.operations[0]
                .preconditions[0]
                .model_copy(update={"path": generated_path, "sha256": _digest(generated_before)}),
            ),
        }
    )
    manifest = manifest.model_copy(
        update={"inventory_digest": to_json(inventory)["inventory_digest"], "operations": (operation,)}
    )
    edge = HardEdge(
        "rename-widgets",
        generated_path,
        ReferenceKind.GENERATED_ARTIFACT,
        generator_owner=canonical_json_bytes(command).decode("utf-8"),
    )
    component = build_manifest_components(
        manifest,  # ty: ignore[invalid-argument-type]
        inventory=inventory,  # ty: ignore[invalid-argument-type]
        hard_edges=(edge,),
    )[0]
    receipt = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=repo)
    return repo, inventory, manifest, component, receipt


def test_successful_symbol_replay_applies_exact_receipt_and_preserves_unrelated_bytes(tmp_path: Path) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    unrelated = (repo / "dev/tracked.txt").read_bytes()

    result = replay_object_name_component(
        manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
    )

    assert result.receipt_id == receipt.receipt_id
    assert result.changed_paths == receipt.changed_paths
    assert (repo / "src/example/contracts.py").read_bytes() == b"class Widget:\n    pass\n"
    assert (repo / "dev/tracked.txt").read_bytes() == unrelated
    assert result.gate_outcomes == receipt.gate_outcomes
    assert not (
        repo.parent / f".{repo.name}.object-name-transaction-{receipt.receipt_id.removeprefix('sha256:')}"
    ).exists()


def test_successful_symbol_replay_tolerates_unrelated_post_receipt_bytes(tmp_path: Path) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    unrelated = repo / "dev/untracked.txt"
    unrelated.write_bytes(b"concurrent unrelated bytes\n")

    replay_object_name_component(
        manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
    )

    assert unrelated.read_bytes() == b"concurrent unrelated bytes\n"
    assert (repo / "src/example/contracts.py").read_bytes() == b"class Widget:\n    pass\n"


def test_successful_generator_backed_replay_applies_and_reports_exact_owner_output(tmp_path: Path) -> None:
    repo, inventory, manifest, component, receipt = _generated_case(tmp_path)

    result = replay_object_name_component(
        manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
    )

    assert result.generator_outcomes == receipt.generator_outcomes
    assert len(result.generator_outcomes) == 1
    assert result.generator_outcomes[0].argv == manifest.operations[0].generator_commands[0]
    assert result.generator_outcomes[0].return_code == 0
    assert (repo / "dev/generated.txt").read_bytes() == b"generated Widget\n"
    assert (repo / "src/example/contracts.py").read_bytes() == b"class Widget:\n    pass\n"


def test_successful_module_replay_uses_deterministic_mixed_transaction_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, inventory, manifest, component, receipt = _module_case(tmp_path)
    events: list[tuple[str, str]] = []
    original_replace = replay_module._replace_staged
    original_unlink = replay_module._unlink_regular

    def track_replace(root: Path, relative: str, staged: Path, *, expected: bytes | None) -> None:
        events.append(("replace", relative))
        original_replace(root, relative, staged, expected=expected)

    def track_unlink(root: Path, relative: str, *, expected: bytes) -> None:
        events.append(("unlink", relative))
        original_unlink(root, relative, expected=expected)

    monkeypatch.setattr(replay_module, "_replace_staged", track_replace)
    monkeypatch.setattr(replay_module, "_unlink_regular", track_unlink)

    result = replay_object_name_component(
        manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
    )

    assert events == [
        ("replace", "src/example/consumer.py"),
        ("replace", "src/example/widget.py"),
        ("unlink", "src/example/widgets.py"),
    ]
    assert result.changed_paths == receipt.changed_paths
    assert not (repo / "src/example/widgets.py").exists()
    assert (repo / "src/example/widget.py").read_bytes() == b"VALUE = 1\n"
    assert (repo / "src/example/consumer.py").read_bytes() == b"import example.widget\n"


@pytest.mark.parametrize(("method", "position"), [("replace", 1), ("replace", 2), ("unlink", 1)])
def test_mixed_transaction_failure_at_each_mutation_position_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str, position: int
) -> None:
    repo, inventory, manifest, component, receipt = _module_case(tmp_path)
    before = _live_bytes(repo)
    original = getattr(replay_module, f"_{method}_staged" if method == "replace" else "_unlink_regular")
    calls = 0

    def fail_once(*args: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == position:
            raise OSError(f"{method}-{position}")
        original(*args, **kwargs)

    monkeypatch.setattr(
        replay_module,
        "_replace_staged" if method == "replace" else "_unlink_regular",
        fail_once,
    )

    with pytest.raises(ObjectNameReplayError, match="rolled back"):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )

    assert _live_bytes(repo) == before


@pytest.mark.parametrize("position", [1, 2])
def test_staging_failure_at_each_module_output_position_leaves_live_tree_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, position: int
) -> None:
    repo, inventory, manifest, component, receipt = _module_case(tmp_path)
    before = _live_bytes(repo)
    original = replay_module._stage_bytes
    calls = 0

    def fail_position(*args: Any, **kwargs: Any) -> Path:
        nonlocal calls
        calls += 1
        if calls == position:
            raise OSError(f"stage-{position}")
        return original(*args, **kwargs)

    monkeypatch.setattr(replay_module, "_stage_bytes", fail_position)

    with pytest.raises(ObjectNameReplayError, match="rolled back"):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )

    assert _live_bytes(repo) == before


@pytest.mark.parametrize(("method", "position"), [("replace", 1), ("replace", 2), ("unlink", 1)])
def test_failure_after_each_mutation_side_effect_is_still_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str, position: int
) -> None:
    repo, inventory, manifest, component, receipt = _module_case(tmp_path)
    before = _live_bytes(repo)
    attribute = "_replace_staged" if method == "replace" else "_unlink_regular"
    original = getattr(replay_module, attribute)
    calls = 0

    def apply_then_fail(*args: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        original(*args, **kwargs)
        if calls == position:
            raise OSError(f"after-{method}-{position}")

    monkeypatch.setattr(replay_module, attribute, apply_then_fail)

    with pytest.raises(ObjectNameReplayError, match="rolled back"):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )

    assert _live_bytes(repo) == before


def test_real_rollback_attempts_every_member_and_aggregates_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    first = root / "first.py"
    second = root / "second.py"
    first.write_bytes(b"applied-one")
    second.write_bytes(b"applied-two")
    attempted: list[str] = []
    original_unlink = Path.unlink

    def refuse_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        attempted.append(path.name)
        raise OSError(f"cannot unlink {path.name}")

    monkeypatch.setattr(Path, "unlink", refuse_unlink)
    with pytest.raises(ObjectNameReplayError, match=r"rollback was incomplete.*first.py.*second.py"):
        replay_module._restore(
            root=root,
            baseline_payloads={"first.py": None, "second.py": None},
            mutation_intents={"first.py": b"applied-one", "second.py": b"applied-two"},
            created_directories=(),
        )
    monkeypatch.setattr(Path, "unlink", original_unlink)

    assert attempted == ["first.py", "second.py"]
    assert first.read_bytes() == b"applied-one"
    assert second.read_bytes() == b"applied-two"


@pytest.mark.parametrize(
    "field",
    [
        "schema",
        "source-unchanged",
        "receipt-id",
        "evidence-digest",
        "changed-path-digest",
        "failed-gate",
    ],
)
def test_invalid_receipt_integrity_refuses_before_any_live_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    if field == "schema":
        candidate = replace(receipt, schema_version=99)
    elif field == "source-unchanged":
        candidate = replace(receipt, source_tree_unchanged=False)
    elif field == "receipt-id":
        candidate = replace(receipt, receipt_id=_digest(b"wrong"))
    elif field == "evidence-digest":
        candidate = replace(receipt, evidence_digest=_digest(b"wrong"))
    elif field == "changed-path-digest":
        candidate = replace(receipt, changed_path_digest=_digest(b"wrong"))
    else:
        failed = replace(receipt.gate_outcomes[0], return_code=7)
        candidate = replace(receipt, gate_outcomes=(failed,))
    writes: list[str] = []
    monkeypatch.setattr(replay_module, "_replace_staged", lambda *_args, **_kwargs: writes.append("replace"))
    monkeypatch.setattr(replay_module, "_unlink_regular", lambda *_args, **_kwargs: writes.append("unlink"))

    with pytest.raises(ObjectNameReplayError):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=candidate, repo_root=repo
        )

    assert writes == []
    assert (repo / "src/example/contracts.py").read_bytes() == b"class Widgets:\n    pass\n"


@pytest.mark.parametrize(
    "drift",
    ["manifest", "inventory", "component", "tool", "generator", "gate", "content"],
)
def test_authority_and_regenerated_evidence_drift_refuses_before_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    supplied_manifest, supplied_inventory, supplied_component, supplied_receipt = (
        manifest,
        inventory,
        component,
        receipt,
    )
    if drift == "manifest":
        operation = manifest.operations[0].model_copy(update={"rationale": "different reviewed intent"})
        supplied_manifest = manifest.model_copy(update={"operations": (operation,)})
    elif drift == "inventory":
        supplied_inventory = replace(inventory, declarations=())
    elif drift == "component":
        supplied_component = replace(component, component_id=_digest(b"other-component"))
    elif drift == "tool":
        supplied_receipt = _retag(replace(receipt, tool_versions=((*receipt.tool_versions[:-1], ("uv", "changed")))))
    elif drift == "generator":
        supplied_receipt = _retag(replace(receipt, generator_outcomes=(receipt.gate_outcomes[0],)))
    elif drift == "gate":
        changed = replace(receipt.gate_outcomes[0], stdout_sha256=_digest(b"changed"))
        supplied_receipt = _retag(replace(receipt, gate_outcomes=(changed,)))
    else:
        supplied_receipt = _retag(
            replace(receipt, proposed_file_digests=((receipt.changed_paths[0], _digest(b"changed")),))
        )
    writes: list[str] = []
    monkeypatch.setattr(replay_module, "_replace_staged", lambda *_args, **_kwargs: writes.append("replace"))
    monkeypatch.setattr(replay_module, "_unlink_regular", lambda *_args, **_kwargs: writes.append("unlink"))

    with pytest.raises(ObjectNameReplayError):
        replay_object_name_component(
            supplied_manifest,
            inventory=supplied_inventory,
            component=supplied_component,
            receipt=supplied_receipt,
            repo_root=repo,
        )

    assert writes == []


@pytest.mark.parametrize("forgery", ["affected-paths", "hard-edges"])
def test_component_structural_forgery_reaches_canonical_preflight_and_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forgery: str
) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    if forgery == "affected-paths":
        supplied_component = replace(component, affected_paths=(*component.affected_paths, "dev/forged.py"))
    else:
        supplied_component = replace(component, hard_edges=())
    writes: list[str] = []
    monkeypatch.setattr(replay_module, "_replace_staged", lambda *_args, **_kwargs: writes.append("replace"))
    monkeypatch.setattr(replay_module, "_unlink_regular", lambda *_args, **_kwargs: writes.append("unlink"))

    with pytest.raises(
        ObjectNameReplayError,
        match=r"exact preflight.*supplied component differs from the canonical repository graph",
    ):
        replay_object_name_component(
            manifest,
            inventory=inventory,
            component=supplied_component,
            receipt=receipt,
            repo_root=repo,
        )

    assert writes == []


def test_occupied_transaction_is_refused_without_deleting_foreign_evidence(tmp_path: Path) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    transaction = repo.parent / f".{repo.name}.object-name-transaction-{receipt.receipt_id.removeprefix('sha256:')}"
    transaction.mkdir()
    sentinel = transaction / "foreign-evidence"
    sentinel.write_bytes(b"keep\n")

    with pytest.raises(
        ObjectNameReplayError, match="unfinished replay transaction requires explicit operator inspection"
    ):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )

    assert sentinel.read_bytes() == b"keep\n"


@pytest.mark.parametrize("case", ["existing", "absent-target"])
def test_late_concurrent_bytes_are_preserved_and_rollback_failure_is_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    if case == "existing":
        repo, inventory, manifest, component, receipt = _case(tmp_path)
        contested = "src/example/contracts.py"
    else:
        repo, inventory, manifest, component, receipt = _module_case(tmp_path)
        contested = "src/example/widget.py"
    original = replay_module._replace_staged

    def race(root: Path, relative: str, staged: Path, *, expected: bytes | None) -> None:
        if relative == contested:
            (root / relative).write_bytes(b"concurrent bytes\n")
        original(root, relative, staged, expected=expected)

    monkeypatch.setattr(replay_module, "_replace_staged", race)

    with pytest.raises(
        ObjectNameReplayError,
        match=r"live replay failed and rollback failed.*rollback preserves unexpected concurrent bytes",
    ):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )

    assert (repo / contested).read_bytes() == b"concurrent bytes\n"


def test_base_exception_during_local_staging_closes_descriptor_and_removes_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.py"
    original_fdopen = replay_module.os.fdopen
    monkeypatch.setattr(
        replay_module.os,
        "fdopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        replay_module._stage_bytes(target, b"payload", label="stage")

    monkeypatch.setattr(replay_module.os, "fdopen", original_fdopen)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("phase", ["mkstemp", "write", "flush", "fsync", "digest", "link"])
def test_staging_failure_phases_remove_local_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    target = tmp_path / "target.py"
    original_fdopen = replay_module.os.fdopen
    original_fsync = replay_module.os.fsync
    original_link_check = replay_module.is_link_like

    class FailingStream:
        def __init__(self, stream: Any) -> None:
            self.stream = stream

        def __enter__(self) -> FailingStream:
            self.stream.__enter__()
            return self

        def __exit__(self, *args: Any) -> Any:
            return self.stream.__exit__(*args)

        def write(self, payload: bytes) -> int:
            if phase == "write":
                raise OSError("write")
            return cast("int", self.stream.write(payload))

        def flush(self) -> None:
            if phase == "flush":
                raise OSError("flush")
            self.stream.flush()

        def fileno(self) -> int:
            return cast("int", self.stream.fileno())

    if phase == "mkstemp":
        monkeypatch.setattr(
            replay_module.tempfile, "mkstemp", lambda **_kwargs: (_ for _ in ()).throw(OSError("mkstemp"))
        )
    else:
        monkeypatch.setattr(
            replay_module.os,
            "fdopen",
            lambda descriptor, mode: FailingStream(original_fdopen(descriptor, mode)),
        )
    if phase == "fsync":
        monkeypatch.setattr(replay_module.os, "fsync", lambda _descriptor: (_ for _ in ()).throw(OSError("fsync")))
    if phase == "digest":
        monkeypatch.setattr(replay_module, "sha256_file", lambda _path: "0" * 64)
    if phase == "link":
        monkeypatch.setattr(
            replay_module,
            "is_link_like",
            lambda path: ".object-name-stage-" in Path(path).name or original_link_check(path),
        )

    with pytest.raises((OSError, ObjectNameReplayError)):
        replay_module._stage_bytes(target, b"payload", label="stage")

    monkeypatch.setattr(replay_module.os, "fsync", original_fsync)
    remaining = list(tmp_path.iterdir())
    if phase == "link":
        assert len(remaining) == 1
    else:
        assert remaining == []


@pytest.mark.parametrize(
    "changed_paths",
    [(), ("src/example/contracts.py", "dev/surplus.py"), ("src/example/contracts.py",) * 2],
)
def test_receipt_allowlist_shape_drift_refuses_before_live_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed_paths: tuple[str, ...]
) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    candidate = _retag(replace(receipt, changed_paths=changed_paths, changed_path_digest=_digest(b"temporary")))
    candidate = _retag(
        replace(
            candidate,
            changed_path_digest=replay_module._digest(replay_module.canonical_json_bytes(list(changed_paths))),
        )
    )
    writes: list[str] = []
    monkeypatch.setattr(replay_module, "_replace_staged", lambda *_args, **_kwargs: writes.append("replace"))
    monkeypatch.setattr(replay_module, "_unlink_regular", lambda *_args, **_kwargs: writes.append("unlink"))

    with pytest.raises(ObjectNameReplayError):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=candidate, repo_root=repo
        )

    assert writes == []


@pytest.mark.parametrize("relative", ["../outside.py", "/absolute.py", ".git/config", "dev\\bad.py"])
def test_unsafe_replay_path_forms_are_refused(tmp_path: Path, relative: str) -> None:
    root = tmp_path.resolve()
    with pytest.raises(ObjectNameReplayError, match="unsafe replay path"):
        replay_module._safe_path(root, relative, allow_missing_leaf=True)


@pytest.mark.parametrize("failure", ["stage", "replace", "post-gate", "finding", "content"])
def test_apply_and_postcondition_failures_restore_exact_live_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    before = _live_bytes(repo)
    if failure == "stage":
        monkeypatch.setattr(
            replay_module, "_stage_bytes", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("stage"))
        )
    elif failure == "replace":
        original = replay_module._replace_staged
        calls = 0

        def fail_replace(*args: Any, **kwargs: Any) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("replace")
            original(*args, **kwargs)

        monkeypatch.setattr(replay_module, "_replace_staged", fail_replace)
    elif failure == "post-gate":
        monkeypatch.setattr(
            replay_module,
            "_run_gates_in_verified_copy",
            lambda **_kwargs: (_ for _ in ()).throw(ObjectNameReplayError("gate")),
        )
    elif failure == "finding":
        monkeypatch.setattr(replay_module, "_finding_delta", lambda *_args: object())
    else:
        original_snapshot = replay_module._snapshot
        original_gates = replay_module._run_gates_in_verified_copy
        post_gate = False

        def gates_finished_content(**kwargs: Any) -> Any:
            nonlocal post_gate
            result = original_gates(**kwargs)
            post_gate = True
            return result

        def corrupt_post_snapshot(root: Path, paths: Any) -> Any:
            result = original_snapshot(root, paths)
            if post_gate and root.resolve() == repo.resolve():
                return tuple(
                    (path, _digest(b"wrong")) if path == receipt.changed_paths[0] else (path, digest)
                    for path, digest in result
                )
            return result

        monkeypatch.setattr(replay_module, "_run_gates_in_verified_copy", gates_finished_content)
        monkeypatch.setattr(replay_module, "_snapshot", corrupt_post_snapshot)

    with pytest.raises(ObjectNameReplayError):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )

    assert _live_bytes(repo) == before


def test_rollback_failure_reports_both_apply_and_rollback_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    monkeypatch.setattr(
        replay_module,
        "_run_gates_in_verified_copy",
        lambda **_kwargs: (_ for _ in ()).throw(ObjectNameReplayError("apply failed")),
    )
    monkeypatch.setattr(
        replay_module,
        "_restore",
        lambda **_kwargs: (_ for _ in ()).throw(ObjectNameReplayError("rollback failed")),
    )

    with pytest.raises(ObjectNameReplayError, match=r"replay_error=apply failed; rollback_error=rollback failed"):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )


def test_base_exception_during_apply_is_rolled_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    before = _live_bytes(repo)
    monkeypatch.setattr(
        replay_module,
        "_run_gates_in_verified_copy",
        lambda **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(ObjectNameReplayError, match="rolled back"):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )

    assert _live_bytes(repo) == before


@pytest.mark.parametrize(("method", "position"), [("replace", 2), ("unlink", 1)])
def test_base_exception_after_partial_mixed_mutation_restores_exact_live_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str, position: int
) -> None:
    repo, inventory, manifest, component, receipt = _module_case(tmp_path)
    before = _live_bytes(repo)
    attribute = "_replace_staged" if method == "replace" else "_unlink_regular"
    original = getattr(replay_module, attribute)
    calls = 0

    def apply_then_interrupt(*args: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        original(*args, **kwargs)
        if calls == position:
            raise KeyboardInterrupt(f"after-{method}-{position}")

    monkeypatch.setattr(replay_module, attribute, apply_then_interrupt)

    with pytest.raises(ObjectNameReplayError, match=r"live replay failed and was rolled back: after-"):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )

    assert _live_bytes(repo) == before


def test_linked_root_and_unsafe_receipt_paths_refuse_without_writes(tmp_path: Path) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    linked = tmp_path / "linked-repo"
    try:
        linked.symlink_to(repo, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(ObjectNameReplayError, match="root is link-like"):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=linked
        )


def test_cleanup_failure_does_not_mask_primary_apply_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    monkeypatch.setattr(
        replay_module,
        "_run_gates_in_verified_copy",
        lambda **_kwargs: (_ for _ in ()).throw(ObjectNameReplayError("primary apply failure")),
    )
    monkeypatch.setattr(
        replay_module,
        "_cleanup",
        lambda *_args: (_ for _ in ()).throw(OSError("cleanup failure")),
    )

    with pytest.raises(ObjectNameReplayError, match="primary apply failure"):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )


def test_cleanup_failure_after_successful_apply_is_reported_and_keeps_transaction_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    transaction = repo.parent / f".{repo.name}.object-name-transaction-{receipt.receipt_id.removeprefix('sha256:')}"
    monkeypatch.setattr(
        replay_module,
        "_cleanup",
        lambda *_args: (_ for _ in ()).throw(OSError("cleanup after success")),
    )

    with pytest.raises(ObjectNameReplayError, match="replay stage cleanup failed"):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )

    assert (repo / "src/example/contracts.py").read_bytes() == b"class Widget:\n    pass\n"
    assert transaction.is_dir()


def test_rollback_failure_precedes_cleanup_failure_and_keeps_transaction_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    transaction = repo.parent / f".{repo.name}.object-name-transaction-{receipt.receipt_id.removeprefix('sha256:')}"
    monkeypatch.setattr(
        replay_module,
        "_run_gates_in_verified_copy",
        lambda **_kwargs: (_ for _ in ()).throw(ObjectNameReplayError("apply failed")),
    )
    monkeypatch.setattr(
        replay_module,
        "_restore",
        lambda **_kwargs: (_ for _ in ()).throw(ObjectNameReplayError("rollback failed")),
    )
    monkeypatch.setattr(
        replay_module,
        "_cleanup",
        lambda *_args: (_ for _ in ()).throw(OSError("cleanup failed")),
    )

    with pytest.raises(
        ObjectNameReplayError,
        match=r"replay_error=apply failed; rollback_error=rollback failed",
    ) as raised:
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )

    assert "cleanup failed" not in str(raised.value)
    assert transaction.is_dir()
