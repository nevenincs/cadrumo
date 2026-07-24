"""The status-page presenter must never pre-empt the machine contract.

``present_status_tui`` is the seam that decides whether ``aeat config
profile status`` renders the read-only full-screen surface or falls
through to the unchanged envelope path. These tests pin that gate: a
``--format json`` request and any non-full-screen host MUST return
``False`` so the JSON / text envelope callers reach the identical machine
output the conformance suites lock. The full-screen presentation itself is
never launched here (it would take over the controlling terminal); the
gate's refusal is what guards the contract.
"""

from __future__ import annotations

import click
import pytest
import typer

from ....cli._config import _status_frontend
from ....cli._config._status_frontend import present_status_tui

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _ctx_with_format(format_name: str) -> typer.Context:
    ctx = typer.Context(click.Command("status"))
    ctx.ensure_object(dict)["format"] = format_name
    return ctx


def test_json_format_falls_through_to_the_envelope_path() -> None:
    # A JSON caller must never be diverted into the interactive surface,
    # regardless of the host's console capability.
    assert present_status_tui(_ctx_with_format("json")) is False


def test_non_full_screen_host_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    from cadrumo.core.flows import FrontendCapability

    monkeypatch.setattr(
        "cadrumo.application.flows.detect_frontend_capability",
        lambda: FrontendCapability.NON_INTERACTIVE,
    )
    assert present_status_tui(_ctx_with_format("text")) is False


def test_line_capable_host_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    from cadrumo.core.flows import FrontendCapability

    monkeypatch.setattr(
        "cadrumo.application.flows.detect_frontend_capability",
        lambda: FrontendCapability.LINE,
    )
    assert present_status_tui(_ctx_with_format("text")) is False


def test_presenter_module_exposes_a_read_only_builder() -> None:
    # The builder assembles a view-model and nothing else; it is the only
    # public surface besides the gate, so the presenter has no write verb.
    assert set(_status_frontend.__all__) == {"build_status_page_data", "present_status_tui"}
