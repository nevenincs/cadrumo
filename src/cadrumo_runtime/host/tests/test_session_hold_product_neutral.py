"""The held person bridge and the runtime's commands stay a generic host: they name no product setup.

The hold relays registered operations by the definition id its parent names.
A module of the bridge that imports the product's setup, model
catalogue or Google adapter code, or spells a ``dependencies.*`` definition id,
has taken product meaning into the runtime; this gate refuses it. The runtime's
commands likewise import no setup code and no Google adapter: a sign-in from
the desktop or the TUI is the product's registered Google login operation.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FORBIDDEN_MODULE_PREFIXES = (
    "cadrumo.application.dependency_",
    "cadrumo.core.model_roles",
    "cadrumo.adapters.outbound.google",
    "cadrumo.entrypoints",
)
_COMMAND_FORBIDDEN_MODULE_PREFIXES = ("cadrumo.application.dependency_", "cadrumo.adapters.outbound.google")
_FORBIDDEN_TEXT_PREFIXES = ("dependencies.", "dependencies:")
_BRIDGE_MODULES = "session_hold*.py"


def product_knowledge(
    source: str, *, prefixes: tuple[str, ...] = _FORBIDDEN_MODULE_PREFIXES, ids: bool = True
) -> list[str]:
    """Return each product import, and with ``ids`` each product definition id, a module spells, sorted."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
        found.extend(f"import {module}" for module in modules if module.startswith(prefixes))
        if (
            ids
            and isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.startswith(_FORBIDDEN_TEXT_PREFIXES)
        ):
            found.append(f"text {node.value}")
    return sorted(set(found))


def test_every_bridge_module_names_no_product_setup() -> None:
    modules = sorted((Path(__file__).resolve().parents[1]).glob(_BRIDGE_MODULES))
    assert {module.name for module in modules} >= {"session_hold.py", "session_hold_operations.py"}
    for module in modules:
        assert product_knowledge(module.read_text(encoding="utf-8")) == [], module.name


def test_no_runtime_command_imports_product_setup_or_the_google_adapters() -> None:
    commands = Path(__file__).resolve().parents[2] / "commands"
    modules = sorted(path for path in commands.rglob("*.py") if "tests" not in path.relative_to(commands).parts)
    assert any(module.name == "google.py" for module in modules)
    for module in modules:
        found = product_knowledge(
            module.read_text(encoding="utf-8"), prefixes=_COMMAND_FORBIDDEN_MODULE_PREFIXES, ids=False
        )
        assert found == [], module.relative_to(commands)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "from cadrumo.application.dependency_setup_operation import X\n",
            [
                "import cadrumo.application.dependency_setup_operation",
                "import cadrumo.application.dependency_setup_operation.X",
            ],
        ),
        ("import cadrumo.core.model_roles\n", ["import cadrumo.core.model_roles"]),
        ("from cadrumo.application import dependency_wording\n", ["import cadrumo.application.dependency_wording"]),
        ('DEFINITION = "dependencies.setup"\n', ["text dependencies.setup"]),
        ('SUBJECT = "dependencies:installation"\n', ["text dependencies:installation"]),
        (
            "from cadrumo.adapters.outbound.google.oauth_flow import X\n",
            [
                "import cadrumo.adapters.outbound.google.oauth_flow",
                "import cadrumo.adapters.outbound.google.oauth_flow.X",
            ],
        ),
        ("from cadrumo.application.operations.registry import X\nACTION = 'operation_submit'\n", []),
    ],
)
def test_the_gate_detects_a_planted_product_import_or_definition_id(source: str, expected: list[str]) -> None:
    assert product_knowledge(source) == sorted(expected)
