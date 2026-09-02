"""Detector teeth for receipt-bound object-name replay transactions."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from .. import object_name_graph as graph_module
from .. import object_name_replay as replay_module
from ..object_name_rehearsal import ObjectNameRehearsalReceipt, rehearse_object_name_component
from ..object_name_replay import ObjectNameReplayError, replay_object_name_component
from .test_object_name_rehearsal import _digest, _fixture, _live_bytes

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


@pytest.mark.parametrize("drift", ["manifest", "inventory", "component", "file", "tool", "gate", "content"])
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
    elif drift == "file":
        (repo / "dev/untracked.txt").write_bytes(b"drift\n")
    elif drift == "tool":
        supplied_receipt = _retag(replace(receipt, tool_versions=((*receipt.tool_versions[:-1], ("uv", "changed")))))
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


def test_occupied_transaction_is_refused_without_deleting_foreign_evidence(tmp_path: Path) -> None:
    repo, inventory, manifest, component, receipt = _case(tmp_path)
    transaction = repo.parent / f".{repo.name}.object-name-transaction-{receipt.receipt_id.removeprefix('sha256:')}"
    transaction.mkdir()
    sentinel = transaction / "foreign-evidence"
    sentinel.write_bytes(b"keep\n")

    with pytest.raises(ObjectNameReplayError, match="unfinished replay transaction requires explicit operator inspection"):
        replay_object_name_component(
            manifest, inventory=inventory, component=component, receipt=receipt, repo_root=repo
        )

    assert sentinel.read_bytes() == b"keep\n"


@pytest.mark.parametrize("failure", ["stage", "replace", "post-gate", "finding", "changed-path", "content"])
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
    elif failure == "changed-path":
        original_paths = replay_module._git_snapshot_paths
        original_gates = replay_module._run_gates_in_verified_copy
        post_gate = False

        def gates_finished_paths(**kwargs: Any) -> Any:
            nonlocal post_gate
            result = original_gates(**kwargs)
            post_gate = True
            return result

        def omit_live_path(root: Path) -> tuple[str, ...]:
            paths = original_paths(root)
            if post_gate and root.resolve() == repo.resolve():
                return tuple(path for path in paths if path != "dev/tracked.txt")
            return paths

        monkeypatch.setattr(replay_module, "_run_gates_in_verified_copy", gates_finished_paths)
        monkeypatch.setattr(replay_module, "_git_snapshot_paths", omit_live_path)
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
