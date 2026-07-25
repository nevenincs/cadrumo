"""Guards for the operator-facing surface a command-group import failure renders.

The classification seam decides whether a lazy import failure is a missing
optional extra (degrade to a placeholder) or a missing required dependency
(refuse loudly); ``test_command_group_import_classification`` owns that
decision in the unit lane. This module owns what the operator actually sees
once the decision is made, which is where the original defect was visible:
``app modelo --help`` exited 0 and rendered a subcommand-less placeholder while
a required dependency was simply absent.

The required-dependency coverage runs in a fresh interpreter with a real
:mod:`importlib` meta-path finder that refuses the blocked package, so the
module is genuinely unimportable exactly as it would be on an incomplete
install — the production condition, not a simulation of it.

Assertions are structural throughout — registered error code, category, exit
code, and context keys — never the localised prose, which is free to change.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from ....core import OPTIONAL_EXTRAS
from ....core.errors import ErrorCategory, get_error_exit_code
from .. import _surface_for_import_failure
from .._errors import decorate_typer_app
from ._command_group_import_support import (
    AFFECTED_GROUP,
    EXPECTED_ERROR_CODE,
    REQUIRED_DEPENDENCY,
    run_cli_with_blocked_package,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_missing_required_dependency_refuses_instead_of_degrading() -> None:
    """A required dependency's absence refuses loudly, naming module and remedy.

    This is the regression gate for the silent degradation. Before the fix this
    invocation exited 0 and printed a subcommand-less help page; the group had
    quietly lost all 23 of its subcommands while reporting nothing wrong.
    """
    completed = run_cli_with_blocked_package(
        REQUIRED_DEPENDENCY,
        ["--format", "json", "app", AFFECTED_GROUP, "--help"],
    )

    assert completed.returncode == get_error_exit_code(ErrorCategory.FAIL), (
        f"expected the FAIL exit code, got {completed.returncode}: {completed.stdout}{completed.stderr}"
    )
    document = json.loads(completed.stderr.strip().splitlines()[-1])
    error = document["error"]
    assert error["code"] == EXPECTED_ERROR_CODE
    assert error["category"] == ErrorCategory.FAIL.value
    # The refusal must name the actual failure and an actionable remedy.
    assert error["context"]["module"] == REQUIRED_DEPENDENCY
    assert error["context"]["group"] == AFFECTED_GROUP
    assert error["suggestion"], "a required-dependency refusal must carry a remedy"
    # The failure rides the shared envelope spine, not a bespoke channel.
    assert document["status"] == "error"
    assert document["notices"] == []


def test_missing_required_dependency_does_not_render_a_placeholder_group() -> None:
    """The degraded surface is gone: no subcommand-less group help is rendered.

    Complements the JSON gate above by covering the plain-text surface an
    operator actually sees, and by asserting the *absence* of the specific shape
    that made the defect invisible — a successful help render for a group whose
    subcommand list has silently emptied.
    """
    completed = run_cli_with_blocked_package(REQUIRED_DEPENDENCY, ["app", AFFECTED_GROUP, "--help"])

    assert completed.returncode != 0, completed.stdout
    assert "Usage: aeat app modelo" not in completed.stdout
    assert REQUIRED_DEPENDENCY in completed.stderr
    assert "Traceback" not in completed.stderr, completed.stderr


def test_missing_optional_extra_still_degrades_gracefully() -> None:
    """A registered optional extra keeps its graceful placeholder surface.

    The legitimate half of the distinction. A bare install omits these packages
    by design, so the subtree must stay resolvable, render help, and refuse with
    the install hint rather than crashing the CLI.
    """
    extra = next(candidate for candidate in OPTIONAL_EXTRAS if candidate.extra == "browser")
    error = ModuleNotFoundError(f"No module named {extra.import_name!r}", name=extra.import_name)

    surface = _surface_for_import_failure("live", error)
    decorate_typer_app(surface)

    help_result = CliRunner().invoke(surface, ["--help"])
    assert help_result.exit_code == 0, help_result.output

    refusal = CliRunner().invoke(surface, [])
    assert refusal.exit_code == get_error_exit_code(ErrorCategory.ERROR), refusal.output
    # The refusal names the exact install command, never a bare "unavailable".
    assert extra.install_hint in refusal.output
