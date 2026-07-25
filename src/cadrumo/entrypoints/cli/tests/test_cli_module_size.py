"""Static size guards for CLI modules and command functions.

See Also:
    :func:`~tests._inventory.package_python_files`
        Shared source inventory used to enumerate production CLI modules
        without bespoke filesystem walking.
    :mod:`~tests.test_codebase_size_budgets`
        Codebase-wide sibling ratchet that mirrors the CLI module and callable
        size ceilings.

CLI modules must stay bounded so they decompose without breaking public
hexagonal facades.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ....core.paths import PROJECT_ROOT
from ....tests import ast_for_path, package_python_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI_ROOT = PROJECT_ROOT / "src" / "cadrumo" / "entrypoints" / "cli"
_DEFAULT_MODULE_LINE_LIMIT = 1250
# Per-module ceilings for SPLIT-CANDIDATE CLI modules grown by recovered features.
_MODULE_LINE_LIMIT_OVERRIDES = {
    "_config/__init__.py": 1261,  # SPLIT-CANDIDATE
    "_modelo.py": 1320,  # SPLIT-CANDIDATE
    # _modelo_payloads.py: extracted the `bindings list`/`bindings resolve`
    # payload family to the sibling `_modelo_bindings_payloads.py` module;
    # re-pinned to the smaller post-split size.
    "_modelo_payloads.py": 1341,  # SPLIT-CANDIDATE
    # _ledger_payloads.py: extracted the invoice/inventory/evidence sub-app
    # payload families to the sibling `_ledger_business_payloads.py` module;
    # back under the default budget, override removed.
    # Docstring core-struct cross-link sweep (aeat-docs-scaffolding-cli /
    # core-struct-docstring-links) added a handful of `:class:`/`:func:` links
    # across the IVA-wallet and filed-live command docstrings; re-pinned to
    # the present size, matching the sibling override in
    # test_codebase_size_budgets.py. Regrew to 1296 under concurrent
    # live-command feature work plus feature/profile branch growth; re-pinned
    # with small headroom per the ship-authorised rebaseline.
    "_app_live.py": 1320,  # SPLIT-CANDIDATE
    # _config_payloads.py: grew past the default budget under the login/logout
    # campaign (the login and logout door registrations, the hard-cut switch,
    # then the profile-export pre-journal cleartext-window fix). Pinned at
    # EXACTLY the present size, with no headroom, so the next line of growth
    # reds this gate again rather than being absorbed. SPLIT-CANDIDATE for the
    # campaign owner: extract the login/session payload family to a sibling
    # module, following the `_ledger_payloads.py` -> `_ledger_business_payloads.py`
    # split recorded above.
    "_config_payloads.py": 1266,  # SPLIT-CANDIDATE
    # _ledger_read_cli.py: grew past the default budget under the invoice-linkage
    # campaign (single-transaction link commit, typed link-inconsistency
    # direction, then the linkage audit event). Pinned at EXACTLY the present
    # size with no headroom. SPLIT-CANDIDATE for the campaign owner: the invoice
    # link/verify read surface is the extractable family.
    "_ledger_read_cli.py": 1257,  # SPLIT-CANDIDATE
}
_DEFAULT_COMMAND_LINE_LIMIT = 180
# Per-command ceilings for command bodies pinned above the default, mirroring the
# sibling _CALLABLE_LINE_LIMIT_OVERRIDES in test_codebase_size_budgets.py. Keyed by
# (CLI-relative module path, function name). SPLIT-CANDIDATE: owners should extract
# helpers on their next pass rather than growing these further.
_COMMAND_LINE_LIMIT_OVERRIDES = {
    # SPLIT-CANDIDATE: a wide Typer signature (manual + LLM + saturate + evidence +
    # auto-split routes). The LLM-routing bodies live in `_ledger_llm_cli.py`;
    # what remains here is the option surface and the route dispatch.
    ("_ledger.py", "ledger_classify"): 234,  # SPLIT-CANDIDATE (concurrent growth)
    ("_ledger.py", "ledger_add"): 250,  # SPLIT-CANDIDATE (regrew to 245; small-headroom rebaseline)
}


def _production_cli_modules() -> tuple[Path, ...]:
    return tuple(
        path
        for path in package_python_files()
        if path.is_relative_to(_CLI_ROOT)
        if not path.name.startswith("test_") and "/test_" not in path.relative_to(_CLI_ROOT).as_posix()
    )


def test_production_cli_modules_do_not_grow_into_new_monoliths() -> None:
    """CLI modules have the same hard size limit as the rest of the codebase."""
    offenders: list[str] = []
    for path in _production_cli_modules():
        relative = path.relative_to(_CLI_ROOT).as_posix()
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        budget = _MODULE_LINE_LIMIT_OVERRIDES.get(relative, _DEFAULT_MODULE_LINE_LIMIT)
        if line_count > budget:
            offenders.append(f"{relative}: {line_count} lines > budget {budget}")

    assert offenders == [], "CLI module size budget exceeded:\n  " + "\n  ".join(offenders)


def test_cli_command_functions_do_not_grow_past_complexity_budget(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Command and command-registrar bodies have bounded line budgets."""
    offenders: list[str] = []
    for path in _production_cli_modules():
        relative = path.relative_to(_CLI_ROOT).as_posix()
        tree = ast_for_path(path, source_tree_ast)
        if tree is None:
            raise AssertionError(f"unable to parse {relative}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            decorators = tuple(ast.unparse(decorator) for decorator in node.decorator_list)
            is_command_body = any(".command" in decorator for decorator in decorators)
            is_registrar = node.name.startswith("register_") and relative.startswith("_modelo")
            if not (is_command_body or is_registrar):
                continue
            assert node.end_lineno is not None
            length = node.end_lineno - node.lineno + 1
            budget = _COMMAND_LINE_LIMIT_OVERRIDES.get((relative, node.name), _DEFAULT_COMMAND_LINE_LIMIT)
            if length > budget:
                offenders.append(f"{relative}:{node.name}: {length} lines > budget {budget}")

    assert offenders == [], "CLI command size budget exceeded:\n  " + "\n  ".join(offenders)
