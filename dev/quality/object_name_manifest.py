"""Strict reviewed-intent boundary for object-name rename operations.

The object-name audit owns declaration and finding identity.  This module does
not reproduce that census or its hashes: it loads authored rename intent and
binds every row back to a current :class:`ObjectNameAuditResult` before any
planner or transformer may consume it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from cadrumo.core.hashing import canonical_json_bytes, prefixed_digest, sha256_file, validate_prefixed_digest
from cadrumo.core.link_safety import is_link_like
from cadrumo.core.toml import freeze_toml, read_toml

from ..audit.object_names import ObjectNameAuditResult, ObjectNameDeclaration, ObjectNameKind

__all__ = [
    "MANDATORY_OBJECT_NAME_GATES",
    "ObjectNameFilePrecondition",
    "ObjectNameGateCommand",
    "ObjectNameGateFamily",
    "ObjectNameManifestError",
    "ObjectNamePathMove",
    "ObjectNameRenameManifest",
    "ObjectNameRenameOperation",
    "load_object_name_manifest",
    "load_validated_object_name_manifest",
    "object_name_manifest_digest",
    "select_object_name_execution",
    "validate_object_name_manifest",
]


_DIGEST_PATTERN: Final[str] = r"^sha256:[0-9a-f]{64}$"
_IDENTIFIER_PATTERN: Final[str] = r"^[a-z0-9][a-z0-9-]*$"
_LOCATOR_PATTERN: Final[str] = r"^(?:module|class|enum|function):[A-Za-z_][A-Za-z0-9_.]*#binding=[1-9][0-9]*$"
_SOURCE_ROOTS: Final[frozenset[str]] = frozenset({"dev", "src"})

OperationKind = Literal["module-rename", "symbol-rename"]
OperationDisposition = Literal["lexical-singular", "rename-distinct", "merge-authority"]
OperationLifecycle = Literal["proposed", "reviewed", "retired"]
ReferenceClass = Literal[
    "definition",
    "static-import",
    "type-only-import",
    "dynamic-target",
    "export",
    "shared-consumer",
    "generated-artifact",
]
ObjectNameGateFamily = Literal[
    "parsing-import",
    "architecture",
    "semantic-overlap",
    "clone",
    "type-lint",
    "focused",
]


class ObjectNameManifestError(ValueError):
    """The reviewed rename manifest is malformed, ambiguous, or stale."""


class _StrictModel(BaseModel):
    """Immutable authored contract with no ignored fields or coercion."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ObjectNameGateCommand(_StrictModel):
    """One production-owned gate command with a closed evidence family."""

    family: ObjectNameGateFamily
    argv: tuple[str, ...] = Field(min_length=1)

    @field_validator("argv")
    @classmethod
    def _validate_argv(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not token for token in value):
            raise ValueError("gate argv must contain only non-empty tokens")
        return value


MANDATORY_OBJECT_NAME_GATES: Final[tuple[ObjectNameGateCommand, ...]] = (
    ObjectNameGateCommand(family="parsing-import", argv=("just", "check-imports")),
    ObjectNameGateCommand(family="architecture", argv=("just", "check-architecture")),
    ObjectNameGateCommand(family="semantic-overlap", argv=("just", "check-semantic")),
    ObjectNameGateCommand(family="clone", argv=("just", "audit-duplication")),
    ObjectNameGateCommand(family="type-lint", argv=("just", "check-types")),
    ObjectNameGateCommand(family="type-lint", argv=("just", "check-style")),
)


def _safe_repo_path(value: str) -> str:
    if not value or "\\" in value or ":" in value:
        raise ValueError("must be a normalized repository-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("must be a normalized repository-relative POSIX path")
    if path.parts[0] == ".git":
        raise ValueError("must not address repository metadata")
    return value


def _safe_source_path(value: str) -> str:
    _safe_repo_path(value)
    path = PurePosixPath(value)
    if not path.parts or path.parts[0] not in _SOURCE_ROOTS:
        raise ValueError("must be below src/ or dev/")
    return value


def _require_sorted_unique(values: tuple[str, ...], *, subject: str) -> None:
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{subject} must be sorted and unique")


class ObjectNameFilePrecondition(_StrictModel):
    """Expected exact bytes for one existing affected file."""

    path: str
    sha256: str = Field(pattern=_DIGEST_PATTERN)

    _validate_path = field_validator("path")(_safe_repo_path)

    @field_validator("sha256")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return validate_prefixed_digest(value, field_name="object-name file precondition")


class ObjectNamePathMove(_StrictModel):
    """One exact module source-to-target filesystem move."""

    source: str
    target: str

    _validate_paths = field_validator("source", "target")(_safe_source_path)

    @model_validator(mode="after")
    def _require_distinct_paths(self) -> ObjectNamePathMove:
        if self.source == self.target:
            raise ValueError("object-name move source and target must differ")
        return self


class ObjectNameRenameOperation(_StrictModel):
    """One reviewed lexical operation or non-executable adjudication."""

    operation_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    finding_id: str = Field(pattern=_DIGEST_PATTERN)
    operation_kind: OperationKind
    disposition: OperationDisposition
    lifecycle: OperationLifecycle
    old_locator: str = Field(pattern=_LOCATOR_PATTERN)
    old_path: str
    new_locator: str | None = Field(default=None, pattern=_LOCATOR_PATTERN)
    new_path: str | None = None
    owner: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    preconditions: tuple[ObjectNameFilePrecondition, ...] = Field(min_length=1)
    expected_reference_classes: tuple[ReferenceClass, ...] = Field(min_length=1)
    moves: tuple[ObjectNamePathMove, ...] = ()
    changed_paths: tuple[str, ...] = Field(min_length=1)
    generator_commands: tuple[tuple[str, ...], ...] = ()
    focused_gates: tuple[tuple[str, ...], ...] = Field(min_length=1)

    _validate_old_path = field_validator("old_path")(_safe_source_path)

    @field_validator("new_path")
    @classmethod
    def _validate_new_path(cls, value: str | None) -> str | None:
        return None if value is None else _safe_source_path(value)

    @field_validator("owner", "rationale")
    @classmethod
    def _require_meaningful_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must contain non-whitespace text")
        return value

    @field_validator("changed_paths")
    @classmethod
    def _validate_changed_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for path in value:
            _safe_repo_path(path)
        _require_sorted_unique(value, subject="changed paths")
        return value

    @field_validator("generator_commands", "focused_gates")
    @classmethod
    def _validate_commands(cls, value: tuple[tuple[str, ...], ...]) -> tuple[tuple[str, ...], ...]:
        if any(not argv or any(not token for token in argv) for argv in value):
            raise ValueError("commands must be non-empty argv arrays containing non-empty tokens")
        return value

    @model_validator(mode="after")
    def _validate_operation_shape(self) -> ObjectNameRenameOperation:
        precondition_paths = tuple(item.path for item in self.preconditions)
        _require_sorted_unique(precondition_paths, subject="preconditions")
        reference_classes = tuple(self.expected_reference_classes)
        _require_sorted_unique(reference_classes, subject="expected reference classes")
        if "definition" not in reference_classes:
            raise ValueError("expected reference classes must include definition")
        move_sources = tuple(move.source for move in self.moves)
        move_targets = tuple(move.target for move in self.moves)
        _require_sorted_unique(move_sources, subject="move sources")
        _require_sorted_unique(move_targets, subject="move targets")

        generated = "generated-artifact" in reference_classes
        if generated != bool(self.generator_commands):
            raise ValueError("generated-artifact references and generator commands must be declared together")

        executable = self.disposition in {"lexical-singular", "rename-distinct"}
        if not executable:
            if self.new_locator is not None or self.new_path is not None or self.moves:
                raise ValueError(
                    f"{self.disposition} is adjudication-only and must not declare rename targets or moves"
                )
            return self
        if self.lifecycle != "reviewed":
            raise ValueError("executable rename operations must have reviewed lifecycle")
        if self.new_locator is None or self.new_path is None:
            raise ValueError("executable rename operations require new_locator and new_path")
        if self.new_locator == self.old_locator:
            raise ValueError("executable rename locator must change")
        if self.new_locator.split(":", 1)[0] != self.old_locator.split(":", 1)[0]:
            raise ValueError("a rename must preserve the declaration kind")
        if self.operation_kind == "symbol-rename":
            if self.old_locator.startswith("module:") or self.new_locator.startswith("module:"):
                raise ValueError("symbol renames require non-module locators")
            if self.old_path != self.new_path or self.moves:
                raise ValueError("symbol renames stay in one file and declare no filesystem move")
        else:
            if not self.old_locator.startswith("module:") or not self.new_locator.startswith("module:"):
                raise ValueError("module renames require module locators")
            if PurePosixPath(self.new_path).suffix != ".py":
                raise ValueError("module rename targets must remain Python source files")
            if len(self.moves) != 1 or self.moves[0] != ObjectNamePathMove(source=self.old_path, target=self.new_path):
                raise ValueError("module renames require exactly the old_path to new_path move")
        required_changes = {self.old_path, self.new_path}
        required_changes.update(move.source for move in self.moves)
        required_changes.update(move.target for move in self.moves)
        if not required_changes.issubset(self.changed_paths):
            raise ValueError("changed paths must include every rename and move path")
        return self


class ObjectNameRenameManifest(_StrictModel):
    """Complete reviewed selection bound to one object-name inventory."""

    schema_version: Literal[1]
    inventory_digest: str = Field(pattern=_DIGEST_PATTERN)
    operations: tuple[ObjectNameRenameOperation, ...] = Field(min_length=1)

    @field_validator("inventory_digest")
    @classmethod
    def _validate_inventory_digest(cls, value: str) -> str:
        return validate_prefixed_digest(value, field_name="object-name inventory digest")

    @model_validator(mode="after")
    def _require_unambiguous_operations(self) -> ObjectNameRenameManifest:
        operation_ids = tuple(operation.operation_id for operation in self.operations)
        _require_sorted_unique(operation_ids, subject="operation ids")
        finding_dispositions: dict[str, set[OperationDisposition]] = {}
        for operation in self.operations:
            finding_dispositions.setdefault(operation.finding_id, set()).add(operation.disposition)
        if any(len(dispositions) != 1 for dispositions in finding_dispositions.values()):
            raise ValueError("each selected finding must have exactly one disposition")

        old_locators = tuple(operation.old_locator for operation in self.operations)
        if len(old_locators) != len(set(old_locators)):
            raise ValueError("each source locator must be claimed by exactly one operation")

        target_locators = tuple(
            operation.new_locator for operation in self.operations if operation.new_locator is not None
        )
        if len(target_locators) != len(set(target_locators)):
            raise ValueError("rename operations must not claim duplicate target locators")
        move_sources = tuple(move.source for operation in self.operations for move in operation.moves)
        move_targets = tuple(move.target for operation in self.operations for move in operation.moves)
        if len(move_sources) != len(set(move_sources)) or len(move_targets) != len(set(move_targets)):
            raise ValueError("rename operations must not claim duplicate move paths")
        return self


def load_object_name_manifest(path: Path) -> ObjectNameRenameManifest:
    """Load one regular strict TOML rename manifest without consulting live state."""
    if is_link_like(path) or not path.is_file():
        raise ObjectNameManifestError(f"object-name manifest must be a regular file: {path}")
    frozen = freeze_toml(read_toml(path, error_factory=ObjectNameManifestError))
    try:
        return ObjectNameRenameManifest.model_validate(frozen)
    except ValidationError as exc:
        raise ObjectNameManifestError(f"{path}: invalid object-name manifest: {exc}") from exc


def _locator_name(locator: str) -> str:
    qualified = locator.split(":", 1)[1].rsplit("#binding=", 1)[0]
    return qualified.rsplit(".", 1)[-1]


def _duplicates(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return tuple(sorted(duplicates))


def _repo_path_without_links(repo_root: Path, relative: str, *, operation_id: str) -> Path:
    """Resolve a lexical manifest path while refusing linked path components."""
    current = repo_root
    for part in PurePosixPath(relative).parts:
        current /= part
        if is_link_like(current):
            raise ObjectNameManifestError(
                f"operation {operation_id!r} path traverses a link-like component: {relative}",
            )
    return current


def validate_object_name_manifest(
    manifest: ObjectNameRenameManifest,
    *,
    inventory: ObjectNameAuditResult,
    repo_root: Path,
) -> ObjectNameRenameManifest:
    """Bind authored intent to the current inventory and exact working bytes."""
    findings_by_id = {finding.id: finding for finding in inventory.findings}
    declarations_by_locator: dict[str, list[ObjectNameDeclaration]] = {}
    for declaration in inventory.declarations:
        declarations_by_locator.setdefault(declaration.qualified_locator, []).append(declaration)

    selected_old_locators = {
        operation.old_locator
        for operation in manifest.operations
        if operation.disposition in {"lexical-singular", "rename-distinct"}
    }
    target_names = tuple(
        _locator_name(operation.new_locator) for operation in manifest.operations if operation.new_locator is not None
    )
    duplicate_target_names = _duplicates(target_names)
    if duplicate_target_names:
        raise ObjectNameManifestError(f"object-name manifest claims duplicate target names: {duplicate_target_names!r}")
    occupied_targets = tuple(
        sorted(
            {
                declaration.name
                for declaration in inventory.declarations
                if declaration.name in target_names and declaration.qualified_locator not in selected_old_locators
            },
        ),
    )
    if occupied_targets:
        raise ObjectNameManifestError(f"object-name manifest targets already exist: {occupied_targets!r}")

    for operation in manifest.operations:
        finding = findings_by_id.get(operation.finding_id)
        if finding is None:
            raise ObjectNameManifestError(f"operation {operation.operation_id!r} names a stale or unknown finding")
        if not finding.enforced:
            raise ObjectNameManifestError(f"operation {operation.operation_id!r} selects an advisory finding")
        if operation.old_locator not in finding.qualified_sites:
            raise ObjectNameManifestError(
                f"operation {operation.operation_id!r} old locator is not a site of finding {operation.finding_id}",
            )
        declarations = declarations_by_locator.get(operation.old_locator, [])
        if not declarations or any(declaration.path != operation.old_path for declaration in declarations):
            raise ObjectNameManifestError(f"operation {operation.operation_id!r} old declaration path is stale")
        old_kind = declarations[0].kind
        if operation.operation_kind == "module-rename" and old_kind is not ObjectNameKind.MODULE:
            raise ObjectNameManifestError(f"operation {operation.operation_id!r} is not a module declaration")
        if operation.operation_kind == "symbol-rename" and old_kind is ObjectNameKind.MODULE:
            raise ObjectNameManifestError(f"operation {operation.operation_id!r} is not a symbol declaration")
        if operation.new_locator is not None and _locator_name(operation.new_locator) == declarations[0].name:
            raise ObjectNameManifestError(
                f"operation {operation.operation_id!r} target must change the audited object name",
            )
        if operation.operation_kind == "module-rename" and (
            PurePosixPath(operation.old_path).suffix != ".py"
            or operation.new_path is None
            or PurePosixPath(operation.new_path).suffix != ".py"
        ):
            raise ObjectNameManifestError(f"operation {operation.operation_id!r} module paths must be Python files")
        expected_target_locator = None
        if operation.new_locator is not None and operation.new_path is not None:
            expected_target_locator = replace(
                declarations[0],
                name=_locator_name(operation.new_locator),
                path=operation.new_path,
            ).qualified_locator
        if operation.new_locator is not None and operation.new_locator != expected_target_locator:
            raise ObjectNameManifestError(
                f"operation {operation.operation_id!r} target path and locator disagree",
            )

        preconditions = {item.path: item.sha256 for item in operation.preconditions}
        declaration_hashes = {declaration.source_hash for declaration in declarations}
        if None in declaration_hashes or len(declaration_hashes) != 1:
            raise ObjectNameManifestError(
                f"operation {operation.operation_id!r} source hash is unavailable or ambiguous",
            )
        if preconditions.get(operation.old_path) != next(iter(declaration_hashes)):
            raise ObjectNameManifestError(
                f"operation {operation.operation_id!r} old-path precondition does not match the inventory source hash",
            )
        required_existing = {operation.old_path}
        for relative in operation.changed_paths:
            target = _repo_path_without_links(repo_root, relative, operation_id=operation.operation_id)
            if target.exists() or is_link_like(target):
                required_existing.add(relative)
        if set(preconditions) != required_existing:
            missing = sorted(required_existing - set(preconditions))
            stale = sorted(set(preconditions) - required_existing)
            raise ObjectNameManifestError(
                f"operation {operation.operation_id!r} preconditions are incomplete or stale; "
                f"missing={missing!r}, stale={stale!r}",
            )
        for relative, expected in preconditions.items():
            target = _repo_path_without_links(repo_root, relative, operation_id=operation.operation_id)
            if not target.is_file():
                raise ObjectNameManifestError(
                    f"operation {operation.operation_id!r} input is not a regular file: {relative}"
                )
            actual = f"sha256:{sha256_file(target)}"
            if actual != expected:
                raise ObjectNameManifestError(
                    f"operation {operation.operation_id!r} byte precondition is stale for {relative}",
                )
        if operation.operation_kind == "module-rename" and operation.new_path is not None:
            target = _repo_path_without_links(repo_root, operation.new_path, operation_id=operation.operation_id)
            if target.exists() or is_link_like(target):
                raise ObjectNameManifestError(
                    f"operation {operation.operation_id!r} module target already exists: {operation.new_path}",
                )
    return manifest


def load_validated_object_name_manifest(
    path: Path,
    *,
    inventory: ObjectNameAuditResult,
    repo_root: Path,
) -> ObjectNameRenameManifest:
    """Load authored intent and refuse every mismatch with current state."""
    return validate_object_name_manifest(load_object_name_manifest(path), inventory=inventory, repo_root=repo_root)


def select_object_name_execution(
    manifest: ObjectNameRenameManifest,
) -> tuple[ObjectNameRenameOperation, ...]:
    """Return only reviewed lexical operations; adjudications never execute."""
    return tuple(
        operation
        for operation in manifest.operations
        if operation.lifecycle == "reviewed" and operation.disposition in {"lexical-singular", "rename-distinct"}
    )


def object_name_manifest_digest(manifest: ObjectNameRenameManifest) -> str:
    """Return the canonical digest receipts use to bind reviewed intent."""
    return prefixed_digest(canonical_json_bytes(manifest.model_dump(mode="json")))
