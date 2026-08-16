"""Real-behavior tests for ``modelo work create --quiet`` output trimming.

A verb-level ``--quiet`` on
``aeat app modelo work create`` suppresses the human-readable
confirmation prose while leaving the machine surface (the
``--format json`` :class:`SchemaEnvelope` and its notices) untouched.

These tests drive the exact emit boundary the flag flows through
(:func:`_emit_work_create_result`) and the shared transport it relies on
(:func:`_emit_envelope`) with a real
:class:`~cadrumo.domain.modelos.WorkUnit`, a real registered result model,
and a real Typer/Click context, capturing stdout. No mocks, stubs, or
skips.

The tests deliberately avoid the full CLI dispatch and the plazo/deadline
projection so the quiet contract is verified without loading the modelo
registry — the output-trimming decision is pure transport logic that owes
nothing to registry validation, and the ``work create`` dispatch path
eagerly validates the whole registry. A Modelo 130 unit is
used so the Modelo-100 filing-obligation advisory channel
short-circuits to empty, isolating the confirmation-prose trimming under
test.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import cast

import pytest
import typer
import typer.main
from typer._click.core import Command as TyperCommand
from typer.core import TyperGroup, TyperOption

from ....core import Period
from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id
from ....tests.cli_runner import cadrumo_click_command, invoke_cached_cli, semantic_cli_output
from .._common import _emit_envelope
from .._modelo_payloads import WorkCreateResult
from .._modelo_rendering import work_unit_payload
from .._modelo_work_lifecycle_cli import _emit_work_create_result
from ._english_locale_fixture import english_locale_fixture

__all__ = ["english_locale_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_BUCKET_ID = "30330300-0000-4000-8000-000000000130"


def _build_m130_unit() -> WorkUnit:
    period = Period.from_year_and_code(2025, "1T")
    wid = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2025,
        period=period,
        revision_id="2019-y-siguientes",
    )
    return WorkUnit(
        work_unit_id=wid,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("130"),
        filing_year=2025,
        period=period,
        revision_id="2019-y-siguientes",
        name="130 2025 1T",
        created_at=_T0,
        updated_at=_T0,
    )


def _context(format_name: str) -> typer.Context:
    app = typer.Typer()

    @app.command()
    def _noop() -> None: ...

    return typer.Context(typer.main.get_command(app), obj={"format": format_name})


def _work_create_result() -> WorkCreateResult:
    return WorkCreateResult.model_validate(
        {
            "operation": "modelo.work.create",
            "status": "created",
            "status_message": "New work unit created.",
            "name_applied": None,
            "applicability_guard_bypassed": False,
            **work_unit_payload(_build_m130_unit()).model_dump(mode="python"),
        },
    )


# ---------------------------------------------------------------------------
# The flag is wired onto the live create verb
# ---------------------------------------------------------------------------


def test_quiet_flag_is_registered_on_the_create_verb() -> None:
    """``--quiet`` is a real option on ``app modelo work create``.

    ``--help`` renders the Typer tree without loading the modelo registry,
    so this pins the flag wiring independently of registry validation. The
    The rendered surface proves the option is reachable. The live Click
    parameter proves it carries documentation without coupling this test to
    whichever output locale materialized the cached command tree first.
    """
    result = invoke_cached_cli(["app", "modelo", "work", "create", "--help"])
    assert result.exit_code == 0, result.output
    help_output = semantic_cli_output(result)
    assert "--quiet" in help_output

    command = cast(TyperCommand, cadrumo_click_command())
    context = typer.Context(command)
    for segment in ("app", "modelo", "work", "create"):
        assert isinstance(command, TyperGroup)
        resolved = command.get_command(context, segment)
        assert resolved is not None
        command = resolved
        context = typer.Context(command, parent=context)
    quiet = next(param for param in command.params if isinstance(param, TyperOption) and "--quiet" in param.opts)
    assert quiet.help is not None and quiet.help.strip()


# ---------------------------------------------------------------------------
# The quiet flag on the real create emit boundary
# ---------------------------------------------------------------------------


def test_text_mode_quiet_suppresses_confirmation(capsys: pytest.CaptureFixture[str]) -> None:
    """``quiet`` trims every confirmation line in text mode.

    Modelo 130 has no filing-obligation advisory (that notice channel is
    Modelo 100 only), so the quiet text surface is empty — proving the
    flag suppressed the prose without swallowing a notice.
    """
    _emit_work_create_result(
        _context("text"),
        unit=_build_m130_unit(),
        reused=False,
        name=None,
        name_applied=None,
        allow_not_applicable=False,
        quiet=True,
    )
    out = capsys.readouterr().out
    assert out.strip() == ""
    assert "operation" not in out
    assert "work_unit_id" not in out
    assert "New work unit created." not in out


def test_quiet_json_envelope_is_complete(capsys: pytest.CaptureFixture[str]) -> None:
    """The quiet JSON envelope carries the full typed machine surface.

    ``--quiet`` may only trim human text lines; in JSON mode the typed
    ``result`` payload and the envelope spine must be emitted in full,
    proving the flag never degrades the machine surface.
    """
    _emit_work_create_result(
        _context("json"),
        unit=_build_m130_unit(),
        reused=False,
        name=None,
        name_applied=None,
        allow_not_applicable=False,
        quiet=True,
    )
    envelope = json.loads(capsys.readouterr().out)

    assert envelope["schema_version"]
    assert envelope["command"] == "modelo.work.create"
    assert envelope["status"] == "success"
    result = envelope["result"]
    assert isinstance(result, dict)
    assert result["status"] == "created"
    assert result["operation"] == "modelo.work.create"
    assert result["status_message"] == "New work unit created."
    assert result["work_unit_id"]
    assert result["modelo"] == "130"


# ---------------------------------------------------------------------------
# The transport contract the quiet branch relies on
# ---------------------------------------------------------------------------
#
# The quiet branch only ever changes the ``lines`` argument passed to
# ``_emit_envelope``; it never touches ``result`` or ``notices``. These
# tests pin that (a) text mode emits the supplied lines, so a populated
# (non-quiet) line set prints and an empty (quiet) line set is silent,
# and (b) JSON mode is byte-identical regardless of the lines, so the
# quiet branch provably cannot affect the machine surface.


def test_text_mode_emits_the_supplied_lines(capsys: pytest.CaptureFixture[str]) -> None:
    """Text mode prints exactly the supplied line iterator.

    This is the non-quiet half of the contrast: a populated line set (as
    the create verb builds when ``quiet`` is False) reaches the operator,
    so the quiet-mode empty line set is a real suppression, not a no-op on
    always-empty output.
    """
    result = _work_create_result()
    lines = [
        "operation\tmodelo.work.create",
        "status\tcreated",
        "work_unit_id\tabc123",
        "New work unit created.",
    ]

    _emit_envelope(_context("text"), command="modelo.work.create", result=result, lines=lines)
    out = capsys.readouterr().out

    for line in lines:
        assert line in out


def test_json_output_is_byte_identical_regardless_of_lines(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON output ignores the ``lines`` argument entirely.

    Emitting the same registered result with a populated line set (the
    non-quiet build) and with an empty line set (the quiet build) yields
    byte-identical JSON. The quiet branch only varies ``lines``, so this
    proves ``--quiet`` cannot alter the ``--format json`` envelope.
    """
    result = _work_create_result()

    _emit_envelope(
        _context("json"),
        command="modelo.work.create",
        result=result,
        lines=["operation\tmodelo.work.create", "New work unit created."],
    )
    with_lines = capsys.readouterr().out

    _emit_envelope(_context("json"), command="modelo.work.create", result=result, lines=[])
    without_lines = capsys.readouterr().out

    assert with_lines == without_lines
    assert json.loads(with_lines)["result"]["work_unit_id"]
