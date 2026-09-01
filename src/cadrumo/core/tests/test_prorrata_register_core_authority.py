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
    # This required the enums to appear in the `cadrumo.core` facade's
    # __all__. That facade is now inert, so the surviving guarantee is the one
    # below: each enum is DEFINED by prorrata_register, and no other facade
    # re-exports it.
    assert ProrrataProvisionalProvenance.__module__ == "cadrumo.core.prorrata_register"
    assert ProrrataRegisterRegime.__module__ == "cadrumo.core.prorrata_register"

    for module_name, relative_path in _FACADES:
        facade = importlib.import_module(module_name)
        assert all(not hasattr(facade, enum_name) for enum_name in _ENUMS), module_name
        assert all(enum_name not in facade.__all__ for enum_name in _ENUMS), module_name

        # This also pinned HOW each namespace re-imported the enums from the
        # core facade, aliased under a leading underscore. Both namespaces are
        # inert now, so that pattern no longer exists to pin. What it protected
        # -- one owning module, no rival re-export -- is asserted above.
        tree = _read_ast(repo_path(relative_path), source_tree_ast)
        redeclarations = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in _ENUMS
        ]
        assert not redeclarations, relative_path
