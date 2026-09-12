"""Exact authority, runtime, and legacy-absence gates for Modelo work."""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
import types
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import cache
from importlib.util import find_spec, resolve_name
from pathlib import Path
from typing import cast, get_args, get_origin

import pytest
from typer.main import get_command

from .._command_runtime import build_command_subtree
from .._modelo_audit_command_specs import MODELO_ROOT_COMMAND_SPEC
from .._modelo_core_command_specs import MODELO_CORE_COMMAND_SPECS
from .._root_command_specs import ROOT_COMMAND_SPECS
from ..command_spec import BindingState, CommandSpecGraph, DefaultKind, SchemaState
from ..modelo_work_command_specs import MODELO_WORK_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

EXPECTED_TOKENS = {
    "calculate",
    "create",
    "dependencies",
    "discard",
    "file",
    "list",
    "observations",
    "rename",
    "resume",
    "review",
    "run",
    "run-details",
    "revision",
    "revisions",
    "runs",
    "select",
    "status",
    "verify",
    "wizard",
}


def _graph() -> CommandSpecGraph:
    return CommandSpecGraph(
        (*ROOT_COMMAND_SPECS, MODELO_ROOT_COMMAND_SPEC, *MODELO_CORE_COMMAND_SPECS, *MODELO_WORK_COMMAND_SPECS)
    )


@dataclass(frozen=True)
class _StaticTarget:
    module: str
    qualname: str
    node: ast.AST | None

    def __call__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(f"static target {self.module}:{self.qualname} is not executable")

    @property
    def __signature__(self) -> inspect.Signature:
        if not isinstance(self.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return inspect.Signature()
        names = [argument.arg for argument in (*self.node.args.posonlyargs, *self.node.args.args)]
        names.extend(argument.arg for argument in self.node.args.kwonlyargs)
        if self.node.args.vararg is not None:
            names.insert(len(self.node.args.posonlyargs) + len(self.node.args.args), self.node.args.vararg.arg)
        if self.node.args.kwarg is not None:
            names.append(self.node.args.kwarg.arg)
        return inspect.Signature(inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD) for name in names)


def _source(module_name: str) -> tuple[Path, ast.Module] | None:
    try:
        spec = find_spec(module_name)
    except (ImportError, ModuleNotFoundError, ValueError):
        return None
    origin = None if spec is None else spec.origin
    if origin is None or origin in {"built-in", "frozen"}:
        return None
    path = Path(origin)
    if not path.is_file():
        return None
    try:
        return path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return None


def _target_node(module_name: str, qualname: str, seen: frozenset[str] = frozenset()) -> ast.AST | None:
    if module_name in seen:
        return None
    loaded = _source(module_name)
    if loaded is None:
        return None
    _, tree = loaded
    part, _, remainder = qualname.partition(".")
    for node in tree.body:
        if getattr(node, "name", None) == part:
            return _target_node(module_name, remainder, seen | {module_name}) if remainder else node
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (alias.asname or alias.name) != part:
                    continue
                imported = node.module or ""
                if node.level:
                    package = module_name if loaded[0].name == "__init__.py" else module_name.rpartition(".")[0]
                    imported = resolve_name("." * node.level + imported, package)
                return _target_node(imported, alias.name, seen | {module_name})
    return None


@cache
def _resolve(module_name: str, qualname: str) -> _StaticTarget:
    if _source(module_name) is None and module_name != "builtins":
        raise ImportError(module_name)
    node = _target_node(module_name, qualname)
    if node is None and module_name != "builtins":
        raise AttributeError(f"{module_name}.{qualname}")
    return _StaticTarget(module_name, qualname, node)


def _annotation_target(module_name: str, node: ast.AST, imports: dict[str, tuple[str, str]]) -> _StaticTarget | None:
    if isinstance(node, ast.Name):
        target_module, target_name = imports.get(node.id, ("builtins", node.id))
        return _resolve(target_module, target_name)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in imports:
        target_module, target_name = imports[node.value.id]
        return _resolve(target_module, f"{target_name}.{node.attr}" if target_name else node.attr)
    if isinstance(node, ast.Subscript):
        child = node.slice.elts[0] if isinstance(node.slice, ast.Tuple) and node.slice.elts else node.slice
        return _annotation_target(module_name, child, imports)
    if isinstance(node, ast.BinOp):
        return _annotation_target(module_name, node.left, imports) or _annotation_target(
            module_name, node.right, imports
        )
    return None


def _static_type_hints(target: _StaticTarget) -> dict[str, object]:
    if not isinstance(target.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return {}
    loaded = _source(target.module)
    if loaded is None:
        return {}
    _, tree = loaded
    imports: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            imported = node.module or ""
            if node.level:
                package = target.module if loaded[0].name == "__init__.py" else target.module.rpartition(".")[0]
                imported = resolve_name("." * node.level + imported, package)
            for alias in node.names:
                if alias.name != "*":
                    imports[alias.asname or alias.name] = (imported, alias.name)
    return {
        argument.arg: hint
        for argument in (*target.node.args.posonlyargs, *target.node.args.args, *target.node.args.kwonlyargs)
        if (hint := _annotation_target(target.module, argument.annotation, imports)) is not None
    }


def _semantic_annotation(annotation: object) -> object:
    origin = get_origin(annotation)
    if origin is types.UnionType:
        annotation = next(item for item in get_args(annotation) if item is not type(None))
        origin = get_origin(annotation)
    if origin in {list, tuple}:
        return get_args(annotation)[0]
    return annotation


def test_modelo_work_specs_are_the_exact_owned_leaf_set() -> None:
    assert len(MODELO_WORK_COMMAND_SPECS) == 19
    assert {spec.token for spec in MODELO_WORK_COMMAND_SPECS} == EXPECTED_TOKENS
    assert {spec.parent_key for spec in MODELO_WORK_COMMAND_SPECS} == {"app_modelo_work"}
    assert {spec.key for spec in MODELO_WORK_COMMAND_SPECS} == {
        f"app_modelo_work_{token.replace('-', '_')}" for token in EXPECTED_TOKENS
    }


def test_modelo_work_specs_match_public_handler_signatures_and_resolve_targets() -> None:
    for spec in MODELO_WORK_COMMAND_SPECS:
        assert spec.handler is not None
        assert spec.handler.state is BindingState.TARGET
        assert spec.handler.target is not None
        assert not spec.handler.target.qualname.startswith("_")
        assert "<locals>" not in spec.handler.target.qualname
        handler = _resolve(spec.handler.target.module, spec.handler.target.qualname)
        assert callable(handler)
        expected = (spec.invocation.context_parameter, *(parameter.name for parameter in spec.parameters))
        assert tuple(inspect.signature(handler).parameters) == expected
        assert spec.result_schema.state is SchemaState.TARGET
        assert spec.result_schema.target is not None
        assert _resolve(spec.result_schema.target.module, spec.result_schema.target.qualname) is not None
        assert spec.result_schema.identity == f"modelo.work.{spec.token.replace('-', '_')}"


def test_modelo_work_parameter_types_and_defaults_match_behavior_contracts() -> None:
    for spec in MODELO_WORK_COMMAND_SPECS:
        assert spec.handler is not None and spec.handler.target is not None
        handler = cast(
            Callable[..., object],
            _resolve(spec.handler.target.module, spec.handler.target.qualname),
        )
        signature = inspect.signature(handler)
        hints = _static_type_hints(handler)
        for parameter in spec.parameters:
            behavior_parameter = signature.parameters[parameter.name]
            expected_type = _resolve(parameter.value.annotation.module, parameter.value.annotation.qualname)
            assert _semantic_annotation(hints[parameter.name]) is expected_type
            if parameter.default.kind is DefaultKind.REQUIRED:
                assert behavior_parameter.default is inspect.Parameter.empty
                continue
            behavior_default = behavior_parameter.default
            if isinstance(behavior_default, Enum):
                behavior_default = behavior_default.value
            declared_default = parameter.default.literal
            if getattr(parameter, "multiple", False) and behavior_default is None:
                behavior_default = ()
            assert declared_default == behavior_default


def test_every_modelo_work_subtree_compiles_from_specs() -> None:
    graph = _graph()
    for key in ("app_modelo_work", *(spec.key for spec in MODELO_WORK_COMMAND_SPECS)):
        assert get_command(build_command_subtree(graph, key)) is not None


def test_importing_modelo_work_specs_does_not_import_behavior() -> None:
    behavior_modules = {
        spec.handler.target.module for spec in MODELO_WORK_COMMAND_SPECS if spec.handler and spec.handler.target
    }
    for module_name in behavior_modules:
        sys.modules.pop(module_name, None)
    importlib.reload(importlib.import_module("..modelo_work_command_specs", __package__))
    assert behavior_modules.isdisjoint(sys.modules)


def test_modelo_work_package_has_no_legacy_structural_authority() -> None:
    cli_root = Path(__file__).parents[1]
    paths = sorted(cli_root.glob("_modelo_work*.py"))
    assert not (cli_root / "_modelo_work.py").exists()
    assert not (cli_root / "_modelo_work_options.py").exists()
    forbidden_names = {"command_execution_policy", "declare_metadata_group", "register_schema"}
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert "Typer(" not in source
        assert "typer.Option(" not in source
        assert "typer.Argument(" not in source
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("register_work_")
            for node in ast.walk(tree)
        )
        assert not any(isinstance(node, ast.Name) and node.id in forbidden_names for node in ast.walk(tree))
        assert not any(
            isinstance(node, ast.Attribute) and node.attr in {"command", "callback", "add_typer"}
            for node in ast.walk(tree)
        )
