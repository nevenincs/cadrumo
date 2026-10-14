"""Importing a tax CLI entry module costs its shell, not the work behind it.

The ``aeat`` entry is imported before anything has been parsed or selected, so
every module it imports is paid on every start -- ``--help``, a refused verb
and shell completion included. Command handlers, error-code catalogues, locale
catalogues, pydantic models and logging configuration load when first needed.

Each entry module is gated two ways in a fresh interpreter: its Cadrumo
modules must stay within an explicit allow-list, so a new eager import is a
reviewed decision rather than a drift, and a deny-list of heavy third-party
and standard-library subtrees must stay absent. Wall time is deliberately not
measured: it depends on the host, while the imported set does not.
"""

from __future__ import annotations

import pytest

from cadrumo.tests.entry_import_floor_support import (
    LOGGING_IMPORT_CLOSURE,
    denied_imports,
    imported_modules,
    unlisted_modules,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The CLI entry imports the declarative command graph and the vocabulary it is
#: declared in; Typer, the error boundary and every command module load when
#: the app is built or a command runs.
_CLI_MAIN_ALLOWED: frozenset[str] = frozenset(
    {
        "cadrumo",
        "cadrumo.application",
        "cadrumo.application.operator_surface",
        "cadrumo_client.contracts.command_ports",
        "cadrumo.core",
        "cadrumo.core.cli_metadata",
        "cadrumo.core.product_identity",
        "cadrumo.core.storage_environment",
        "cadrumo.core.transport_locus",
        "cadrumo.core.type_guards",
        "cadrumo.entrypoints",
        "cadrumo.entrypoints.cli",
        "cadrumo.entrypoints.cli._command_parameter_validation",
        "cadrumo.entrypoints.cli._command_policy_validation",
        "cadrumo.entrypoints.cli._command_secret_contracts",
        "cadrumo.entrypoints.cli._command_structure_validation",
        "cadrumo.entrypoints.cli._root_command_specs",
        "cadrumo.entrypoints.cli.command_graph",
        "cadrumo.entrypoints.cli.command_parameter_contracts",
        "cadrumo.entrypoints.cli.command_shared_contracts",
        "cadrumo.entrypoints.cli.command_spec",
        "cadrumo.entrypoints.cli.command_specs",
        "cadrumo.entrypoints.cli.main",
    }
)


@pytest.mark.parametrize(
    ("module", "allowed"),
    [
        pytest.param("cadrumo.entrypoints.cli.main", _CLI_MAIN_ALLOWED, id="cli-main"),
        pytest.param("cadrumo.core.logging", LOGGING_IMPORT_CLOSURE, id="core-logging"),
    ],
)
def test_an_entry_import_loads_only_its_shell(module: str, allowed: frozenset[str]) -> None:
    names = imported_modules(module)

    assert denied_imports(names) == [], (
        f"importing {module} loaded subtrees that belong to first use. Find the eager import "
        "with `python -X importtime -c 'import <module>'` and move it into the function that needs it."
    )
    assert unlisted_modules(names, allowed) == [], (
        f"importing {module} gained Cadrumo modules outside its allow-list. Defer the import, "
        "or extend the allow-list only if the module is genuinely part of the entry shell."
    )


def test_the_floor_detects_an_eager_catalogue_import() -> None:
    """ANTI-TAUTOLOGY: both scans must say yes to a module that builds the catalogue models."""
    names = imported_modules("cadrumo.core.errors.error_codes")

    assert "pydantic" in denied_imports(names)
    assert "cadrumo.core.errors.error_codes" in unlisted_modules(names, _CLI_MAIN_ALLOWED)
