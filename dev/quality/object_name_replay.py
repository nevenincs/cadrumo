"""Explicit, receipt-bound replay of reviewed object-name transformations."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.hashing import canonical_json_bytes, prefixed_digest, sha256_file
from cadrumo.core.link_safety import is_link_like

from ..audit.object_names import ObjectNameAuditResult, scan, to_json
from .object_name_graph import OperationComponent
from .object_name_manifest import ObjectNameRenameManifest, object_name_manifest_digest
from .object_name_rehearsal import (
    ObjectNameGateOutcome,
    ObjectNameRehearsalError,
    ObjectNameRehearsalReceipt,
    _finding_delta,
    _git_snapshot_paths,
    _receipt_payload,
    _run_command,
    _snapshot,
    _temporary_paths,
    _tree_digest,
    rehearse_object_name_component,
)

__all__ = [
    "ObjectNameReplayError",
    "ObjectNameReplayResult",
    "replay_object_name_component",
]

_DIGEST_PREFIX: Final[str] = "sha256:"
_RECEIPT_SCHEMA_VERSION: Final[int] = 1


class ObjectNameReplayError(RuntimeError):
    """An exact reviewed rehearsal cannot be applied safely to the live tree."""


@dataclass(frozen=True, slots=True)
class ObjectNameReplayResult:
    """Evidence that one explicit receipt was applied and verified."""

    receipt_id: str
    changed_paths: tuple[str, ...]
    post_tree_digest: str
    generator_outcomes: tuple[ObjectNameGateOutcome, ...]
    gate_outcomes: tuple[ObjectNameGateOutcome, ...]


def _digest(payload: bytes) -> str:
    return prefixed_digest(payload)


def _safe_path(root: Path, relative: str, *, allow_missing_leaf: bool = False) -> Path:
    candidate = PurePosixPath(relative)
    if (
        "\\" in relative
        or ":" in relative
        or candidate.is_absolute()
        or any(part in {"", ".", "..", ".git"} for part in candidate.parts)
    ):
        raise ObjectNameReplayError(f"unsafe replay path: {relative!r}")
    path = root
    for index, part in enumerate(candidate.parts):
        path /= part
        if is_link_like(path):
            raise ObjectNameReplayError(f"replay path traverses a link-like component: {relative}")
        if not path.exists() and (allow_missing_leaf or index < len(candidate.parts) - 1):
            continue
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise ObjectNameReplayError(f"replay path escapes the repository: {relative}") from exc
    return path


def _receipt_digest(receipt: ObjectNameRehearsalReceipt, *, evidence: bool) -> str:
    return _digest(canonical_json_bytes(_receipt_payload(receipt, include_output_evidence=evidence)))


def _validate_receipt_integrity(receipt: ObjectNameRehearsalReceipt) -> None:
    if receipt.schema_version != _RECEIPT_SCHEMA_VERSION or not receipt.source_tree_unchanged:
        raise ObjectNameReplayError("receipt is not a successful current-schema rehearsal")
    if any(item.return_code != 0 for item in (*receipt.generator_outcomes, *receipt.gate_outcomes)):
        raise ObjectNameReplayError("receipt contains a failed declared command")
    if receipt.receipt_id != _receipt_digest(receipt, evidence=False):
        raise ObjectNameReplayError("receipt identity digest is invalid")
    if receipt.evidence_digest != _receipt_digest(receipt, evidence=True):
        raise ObjectNameReplayError("receipt evidence digest is invalid")
    expected_changed_digest = _digest(canonical_json_bytes(list(receipt.changed_paths)))
    if receipt.changed_path_digest != expected_changed_digest:
        raise ObjectNameReplayError("receipt changed-path digest is invalid")


def _command_environment(root: Path) -> dict[str, str]:
    import sys

    environment = os.environ.copy()
    environment["VIRTUAL_ENV"] = sys.prefix
    environment["UV_PROJECT_ENVIRONMENT"] = sys.prefix
    environment["PYTHONPATH"] = os.pathsep.join((str(root / "src"), str(root)))
    return environment


def _run_exact_commands(
    expected: tuple[ObjectNameGateOutcome, ...], *, root: Path
) -> tuple[ObjectNameGateOutcome, ...]:
    environment = _command_environment(root)
    outcomes = tuple(_run_command(item.argv, cwd=root, environment=environment) for item in expected)
    for outcome in outcomes:
        if outcome.return_code != 0:
            raise ObjectNameReplayError(
                f"post-apply command failed: argv={outcome.argv!r}, return_code={outcome.return_code}, "
                f"stdout_sha256={outcome.stdout_sha256}, stderr_sha256={outcome.stderr_sha256}"
            )
    return outcomes


def _stage_bytes(target: Path, payload: bytes, *, label: str) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.object-name-{label}-", dir=target.parent)
    staged = Path(name)
    try:
        if is_link_like(staged) or staged.stat().st_dev != target.parent.stat().st_dev:
            raise ObjectNameReplayError(f"unsafe cross-filesystem replay staging path for {target}")
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if f"{_DIGEST_PREFIX}{sha256_file(staged)}" != _digest(payload):
            raise ObjectNameReplayError(f"staged replay bytes failed verification for {target}")
        return staged
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        if staged.exists() and not is_link_like(staged):
            staged.unlink()
        raise


def _cleanup(paths: tuple[Path, ...]) -> None:
    for path in paths:
        if path.exists() and not is_link_like(path) and path.is_file():
            path.unlink()


def _restore(
    *,
    root: Path,
    baseline_payloads: dict[str, bytes | None],
    baseline_paths: tuple[str, ...],
) -> None:
    failures: list[str] = []
    current_paths = set(_temporary_paths(root))
    baseline_members = {path for path, payload in baseline_payloads.items() if payload is not None}
    for relative in sorted(current_paths - baseline_members, reverse=True):
        try:
            path = _safe_path(root, relative)
            if not path.is_file() or is_link_like(path):
                raise ObjectNameReplayError(f"rollback member is not a regular file: {relative}")
            path.unlink()
            fsync_parent_dir(path)
        except Exception as exc:  # rollback must attempt every member
            failures.append(f"{relative}: {exc}")
    for relative, payload in sorted(baseline_payloads.items()):
        if payload is None:
            continue
        try:
            target = _safe_path(root, relative, allow_missing_leaf=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            staged = _stage_bytes(target, payload, label="restore")
            os.replace(staged, target)
            fsync_parent_dir(target)
        except Exception as exc:  # rollback must attempt every member
            failures.append(f"{relative}: {exc}")
    try:
        if _git_snapshot_paths(root) != baseline_paths or _snapshot(root, baseline_paths) != tuple(
            (path, None if payload is None else _digest(payload)) for path, payload in baseline_payloads.items()
        ):
            failures.append("restored tree differs from the pre-transaction snapshot")
    except Exception as exc:
        failures.append(f"cannot verify restored tree: {exc}")
    if failures:
        raise ObjectNameReplayError("rollback was incomplete: " + "; ".join(failures))


def replay_object_name_component(
    manifest: ObjectNameRenameManifest,
    *,
    inventory: ObjectNameAuditResult,
    component: OperationComponent,
    receipt: ObjectNameRehearsalReceipt,
    repo_root: Path,
) -> ObjectNameReplayResult:
    """Apply exactly one caller-supplied successful rehearsal receipt."""
    _validate_receipt_integrity(receipt)
    raw_root = Path(repo_root)
    if is_link_like(raw_root):
        raise ObjectNameReplayError(f"live replay root is link-like: {raw_root}")
    root = raw_root.resolve()
    if not (root / ".git").is_dir() or not (root / "src").is_dir() or not (root / "dev").is_dir():
        raise ObjectNameReplayError(f"live replay root is not a repository worktree: {root}")
    if receipt.manifest_digest != object_name_manifest_digest(manifest):
        raise ObjectNameReplayError("receipt manifest digest differs from the supplied manifest")
    inventory_digest = to_json(inventory)["inventory_digest"]
    if receipt.inventory_digest != inventory_digest or receipt.inventory_digest != manifest.inventory_digest:
        raise ObjectNameReplayError("receipt inventory digest differs from current authority")
    if (receipt.component_id, receipt.operation_ids) != (component.component_id, component.operation_ids):
        raise ObjectNameReplayError("receipt component identity differs from the supplied component")

    snapshot_paths = _git_snapshot_paths(root)
    baseline_files = _snapshot(root, snapshot_paths)
    if baseline_files != receipt.baseline_files or _tree_digest(baseline_files) != receipt.baseline_tree_digest:
        raise ObjectNameReplayError("live tree differs from the receipt baseline")
    baseline_by_path = dict(baseline_files)
    if any(baseline_by_path.get(path) != digest for path, digest in receipt.input_file_digests):
        raise ObjectNameReplayError("live transformation input bytes differ from the receipt")

    try:
        exact = rehearse_object_name_component(manifest, inventory=inventory, component=component, repo_root=root)
    except ObjectNameRehearsalError as exc:
        raise ObjectNameReplayError(f"exact preflight rehearsal refused replay: {exc}") from exc
    if exact.receipt_id != receipt.receipt_id or (
        exact.proposed_file_digests,
        exact.changed_paths,
        exact.finding_delta,
        exact.tool_versions,
        tuple((item.argv, item.return_code) for item in exact.generator_outcomes),
        tuple((item.argv, item.return_code) for item in exact.gate_outcomes),
    ) != (
        receipt.proposed_file_digests,
        receipt.changed_paths,
        receipt.finding_delta,
        receipt.tool_versions,
        tuple((item.argv, item.return_code) for item in receipt.generator_outcomes),
        tuple((item.argv, item.return_code) for item in receipt.gate_outcomes),
    ):
        raise ObjectNameReplayError("regenerated transformation or verification differs from the receipt")
    if tuple(sorted(receipt.changed_paths)) != tuple(sorted(component.affected_paths)):
        raise ObjectNameReplayError("receipt changed paths differ from the component allowlist")

    proposal_root = Path(exact.rehearsal_root)
    proposed_payloads: dict[str, bytes | None] = {}
    for relative, expected_digest in receipt.proposed_file_digests:
        source = _safe_path(proposal_root, relative, allow_missing_leaf=True)
        payload = None if expected_digest is None else source.read_bytes()
        if payload is not None and _digest(payload) != expected_digest:
            raise ObjectNameReplayError(f"regenerated output digest differs for {relative}")
        proposed_payloads[relative] = payload

    # Preserve the complete eligible tree so a failed postcondition can undo gate side effects too.
    baseline_payloads = {
        relative: None if digest is None else _safe_path(root, relative).read_bytes()
        for relative, digest in baseline_files
    }
    if _snapshot(root, snapshot_paths) != baseline_files:
        raise ObjectNameReplayError("live tree drifted before replay staging")
    stages: dict[str, Path] = {}
    try:
        for relative, payload in sorted(proposed_payloads.items()):
            target = _safe_path(root, relative, allow_missing_leaf=True)
            if payload is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                stages[relative] = _stage_bytes(target, payload, label="stage")
        if _snapshot(root, snapshot_paths) != baseline_files:
            raise ObjectNameReplayError("live tree drifted before the replay transaction")
        for relative, payload in sorted(proposed_payloads.items()):
            target = _safe_path(root, relative, allow_missing_leaf=True)
            if payload is None:
                if not target.is_file() or is_link_like(target):
                    raise ObjectNameReplayError(f"replay deletion target changed: {relative}")
                target.unlink()
            else:
                os.replace(stages.pop(relative), target)
            fsync_parent_dir(target)

        generator_outcomes = _run_exact_commands(receipt.generator_outcomes, root=root)
        gate_outcomes = _run_exact_commands(receipt.gate_outcomes, root=root)
        after_inventory = scan((root / "src", root / "dev"), root)
        if _finding_delta(inventory, after_inventory) != receipt.finding_delta:
            raise ObjectNameReplayError("post-apply object-name finding delta differs from the receipt")
        after_paths = _temporary_paths(root)
        after_files = _snapshot(root, after_paths)
        actual_changed = tuple(
            sorted(
                path
                for path in set(dict(baseline_files)) | set(dict(after_files))
                if dict(baseline_files).get(path) != dict(after_files).get(path)
            )
        )
        if actual_changed != receipt.changed_paths:
            raise ObjectNameReplayError("post-apply changed paths differ from the receipt allowlist")
        if tuple((path, dict(after_files).get(path)) for path in actual_changed) != receipt.proposed_file_digests:
            raise ObjectNameReplayError("post-apply content digests differ from the receipt")
        return ObjectNameReplayResult(
            receipt_id=receipt.receipt_id,
            changed_paths=actual_changed,
            post_tree_digest=_tree_digest(after_files),
            generator_outcomes=generator_outcomes,
            gate_outcomes=gate_outcomes,
        )
    except BaseException as apply_error:
        try:
            _restore(root=root, baseline_payloads=baseline_payloads, baseline_paths=snapshot_paths)
        except BaseException as rollback_error:
            raise ObjectNameReplayError(
                f"live replay failed and rollback failed; replay_error={apply_error}; rollback_error={rollback_error}"
            ) from rollback_error
        if isinstance(apply_error, ObjectNameReplayError):
            raise
        raise ObjectNameReplayError(f"live replay failed and was rolled back: {apply_error}") from apply_error
    finally:
        _cleanup(tuple(stages.values()))
