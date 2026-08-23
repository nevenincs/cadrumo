"""Independent exact-set and authority gates for the app ledger CommandSpec subtree."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from .._app_ledger_command_specs import LEDGER_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_EXPECTED_SUFFIXES = {
    (),
    ("add",),
    ("allocate",),
    ("archive",),
    ("attach",),
    ("bienes-inversion",),
    ("bienes-inversion", "declare"),
    ("bienes-inversion", "list"),
    ("categories",),
    ("check",),
    ("classify",),
    ("counterparty",),
    ("counterparty", "confirm"),
    ("counterparty", "show"),
    ("counterparty", "withdraw"),
    ("detach",),
    ("doclink",),
    ("evidence",),
    ("evidence", "add"),
    ("evidence", "attachment-queue"),
    ("evidence", "attachment-view"),
    ("evidence", "batch"),
    ("evidence", "confirm"),
    ("evidence", "consent"),
    ("evidence", "consent", "list"),
    ("evidence", "consent", "rederive"),
    ("evidence", "extract"),
    ("evidence", "list"),
    ("evidence", "remove"),
    ("evidence", "review"),
    ("evidence", "review", "list"),
    ("evidence", "review", "show"),
    ("evidence", "update"),
    ("evidence", "view"),
    ("exclude",),
    ("export",),
    ("history",),
    ("import",),
    ("inventory",),
    ("inventory", "closing-authority-record"),
    ("inventory", "create"),
    ("inventory", "list"),
    ("inventory", "movement"),
    ("inventory", "movement", "add"),
    ("inventory", "valuation"),
    ("inventory", "valuation", "preview"),
    ("invoice",),
    ("invoice", "add"),
    ("invoice", "import"),
    ("invoice", "list"),
    ("invoice", "remove"),
    ("invoice", "update"),
    ("invoice", "view"),
    ("invoice", "wizard"),
    ("link",),
    ("list",),
    ("llm-diagnostics",),
    ("merge",),
    ("participation",),
    ("participation", "rebuild"),
    ("preflight",),
    ("prorrata",),
    ("prorrata", "declare-sector"),
    ("prorrata", "elect-especial"),
    ("prorrata", "elect-general"),
    ("prorrata", "list"),
    ("prorrata", "revoke-especial"),
    ("pull-folder",),
    ("ratios",),
    ("ratios", "eligible"),
    ("ratios", "list"),
    ("ratios", "set"),
    ("ratios", "unset"),
    ("ratios", "validate"),
    ("remove",),
    ("reset",),
    ("restore",),
    ("review",),
    ("rule",),
    ("rule", "add"),
    ("rule", "apply"),
    ("rule", "list"),
    ("split",),
    ("stash",),
    ("status",),
    ("track",),
    ("update",),
    ("view",),
}
_OWNED_HANDLER_MODULES = (
    "cadrumo.entrypoints.cli._bienes_inversion_cli",
    "cadrumo.entrypoints.cli._ledger",
    "cadrumo.entrypoints.cli._ledger_business_invoice_cli",
    "cadrumo.entrypoints.cli._ledger_counterparty_cli",
    "cadrumo.entrypoints.cli._ledger_evidence_batch_cli",
    "cadrumo.entrypoints.cli._ledger_evidence_cli",
    "cadrumo.entrypoints.cli._ledger_evidence_consent_cli",
    "cadrumo.entrypoints.cli._ledger_evidence_review_cli",
    "cadrumo.entrypoints.cli._ledger_import_cli",
    "cadrumo.entrypoints.cli._ledger_inventory_cli",
    "cadrumo.entrypoints.cli._ledger_lifecycle_cli",
    "cadrumo.entrypoints.cli._ledger_ratios_cli",
    "cadrumo.entrypoints.cli._ledger_read_cli",
    "cadrumo.entrypoints.cli._ledger_review_cli",
    "cadrumo.entrypoints.cli._ledger_rules_cli",
    "cadrumo.entrypoints.cli._participation_cli",
    "cadrumo.entrypoints.cli._prorrata_register_cli",
)


def test_ledger_command_specs_are_the_exact_live_88_node_set() -> None:
    by_key = {spec.key: spec for spec in LEDGER_COMMAND_SPECS}

    def suffix(key: str) -> tuple[str, ...]:
        spec = by_key[key]
        if spec.parent_key == "app":
            return ()
        assert spec.parent_key is not None
        return (*suffix(spec.parent_key), spec.token)

    assert len(LEDGER_COMMAND_SPECS) == 88
    assert {suffix(spec.key) for spec in LEDGER_COMMAND_SPECS} == _EXPECTED_SUFFIXES
    assert sum(spec.kind == "group" for spec in LEDGER_COMMAND_SPECS) == 14
    assert sum(spec.kind == "leaf" for spec in LEDGER_COMMAND_SPECS) == 74
    assert sum(spec.handler is not None for spec in LEDGER_COMMAND_SPECS) == 75


def test_every_ledger_executable_uses_a_resolvable_public_behavior_target() -> None:
    executable = tuple(spec for spec in LEDGER_COMMAND_SPECS if spec.handler is not None)
    assert len(executable) == 75
    for spec in executable:
        assert spec.handler is not None
        assert spec.handler.target is not None
        target = spec.handler.target
        assert "<locals>" not in target.qualname
        assert not target.qualname.startswith("_")
        resolved = getattr(importlib.import_module(target.module), target.qualname)
        assert callable(resolved)


def test_ledger_handlers_have_no_structural_typer_or_policy_authority() -> None:
    root = Path(__file__).parents[1]
    forbidden_calls = {"Typer", "Option", "Argument", "command_execution_policy", "declare_metadata_group"}
    for module_name in _OWNED_HANDLER_MODULES:
        source_path = root / f"{module_name.rsplit('.', 1)[-1]}.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert not node.name.startswith(("register_", "_register_"))
                assert not node.decorator_list
            if isinstance(node, ast.Call):
                name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else (node.func.id if isinstance(node.func, ast.Name) else "")
                )
                assert name not in forbidden_calls
                assert name != "add_typer"
