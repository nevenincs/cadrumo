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
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Final, cast

from cadrumo.core.hashing import canonical_json_bytes, prefixed_digest, sha256_file
from cadrumo.core.link_safety import is_link_like

from ..audit.object_names import (
    ObjectNameAuditResult,
    ObjectNameFinding,
    ObjectNameFindingKind,
    analyse,
    collect_declarations,
    scan,
    to_json,
)
from .object_name_graph import (
    HardEdge,
    InventoryLike,
    ObjectNameGraphError,
    OperationComponent,
    ReferenceKind,
    RenameManifestLike,
    build_manifest_components,
    collect_import_edges,
    operation_locators,
)
from .object_name_manifest import (
    ObjectNameManifestError,
    ObjectNameRenameManifest,
    object_name_manifest_digest,
    select_object_name_execution,
    validate_object_name_manifest,
)
from .object_name_transform import ObjectNameTransformError, ObjectNameTransformResult, plan_object_name_transformation

__all__ = [
    "ObjectNameFindingDelta",
    "ObjectNameGateOutcome",
    "ObjectNameRehearsalError",
    "ObjectNameRehearsalReceipt",
    "canonical_object_name_component_set",
    "rehearse_object_name_component",
]

_RECEIPT_SCHEMA_VERSION: Final[int] = 1
_DIGEST_PREFIX: Final[str] = "sha256:"
_COMMAND_TIMEOUT_SECONDS: Final[int] = 1_800
_EXCLUDED_DIRECTORY_NAMES: Final[frozenset[str]] = frozenset(
    {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".venv", "__pycache__", "node_modules"}
)
_FIRST_PARTY_IMPORT_ROOTS: Final[tuple[str, ...]] = ("cadrumo", "cadrumo_harness", "dev")


class ObjectNameRehearsalError(RuntimeError):
    """The current tree cannot produce a safe successful rehearsal receipt."""


@contextmanager
def _isolated_first_party_import_state() -> Iterator[None]:
    """Keep live-tree imports from contaminating graph inspection in the copy."""
    owned = {
        name: module
        for name, module in tuple(sys.modules.items())
        if any(name == root or name.startswith(f"{root}.") for root in _FIRST_PARTY_IMPORT_ROOTS)
    }
    for name in owned:
        sys.modules.pop(name, None)
    try:
        yield
    finally:
        for name in tuple(sys.modules):
            if any(name == root or name.startswith(f"{root}.") for root in _FIRST_PARTY_IMPORT_ROOTS):
                sys.modules.pop(name, None)
        sys.modules.update(owned)


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
    baseline_files: tuple[tuple[str, str | None], ...]
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
    evidence_digest: str


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
    if (
        "\\" in relative
        or ":" in relative
        or candidate.is_absolute()
        or any(part in {"", ".", "..", ".git"} for part in candidate.parts)
    ):
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


def _snapshot(repo_root: Path, paths: Sequence[str]) -> tuple[tuple[str, str | None], ...]:
    files: list[tuple[str, str | None]] = []
    for relative in paths:
        path = _regular_file(repo_root, relative)
        try:
            digest = None if path is None else f"{_DIGEST_PREFIX}{sha256_file(path)}"
        except FileNotFoundError:
            # A concurrent tracked deletion between the existence check and
            # hashing is the same observable snapshot state as an absent file.
            digest = None
        files.append((relative, digest))
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


def _tree_digest(files: Sequence[tuple[str, str | None]]) -> str:
    return _digest_bytes(canonical_json_bytes({"schema_version": 1, "files": list(files)}))


def _inventory_after_allowed_changes(
    before: ObjectNameAuditResult,
    *,
    repo_root: Path,
    changed_paths: Sequence[str],
) -> ObjectNameAuditResult:
    """Re-analyse the inventory after an already-bounded set of Python edits."""
    changed_python = frozenset(path for path in changed_paths if PurePosixPath(path).suffix == ".py")
    if not changed_python:
        return before
    parents = tuple(sorted({repo_root.joinpath(*PurePosixPath(path).parts).parent for path in changed_python}))
    refreshed, refreshed_errors = collect_declarations(parents, repo_root)
    declarations = tuple(item for item in before.declarations if item.path not in changed_python) + tuple(
        item for item in refreshed if item.path in changed_python
    )
    retained_errors = tuple(
        finding
        for finding in before.findings
        if finding.kind is ObjectNameFindingKind.SOURCE_ERROR
        and not any(site in changed_python for site in finding.qualified_sites)
    )
    changed_errors = tuple(
        finding
        for finding in refreshed_errors
        if any(site in changed_python for site in finding.qualified_sites)
    )
    return analyse(
        tuple(sorted(declarations, key=lambda item: (item.path, item.line, item.kind, item.name))),
        retained_errors + changed_errors,
    )


def _copy_snapshot(
    source_root: Path,
    target_root: Path,
    files: Sequence[tuple[str, str | None]],
    *,
    guarded_paths: frozenset[str] | None = None,
) -> None:
    exact_paths = frozenset(path for path, _digest in files) if guarded_paths is None else guarded_paths
    exact_paths |= frozenset(path for path, _digest in files if PurePosixPath(path).suffix == ".py")
    for source_root_name in ("src", "dev"):
        (target_root / source_root_name).mkdir(parents=True, exist_ok=True)
    for relative, expected_digest in files:
        if expected_digest is None:
            continue
        source = _regular_file(source_root, relative)
        if source is None:
            if relative in exact_paths:
                raise ObjectNameRehearsalError(f"snapshot source disappeared during copy: {relative}")
            continue
        target = target_root.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)
        actual_digest = f"{_DIGEST_PREFIX}{sha256_file(target)}"
        if relative in exact_paths and actual_digest != expected_digest:
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


def _run_command(argv: tuple[str, ...], *, cwd: Path, environment: Mapping[str, str]) -> ObjectNameGateOutcome:
    try:
        completed = subprocess.run(  # noqa: S603
            argv,
            cwd=cwd,
            env=environment,
            capture_output=True,
            check=False,
            timeout=_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ObjectNameRehearsalError(f"cannot execute declared command {argv!r}") from exc
    return ObjectNameGateOutcome(
        argv=argv,
        return_code=completed.returncode,
        stdout_sha256=_digest_bytes(completed.stdout),
        stdout_bytes=len(completed.stdout),
        stderr_sha256=_digest_bytes(completed.stderr),
        stderr_bytes=len(completed.stderr),
    )


def _failed_command_message(outcome: ObjectNameGateOutcome) -> str:
    return (
        f"declared rehearsal command failed: argv={outcome.argv!r}, return_code={outcome.return_code}, "
        f"stdout_sha256={outcome.stdout_sha256}, stdout_bytes={outcome.stdout_bytes}, "
        f"stderr_sha256={outcome.stderr_sha256}, stderr_bytes={outcome.stderr_bytes}"
    )


def _tool_version(argv: tuple[str, ...], *, cwd: Path) -> str:
    try:
        completed = subprocess.run(  # noqa: S603
            argv,
            cwd=cwd,
            capture_output=True,
            check=False,
            text=True,
            timeout=_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ObjectNameRehearsalError(f"cannot determine tool version with {argv!r}") from exc
    if completed.returncode != 0:
        raise ObjectNameRehearsalError(f"tool version command failed: {argv!r}")
    return completed.stdout.strip()


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


def _receipt_payload(
    receipt: ObjectNameRehearsalReceipt,
    *,
    include_output_evidence: bool,
) -> Mapping[str, object]:
    payload: dict[str, object] = {
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
        "generator_outcomes": [
            asdict(outcome) if include_output_evidence else {"argv": outcome.argv, "return_code": outcome.return_code}
            for outcome in receipt.generator_outcomes
        ],
        "gate_outcomes": [
            asdict(outcome) if include_output_evidence else {"argv": outcome.argv, "return_code": outcome.return_code}
            for outcome in receipt.gate_outcomes
        ],
        "source_tree_unchanged": receipt.source_tree_unchanged,
    }
    return payload


def canonical_object_name_component_set(
    manifest: ObjectNameRenameManifest,
    *,
    inventory: ObjectNameAuditResult,
    repo_root: Path,
    graph_cache_dir: str | None = None,
) -> tuple[OperationComponent, ...]:
    """Derive canonical components from repository evidence and reviewed generator intent."""
    root = repo_root.resolve()
    try:
        graph_manifest = cast("RenameManifestLike", manifest)
        graph_inventory = cast("InventoryLike", inventory)
        discovered_edges = collect_import_edges(
            operation_locators(graph_manifest),
            repo_root=root,
            cache_dir=graph_cache_dir,
        )
        discovered_by_operation: dict[str, set[str]] = {}
        for edge in discovered_edges:
            discovered_by_operation.setdefault(edge.operation_id, set()).add(edge.path)
        derived_generator_edges: list[HardEdge] = []
        for operation in select_object_name_execution(manifest):
            if "generated-artifact" not in operation.expected_reference_classes:
                continue
            explicit_transform_paths = {operation.old_path, *(move.target for move in operation.moves)}
            generated_paths = (
                set(operation.changed_paths)
                - discovered_by_operation.get(operation.operation_id, set())
                - explicit_transform_paths
            )
            if not generated_paths:
                raise ObjectNameRehearsalError(
                    f"operation {operation.operation_id!r} declares generated artifacts without an output path"
                )
            generator_owner = canonical_json_bytes(operation.generator_commands).decode("utf-8")
            derived_generator_edges.extend(
                HardEdge(
                    operation.operation_id,
                    path,
                    ReferenceKind.GENERATED_ARTIFACT,
                    generator_owner=generator_owner,
                )
                for path in sorted(generated_paths)
            )
        return build_manifest_components(
            graph_manifest,
            inventory=graph_inventory,
            hard_edges=(*discovered_edges, *derived_generator_edges),
        )
    except ObjectNameGraphError as exc:
        raise ObjectNameRehearsalError(f"cannot reconstruct the reviewed component: {exc}") from exc


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
    graph_cache = tempfile.TemporaryDirectory(prefix="cadrumo-object-name-graph-")
    executable = {operation.operation_id: operation for operation in select_object_name_execution(manifest)}
    canonical_components = canonical_object_name_component_set(
        manifest,
        inventory=inventory,
        repo_root=root,
        graph_cache_dir=graph_cache.name,
    )
    canonical = next((item for item in canonical_components if item.component_id == component.component_id), None)
    if canonical is None or (
        canonical.component_id,
        canonical.operation_ids,
        canonical.affected_paths,
        canonical.hard_edges,
    ) != (
        component.component_id,
        component.operation_ids,
        component.affected_paths,
        component.hard_edges,
    ):
        raise ObjectNameRehearsalError("supplied component differs from the canonical repository graph")
    try:
        selected = tuple(executable[operation_id] for operation_id in component.operation_ids)
    except KeyError as exc:
        raise ObjectNameRehearsalError(f"reviewed component names a non-executable operation: {exc.args[0]}") from exc
    generated_paths_by_operation = {
        operation.operation_id: frozenset(
            edge.path
            for edge in component.hard_edges
            if edge.operation_id == operation.operation_id and edge.kind is ReferenceKind.GENERATED_ARTIFACT
        )
        for operation in selected
    }
    transform_operations = tuple(
        operation.model_copy(
            update={
                "changed_paths": tuple(
                    path
                    for path in operation.changed_paths
                    if path not in generated_paths_by_operation[operation.operation_id]
                ),
                "expected_reference_classes": tuple(
                    kind for kind in operation.expected_reference_classes if kind != "generated-artifact"
                ),
                "generator_commands": (),
            }
        )
        for operation in selected
    )
    component_manifest = manifest.model_copy(update={"operations": transform_operations})
    allowed_paths = tuple(sorted({path for operation in selected for path in operation.changed_paths}))
    transform_allowed_paths = tuple(
        sorted({path for operation in transform_operations for path in operation.changed_paths})
    )
    try:
        validate_object_name_manifest(manifest, inventory=inventory, repo_root=root)
    except ObjectNameManifestError as exc:
        raise ObjectNameRehearsalError(f"reviewed manifest is not current: {exc}") from exc

    snapshot_paths = _git_snapshot_paths(root)
    baseline_files = _snapshot(root, snapshot_paths)
    input_paths = tuple(sorted({item.path for operation in selected for item in operation.preconditions}))
    guarded_paths = tuple(sorted(set(input_paths) | set(allowed_paths)))
    receipt_baseline_files = _snapshot(root, guarded_paths)
    baseline_tree_digest = _tree_digest(receipt_baseline_files)
    baseline_by_path = dict(baseline_files)
    try:
        input_file_digests = tuple(
            (path, digest) for path in input_paths if (digest := baseline_by_path[path]) is not None
        )
    except KeyError as exc:
        raise ObjectNameRehearsalError(f"manifest input is absent from the current snapshot: {exc.args[0]}") from exc
    if len(input_file_digests) != len(input_paths):
        raise ObjectNameRehearsalError("manifest input is a tracked deletion in the current snapshot")

    system_temporary_candidate = Path(tempfile.gettempdir())
    if is_link_like(system_temporary_candidate):
        raise ObjectNameRehearsalError(f"system temporary root is unsafe: {system_temporary_candidate}")
    system_temporary_root = system_temporary_candidate.resolve()
    if (
        not system_temporary_root.is_dir()
        or is_link_like(system_temporary_root)
        or system_temporary_root.is_relative_to(root)
    ):
        raise ObjectNameRehearsalError(f"system temporary root is unsafe: {system_temporary_root}")
    try:
        temporary_parent = Path(tempfile.mkdtemp(prefix="cadrumo-object-name-", dir=system_temporary_root)).resolve()
    except OSError as exc:
        raise ObjectNameRehearsalError("cannot allocate the system-temporary rehearsal root") from exc
    temporary_root = temporary_parent / "repository"
    source_unchanged = False
    try:
        if temporary_parent.parent != system_temporary_root or is_link_like(temporary_parent):
            raise ObjectNameRehearsalError(f"allocated rehearsal parent is unsafe: {temporary_parent}")
        temporary_root.mkdir()
        _copy_snapshot(root, temporary_root, baseline_files, guarded_paths=frozenset(guarded_paths))
        copied_baseline_files = _snapshot(temporary_root, tuple(path for path, _digest in baseline_files))
        if _snapshot(temporary_root, guarded_paths) != receipt_baseline_files:
            raise ObjectNameRehearsalError("selected component bytes changed during the temporary copy")
        copied_inventory = scan((temporary_root / "src", temporary_root / "dev"), temporary_root)
        with _isolated_first_party_import_state():
            copied_components = canonical_object_name_component_set(
                manifest,
                inventory=copied_inventory,
                repo_root=temporary_root,
                graph_cache_dir=graph_cache.name,
            )
        copied_component = next(
            (item for item in copied_components if item.component_id == component.component_id),
            None,
        )
        if copied_component is None or (
            copied_component.operation_ids,
            copied_component.affected_paths,
            copied_component.hard_edges,
        ) != (
            component.operation_ids,
            component.affected_paths,
            component.hard_edges,
        ):
            raise ObjectNameRehearsalError("copied repository graph differs from the reviewed component")
        copied_inventory_digest = cast("str", to_json(copied_inventory)["inventory_digest"])
        if not isinstance(copied_inventory_digest, str):
            raise ObjectNameRehearsalError("copied inventory did not emit a string digest")
        try:
            result = plan_object_name_transformation(component_manifest, repo_root=temporary_root)
        except ObjectNameTransformError as exc:
            raise ObjectNameRehearsalError(f"bounded transformation refused: {exc}") from exc
        if result.changed_paths != transform_allowed_paths:
            raise ObjectNameRehearsalError("transformation paths differ from the reviewed allowlist")
        _materialise(temporary_root, result)

        generator_argv = tuple(command for operation in selected for command in operation.generator_commands)
        gate_argv = tuple(command for operation in selected for command in operation.focused_gates)
        command_environment = os.environ.copy()
        command_environment["VIRTUAL_ENV"] = sys.prefix
        command_environment["UV_PROJECT_ENVIRONMENT"] = sys.prefix
        command_environment["PYTHONPATH"] = os.pathsep.join((str(temporary_root / "src"), str(temporary_root)))
        generator_results: list[ObjectNameGateOutcome] = []
        gate_results: list[ObjectNameGateOutcome] = []
        for argv in generator_argv:
            outcome = _run_command(argv, cwd=temporary_root, environment=command_environment)
            generator_results.append(outcome)
            if outcome.return_code != 0:
                raise ObjectNameRehearsalError(_failed_command_message(outcome))
        for argv in gate_argv:
            outcome = _run_command(argv, cwd=temporary_root, environment=command_environment)
            gate_results.append(outcome)
            if outcome.return_code != 0:
                raise ObjectNameRehearsalError(_failed_command_message(outcome))
        generator_outcomes = tuple(generator_results)
        gate_outcomes = tuple(gate_results)

        after_inventory = _inventory_after_allowed_changes(
            copied_inventory,
            repo_root=temporary_root,
            changed_paths=allowed_paths,
        )
        finding_delta = _finding_delta(copied_inventory, after_inventory)
        if finding_delta.after_count > finding_delta.before_count or finding_delta.introduced_signatures:
            raise ObjectNameRehearsalError("rehearsal introduces an enforced object-name finding")

        after_paths = _temporary_paths(temporary_root)
        after_files = _snapshot(temporary_root, after_paths)
        changed = tuple(
            sorted(
                path
                for path in set(dict(copied_baseline_files)) | set(dict(after_files))
                if dict(copied_baseline_files).get(path) != dict(after_files).get(path)
            )
        )
        if changed != allowed_paths:
            raise ObjectNameRehearsalError("materialised changed paths differ from the reviewed allowlist")
        proposed_digests = tuple((path, dict(after_files).get(path)) for path in changed)
        changed_path_digest = _digest_bytes(canonical_json_bytes(list(changed)))
        tool_versions = tuple(
            sorted(
                (
                    ("git", _tool_version(("git", "--version"), cwd=temporary_root)),
                    ("libcst", importlib.metadata.version("libcst")),
                    ("python", sys.version.split()[0]),
                    ("rehearsal", str(_RECEIPT_SCHEMA_VERSION)),
                    (
                        "runtime-environment",
                        _digest_bytes(canonical_json_bytes({"executable": sys.executable, "prefix": sys.prefix})),
                    ),
                    ("uv", _tool_version(("uv", "--version"), cwd=temporary_root)),
                )
            )
        )
        source_unchanged = _snapshot(root, guarded_paths) == receipt_baseline_files
        if not source_unchanged:
            raise ObjectNameRehearsalError("source tree changed while rehearsal was running")
        provisional = ObjectNameRehearsalReceipt(
            schema_version=_RECEIPT_SCHEMA_VERSION,
            rehearsal_root=str(temporary_root),
            manifest_digest=object_name_manifest_digest(manifest),
            inventory_digest=copied_inventory_digest,
            component_id=component.component_id,
            operation_ids=component.operation_ids,
            baseline_tree_digest=baseline_tree_digest,
            baseline_files=receipt_baseline_files,
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
            evidence_digest="",
        )
        stable_receipt = replace(
            provisional,
            receipt_id=_digest_bytes(
                canonical_json_bytes(_receipt_payload(provisional, include_output_evidence=False))
            ),
        )
        return replace(
            stable_receipt,
            evidence_digest=_digest_bytes(
                canonical_json_bytes(_receipt_payload(stable_receipt, include_output_evidence=True))
            ),
        )
    except ObjectNameRehearsalError as exc:
        raise ObjectNameRehearsalError(f"{exc}; retained rehearsal root: {temporary_root}") from exc
    except Exception as exc:
        raise ObjectNameRehearsalError(f"rehearsal failed; retained rehearsal root: {temporary_root}") from exc
    finally:
        graph_cache.cleanup()
        try:
            final_source_unchanged = _snapshot(root, guarded_paths) == receipt_baseline_files
        except Exception as exc:
            raise ObjectNameRehearsalError(
                f"cannot verify source immutability; retained rehearsal root: {temporary_root}"
            ) from exc
        if not final_source_unchanged:
            raise ObjectNameRehearsalError(
                f"source tree changed during rehearsal; retained rehearsal root: {temporary_root}"
            )
