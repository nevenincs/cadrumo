"""Exact-set and contract gates for the import-light app live authority."""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

import pytest
from typer.main import get_command

from .._app_live_command_specs import LIVE_COMMAND_SPECS
from .._command_runtime import build_command_subtree
from .._command_spec import BindingState, CommandSpecGraph, LazyBinding
from .._root_command_specs import ROOT_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


EXPECTED_LIVE_PATHS = {
    "app live",
    "app live borrador",
    "app live borrador 100",
    "app live borrador 100 latest",
    "app live borrador 100 list",
    "app live borrador 100 view",
    "app live deudas",
    "app live deudas latest",
    "app live deudas list",
    "app live deudas view",
    "app live expedientes",
    "app live expedientes latest",
    "app live expedientes list",
    "app live expedientes pull",
    "app live expedientes view",
    "app live filed",
    "app live filed discover",
    "app live filed list",
    "app live filed pull",
    "app live filed pull-all",
    "app live filed pull-sources",
    "app live iva-wallet",
    "app live iva-wallet history",
    "app live iva-wallet pull",
    "app live iva-wallet pull-evidence",
    "app live iva-wallet pull-history",
    "app live justificante",
    "app live justificante list",
    "app live justificante pull",
    "app live justificante view",
    "app live notifications",
    "app live notifications document",
    "app live notifications document history",
    "app live notifications document pull",
    "app live notifications document view",
    "app live notifications latest",
    "app live notifications list",
    "app live notifications pull",
    "app live notifications view",
    "app live portals",
    "app live portals list",
    "app live portals view",
    "app live verify",
    "app live verify latest",
    "app live verify list",
    "app live verify nif-iva",
    "app live verify tgvi",
    "app live verify view",
}


def _resolve(binding: LazyBinding) -> object:
    assert binding.state is BindingState.TARGET
    assert binding.target is not None
    value: object = import_module(binding.target.module)
    for part in binding.target.qualname.split("."):
        value = getattr(value, part)
    return value


def test_live_specs_are_the_exact_complete_current_surface() -> None:
    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *LIVE_COMMAND_SPECS))
    live_keys = {spec.key for spec in LIVE_COMMAND_SPECS}
    actual = {" ".join(node.path[1:]) for node in graph.nodes() if node.spec.key in live_keys}
    assert len(LIVE_COMMAND_SPECS) == 48
    assert actual == EXPECTED_LIVE_PATHS


def test_every_live_leaf_has_public_resolvable_behavior_and_schema_targets() -> None:
    leaves = [spec for spec in LIVE_COMMAND_SPECS if spec.kind == "leaf"]
    assert len(leaves) == 36
    for spec in leaves:
        assert spec.handler is not None
        assert spec.handler.target is not None
        assert "<locals>" not in spec.handler.target.qualname
        assert not spec.handler.target.qualname.startswith("_")
        assert callable(_resolve(spec.handler))
        assert spec.result_schema.target is not None
        assert _resolve(LazyBinding.available(spec.result_schema.target)) is not None


def test_live_specs_own_policy_schema_and_localised_parameter_contracts() -> None:
    for spec in LIVE_COMMAND_SPECS:
        assert spec.help_key.value.startswith("cli.app.live.")
        assert spec.policy.capabilities
        if spec.kind == "leaf":
            assert spec.result_schema.identity is not None
            assert spec.result_schema.identity.startswith("app.live.")
        for parameter in spec.parameters:
            assert parameter.help_key is None or parameter.help_key.value.startswith("cli.app.live.")


def test_every_live_subtree_compiles_from_specs_without_legacy_structure() -> None:
    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *LIVE_COMMAND_SPECS))
    for spec in LIVE_COMMAND_SPECS:
        app = build_command_subtree(graph, spec.key)
        assert get_command(app) is not None


def test_live_behavior_and_payload_modules_contain_no_structural_authority() -> None:
    cli_root = Path(__file__).parents[1]
    assert not (cli_root / "_app_live_payloads.py").exists()
    paths = [cli_root / "_app_live.py", cli_root / "_app_live_payloads_support.py"]
    paths.extend(sorted(cli_root.glob("_app_live_*_payloads.py")))
    paths.extend(sorted(cli_root.glob("_app_live_*_cli.py")))
    forbidden_names = {"command_execution_policy", "declare_metadata_group", "register_schema"}
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert "Typer(" not in source
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("register_")
            for node in ast.walk(tree)
        )
        assert not any(isinstance(node, ast.Name) and node.id in forbidden_names for node in ast.walk(tree))
        assert not any(
            isinstance(node, ast.Attribute) and node.attr in {"command", "callback", "add_typer"}
            for node in ast.walk(tree)
        )
