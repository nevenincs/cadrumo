"""Unit tests for the shared CLI error boundary.

Exercises :func:`aeat.entrypoints.cli._errors.decorate_typer_app`
across every error category surfaced by the CLI:
``LOCKED``/``REFUSED``/``AUTH``/``INTEGRITY``/``FAIL``/``INTERNAL``/``DEPRECATED``/``MOVED``,
plus validation errors, unexpected runtime errors, and the
``--json`` and JSON-alias flag plumbing. Also verifies that
:func:`aeat.entrypoints.cli._errors.error_boundary_under_test`
re-raises the original exception so test code can assert on the
exact failure type.
"""

from __future__ import annotations

import json

import pytest
import typer
from pydantic import BaseModel, ConfigDict, ValidationError
from typer.testing import CliRunner

from ...adapters.outbound.aeat.auth.certificate import AeatSessionExpiredError
from ...adapters.outbound.aeat.browser.session import BrowserError
from ...application.review._errors import ReviewKindReservedError
from ...core.access_gate import LiveSubmitForbiddenError
from ...core.errors import (
    DeprecatedAliasError,
    ErrorCategory,
    MovedAliasError,
    get_error_exit_code,
)
from ...core.observability._errors import RunContextMissingError
from ...domain.portals._errors import PortalIntegrityError
from ._errors import decorate_typer_app, error_boundary_under_test

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

runner = CliRunner()

app = typer.Typer(name="aeat", no_args_is_help=True)


@app.command("locked")
def locked_command(json: bool = typer.Option(False, "--json")) -> None:
    raise LiveSubmitForbiddenError()


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


class _StrictPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    value: int


@app.command("validation")
def validation_command() -> None:
    _StrictPayload.model_validate({"value": "bad"})


@app.command("unexpected")
def unexpected_command() -> None:
    raise RuntimeError("boom")


@app.command("json-alias")
def json_alias_command(as_json: bool = typer.Option(False, "--json")) -> None:
    _ = as_json
    raise LiveSubmitForbiddenError()


@app.command("passthrough")
def passthrough_command() -> None:
    raise typer.Exit(code=2)


decorate_typer_app(app)


def test_human_readable_error_is_emitted_by_default() -> None:
    result = runner.invoke(app, ["locked"])

    assert result.exit_code == get_error_exit_code(ErrorCategory.LOCKED)
    assert result.stdout == ""
    assert "LOCKED:" in result.stderr
    assert "-> Run `aeat submission export`" in result.stderr


def test_json_error_is_emitted_when_json_flag_is_present() -> None:
    result = runner.invoke(app, ["locked", "--json"])

    assert result.exit_code == get_error_exit_code(ErrorCategory.LOCKED)
    assert result.stdout == ""

    payload = json.loads(result.stderr)
    assert payload["error"]["category"] == "LOCKED"
    assert payload["error"]["schema_version"] == "1"


def test_json_error_is_emitted_when_json_flag_uses_non_json_parameter_name() -> None:
    result = runner.invoke(app, ["json-alias", "--json"])

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
        ("validation", ErrorCategory.INTEGRITY),
        ("unexpected", ErrorCategory.INTERNAL),
    ],
)
def test_exit_code_matches_placeholder_category_mapping(
    command_name: str,
    category: ErrorCategory,
) -> None:
    result = runner.invoke(app, [command_name])
    assert result.exit_code == get_error_exit_code(category)


def test_boundary_re_raises_original_exception_under_test() -> None:
    with error_boundary_under_test(), pytest.raises(LiveSubmitForbiddenError):
        runner.invoke(app, ["locked"], catch_exceptions=False)


def test_validation_error_is_wrapped_into_structured_boundary() -> None:
    result = runner.invoke(app, ["validation"])

    assert result.exit_code == get_error_exit_code(ErrorCategory.INTEGRITY)
    assert result.stdout == ""
    assert "INTEGRITY:" in result.stderr
    assert "The command input failed validation." in result.stderr
    assert "error_type: ValidationError" in result.stderr


def test_unexpected_exception_is_wrapped_into_structured_boundary() -> None:
    result = runner.invoke(app, ["unexpected"])

    assert result.exit_code == get_error_exit_code(ErrorCategory.INTERNAL)
    assert result.stdout == ""
    assert "INTERNAL:" in result.stderr
    assert "The command failed due to an unexpected internal error." in result.stderr
    assert "error_type: RuntimeError" in result.stderr


def test_boundary_re_raises_validation_error_under_test() -> None:
    with error_boundary_under_test(), pytest.raises(ValidationError):
        runner.invoke(app, ["validation"], catch_exceptions=False)


def test_boundary_re_raises_unexpected_exception_under_test() -> None:
    with error_boundary_under_test(), pytest.raises(RuntimeError, match="boom"):
        runner.invoke(app, ["unexpected"], catch_exceptions=False)


def test_click_control_flow_passes_through_unchanged() -> None:
    result = runner.invoke(app, ["passthrough"])

    assert result.exit_code == 2
    assert result.stderr == ""
