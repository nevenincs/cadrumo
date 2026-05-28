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
from .redaction import CLI_BUCKET_ID_PLACEHOLDER, CLI_OBJECT_KEY_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_PROFILE_ID = "123e4567-e89b-12d3-a456-426614174000"
_NIF = "12345678Z"
_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaaaaaaaaaa.bbbbbbbbbbbb"
_URL = "https://example.test/private/path?token=secret"
_OBJECT_KEY = "wallet:2026-secret"


class _Payload(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    path: Path
    amount: Decimal
    day: date


def test_render_command_output_renders_text_lines() -> None:
    rendered = render_command_output(
        format_name="text",
        payload={"ignored": True},
        lines=(
            f"profile={_PROFILE_ID} nif={_NIF} bearer {_JWT}",
            f"url={_URL} object_key={_OBJECT_KEY}",
        ),
    )

    assert rendered.format.value == "text"
    assert _PROFILE_ID not in rendered.text
    assert _NIF not in rendered.text
    assert _JWT not in rendered.text
    assert _URL not in rendered.text
    assert _OBJECT_KEY not in rendered.text
    assert CLI_PROFILE_ID_PLACEHOLDER in rendered.text
    assert f"object_key={CLI_OBJECT_KEY_PLACEHOLDER}" in rendered.text
    assert "https://example.test" in rendered.text
    assert "private/path" not in rendered.text
    assert "sha256:1c9f9632" in rendered.text
    assert "token:sha256:0a2c77ea" in rendered.text


def test_render_command_output_renders_json_payload_with_project_types() -> None:
    rendered = render_command_output(
        format_name="json",
        payload={
            "profile_id": _PROFILE_ID,
            "bucket_id": "bucket-alpha",
            "object_key": _OBJECT_KEY,
            "report": _Payload(path=Path("var/report.json"), amount=Decimal("12.30"), day=date(2026, 5, 13)),
            "nested": {
                "tax_id": _NIF,
                "callback": _URL,
                "authorization": f"bearer {_JWT}",
                "notes": ["operator label", "attachment:raw-key"],
            },
        },
        lines=("ignored",),
    )

    payload = json.loads(rendered.text)
    assert payload == {
        "profile_id": CLI_PROFILE_ID_PLACEHOLDER,
        "bucket_id": CLI_BUCKET_ID_PLACEHOLDER,
        "object_key": CLI_OBJECT_KEY_PLACEHOLDER,
        "report": {"path": "var/report.json", "amount": "12.30", "day": "2026-05-13"},
        "nested": {
            "tax_id": "sha256:1c9f9632",
            "callback": "https://example.test",
            "authorization": "token:sha256:0a2c77ea",
            "notes": ["operator label", CLI_OBJECT_KEY_PLACEHOLDER],
        },
    }
    assert _PROFILE_ID not in rendered.text
    assert _NIF not in rendered.text
    assert _JWT not in rendered.text
    assert _URL not in rendered.text
    assert _OBJECT_KEY not in rendered.text


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
