"""Unit tests for the shared CLI error boundary."""

from __future__ import annotations

import json

import pytest
import typer
from typer.testing import CliRunner

from ..auth.certificate import AeatSessionExpiredError
from ..browser.session import BrowserError
from ..errors import (
    DeprecatedAliasError,
    ErrorCategory,
    MovedAliasError,
    WorkspaceLockedError,
    get_error_exit_code,
)
from ..observability._errors import RunContextMissingError
from ..portals._errors import PortalIntegrityError
from ..review._errors import ReviewKindReservedError
from ._errors import decorate_typer_app, error_boundary_under_test

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

runner = CliRunner()

app = typer.Typer(name="aeat", no_args_is_help=True)


@app.command("locked")
def locked_command(json: bool = typer.Option(False, "--json")) -> None:
    raise WorkspaceLockedError()


@app.command("refused")
def refused_command() -> None:
    raise ReviewKindReservedError("queue", "tracked by issue #230")


@app.command("auth")
def auth_command() -> None:
    raise AeatSessionExpiredError()


@app.command("integrity")
def integrity_command() -> None:
    raise PortalIntegrityError()


@app.command("fail")
def fail_command() -> None:
    raise BrowserError()


@app.command("internal")
def internal_command() -> None:
    raise RunContextMissingError()


@app.command("deprecated")
def deprecated_command() -> None:
    raise DeprecatedAliasError()


@app.command("moved")
def moved_command() -> None:
    raise MovedAliasError()


decorate_typer_app(app)


def test_human_readable_error_is_emitted_by_default() -> None:
    result = runner.invoke(app, ["locked"])

    assert result.exit_code == get_error_exit_code(ErrorCategory.LOCKED)
    assert result.stdout == ""
    assert "LOCKED:" in result.stderr
    assert "-> Run `aeat workflow list`" in result.stderr


def test_json_error_is_emitted_when_json_flag_is_present() -> None:
    result = runner.invoke(app, ["locked", "--json"])

    assert result.exit_code == get_error_exit_code(ErrorCategory.LOCKED)
    assert result.stdout == ""

    payload = json.loads(result.stderr)
    assert payload["error"]["category"] == "LOCKED"
    assert payload["error"]["schema_version"] == "1"


@pytest.mark.parametrize(
    ("command_name", "category"),
    [
        ("locked", ErrorCategory.LOCKED),
        ("refused", ErrorCategory.REFUSED),
        ("auth", ErrorCategory.AUTH),
        ("integrity", ErrorCategory.INTEGRITY),
        ("fail", ErrorCategory.FAIL),
        ("internal", ErrorCategory.INTERNAL),
        ("deprecated", ErrorCategory.DEPRECATED),
        ("moved", ErrorCategory.MOVED),
    ],
)
def test_exit_code_matches_placeholder_category_mapping(
    command_name: str,
    category: ErrorCategory,
) -> None:
    result = runner.invoke(app, [command_name])
    assert result.exit_code == get_error_exit_code(category)


def test_boundary_re_raises_original_exception_under_test() -> None:
    with error_boundary_under_test(), pytest.raises(WorkspaceLockedError):
        runner.invoke(app, ["locked"], catch_exceptions=False)
