from __future__ import annotations

import ast
import importlib
from collections.abc import Mapping
from pathlib import Path

import pytest

from ...tests import ast_for_path, repo_path, repo_relative
from ..prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ENUMS = ("ProrrataProvisionalProvenance", "ProrrataRegisterRegime")
_FACADES = (
    ("cadrumo.domain.prorrata_register", "src/cadrumo/domain/prorrata_register/__init__.py"),
    ("cadrumo.application.prorrata_register", "src/cadrumo/application/prorrata_register/__init__.py"),
)


def _read_ast(path: Path, source_tree_ast: Mapping[Path, ast.AST]) -> ast.AST:
    tree = ast_for_path(path, source_tree_ast)
    if tree is None:
        raise AssertionError(f"unable to parse {repo_relative(path)}")
    return tree


def test_prorrata_register_enums_are_public_only_from_core(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    from .. import __all__ as core_exports

    assert set(_ENUMS) <= set(core_exports)
    assert ProrrataProvisionalProvenance.__module__ == "cadrumo.core.prorrata_register"
    assert ProrrataRegisterRegime.__module__ == "cadrumo.core.prorrata_register"

    for module_name, relative_path in _FACADES:
        facade = importlib.import_module(module_name)
        assert all(not hasattr(facade, enum_name) for enum_name in _ENUMS), module_name
        assert all(enum_name not in facade.__all__ for enum_name in _ENUMS), module_name

        tree = _read_ast(repo_path(relative_path), source_tree_ast)
        core_imports = [
            alias
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 3 and node.module == "core"
            for alias in node.names
            if alias.name in _ENUMS
        ]
        assert {alias.name for alias in core_imports} == set(_ENUMS), relative_path
        assert all(alias.asname == f"_{alias.name}" for alias in core_imports), relative_path
