"""Explicit, receipt-bound replay of reviewed object-name transformations."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.hashing import canonical_json_bytes, prefixed_digest, sha256_file
from cadrumo.core.link_safety import is_link_like

from ..audit.object_names import ObjectNameAuditResult, scan, to_json
from .object_name_graph import OperationComponent, ReferenceKind
from .object_name_manifest import ObjectNameRenameManifest, object_name_manifest_digest
from .object_name_rehearsal import (
    ObjectNameGateOutcome,
    ObjectNameRehearsalError,
    ObjectNameRehearsalReceipt,
    _copy_snapshot,  # pyright: ignore[reportPrivateUsage]
    _finding_delta,  # pyright: ignore[reportPrivateUsage]
    _git_snapshot_paths,  # pyright: ignore[reportPrivateUsage]
    _receipt_payload,  # pyright: ignore[reportPrivateUsage]
    _run_command,  # pyright: ignore[reportPrivateUsage]
    _snapshot,  # pyright: ignore[reportPrivateUsage]
    _tree_digest,  # pyright: ignore[reportPrivateUsage]
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
    if outcomes != expected:
        raise ObjectNameReplayError("post-apply command output evidence differs from the receipt")
    return outcomes


def _run_gates_in_verified_copy(
    *, root: Path, expected: tuple[ObjectNameGateOutcome, ...]
) -> tuple[ObjectNameGateOutcome, ...]:
    paths = _git_snapshot_paths(root)
    files = _snapshot(root, paths)
    temporary_candidate = Path(tempfile.gettempdir())
    if is_link_like(temporary_candidate):
        raise ObjectNameReplayError(f"system temporary root is link-like: {temporary_candidate}")
    system_temporary_root = temporary_candidate.resolve()
    if (
        not system_temporary_root.is_dir()
        or is_link_like(system_temporary_root)
        or system_temporary_root.is_relative_to(root)
    ):
        raise ObjectNameReplayError(f"system temporary root is unsafe: {system_temporary_root}")
    temporary_root = Path(
        tempfile.mkdtemp(prefix="cadrumo-object-name-post-apply-", dir=system_temporary_root)
    ).resolve()
    try:
        if temporary_root.parent != system_temporary_root or is_link_like(temporary_root):
            raise ObjectNameReplayError(f"allocated post-apply verification root is unsafe: {temporary_root}")
        _copy_snapshot(root, temporary_root, files)
        if _snapshot(temporary_root, paths) != files:
            raise ObjectNameReplayError("post-apply verification copy differs from the live candidate")
        outcomes = _run_exact_commands(expected, root=temporary_root)
        if _git_snapshot_paths(root) != paths or _snapshot(root, paths) != files:
            raise ObjectNameReplayError("live tree drifted during post-apply gate verification")
        return outcomes
    finally:
        if temporary_root.exists() and not is_link_like(temporary_root):
            shutil.rmtree(temporary_root)


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
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        if staged.exists() and not is_link_like(staged):
            staged.unlink()
        raise


def _current_payload(root: Path, relative: str) -> bytes | None:
    target = _safe_path(root, relative, allow_missing_leaf=True)
    if not target.exists():
        return None
    if not target.is_file() or is_link_like(target):
        raise ObjectNameReplayError(f"replay target is not a regular unlinked file: {relative}")
    return target.read_bytes()


def _replace_staged(root: Path, relative: str, staged: Path, *, expected: bytes | None) -> None:
    target = _safe_path(root, relative, allow_missing_leaf=True)
    if _current_payload(root, relative) != expected:
        raise ObjectNameReplayError(f"replay target drifted immediately before replace: {relative}")
    if is_link_like(staged) or staged.parent.resolve() != target.parent.resolve():
        raise ObjectNameReplayError(f"staging sibling changed before replace: {relative}")
    os.replace(staged, target)
    verified = _safe_path(root, relative)
    if not verified.is_file() or is_link_like(verified):
        raise ObjectNameReplayError(f"replaced target is not a regular unlinked file: {relative}")
    fsync_parent_dir(verified)


def _unlink_regular(root: Path, relative: str, *, expected: bytes) -> None:
    target = _safe_path(root, relative)
    if _current_payload(root, relative) != expected:
        raise ObjectNameReplayError(f"replay target drifted immediately before unlink: {relative}")
    target.unlink()
    fsync_parent_dir(target)


def _cleanup(paths: tuple[Path, ...]) -> None:
    for path in paths:
        if path.exists() and not is_link_like(path) and path.is_file():
            path.unlink()


def _create_transaction_root(path: Path) -> None:
    """Create one owned marker; pre-existing markers are retained and refused."""
    if path.exists() or is_link_like(path):
        raise ObjectNameReplayError(f"unfinished replay transaction requires explicit operator inspection: {path}")
    path.mkdir()
    if is_link_like(path) or not path.is_dir():
        raise ObjectNameReplayError(f"created replay transaction root is unsafe: {path}")


def _restore(
    *,
    root: Path,
    baseline_payloads: dict[str, bytes | None],
    mutation_intents: dict[str, bytes | None],
    created_directories: tuple[Path, ...],
) -> None:
    failures: list[str] = []
    restorable: dict[str, bytes | None] = {}
    for relative, applied_payload in sorted(mutation_intents.items()):
        baseline_payload = baseline_payloads[relative]
        try:
            current_payload = _current_payload(root, relative)
            if current_payload == baseline_payload:
                continue
            if current_payload != applied_payload:
                failures.append(f"rollback preserves unexpected concurrent bytes: {relative}")
                continue
            restorable[relative] = baseline_payload
        except Exception as exc:
            failures.append(f"cannot inspect rollback member {relative}: {exc}")
    for relative, payload in sorted(restorable.items()):
        if payload is not None:
            continue
        try:
            target = _safe_path(root, relative, allow_missing_leaf=True)
            if target.exists():
                if not target.is_file() or is_link_like(target):
                    raise ObjectNameReplayError(f"rollback member is not a regular file: {relative}")
                target.unlink()
                fsync_parent_dir(target)
        except Exception as exc:  # rollback must attempt every member
            failures.append(f"{relative}: {exc}")
    for relative, payload in sorted(restorable.items()):
        if payload is None:
            continue
        try:
            target = _safe_path(root, relative, allow_missing_leaf=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            staged = _stage_bytes(target, payload, label="restore")
            _replace_staged(root, relative, staged, expected=_current_payload(root, relative))
        except Exception as exc:  # rollback must attempt every member
            failures.append(f"{relative}: {exc}")
    for directory in sorted(created_directories, key=lambda item: len(item.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError as exc:
            failures.append(f"cannot remove created directory {directory}: {exc}")
    for relative, payload in restorable.items():
        try:
            target = _safe_path(root, relative, allow_missing_leaf=True)
            actual = None if not target.exists() else target.read_bytes()
            if actual != payload:
                failures.append(f"restored path differs from pre-transaction bytes: {relative}")
        except Exception as exc:
            failures.append(f"cannot verify restored path {relative}: {exc}")
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
    if (receipt.component_id, receipt.operation_ids) != (component.component_id, component.operation_ids):
        raise ObjectNameReplayError("receipt component identity differs from the supplied component")

    snapshot_paths = tuple(path for path, _digest in receipt.baseline_files)
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
    if (
        exact.proposed_file_digests,
        exact.changed_paths,
        exact.finding_delta,
        exact.tool_versions,
        exact.generator_outcomes,
        exact.gate_outcomes,
    ) != (
        receipt.proposed_file_digests,
        receipt.changed_paths,
        receipt.finding_delta,
        receipt.tool_versions,
        receipt.generator_outcomes,
        receipt.gate_outcomes,
    ):
        raise ObjectNameReplayError("regenerated transformation or verification differs from the receipt")
    reviewed_paths = tuple(
        sorted(
            {
                path
                for operation in manifest.operations
                if operation.operation_id in component.operation_ids
                for path in operation.changed_paths
            }
        )
    )
    if receipt.changed_paths != reviewed_paths:
        raise ObjectNameReplayError("receipt changed paths differ from the component allowlist")

    proposal_root = Path(exact.rehearsal_root)
    proposed_payloads: dict[str, bytes | None] = {}
    for relative, expected_digest in receipt.proposed_file_digests:
        source = _safe_path(proposal_root, relative, allow_missing_leaf=True)
        payload = None if expected_digest is None else source.read_bytes()
        if payload is not None and _digest(payload) != expected_digest:
            raise ObjectNameReplayError(f"regenerated output digest differs for {relative}")
        proposed_payloads[relative] = payload

    generated_paths = frozenset(
        edge.path for edge in component.hard_edges if edge.kind is ReferenceKind.GENERATED_ARTIFACT
    )
    direct_payloads = {path: payload for path, payload in proposed_payloads.items() if path not in generated_paths}
    # Preserve only receipt-owned paths. Rollback must never overwrite unrelated concurrent work.
    baseline_payloads = {
        relative: (_safe_path(root, relative).read_bytes() if _safe_path(root, relative).is_file() else None)
        for relative in receipt.changed_paths
    }
    if _snapshot(root, snapshot_paths) != baseline_files:
        raise ObjectNameReplayError("live tree drifted before replay staging")
    stages: dict[str, Path] = {}
    mutation_intents: dict[str, bytes | None] = {}
    created_directories: list[Path] = []
    transaction_may_be_removed = False
    transaction_root_created_by_this_call = False
    transaction_name = f".{root.name}.object-name-transaction-{receipt.receipt_id.removeprefix('sha256:')}"
    transaction_root = root.parent / transaction_name
    try:
        _create_transaction_root(transaction_root)
        transaction_root_created_by_this_call = True
        for relative, payload in sorted(baseline_payloads.items()):
            marker = transaction_root.joinpath(*PurePosixPath(relative).parts)
            marker.parent.mkdir(parents=True, exist_ok=True)
            with marker.open("xb") as stream:
                stream.write(b"" if payload is None else payload)
                stream.flush()
                os.fsync(stream.fileno())
        absent_marker = transaction_root / ".absent-paths"
        with absent_marker.open("xb") as stream:
            absent_paths = sorted(path for path, payload in baseline_payloads.items() if payload is None)
            stream.write(canonical_json_bytes(absent_paths))
            stream.flush()
            os.fsync(stream.fileno())
        fsync_parent_dir(absent_marker)
        for relative, payload in sorted(direct_payloads.items()):
            target = _safe_path(root, relative, allow_missing_leaf=True)
            if payload is not None:
                missing: list[Path] = []
                parent = target.parent
                while parent != root and not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                target.parent.mkdir(parents=True, exist_ok=True)
                created_directories.extend(reversed(missing))
                stages[relative] = _stage_bytes(target, payload, label="stage")
        if _snapshot(root, snapshot_paths) != baseline_files:
            raise ObjectNameReplayError("live tree drifted before the replay transaction")
        for relative, payload in sorted(direct_payloads.items()):
            target = _safe_path(root, relative, allow_missing_leaf=True)
            if payload is None:
                expected = baseline_payloads[relative]
                if expected is None:
                    raise ObjectNameReplayError(f"receipt cannot delete an absent path: {relative}")
                mutation_intents[relative] = None
                _unlink_regular(root, relative, expected=expected)
            else:
                mutation_intents[relative] = payload
                _replace_staged(
                    root,
                    relative,
                    stages[relative],
                    expected=baseline_payloads[relative],
                )
                stages.pop(relative)

        # Generated bytes are accepted only from the exact owner-command rehearsal.
        for relative in sorted(generated_paths):
            payload = proposed_payloads[relative]
            target = _safe_path(root, relative, allow_missing_leaf=True)
            if payload is None:
                expected = baseline_payloads[relative]
                if expected is None:
                    raise ObjectNameReplayError(f"receipt cannot delete an absent path: {relative}")
                mutation_intents[relative] = None
                _unlink_regular(root, relative, expected=expected)
            else:
                missing = []
                parent = target.parent
                while parent != root and not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                target.parent.mkdir(parents=True, exist_ok=True)
                created_directories.extend(reversed(missing))
                stages[relative] = _stage_bytes(target, payload, label="generated")
                mutation_intents[relative] = payload
                _replace_staged(root, relative, stages[relative], expected=baseline_payloads[relative])
                stages.pop(relative)

        generator_outcomes = exact.generator_outcomes
        gate_outcomes = _run_gates_in_verified_copy(root=root, expected=receipt.gate_outcomes)
        after_inventory = scan((root / "src", root / "dev"), root)
        if _finding_delta(inventory, after_inventory) != receipt.finding_delta:
            raise ObjectNameReplayError("post-apply object-name finding delta differs from the receipt")
        after_paths = _git_snapshot_paths(root)
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
        result = ObjectNameReplayResult(
            receipt_id=receipt.receipt_id,
            changed_paths=actual_changed,
            post_tree_digest=_tree_digest(after_files),
            generator_outcomes=generator_outcomes,
            gate_outcomes=gate_outcomes,
        )
        transaction_may_be_removed = True
        return result
    except BaseException as apply_error:
        try:
            _restore(
                root=root,
                baseline_payloads=baseline_payloads,
                mutation_intents=mutation_intents,
                created_directories=tuple(created_directories),
            )
        except BaseException as rollback_error:
            raise ObjectNameReplayError(
                f"live replay failed and rollback failed; replay_error={apply_error}; rollback_error={rollback_error}"
            ) from rollback_error
        transaction_may_be_removed = True
        if isinstance(apply_error, ObjectNameReplayError):
            raise
        raise ObjectNameReplayError(f"live replay failed and was rolled back: {apply_error}") from apply_error
    finally:
        primary_failure_active = sys.exc_info()[0] is not None
        try:
            _cleanup(tuple(stages.values()))
        except OSError as cleanup_error:
            if not primary_failure_active:
                raise ObjectNameReplayError("replay stage cleanup failed") from cleanup_error
        try:
            if (
                transaction_root_created_by_this_call
                and transaction_may_be_removed
                and transaction_root.exists()
                and not is_link_like(transaction_root)
            ):
                shutil.rmtree(transaction_root)
        except OSError as cleanup_error:
            if not primary_failure_active:
                raise ObjectNameReplayError(
                    f"replay completed but transaction evidence cleanup failed: {transaction_root}"
                ) from cleanup_error
