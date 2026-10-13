"""Importing an entry module costs its shell, not the work behind it.

``aeat`` and the workbench launcher are imported before anything has been
parsed or selected, so every module they import is paid on every start --
``--help``, a refused verb and a shell completion included. The command
handlers, the error-code catalogue, the locale catalogues, pydantic models and
the logging configuration all load when a command or render first needs them.

Each entry module is gated two ways in a fresh interpreter: its Cadrumo
modules must stay within an explicit allow-list, so a new eager import is a
reviewed decision rather than a drift, and a deny-list of heavy third-party
and standard-library subtrees must stay absent. Wall time is deliberately not
measured: it depends on the host, while the imported set does not.
"""

from __future__ import annotations

import json
import sys

import pytest

from cadrumo.tests.audited_process import run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: Subtrees no entry module may import. Each is either a framework that only a
#: built command tree or a rendered page needs, or a cost (model construction,
#: entry-point scans, catalogue parsing, handler configuration) that belongs to
#: the first use.
_DENIED_SUBTREES: tuple[str, ...] = (
    "pydantic",
    "pydantic_core",
    "pydantic_settings",
    "typer",
    "click",
    "rich",
    "textual",
    "yaml",
    "i18n",
    "rtoml",
    "asyncio",
    "importlib.metadata",
    "logging.config",
    "logging.handlers",
)

_LOGGING_CLOSURE: frozenset[str] = frozenset(
    {
        "cadrumo",
        "cadrumo.core",
        "cadrumo.core.cli_metadata",
        "cadrumo.core.diagnostic_log",
        "cadrumo.core.hashing",
        "cadrumo.core.iban",
        "cadrumo.core.logging",
        "cadrumo.core.process_binding",
        "cadrumo.core.redaction",
        "cadrumo.core.redaction.rules",
        "cadrumo.core.redaction.tax_identity_admission",
        "cadrumo.core.type_guards",
    }
)

#: The CLI entry imports the declarative command graph and the vocabulary it is
#: declared in; Typer, the error boundary and every command module load when
#: the app is built or a command runs.
_CLI_MAIN_ALLOWED: frozenset[str] = frozenset(
    {
        "cadrumo",
        "cadrumo.application",
        "cadrumo.application.operator_surface",
        "cadrumo.application.operator_surface.command_ports",
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

#: The workbench launcher needs its logger and the exception root; the
#: application, Textual and the runtime client load when the workbench starts.
_TUI_LAUNCHER_ALLOWED: frozenset[str] = _LOGGING_CLOSURE | {
    "cadrumo.core.errors",
    "cadrumo.core.errors.hierarchy",
    "cadrumo.entrypoints",
    "cadrumo.entrypoints.tui",
    "cadrumo.entrypoints.tui.launcher",
}

_PROBE = """
import json, sys
__import__(sys.argv[1])
print(json.dumps(sorted(sys.modules)))
"""


def _imported_by(module: str) -> frozenset[str]:
    """Return every module a fresh interpreter holds after importing ``module``.

    A fresh process is the method: the test session has imported most of the
    tree already, so its own ``sys.modules`` says nothing about one import.
    """
    completed = run_audited_process(
        [sys.executable, "-I", "-c", _PROBE, module],
        capture_output=True,
        text=True,
        check=False,
        timeout=None,
    )
    assert completed.returncode == 0, completed.stderr
    loaded: object = json.loads(str(completed.stdout).strip().splitlines()[-1])
    assert isinstance(loaded, list)
    names = frozenset(str(name) for name in loaded)
    # A crashed or empty probe would pass every absence check vacuously.
    assert module in names, f"the probe never imported {module}"
    return names


def _denied(names: frozenset[str]) -> list[str]:
    return sorted(
        name for name in names if any(name == root or name.startswith(f"{root}.") for root in _DENIED_SUBTREES)
    )


def _unlisted_cadrumo(names: frozenset[str], allowed: frozenset[str]) -> list[str]:
    return sorted(name for name in names if (name == "cadrumo" or name.startswith("cadrumo.")) and name not in allowed)


@pytest.mark.parametrize(
    ("module", "allowed"),
    [
        pytest.param("cadrumo.entrypoints.cli.main", _CLI_MAIN_ALLOWED, id="cli-main"),
        pytest.param("cadrumo.entrypoints.tui.launcher", _TUI_LAUNCHER_ALLOWED, id="tui-launcher"),
        pytest.param("cadrumo.core.logging", _LOGGING_CLOSURE, id="core-logging"),
    ],
)
def test_an_entry_import_loads_only_its_shell(module: str, allowed: frozenset[str]) -> None:
    names = _imported_by(module)

    assert _denied(names) == [], (
        f"importing {module} loaded subtrees that belong to first use. Find the eager import "
        "with `python -X importtime -c 'import <module>'` and move it into the function that needs it."
    )
    assert _unlisted_cadrumo(names, allowed) == [], (
        f"importing {module} gained Cadrumo modules outside its allow-list. Defer the import, "
        "or extend the allow-list only if the module is genuinely part of the entry shell."
    )


def test_the_floor_detects_an_eager_catalogue_import() -> None:
    """ANTI-TAUTOLOGY: both scans must say yes to a module that builds the catalogue models."""
    names = _imported_by("cadrumo.core.errors.error_codes")

    assert "pydantic" in _denied(names)
    assert "cadrumo.core.errors.error_codes" in _unlisted_cadrumo(names, _CLI_MAIN_ALLOWED)
