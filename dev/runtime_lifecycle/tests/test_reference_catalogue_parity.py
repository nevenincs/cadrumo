"""The harness `authority` tool answers each reference question with the command line's JSON result.

Both sides run for real: the command line through the cached Click runner and
the tool through the adapter's wire boundary, against the same published
authority. A question is one command line and one set of tool arguments; the
tool's `report` must equal the command line's `result`, and a refusal must carry
the same words.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from cadrumo.application.modelo.work_create_policy import ceded_autonomic_modelo_locale_key
from cadrumo.core.i18n.render import tr
from cadrumo.domain.portals.registry import PORTAL_REGISTRY
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.tests.cli_envelope import require_schema_envelope
from cadrumo_harness.mcp.tests.admitted_lease import admitted_adapter

__all__ = ["_isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FIRST_PORTAL = next(iter(PORTAL_REGISTRY.values())).portal.value
_SCOPE = ["--year", "2025", "--period", "1T"]
_SCOPE_ARGS = {"filing_year": 2025, "period": "1T"}

# (label, command line, tool arguments)
_QUESTIONS: tuple[tuple[str, list[str], dict[str, Any]], ...] = (
    ("modelos", ["app", "modelo", "list"], {"query": "modelos"}),
    ("modelos-year", ["app", "modelo", "list", "--year", "2025"], {"query": "modelos", "filing_year": 2025}),
    ("modelos-domain", ["app", "modelo", "list", "--domain", "iva"], {"query": "modelos", "domain": "iva"}),
    (
        "modelos-domain-year",
        ["app", "modelo", "list", "--domain", "irpf", "--year", "2025"],
        {"query": "modelos", "domain": "irpf", "filing_year": 2025},
    ),
    ("support", ["app", "modelo", "support-matrix"], {"query": "support"}),
    (
        "describe-scoped",
        ["app", "modelo", "describe", "130", *_SCOPE],
        {"query": "describe", "modelo": "130", **_SCOPE_ARGS},
    ),
    (
        "describe-scoped-as-of",
        ["app", "modelo", "describe", "130", *_SCOPE, "--as-of", "2025-06-30"],
        {"query": "describe", "modelo": "130", **_SCOPE_ARGS, "as_of": "2025-06-30"},
    ),
    (
        "describe-period-only",
        ["app", "modelo", "describe", "130", "--period", "1T"],
        {"query": "describe", "modelo": "130", "period": "1T"},
    ),
    (
        "describe-census-token",
        ["app", "modelo", "describe", "036", "--period", "alta"],
        {"query": "describe", "modelo": "036", "period": "alta"},
    ),
    ("describe-latest", ["app", "modelo", "describe", "303"], {"query": "describe", "modelo": "303"}),
    (
        "casillas-scoped",
        ["app", "modelo", "casillas", "130", *_SCOPE],
        {"query": "casillas", "modelo": "130", **_SCOPE_ARGS},
    ),
    (
        "casillas-period-only",
        ["app", "modelo", "casillas", "130", "--period", "1T"],
        {"query": "casillas", "modelo": "130", "period": "1T"},
    ),
    ("casillas-latest", ["app", "modelo", "casillas", "130"], {"query": "casillas", "modelo": "130"}),
    (
        "casillas-input-kind",
        ["app", "modelo", "casillas", "130", *_SCOPE, "--input-kind", "computed"],
        {"query": "casillas", "modelo": "130", **_SCOPE_ARGS, "input_kind": "computed"},
    ),
    (
        "casillas-required",
        ["app", "modelo", "casillas", "130", *_SCOPE, "--required"],
        {"query": "casillas", "modelo": "130", **_SCOPE_ARGS, "required": True},
    ),
    (
        "casillas-form-number",
        ["app", "modelo", "casillas", "303", *_SCOPE, "--form-number", "46"],
        {"query": "casillas", "modelo": "303", **_SCOPE_ARGS, "form_number": "46"},
    ),
    (
        "casillas-number",
        ["app", "modelo", "casillas", "130", *_SCOPE, "--number", "03"],
        {"query": "casillas", "modelo": "130", **_SCOPE_ARGS, "casilla_number": "03"},
    ),
    (
        "casillas-combined",
        ["app", "modelo", "casillas", "130", "--period", "1T", "--input-kind", "bound", "--required"],
        {"query": "casillas", "modelo": "130", "period": "1T", "input_kind": "bound", "required": True},
    ),
    (
        "casilla-scoped",
        ["app", "modelo", "casilla", "130", "03", *_SCOPE],
        {"query": "casilla", "modelo": "130", "casilla": "03", **_SCOPE_ARGS},
    ),
    (
        "casilla-period-only",
        ["app", "modelo", "casilla", "130", "01", "--period", "1T"],
        {"query": "casilla", "modelo": "130", "casilla": "01", "period": "1T"},
    ),
    (
        "casilla-latest",
        ["app", "modelo", "casilla", "130", "03"],
        {"query": "casilla", "modelo": "130", "casilla": "03"},
    ),
    (
        "formulas-scoped",
        ["app", "modelo", "formulas", "130", *_SCOPE],
        {"query": "formulas", "modelo": "130", **_SCOPE_ARGS},
    ),
    (
        "formulas-period-only",
        ["app", "modelo", "formulas", "130", "--period", "1T"],
        {"query": "formulas", "modelo": "130", "period": "1T"},
    ),
    ("formulas-latest", ["app", "modelo", "formulas", "130"], {"query": "formulas", "modelo": "130"}),
    ("categories", ["app", "ledger", "categories"], {"query": "categories"}),
    ("portals", ["app", "live", "portals", "list"], {"query": "portals"}),
    (
        "portals-category",
        ["app", "live", "portals", "list", "--category", "filing"],
        {"query": "portals", "category": "filing"},
    ),
    ("portals-modelo", ["app", "live", "portals", "list", "--modelo", "303"], {"query": "portals", "modelo": "303"}),
    ("portal", ["app", "live", "portals", "view", _FIRST_PORTAL], {"query": "portal", "portal": _FIRST_PORTAL}),
    ("auth-providers", ["config", "auth", "providers"], {"query": "auth_providers"}),
    ("apoderado-scopes", ["config", "auth", "apoderado", "scopes", "list"], {"query": "apoderado_scopes"}),
)


def _as_printed(value: object) -> object:
    """Trim a portal URL to scheme and host, as the command line's output redaction does.

    The catalogue's URLs are public data, so the tool returns them whole; the
    command line prints only the origin. Nothing else is rewritten.
    """
    if isinstance(value, dict):
        return {
            key: _origin(item) if key == "url" and isinstance(item, str) else _as_printed(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_as_printed(item) for item in value]
    return value


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.hostname}"


async def _tool_reply(arguments: dict[str, Any]) -> dict[str, Any]:
    # Every tool but status answers only under an admitted session; admission
    # is not this module's subject, so the tool runs under a live lease.
    adapter = admitted_adapter()
    try:
        return await adapter.call("authority", arguments)
    finally:
        await adapter.close()


def _command_line(args: list[str]) -> Any:
    return invoke_cached_cli(["--format", "json", *args])


@pytest.mark.anyio
@pytest.mark.parametrize(("label", "command_line", "arguments"), _QUESTIONS, ids=[row[0] for row in _QUESTIONS])
async def test_tool_report_equals_the_command_line_result(
    label: str, command_line: list[str], arguments: dict[str, Any]
) -> None:
    invocation = _command_line(command_line)
    assert invocation.exit_code == 0, (label, invocation.output)
    reply = await _tool_reply(arguments)

    assert reply["outcome"] == "published", (label, reply)
    assert _as_printed(reply["report"]) == require_schema_envelope(invocation.output), label


def test_every_filter_is_exercised_by_a_question() -> None:
    exercised = {key for _label, _line, arguments in _QUESTIONS for key in arguments}

    assert {
        "filing_year",
        "domain",
        "period",
        "as_of",
        "input_kind",
        "required",
        "form_number",
        "casilla_number",
        "casilla",
        "category",
        "modelo",
        "portal",
    } <= exercised


@pytest.mark.anyio
@pytest.mark.parametrize("query", ["describe", "casillas", "casilla", "formulas"])
@pytest.mark.parametrize("modelo", ["600", "620", "650", "660"])
async def test_a_ceded_autonomic_tax_is_redirected_by_both(query: str, modelo: str) -> None:
    arguments: dict[str, Any] = {"query": query, "modelo": modelo}
    command_line = ["app", "modelo", "casilla" if query == "casilla" else query, modelo]
    if query == "casilla":
        arguments["casilla"] = "01"
        command_line.append("01")
    redirect = tr(ceded_autonomic_modelo_locale_key(modelo) or "", modelo=modelo)

    reply = await _tool_reply(arguments)
    invocation = _command_line(command_line)

    assert reply == {"outcome": "refused", "code": "ceded_autonomic_modelo", "message": redirect}
    assert invocation.exit_code != 0
    assert redirect in invocation.output


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("command_line", "arguments"),
    [
        (
            ["app", "modelo", "describe", "130", "--year", "2025", "--period", "ZZ"],
            {"query": "describe", "modelo": "130", "filing_year": 2025, "period": "ZZ"},
        ),
        (
            ["app", "modelo", "casillas", "130", "--year", "2025", "--period", "2025"],
            {"query": "casillas", "modelo": "130", "filing_year": 2025, "period": "2025"},
        ),
        (
            ["app", "modelo", "formulas", "130", "--year", "2025", "--period", "QQ"],
            {"query": "formulas", "modelo": "130", "filing_year": 2025, "period": "QQ"},
        ),
    ],
    ids=["describe", "casillas", "formulas"],
)
async def test_an_invalid_period_token_is_refused_by_both_with_the_declared_tokens(
    command_line: list[str], arguments: dict[str, Any]
) -> None:
    reply = await _tool_reply(arguments)
    invocation = _command_line(command_line)

    assert reply["outcome"] == "refused"
    assert reply["code"] == "invalid_request"
    assert "1T, 2T, 3T, 4T" in reply["message"]
    assert invocation.exit_code != 0
    assert reply["message"] in invocation.output


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("command_line", "arguments"),
    [
        (
            ["app", "modelo", "describe", "130", "--year", "2025"],
            {"query": "describe", "modelo": "130", "filing_year": 2025},
        ),
        (
            ["app", "modelo", "casilla", "130", "03", "--year", "2025"],
            {"query": "casilla", "modelo": "130", "casilla": "03", "filing_year": 2025},
        ),
        (
            ["app", "modelo", "describe", "130", "--period", "1T", "--as-of", "2025-06-30"],
            {"query": "describe", "modelo": "130", "period": "1T", "as_of": "2025-06-30"},
        ),
    ],
    ids=["year-without-period", "casilla-year-without-period", "as-of-without-year"],
)
async def test_an_incomplete_scope_is_refused_by_both(command_line: list[str], arguments: dict[str, Any]) -> None:
    reply = await _tool_reply(arguments)
    invocation = _command_line(command_line)

    assert reply["outcome"] == "refused"
    assert invocation.exit_code != 0


@pytest.mark.anyio
async def test_both_portal_filters_at_once_are_refused_by_both() -> None:
    reply = await _tool_reply({"query": "portals", "category": "filing", "modelo": "303"})
    invocation = _command_line(["app", "live", "portals", "list", "--category", "filing", "--modelo", "303"])

    assert reply["outcome"] == "refused"
    assert reply["code"] == "invalid_request"
    assert reply["message"] == tr("cli.app.live.portals.category_modelo_exclusive")
    assert invocation.exit_code != 0


@pytest.mark.anyio
async def test_an_unknown_portal_is_refused_by_both() -> None:
    reply = await _tool_reply({"query": "portal", "portal": "NOT_A_PORTAL_ID"})
    invocation = _command_line(["app", "live", "portals", "view", "NOT_A_PORTAL_ID"])

    assert reply["outcome"] == "refused"
    assert reply["code"] == "portal_registry_refused"
    assert invocation.exit_code != 0


@pytest.mark.anyio
async def test_the_one_difference_is_the_portal_url_the_command_line_trims_to_its_origin() -> None:
    reply = await _tool_reply({"query": "portals", "modelo": "303"})
    printed = require_schema_envelope(_command_line(["app", "live", "portals", "list", "--modelo", "303"]).output)

    full_url = reply["report"]["rows"][0]["url"]
    assert urlsplit(full_url).path not in {"", "/"}
    assert printed["rows"][0]["url"] == _origin(full_url)
    assert reply["report"]["rows"][0] != printed["rows"][0]
