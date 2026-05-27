"""Tests for the central command-output renderer."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from .config import override_settings
from .errors import get_registered_error_code, render_error_text
from .output_rendering import OutputFormatRefusedError, OutputRenderingError, render_command_output

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


class _Payload(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    path: Path
    amount: Decimal
    day: date


def test_render_command_output_renders_text_lines() -> None:
    rendered = render_command_output(format_name="text", payload={"ignored": True}, lines=("a", "b"))

    assert rendered.format.value == "text"
    assert rendered.text == "a\nb"


def test_render_command_output_renders_json_payload_with_project_types() -> None:
    rendered = render_command_output(
        format_name="json",
        payload=_Payload(path=Path("var/report.json"), amount=Decimal("12.30"), day=date(2026, 5, 13)),
        lines=("ignored",),
    )

    payload = json.loads(rendered.text)
    assert payload == {"path": "var/report.json", "amount": "12.30", "day": "2026-05-13"}


def test_render_command_output_uses_registered_error_for_unencodable_payload() -> None:
    assert get_registered_error_code(OutputRenderingError).code == "INTERNAL_OUTPUT_RENDERING"

    with pytest.raises(OutputRenderingError) as excinfo:
        render_command_output(format_name="json", payload=object(), lines=())
    error = excinfo.value
    assert error.args == ()
    assert error.context == {"type_name": "object"}
    with override_settings(aeat_output_language="en"):
        assert render_error_text(error).startswith("Internal. Internal error:")


def test_render_command_output_refuses_unsupported_format_with_registered_error() -> None:
    assert get_registered_error_code(OutputFormatRefusedError).code == "REFUSED_OUTPUT_FORMAT"

    with pytest.raises(OutputFormatRefusedError) as excinfo:
        render_command_output(format_name="xml", payload={"ignored": True}, lines=("ignored",))
    error = excinfo.value
    assert error.args == ()
    assert error.context == {"format_name": "xml", "expected": "text,json"}
    with override_settings(aeat_output_language="en"):
        assert render_error_text(error).startswith("Refused. The requested output format is not supported.")
