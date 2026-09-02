"""Bounded LibCST transformations for reviewed object-name renames.

The transformer is deliberately not a discovery tool.  It consumes the strict
manifest contract, checks the exact input bytes again, computes every result in
memory, and refuses the whole component before a filesystem write when syntax or
scope cannot be proved safe.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
from typing import Final

import libcst as cst
from libcst.metadata import MetadataWrapper, QualifiedNameProvider

from cadrumo.core.link_safety import is_link_like
from dev.quality.object_name_manifest import ObjectNameRenameManifest, ObjectNameRenameOperation

__all__ = [
    "ObjectNameChange",
    "ObjectNameTransformError",
    "ObjectNameTransformResult",
    "apply_object_name_transformations",
    "plan_object_name_transformations",
]


_DYNAMIC_IMPORTS: Final[frozenset[str]] = frozenset(
    {"__import__", "builtins.__import__", "import_module", "importlib.import_module"}
)


class ObjectNameTransformError(ValueError):
    """A reviewed rename cannot be represented as one bounded safe transform."""


@dataclass(frozen=True, slots=True)
class ObjectNameChange:
    """One deterministic before/after filesystem entry."""

    path: str
    before_sha256: str | None
    after_sha256: str | None
    content: bytes | None


@dataclass(frozen=True, slots=True)
class ObjectNameTransformResult:
    """A completely validated component transformation, ready for replay."""

    changes: tuple[ObjectNameChange, ...]

    @property
    def changed_paths(self) -> tuple[str, ...]:
        return tuple(change.path for change in self.changes)


@dataclass(frozen=True, slots=True)
class _Rename:
    operation_id: str
    old_module: str
    new_module: str
    old_symbol: str | None
    new_symbol: str | None
    binding: int


def _digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _locator_parts(locator: str) -> tuple[str, str, int]:
    kind, value = locator.split(":", 1)
    qualified, binding_text = value.rsplit("#binding=", 1)
    return kind, qualified, int(binding_text)


def _operation_rename(operation: ObjectNameRenameOperation) -> _Rename:
    if operation.new_locator is None:
        raise ObjectNameTransformError(f"operation {operation.operation_id!r} has no executable target")
    old_kind, old_qualified, binding = _locator_parts(operation.old_locator)
    new_kind, new_qualified, new_binding = _locator_parts(operation.new_locator)
    if old_kind != new_kind or binding != new_binding:
        raise ObjectNameTransformError(
            f"operation {operation.operation_id!r} changes declaration kind or binding identity"
        )
    if old_kind == "module":
        return _Rename(operation.operation_id, old_qualified, new_qualified, None, None, binding)
    old_module, separator, old_symbol = old_qualified.rpartition(".")
    new_module, new_separator, new_symbol = new_qualified.rpartition(".")
    if not separator or not new_separator or old_module != new_module:
        raise ObjectNameTransformError(f"operation {operation.operation_id!r} is not an in-module symbol rename")
    return _Rename(operation.operation_id, old_module, new_module, old_symbol, new_symbol, binding)


def _path(repo_root: Path, relative: str, *, operation_id: str) -> Path:
    current = repo_root
    for part in PurePosixPath(relative).parts:
        current /= part
        if is_link_like(current):
            raise ObjectNameTransformError(
                f"operation {operation_id!r} path traverses a link-like component: {relative}"
            )
    return current


def _module_for_path(relative: str) -> tuple[str, bool]:
    path = PurePosixPath(relative).with_suffix("")
    parts = list(path.parts)
    if parts[0] == "src":
        parts.pop(0)
    package_module = parts[-1] == "__init__"
    if package_module:
        parts.pop()
    return ".".join(parts), package_module


def _dotted_name(node: cst.BaseExpression | None) -> str | None:
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        owner = _dotted_name(node.value)
        return None if owner is None else f"{owner}.{node.attr.value}"
    return None


def _parse_dotted(value: str) -> cst.Name | cst.Attribute:
    expression = cst.parse_expression(value)
    if not isinstance(expression, (cst.Name, cst.Attribute)):
        raise ObjectNameTransformError(f"invalid dotted import target: {value!r}")
    return expression


def _replace_module(value: str, renames: Sequence[_Rename]) -> str:
    matches = [rename for rename in renames if value == rename.old_module or value.startswith(f"{rename.old_module}.")]
    if len(matches) > 1:
        raise ObjectNameTransformError(f"overlapping module rename targets for {value!r}")
    if not matches:
        return value
    rename = matches[0]
    return f"{rename.new_module}{value[len(rename.old_module) :]}"


class _RenameTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)

    def __init__(self, *, path: str, renames: Sequence[_Rename]) -> None:
        self.path = path
        self.renames = renames
        self.module, self.package_module = _module_for_path(path)
        self.definition_counts: dict[str, int] = {}

    def _qualified_names(self, node: cst.CSTNode) -> frozenset[str]:
        names = self.get_metadata(QualifiedNameProvider, node, set())
        return frozenset(name.name for name in names)

    def _symbol_target(self, node: cst.CSTNode, spelling: str) -> str | None:
        qualified = self._qualified_names(node)
        matches = [
            rename
            for rename in self.renames
            if rename.old_symbol == spelling and f"{rename.old_module}.{rename.old_symbol}" in qualified
        ]
        if len(matches) > 1:
            raise ObjectNameTransformError(f"ambiguous symbol reference {spelling!r} in {self.path}")
        return None if not matches else matches[0].new_symbol

    def _record_definition(self, name: str) -> int:
        count = self.definition_counts.get(name, 0) + 1
        self.definition_counts[name] = count
        return count

    def _definition_name(self, original: cst.Name, updated: cst.Name) -> cst.Name:
        occurrence = self._record_definition(original.value)
        matches = [
            rename
            for rename in self.renames
            if rename.old_symbol == original.value and rename.old_module == self.module and rename.binding == occurrence
        ]
        if len(matches) > 1:
            raise ObjectNameTransformError(f"ambiguous definition {original.value!r} in {self.path}")
        return updated if not matches else updated.with_changes(value=matches[0].new_symbol)

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:
        return updated_node.with_changes(name=self._definition_name(original_node.name, updated_node.name))

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.FunctionDef:
        return updated_node.with_changes(name=self._definition_name(original_node.name, updated_node.name))

    def leave_ImportAlias(self, original_node: cst.ImportAlias, updated_node: cst.ImportAlias) -> cst.ImportAlias:
        original = _dotted_name(original_node.name)
        if original is None:
            raise ObjectNameTransformError(f"unsupported import expression in {self.path}")
        replaced = _replace_module(original, self.renames)
        for rename in self.renames:
            if rename.old_symbol is not None and original == rename.old_symbol:
                qualified = self._qualified_names(original_node.name)
                if f"{rename.old_module}.{rename.old_symbol}" in qualified:
                    replaced = rename.new_symbol or replaced
        return updated_node if replaced == original else updated_node.with_changes(name=_parse_dotted(replaced))

    def leave_ImportFrom(self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom) -> cst.ImportFrom:
        if isinstance(original_node.names, cst.ImportStar):
            target = _dotted_name(original_node.module)
            if any(rename.old_symbol is not None and target == rename.old_module for rename in self.renames):
                raise ObjectNameTransformError(f"wildcard import hides symbol references in {self.path}")
        if original_node.relative:
            # Relative module rewrites require import-resolution evidence that the CST
            # alone cannot prove; the graph must surface them and the transform refuses.
            target = _dotted_name(original_node.module) or ""
            if any(
                rename.old_module.endswith(target)
                and (rename.old_symbol is None or isinstance(original_node.names, cst.ImportStar))
                for rename in self.renames
            ):
                raise ObjectNameTransformError(f"relative import rename is unsupported in {self.path}")
            return updated_node
        original = _dotted_name(original_node.module)
        if original is None:
            return updated_node
        replaced = _replace_module(original, self.renames)
        return updated_node if replaced == original else updated_node.with_changes(module=_parse_dotted(replaced))

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        target = self._symbol_target(original_node, original_node.value)
        return updated_node if target is None else updated_node.with_changes(value=target)

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.Attribute:
        target = self._symbol_target(original_node, original_node.attr.value)
        if target is not None:
            return updated_node.with_changes(attr=updated_node.attr.with_changes(value=target))
        qualified = self._qualified_names(original_node)
        matches = [
            rename
            for rename in self.renames
            if rename.old_symbol is None
            and rename.old_module in qualified
            and original_node.attr.value == rename.old_module.rsplit(".", 1)[-1]
        ]
        if len(matches) > 1:
            raise ObjectNameTransformError(f"ambiguous module reference in {self.path}")
        if not matches:
            return updated_node
        return updated_node.with_changes(
            attr=updated_node.attr.with_changes(value=matches[0].new_module.rsplit(".", 1)[-1])
        )

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        called = _dotted_name(original_node.func)
        if called not in _DYNAMIC_IMPORTS or not original_node.args:
            return updated_node
        first = original_node.args[0].value
        if not isinstance(first, cst.SimpleString):
            if any(rename.old_symbol is None for rename in self.renames):
                raise ObjectNameTransformError(f"computed dynamic import target in {self.path}")
            return updated_node
        try:
            value = first.evaluated_value
        except Exception as exc:  # LibCST exposes malformed literal failures at evaluation time.
            raise ObjectNameTransformError(f"invalid dynamic import literal in {self.path}") from exc
        if not isinstance(value, str):
            return updated_node
        replaced = _replace_module(value, self.renames)
        if replaced == value:
            return updated_node
        quote = '"' if first.quote == '"' else "'"
        return updated_node.with_changes(
            args=(
                updated_node.args[0].with_changes(value=cst.SimpleString(f"{quote}{replaced}{quote}")),
                *updated_node.args[1:],
            )
        )


def _transform_python(data: bytes, *, path: str, renames: Sequence[_Rename]) -> bytes:
    bom = data.startswith(b"\xef\xbb\xbf")
    try:
        source = data.decode("utf-8-sig" if bom else "utf-8")
        module = cst.parse_module(source)
        transformed = MetadataWrapper(module).visit(_RenameTransformer(path=path, renames=renames)).code
    except (UnicodeDecodeError, cst.ParserSyntaxError, RecursionError) as exc:
        raise ObjectNameTransformError(f"cannot safely transform {path}: {exc}") from exc
    encoded = transformed.encode("utf-8")
    return b"\xef\xbb\xbf" + encoded if bom else encoded


def plan_object_name_transformations(
    manifest: ObjectNameRenameManifest,
    *,
    repo_root: Path,
) -> ObjectNameTransformResult:
    """Compute one exact reviewed component without modifying the filesystem."""
    root = repo_root.resolve()
    operations = tuple(
        operation
        for operation in manifest.operations
        if operation.lifecycle == "reviewed" and operation.disposition in {"lexical-singular", "rename-distinct"}
    )
    if not operations:
        raise ObjectNameTransformError("manifest selects no executable reviewed operations")
    if any(operation.generator_commands for operation in operations):
        raise ObjectNameTransformError("generated artifacts require the rehearsal generator phase")
    renames = tuple(_operation_rename(operation) for operation in operations)

    expected: dict[str, str] = {}
    owners: dict[str, set[str]] = {}
    allowed: set[str] = set()
    moves: dict[str, str] = {}
    for operation in operations:
        allowed.update(operation.changed_paths)
        for precondition in operation.preconditions:
            prior = expected.setdefault(precondition.path, precondition.sha256)
            if prior != precondition.sha256:
                raise ObjectNameTransformError(f"conflicting byte preconditions for {precondition.path}")
            owners.setdefault(precondition.path, set()).add(operation.operation_id)
        for move in operation.moves:
            if move.source in moves and moves[move.source] != move.target:
                raise ObjectNameTransformError(f"conflicting moves for {move.source}")
            moves[move.source] = move.target

    inputs: dict[str, bytes] = {}
    for relative, digest in sorted(expected.items()):
        operation_id = min(owners[relative])
        path = _path(root, relative, operation_id=operation_id)
        if not path.is_file():
            raise ObjectNameTransformError(f"precondition path is not a regular file: {relative}")
        data = path.read_bytes()
        if _digest(data) != digest:
            raise ObjectNameTransformError(f"byte precondition is stale for {relative}")
        inputs[relative] = data

    for source, target in sorted(moves.items()):
        if source not in inputs:
            raise ObjectNameTransformError(f"move source lacks a byte precondition: {source}")
        target_path = _path(root, target, operation_id="module-move")
        if target_path.exists() or is_link_like(target_path):
            raise ObjectNameTransformError(f"module move target already exists: {target}")

    after: dict[str, bytes] = {}
    for relative, data in sorted(inputs.items()):
        if PurePosixPath(relative).suffix != ".py":
            raise ObjectNameTransformError(f"unsupported non-Python changed surface: {relative}")
        transformed = _transform_python(data, path=relative, renames=renames)
        after[moves.get(relative, relative)] = transformed

    changes: dict[str, ObjectNameChange] = {}
    for relative, data in sorted(inputs.items()):
        target = moves.get(relative, relative)
        transformed = after[target]
        if target != relative:
            changes[relative] = ObjectNameChange(relative, _digest(data), None, None)
            changes[target] = ObjectNameChange(target, None, _digest(transformed), transformed)
        elif transformed != data:
            changes[relative] = ObjectNameChange(relative, _digest(data), _digest(transformed), transformed)
    actual = set(changes)
    if actual != allowed:
        raise ObjectNameTransformError(
            f"actual changed paths do not equal the reviewed allowlist; missing={sorted(allowed - actual)!r}, "
            f"unexpected={sorted(actual - allowed)!r}"
        )
    return ObjectNameTransformResult(tuple(changes[path] for path in sorted(changes)))


def apply_object_name_transformations(
    manifest: ObjectNameRenameManifest,
    *,
    repo_root: Path,
) -> ObjectNameTransformResult:
    """Recheck, plan, and apply one bounded component to the selected tree."""
    result = plan_object_name_transformations(manifest, repo_root=repo_root)
    root = repo_root.resolve()
    # All sources and targets were checked before this mutation loop.  Deletions
    # occur only for explicit reviewed moves, after their target bytes are written.
    for change in result.changes:
        target = root.joinpath(*PurePosixPath(change.path).parts)
        if change.content is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(change.content)
    for change in result.changes:
        if change.content is None:
            root.joinpath(*PurePosixPath(change.path).parts).unlink()
    return result
