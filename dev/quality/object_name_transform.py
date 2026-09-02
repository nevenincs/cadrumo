"""Bounded, read-only planning for reviewed object-name transformations.

The transformer is deliberately not a filesystem mutation API.  It validates the
manifest's raw-byte preconditions, computes the complete proposed byte set, and
returns explicit move and output records for rehearsal or replay to consume.
Unsupported reference classes and ambiguous LibCST metadata fail closed.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, cast, override

import libcst as cst
from libcst.metadata import (
    CodeRange,
    MetadataWrapper,
    PositionProvider,
    QualifiedName,
    QualifiedNameProvider,
    QualifiedNameSource,
)

from cadrumo.core.link_safety import is_link_like
from dev.audit.object_names import declarations_in_source
from dev.quality.object_name_manifest import (
    ObjectNameRenameManifest,
    ObjectNameRenameOperation,
    select_object_name_execution,
)

__all__ = [
    "ObjectNameProposedMove",
    "ObjectNameProposedOutput",
    "ObjectNameTransformError",
    "ObjectNameTransformResult",
    "plan_object_name_transformations",
]


_SHA256_PREFIX: Final[str] = "sha256:"
_UNSUPPORTED_REFERENCE_CLASSES: Final[frozenset[str]] = frozenset({"dynamic-target", "generated-artifact"})


class ObjectNameTransformError(RuntimeError):
    """A reviewed operation cannot be transformed within its declared bounds."""


@dataclass(frozen=True, slots=True)
class ObjectNameProposedOutput:
    """The complete proposed state of one changed repository path.

    ``content=None`` is an explicit deletion.  ``original_sha256=None`` identifies
    a path that must not exist before replay.
    """

    path: str
    original_sha256: str | None
    content: bytes | None


@dataclass(frozen=True, slots=True)
class ObjectNameProposedMove:
    """One explicit source-to-target Python module move."""

    source: str
    target: str


@dataclass(frozen=True, slots=True)
class ObjectNameTransformResult:
    """Immutable proposed outputs; constructing this result performs no writes."""

    outputs: tuple[ObjectNameProposedOutput, ...]
    moves: tuple[ObjectNameProposedMove, ...]

    @property
    def changed_paths(self) -> tuple[str, ...]:
        """Return the exact paths whose proposed bytes differ from the live tree."""
        return tuple(output.path for output in self.outputs)

    def content_by_path(self) -> Mapping[str, bytes | None]:
        """Return a fresh path-to-proposed-content view."""
        return {output.path: output.content for output in self.outputs}


def _sha256(payload: bytes) -> str:
    return f"{_SHA256_PREFIX}{hashlib.sha256(payload).hexdigest()}"


def _locator_parts(locator: str) -> tuple[str, str, int]:
    try:
        kind, qualified_binding = locator.split(":", 1)
        qualified, binding = qualified_binding.rsplit("#binding=", 1)
        occurrence = int(binding)
    except (TypeError, ValueError) as exc:
        raise ObjectNameTransformError(f"malformed object-name locator: {locator!r}") from exc
    if occurrence < 1:
        raise ObjectNameTransformError(f"invalid binding occurrence in locator: {locator!r}")
    return kind, qualified, occurrence


def _module_for_path(relative: str) -> str:
    parts = list(PurePosixPath(relative).with_suffix("").parts)
    if parts and parts[0] == "src":
        parts.pop(0)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _import_package(module: str, relative: str) -> str:
    """Return the package Python uses to resolve relative imports in a path."""
    if PurePosixPath(relative).name == "__init__.py":
        return module
    return module.rpartition(".")[0]


def _resolve_repo_path(repo_root: Path, relative: str) -> Path:
    candidate = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or ":" in relative
        or candidate.is_absolute()
        or candidate.as_posix() != relative
        or any(part in {"", ".", ".."} for part in candidate.parts)
        or candidate.parts[0] == ".git"
    ):
        raise ObjectNameTransformError(f"unsafe repository path: {relative!r}")
    current = repo_root
    for part in candidate.parts:
        current /= part
        if is_link_like(current):
            raise ObjectNameTransformError(f"path traverses a link-like component: {relative}")
    return current


def _dotted_name(node: cst.BaseExpression | None) -> str | None:
    if node is None:
        return ""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        owner = _dotted_name(node.value)
        return None if owner is None else f"{owner}.{node.attr.value}"
    return None


def _dotted_expression(value: str) -> cst.BaseExpression:
    expression = cst.parse_expression(value)
    if not isinstance(expression, (cst.Name, cst.Attribute)):
        raise ObjectNameTransformError(f"module target is not a dotted name: {value!r}")
    return expression


def _absolute_import_from(node: cst.ImportFrom, module_name: str, *, package_module: bool) -> str | None:
    dotted = _dotted_name(node.module)
    if dotted is None:
        return None
    if not node.relative:
        return dotted
    package = module_name if package_module else module_name.rpartition(".")[0]
    relative = f"{'.' * len(node.relative)}{dotted}"
    try:
        return importlib.util.resolve_name(relative, package)
    except (ImportError, ValueError):
        return None


def _qualified_names(transformer: _RenameTransformer, node: cst.CSTNode) -> frozenset[QualifiedName]:
    return frozenset(cast("set[QualifiedName]", transformer.get_metadata(QualifiedNameProvider, node, set())))


class _RenameTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider, QualifiedNameProvider)

    def __init__(
        self,
        *,
        path: str,
        module_name: str,
        package_module: bool,
        operations: Sequence[ObjectNameRenameOperation],
        definition_lines: Mapping[str, frozenset[int]],
    ) -> None:
        self.path = path
        self.module_name = module_name
        self.package_module = package_module
        self.operations = operations
        self.definition_lines = definition_lines
        self.definition_hits: defaultdict[str, int] = defaultdict(int)
        self.reference_hits: defaultdict[str, int] = defaultdict(int)
        self._declaration_name_nodes: set[int] = set()

    def _operation_names(self, operation: ObjectNameRenameOperation) -> tuple[str, str, str, str]:
        _old_kind, old_qualified, _old_occurrence = _locator_parts(operation.old_locator)
        if operation.new_locator is None:
            raise ObjectNameTransformError(f"operation {operation.operation_id!r} has no target locator")
        _new_kind, new_qualified, _new_occurrence = _locator_parts(operation.new_locator)
        if operation.operation_kind == "module-rename":
            return old_qualified, old_qualified.rsplit(".", 1)[-1], new_qualified, new_qualified.rsplit(".", 1)[-1]
        old_module, _, old_name = old_qualified.rpartition(".")
        new_module, _, new_name = new_qualified.rpartition(".")
        if old_module != new_module:
            raise ObjectNameTransformError(f"symbol operation {operation.operation_id!r} changes its owning module")
        return old_module, old_name, new_module, new_name

    @override
    def visit_ClassDef(self, node: cst.ClassDef) -> bool | None:
        self._declaration_name_nodes.add(id(node.name))
        return True

    @override
    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool | None:
        self._declaration_name_nodes.add(id(node.name))
        return True

    @override
    def visit_SimpleString(self, node: cst.SimpleString) -> bool | None:
        try:
            value = node.evaluated_value
        except Exception as exc:
            raise ObjectNameTransformError(f"cannot evaluate a string literal in {self.module_name}") from exc
        if not isinstance(value, str):
            return True
        self._refuse_opaque_spelling(value)
        return True

    @override
    def visit_FormattedStringText(self, node: cst.FormattedStringText) -> bool | None:
        self._refuse_opaque_spelling(node.value)
        return True

    def _refuse_opaque_spelling(self, value: str) -> None:
        for operation in self.operations:
            old_module, old_name, _new_module, _new_name = self._operation_names(operation)
            spellings = (old_module,) if operation.operation_kind == "module-rename" else (old_name,)
            if any(
                re.search(rf"(?<![A-Za-z0-9_]){re.escape(spelling)}(?![A-Za-z0-9_])", value) for spelling in spellings
            ):
                raise ObjectNameTransformError(
                    f"operation {operation.operation_id!r} has an unsupported string reference in {self.module_name}"
                )

    @override
    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:
        return updated_node.with_changes(name=self._renamed_definition(original_node.name, updated_node.name))

    @override
    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.FunctionDef:
        return updated_node.with_changes(name=self._renamed_definition(original_node.name, updated_node.name))

    def _renamed_definition(self, original: cst.Name, updated: cst.Name) -> cst.Name:
        position = cast("CodeRange", self.get_metadata(PositionProvider, original))  # ty: ignore[redundant-cast]
        line = position.start.line
        for operation in self.operations:
            if operation.operation_kind != "symbol-rename" or line not in self.definition_lines[operation.operation_id]:
                continue
            _module, old_name, _new_module, new_name = self._operation_names(operation)
            if original.value != old_name:
                raise ObjectNameTransformError(
                    f"operation {operation.operation_id!r} definition line no longer names {old_name!r}"
                )
            self.definition_hits[operation.operation_id] += 1
            return updated.with_changes(value=new_name)
        return updated

    @override
    def leave_ImportAlias(self, original_node: cst.ImportAlias, updated_node: cst.ImportAlias) -> cst.ImportAlias:
        dotted = _dotted_name(original_node.name)
        if dotted is None:
            raise ObjectNameTransformError("unsupported non-dotted import target")
        for operation in self.operations:
            old_module, old_name, new_module, _new_name = self._operation_names(operation)
            if operation.operation_kind == "module-rename" and dotted == old_module:
                self.reference_hits[operation.operation_id] += 1
                return updated_node.with_changes(name=_dotted_expression(new_module))
            if operation.operation_kind == "symbol-rename" and dotted == old_name:
                # ImportFrom ownership is handled by leave_ImportFrom; an unqualified
                # alias here cannot establish the symbol's defining module.
                continue
        return updated_node

    @override
    def leave_ImportFrom(self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom) -> cst.ImportFrom:
        if original_node.relative:
            for operation in self.operations:
                if operation.operation_kind != "module-rename" or operation.old_path != self.path:
                    continue
                old_module, _old_name, new_module, _new_name = self._operation_names(operation)
                assert operation.new_path is not None
                old_package = _import_package(old_module, operation.old_path)
                new_package = _import_package(new_module, operation.new_path)
                if old_package != new_package:
                    raise ObjectNameTransformError(
                        f"operation {operation.operation_id!r} moves relative-import source across packages"
                    )
        absolute = _absolute_import_from(original_node, self.module_name, package_module=self.package_module)
        if absolute is None or isinstance(original_node.names, cst.ImportStar):
            if isinstance(original_node.names, cst.ImportStar):
                for operation in self.operations:
                    old_module, _old_name, _new_module, _new_name = self._operation_names(operation)
                    if absolute == old_module:
                        raise ObjectNameTransformError(
                            f"operation {operation.operation_id!r} reaches an unsupported star import"
                        )
            return updated_node

        rewritten_module = updated_node.module
        rewritten_relative = updated_node.relative
        rewritten_aliases: list[cst.ImportAlias] = list(cast("Sequence[cst.ImportAlias]", updated_node.names))
        for operation in self.operations:
            old_module, old_name, new_module, new_name = self._operation_names(operation)
            if operation.operation_kind == "symbol-rename" and absolute == old_module:
                changed = False
                aliases: list[cst.ImportAlias] = []
                for alias in rewritten_aliases:
                    if _dotted_name(alias.name) == old_name:
                        aliases.append(alias.with_changes(name=cst.Name(new_name)))
                        changed = True
                    else:
                        aliases.append(alias)
                if changed:
                    rewritten_aliases = aliases
                    self.reference_hits[operation.operation_id] += 1
            elif operation.operation_kind == "module-rename":
                if absolute == old_module:
                    rewritten_module = _dotted_expression(new_module)
                    rewritten_relative = ()
                    self.reference_hits[operation.operation_id] += 1
                elif absolute == old_module.rpartition(".")[0]:
                    old_parent, _, _ = old_module.rpartition(".")
                    new_parent, _, _ = new_module.rpartition(".")
                    matching = [alias for alias in rewritten_aliases if _dotted_name(alias.name) == old_name]
                    if matching:
                        if len(rewritten_aliases) != 1 and old_parent != new_parent:
                            raise ObjectNameTransformError(
                                f"operation {operation.operation_id!r} cannot split a cross-package mixed import"
                            )
                        rewritten_aliases = [
                            alias.with_changes(name=cst.Name(new_name))
                            if _dotted_name(alias.name) == old_name
                            else alias
                            for alias in rewritten_aliases
                        ]
                        if old_parent != new_parent:
                            rewritten_module = _dotted_expression(new_parent)
                            rewritten_relative = ()
                        self.reference_hits[operation.operation_id] += 1
        return updated_node.with_changes(
            module=rewritten_module,
            relative=rewritten_relative,
            names=tuple(rewritten_aliases),
        )

    @override
    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.BaseExpression:
        names = _qualified_names(self, original_node)
        for operation in self.operations:
            old_module, old_name, new_module, new_name = self._operation_names(operation)
            target = f"{old_module}.{old_name}" if operation.operation_kind == "symbol-rename" else old_module
            matching = {name for name in names if name.name == target}
            if not matching:
                continue
            if names != frozenset(matching):
                raise ObjectNameTransformError(
                    f"operation {operation.operation_id!r} has an ambiguous qualified attribute reference"
                )
            self.reference_hits[operation.operation_id] += 1
            if operation.operation_kind == "symbol-rename":
                return updated_node.with_changes(attr=cst.Name(new_name))
            return _dotted_expression(new_module)
        return updated_node

    @override
    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        if id(original_node) in self._declaration_name_nodes:
            return updated_node
        names = _qualified_names(self, original_node)
        for operation in self.operations:
            old_module, old_name, _new_module, new_name = self._operation_names(operation)
            if original_node.value != old_name:
                continue
            target_names = {old_module, f"{old_module}.{old_name}"}
            matching = {name for name in names if name.name in target_names}
            local_definition_reference = (
                operation.operation_kind == "symbol-rename"
                and self.module_name == old_module
                and QualifiedName(old_name, QualifiedNameSource.LOCAL) in names
            )
            if not matching and not local_definition_reference:
                continue
            permitted: set[QualifiedName] = set(matching)
            if local_definition_reference:
                permitted.add(QualifiedName(old_name, QualifiedNameSource.LOCAL))
            if names != frozenset(permitted):
                raise ObjectNameTransformError(
                    f"operation {operation.operation_id!r} has an ambiguous qualified name reference"
                )
            self.reference_hits[operation.operation_id] += 1
            return updated_node.with_changes(value=new_name)
        return updated_node


def _definition_lines(operation: ObjectNameRenameOperation, source: bytes) -> frozenset[int]:
    if operation.operation_kind == "module-rename":
        return frozenset[int]()
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ObjectNameTransformError(f"operation {operation.operation_id!r} definition source is not UTF-8") from exc
    declarations = declarations_in_source(text, operation.old_path)
    line_values: set[int] = set()
    for declaration in declarations:
        if declaration.qualified_locator == operation.old_locator:
            line_values.add(declaration.line)
    lines = frozenset(line_values)
    if not lines:
        raise ObjectNameTransformError(f"operation {operation.operation_id!r} definition binding is absent")
    return lines


def _transform_python(
    source: bytes,
    *,
    relative: str,
    operations: Sequence[ObjectNameRenameOperation],
    definition_lines: Mapping[str, frozenset[int]],
) -> tuple[bytes, _RenameTransformer]:
    try:
        module = cst.parse_module(source)
    except (UnicodeDecodeError, cst.ParserSyntaxError) as exc:
        raise ObjectNameTransformError(f"cannot parse affected Python source {relative}: {exc}") from exc
    transformer = _RenameTransformer(
        path=relative,
        module_name=_module_for_path(relative),
        package_module=PurePosixPath(relative).name == "__init__.py",
        operations=operations,
        definition_lines=definition_lines,
    )
    try:
        changed = MetadataWrapper(module).visit(transformer)
    except (KeyError, RecursionError) as exc:
        raise ObjectNameTransformError(f"cannot resolve metadata for {relative}: {exc}") from exc
    return changed.bytes, transformer


def plan_object_name_transformations(
    manifest: ObjectNameRenameManifest,
    *,
    repo_root: Path,
) -> ObjectNameTransformResult:
    """Compute an exact, fail-closed transformation without writing live files."""
    selected = tuple(sorted(select_object_name_execution(manifest), key=lambda operation: operation.operation_id))
    if not selected:
        raise ObjectNameTransformError("at least one reviewed operation is required")
    if len({operation.operation_id for operation in selected}) != len(selected):
        raise ObjectNameTransformError("operation identifiers must be unique")
    root = repo_root.resolve()
    if not (root / "src").is_dir() or not (root / "dev").is_dir():
        raise ObjectNameTransformError(f"repository root lacks src/ or dev/: {root}")

    allowlist = {path for operation in selected for path in operation.changed_paths}
    expected_hashes: dict[str, str] = {}
    for operation in selected:
        unsupported = _UNSUPPORTED_REFERENCE_CLASSES.intersection(operation.expected_reference_classes)
        if unsupported:
            raise ObjectNameTransformError(
                f"operation {operation.operation_id!r} declares unsupported reference classes: {sorted(unsupported)!r}"
            )
        for precondition in operation.preconditions:
            prior = expected_hashes.setdefault(precondition.path, precondition.sha256)
            if prior != precondition.sha256:
                raise ObjectNameTransformError(f"operations disagree on the byte precondition for {precondition.path}")

    before: dict[str, bytes] = {}
    for relative, expected in sorted(expected_hashes.items()):
        path = _resolve_repo_path(root, relative)
        if not path.is_file():
            raise ObjectNameTransformError(f"precondition path is not a regular file: {relative}")
        payload = path.read_bytes()
        if _sha256(payload) != expected:
            raise ObjectNameTransformError(f"byte precondition is stale for {relative}")
        before[relative] = payload

    move_by_source: dict[str, str] = {}
    move_targets: set[str] = set()
    for operation in selected:
        if operation.operation_kind == "module-rename":
            if len(operation.moves) != 1:
                raise ObjectNameTransformError(
                    f"module operation {operation.operation_id!r} must declare exactly one move"
                )
            move = operation.moves[0]
            if move.source in move_by_source or move.target in move_targets:
                raise ObjectNameTransformError("module move paths must be unique")
            target = _resolve_repo_path(root, move.target)
            if target.exists() or is_link_like(target):
                raise ObjectNameTransformError(f"module move target already exists: {move.target}")
            move_by_source[move.source] = move.target
            move_targets.add(move.target)

    lines_by_operation = {
        operation.operation_id: _definition_lines(operation, before[operation.old_path]) for operation in selected
    }
    operations_by_path: defaultdict[str, list[ObjectNameRenameOperation]] = defaultdict(list)
    for relative in expected_hashes:
        for operation in selected:
            if relative in operation.changed_paths:
                operations_by_path[relative].append(operation)

    proposed: dict[str, bytes | None] = dict(before)
    all_definition_hits: defaultdict[str, int] = defaultdict(int)
    all_reference_hits: defaultdict[str, int] = defaultdict(int)
    for relative, path_operations in sorted(operations_by_path.items()):
        if PurePosixPath(relative).suffix != ".py":
            raise ObjectNameTransformError(f"unsupported non-Python changed path: {relative}")
        transformed, transformer = _transform_python(
            before[relative],
            relative=relative,
            operations=path_operations,
            definition_lines=lines_by_operation,
        )
        proposed[relative] = transformed
        for operation_id, count in transformer.definition_hits.items():
            all_definition_hits[operation_id] += count
        for operation_id, count in transformer.reference_hits.items():
            all_reference_hits[operation_id] += count

    for operation in selected:
        if operation.operation_kind == "symbol-rename":
            expected_definitions = len(lines_by_operation[operation.operation_id])
            if all_definition_hits[operation.operation_id] != expected_definitions:
                raise ObjectNameTransformError(
                    f"operation {operation.operation_id!r} transformed "
                    f"{all_definition_hits[operation.operation_id]} of {expected_definitions} definitions"
                )
        elif all_reference_hits[operation.operation_id] == 0:
            # The move itself is the definition transformation; references are optional.
            pass

    for source, target in sorted(move_by_source.items()):
        if source not in proposed:
            raise ObjectNameTransformError(f"move source has no byte precondition: {source}")
        proposed[target] = proposed[source]
        proposed[source] = None

    actual = {
        relative
        for relative, payload in proposed.items()
        if payload is None or relative not in before or payload != before[relative]
    }
    if actual != allowlist:
        raise ObjectNameTransformError(
            "proposed changed paths differ from the reviewed allowlist; "
            f"missing={sorted(allowlist - actual)!r}, unexpected={sorted(actual - allowlist)!r}"
        )

    outputs = tuple(
        ObjectNameProposedOutput(
            path=relative,
            original_sha256=_sha256(before[relative]) if relative in before else None,
            content=proposed[relative],
        )
        for relative in sorted(actual)
    )
    moves = tuple(
        ObjectNameProposedMove(source=source, target=target) for source, target in sorted(move_by_source.items())
    )
    return ObjectNameTransformResult(outputs=outputs, moves=moves)
