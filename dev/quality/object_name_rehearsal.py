"""Disposable rehearsal and deterministic receipts for object-name renames.

The live worktree is an input only.  Rehearsal snapshots every tracked and
non-ignored untracked file into a system-temporary directory, verifies the
copy, and materialises one reviewed graph component there.  It deliberately
retains the verified copy for operator inspection; cleanup is never implicit.
"""

from __future__ import annotations

import importlib.metadata
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Final

from cadrumo.core.hashing import canonical_json_bytes, prefixed_digest, sha256_file
from cadrumo.core.link_safety import is_link_like

from ..audit.object_names import ObjectNameAuditResult, ObjectNameFinding, scan
from .object_name_graph import OperationComponent
from .object_name_manifest import (
    ObjectNameRenameManifest,
    object_name_manifest_digest,
    select_object_name_execution,
)
from .object_name_transform import ObjectNameTransformResult, plan_object_name_transformation

__all__ = [
    "ObjectNameFindingDelta",
    "ObjectNameGateOutcome",
    "ObjectNameRehearsalError",
    "ObjectNameRehearsalReceipt",
    "rehearse_object_name_component",
]

_RECEIPT_SCHEMA_VERSION: Final[int] = 1
_DIGEST_PREFIX: Final[str] = "sha256:"
_EXCLUDED_DIRECTORY_NAMES: Final[frozenset[str]] = frozenset(
    {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".venv", "__pycache__", "node_modules"}
)


class ObjectNameRehearsalError(RuntimeError):
    """The current tree cannot produce a safe successful rehearsal receipt."""


@dataclass(frozen=True, slots=True)
class ObjectNameGateOutcome:
    """Deterministic evidence for one argv command executed in the copy."""

    argv: tuple[str, ...]
    return_code: int
    stdout_sha256: str
    stdout_bytes: int
    stderr_sha256: str
    stderr_bytes: int


@dataclass(frozen=True, slots=True)
class ObjectNameFindingDelta:
    """Canonical enforced-finding evidence before and after transformation."""

    before_count: int
    after_count: int
    resolved_ids: tuple[str, ...]
    introduced_ids: tuple[str, ...]
    introduced_signatures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ObjectNameRehearsalReceipt:
    """Immutable evidence needed to authorize an exact later replay."""

    schema_version: int
    rehearsal_root: str = field(compare=False)
    manifest_digest: str
    inventory_digest: str
    component_id: str
    operation_ids: tuple[str, ...]
    baseline_tree_digest: str
    baseline_files: tuple[tuple[str, str], ...]
    input_file_digests: tuple[tuple[str, str], ...]
    proposed_file_digests: tuple[tuple[str, str | None], ...]
    changed_paths: tuple[str, ...]
    changed_path_digest: str
    finding_delta: ObjectNameFindingDelta
    tool_versions: tuple[tuple[str, str], ...]
    generator_outcomes: tuple[ObjectNameGateOutcome, ...]
    gate_outcomes: tuple[ObjectNameGateOutcome, ...]
    source_tree_unchanged: bool
    receipt_id: str


def _digest_bytes(payload: bytes) -> str:
    return prefixed_digest(payload)


def _git_snapshot_paths(repo_root: Path) -> tuple[str, ...]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],  # noqa: S607
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ObjectNameRehearsalError("cannot enumerate tracked and relevant untracked files") from exc
    try:
        decoded = result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ObjectNameRehearsalError("git returned a non-UTF-8 repository path") from exc
    paths = tuple(sorted(path for path in decoded.split("\0") if path and _eligible_snapshot_path(path)))
    if not paths or len(paths) != len(set(paths)):
        raise ObjectNameRehearsalError("repository snapshot path inventory is empty or ambiguous")
    return paths


def _eligible_snapshot_path(relative: str) -> bool:
    candidate = PurePosixPath(relative)
    return not any(part in _EXCLUDED_DIRECTORY_NAMES for part in candidate.parts) and candidate.suffix != ".pyc"


def _regular_file(repo_root: Path, relative: str) -> Path | None:
    candidate = PurePosixPath(relative)
    if candidate.is_absolute() or any(part in {"", ".", "..", ".git"} for part in candidate.parts):
        raise ObjectNameRehearsalError(f"unsafe repository snapshot path: {relative!r}")
    path = repo_root
    for part in candidate.parts:
        path /= part
        if is_link_like(path):
            raise ObjectNameRehearsalError(f"snapshot path traverses a link-like component: {relative}")
    if not path.exists():
        return None  # A tracked working-tree deletion is represented by absence.
    if is_link_like(path) or not path.is_file():
        raise ObjectNameRehearsalError(f"snapshot input is not a regular unlinked file: {relative}")
    return path


def _snapshot(repo_root: Path, paths: Sequence[str]) -> tuple[tuple[str, str], ...]:
    files: list[tuple[str, str]] = []
    for relative in paths:
        path = _regular_file(repo_root, relative)
        if path is not None:
            files.append((relative, f"{_DIGEST_PREFIX}{sha256_file(path)}"))
    return tuple(files)


def _temporary_paths(repo_root: Path) -> tuple[str, ...]:
    paths: list[str] = []
    for directory, directory_names, file_names in os.walk(repo_root, followlinks=False):
        owner = Path(directory)
        retained_directories: list[str] = []
        for name in sorted(directory_names):
            child = owner / name
            if is_link_like(child):
                raise ObjectNameRehearsalError(
                    f"temporary command created a link-like path: {child.relative_to(repo_root).as_posix()}"
                )
            if name not in _EXCLUDED_DIRECTORY_NAMES:
                retained_directories.append(name)
        directory_names[:] = retained_directories
        for name in sorted(file_names):
            path = owner / name
            if path.suffix == ".pyc":
                continue
            relative = path.relative_to(repo_root).as_posix()
            if is_link_like(path):
                raise ObjectNameRehearsalError(f"temporary command created a link-like path: {relative}")
            paths.append(relative)
    return tuple(sorted(paths))


def _tree_digest(files: Sequence[tuple[str, str]]) -> str:
    return _digest_bytes(canonical_json_bytes({"schema_version": 1, "files": list(files)}))


def _copy_snapshot(
    source_root: Path,
    target_root: Path,
    files: Sequence[tuple[str, str]],
) -> None:
    for relative, expected_digest in files:
        source = _regular_file(source_root, relative)
        if source is None:
            raise ObjectNameRehearsalError(f"snapshot source disappeared during copy: {relative}")
        target = target_root.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target, follow_symlinks=False)
        actual_digest = f"{_DIGEST_PREFIX}{sha256_file(target)}"
        if actual_digest != expected_digest:
            raise ObjectNameRehearsalError(f"temporary copy hash differs for {relative}")


def _materialise(target_root: Path, result: ObjectNameTransformResult) -> None:
    for output in result.outputs:
        target = target_root.joinpath(*PurePosixPath(output.path).parts)
        if output.content is None:
            if not target.is_file() or is_link_like(target):
                raise ObjectNameRehearsalError(f"proposed deletion is not a regular file: {output.path}")
            target.unlink()
            continue
        if target.exists() and (is_link_like(target) or not target.is_file()):
            raise ObjectNameRehearsalError(f"proposed output target is not a regular file: {output.path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.object-name-output")
        if temporary.exists() or is_link_like(temporary):
            raise ObjectNameRehearsalError(f"temporary output path is occupied: {output.path}")
        temporary.write_bytes(output.content)
        os.replace(temporary, target)


def _run_command(argv: tuple[str, ...], *, cwd: Path) -> ObjectNameGateOutcome:
    try:
        completed = subprocess.run(argv, cwd=cwd, capture_output=True, check=False)  # noqa: S603
    except OSError as exc:
        raise ObjectNameRehearsalError(f"cannot execute declared command {argv!r}") from exc
    return ObjectNameGateOutcome(
        argv=argv,
        return_code=completed.returncode,
        stdout_sha256=_digest_bytes(completed.stdout),
        stdout_bytes=len(completed.stdout),
        stderr_sha256=_digest_bytes(completed.stderr),
        stderr_bytes=len(completed.stderr),
    )


def _finding_signature(finding: ObjectNameFinding) -> str:
    kind = finding.kind
    name = finding.name
    object_kinds = sorted(item.value for item in finding.object_kinds)
    return _digest_bytes(canonical_json_bytes({"kind": kind.value, "name": name, "object_kinds": object_kinds}))


def _finding_delta(before: ObjectNameAuditResult, after: ObjectNameAuditResult) -> ObjectNameFindingDelta:
    before_findings = tuple(finding for finding in before.findings if finding.enforced)
    after_findings = tuple(finding for finding in after.findings if finding.enforced)
    before_ids = {finding.id for finding in before_findings}
    after_ids = {finding.id for finding in after_findings}
    introduced_signatures = tuple(
        sorted(
            {_finding_signature(finding) for finding in after_findings}
            - {_finding_signature(f) for f in before_findings}
        )
    )
    return ObjectNameFindingDelta(
        before_count=len(before_findings),
        after_count=len(after_findings),
        resolved_ids=tuple(sorted(before_ids - after_ids)),
        introduced_ids=tuple(sorted(after_ids - before_ids)),
        introduced_signatures=introduced_signatures,
    )


def _receipt_payload(receipt: ObjectNameRehearsalReceipt) -> Mapping[str, object]:
    return {
        "schema_version": receipt.schema_version,
        "manifest_digest": receipt.manifest_digest,
        "inventory_digest": receipt.inventory_digest,
        "component_id": receipt.component_id,
        "operation_ids": receipt.operation_ids,
        "baseline_tree_digest": receipt.baseline_tree_digest,
        "baseline_files": receipt.baseline_files,
        "input_file_digests": receipt.input_file_digests,
        "proposed_file_digests": receipt.proposed_file_digests,
        "changed_paths": receipt.changed_paths,
        "changed_path_digest": receipt.changed_path_digest,
        "finding_delta": {
            "before_count": receipt.finding_delta.before_count,
            "after_count": receipt.finding_delta.after_count,
            "resolved_ids": receipt.finding_delta.resolved_ids,
            "introduced_ids": receipt.finding_delta.introduced_ids,
            "introduced_signatures": receipt.finding_delta.introduced_signatures,
        },
        "tool_versions": receipt.tool_versions,
        "generator_outcomes": [asdict(outcome) for outcome in receipt.generator_outcomes],
        "gate_outcomes": [asdict(outcome) for outcome in receipt.gate_outcomes],
        "source_tree_unchanged": receipt.source_tree_unchanged,
    }


def rehearse_object_name_component(
    manifest: ObjectNameRenameManifest,
    *,
    inventory: ObjectNameAuditResult,
    component: OperationComponent,
    repo_root: Path,
) -> ObjectNameRehearsalReceipt:
    """Rehearse exactly one complete reviewed component outside the live tree."""
    root = repo_root.resolve()
    if not (root / ".git").exists() or not (root / "src").is_dir() or not (root / "dev").is_dir():
        raise ObjectNameRehearsalError(f"rehearsal root is not a repository worktree: {root}")
    selected = tuple(sorted(select_object_name_execution(manifest), key=lambda item: item.operation_id))
    selected_ids = tuple(operation.operation_id for operation in selected)
    if selected_ids != component.operation_ids:
        raise ObjectNameRehearsalError("manifest execution must equal exactly one reviewed graph component")

    snapshot_paths = _git_snapshot_paths(root)
    baseline_files = _snapshot(root, snapshot_paths)
    baseline_tree_digest = _tree_digest(baseline_files)
    input_paths = tuple(sorted({item.path for operation in selected for item in operation.preconditions}))
    baseline_by_path = dict(baseline_files)
    try:
        input_file_digests = tuple((path, baseline_by_path[path]) for path in input_paths)
    except KeyError as exc:
        raise ObjectNameRehearsalError(f"manifest input is absent from the current snapshot: {exc.args[0]}") from exc

    system_temporary_root = Path(tempfile.gettempdir()).resolve()
    if not system_temporary_root.is_dir() or is_link_like(system_temporary_root):
        raise ObjectNameRehearsalError(f"system temporary root is unsafe: {system_temporary_root}")
    temporary_parent = Path(tempfile.mkdtemp(prefix="cadrumo-object-name-", dir=system_temporary_root)).resolve()
    if temporary_parent.parent != system_temporary_root or is_link_like(temporary_parent):
        raise ObjectNameRehearsalError(f"allocated rehearsal parent is unsafe: {temporary_parent}")
    temporary_root = temporary_parent / "repository"
    temporary_root.mkdir()
    source_unchanged = False
    try:
        _copy_snapshot(root, temporary_root, baseline_files)
        if _snapshot(temporary_root, tuple(path for path, _digest in baseline_files)) != baseline_files:
            raise ObjectNameRehearsalError("verified temporary snapshot differs from the current tree")

        result = plan_object_name_transformation(manifest, repo_root=temporary_root)
        if result.changed_paths != tuple(sorted(component.affected_paths)):
            raise ObjectNameRehearsalError("transformation paths differ from the reviewed component")
        _materialise(temporary_root, result)

        generator_argv = tuple(command for operation in selected for command in operation.generator_commands)
        gate_argv = tuple(command for operation in selected for command in operation.focused_gates)
        generator_outcomes = tuple(_run_command(argv, cwd=temporary_root) for argv in generator_argv)
        gate_outcomes = tuple(_run_command(argv, cwd=temporary_root) for argv in gate_argv)
        failed = tuple(outcome.argv for outcome in (*generator_outcomes, *gate_outcomes) if outcome.return_code != 0)
        if failed:
            raise ObjectNameRehearsalError(f"declared rehearsal commands failed: {failed!r}")

        after_inventory = scan((temporary_root / "src", temporary_root / "dev"), temporary_root)
        finding_delta = _finding_delta(inventory, after_inventory)
        if finding_delta.after_count > finding_delta.before_count or finding_delta.introduced_signatures:
            raise ObjectNameRehearsalError("rehearsal introduces an enforced object-name finding")

        after_paths = _temporary_paths(temporary_root)
        after_files = _snapshot(temporary_root, after_paths)
        changed = tuple(
            sorted(
                path
                for path in set(dict(baseline_files)) | set(dict(after_files))
                if dict(baseline_files).get(path) != dict(after_files).get(path)
            )
        )
        if changed != tuple(sorted(component.affected_paths)):
            raise ObjectNameRehearsalError("materialised changed paths differ from the reviewed component")
        proposed_digests = tuple((path, dict(after_files).get(path)) for path in changed)
        changed_path_digest = _digest_bytes(canonical_json_bytes(list(changed)))
        tool_versions = (
            ("libcst", importlib.metadata.version("libcst")),
            ("python", sys.version.split()[0]),
            ("rehearsal", str(_RECEIPT_SCHEMA_VERSION)),
        )
        source_paths_after = _git_snapshot_paths(root)
        source_unchanged = (
            source_paths_after == snapshot_paths and _snapshot(root, source_paths_after) == baseline_files
        )
        if not source_unchanged:
            raise ObjectNameRehearsalError("source tree changed while rehearsal was running")
        provisional = ObjectNameRehearsalReceipt(
            schema_version=_RECEIPT_SCHEMA_VERSION,
            rehearsal_root=str(temporary_root),
            manifest_digest=object_name_manifest_digest(manifest),
            inventory_digest=manifest.inventory_digest,
            component_id=component.component_id,
            operation_ids=component.operation_ids,
            baseline_tree_digest=baseline_tree_digest,
            baseline_files=baseline_files,
            input_file_digests=input_file_digests,
            proposed_file_digests=proposed_digests,
            changed_paths=changed,
            changed_path_digest=changed_path_digest,
            finding_delta=finding_delta,
            tool_versions=tool_versions,
            generator_outcomes=generator_outcomes,
            gate_outcomes=gate_outcomes,
            source_tree_unchanged=True,
            receipt_id="",
        )
        return replace(
            provisional,
            receipt_id=_digest_bytes(canonical_json_bytes(_receipt_payload(provisional))),
        )
    finally:
        current_paths = _git_snapshot_paths(root)
        if not source_unchanged and (
            current_paths != snapshot_paths or _snapshot(root, current_paths) != baseline_files
        ):
            raise ObjectNameRehearsalError("source tree changed during failed rehearsal cleanup")
