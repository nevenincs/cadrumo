"""Tests for the central command-output renderer."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from ..config import override_settings
from ..errors import get_registered_error_code, render_error_text
from ..output_rendering import OutputFormatRefusedError, OutputRenderingError, render_command_output
from ..redaction import CLI_BUCKET_ID_PLACEHOLDER, CLI_OBJECT_KEY_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROFILE_ID = "986c0dc9-56dc-422b-9d8f-698661b9eb1e"  # was '123e4567-e89b-12d3-a456-426614174000'
_NIF = "12345678Z"
_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaaaaaaaaaa.bbbbbbbbbbbb"
_URL = "https://example.test/private/path?token=secret"
_OBJECT_KEY = "wallet:2026-secret"
_OTHER_OBJECT_KEY = "wallet:2026-other"


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
            _PROFILE_ID: "profile keyed",
            _NIF: "tax keyed",
            _URL: "url keyed",
            f"bearer {_JWT}": "token keyed",
            _OBJECT_KEY: "object keyed",
            _OTHER_OBJECT_KEY: "second object keyed",
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
        CLI_PROFILE_ID_PLACEHOLDER: "profile keyed",
        "sha256:1c9f9632": "tax keyed",
        "https://example.test": "url keyed",
        "token:sha256:0a2c77ea": "token keyed",
        CLI_OBJECT_KEY_PLACEHOLDER: "object keyed",
        f"{CLI_OBJECT_KEY_PLACEHOLDER}#2": "second object keyed",
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
    assert _OTHER_OBJECT_KEY not in rendered.text


def test_render_command_output_json_identifier_redaction_honours_reveal_opt_in() -> None:
    """Default JSON placeholders can be revealed for opaque profile/bucket ids only."""

    default_rendered = render_command_output(
        format_name="json",
        payload={"bucket_id": _PROFILE_ID, "profile_id": _PROFILE_ID},
        lines=("ignored",),
    )

    default_payload = json.loads(default_rendered.text)
    assert default_payload == {
        "bucket_id": CLI_BUCKET_ID_PLACEHOLDER,
        "profile_id": CLI_PROFILE_ID_PLACEHOLDER,
    }
    assert _PROFILE_ID not in default_rendered.text

    with override_settings(cadrumo_cli_reveal_identifiers=True):
        revealed_rendered = render_command_output(
            format_name="json",
            payload={"bucket_id": _PROFILE_ID, "profile_id": _PROFILE_ID, "tax_id": _NIF},
            lines=("ignored",),
        )

    revealed_payload = json.loads(revealed_rendered.text)
    assert revealed_payload["bucket_id"] == _PROFILE_ID
    assert revealed_payload["profile_id"] == _PROFILE_ID
    # Tax identity stays redacted even under the reveal opt-out.
    assert revealed_payload["tax_id"].startswith("sha256:")
    assert _NIF not in revealed_rendered.text


def test_render_command_output_does_not_corrupt_tabular_header_in_text() -> None:
    """The text renderer must not rewrite a column-header field name."""

    header = "filing_record_id\tbucket_id\tmodelo\tyear\tperiod\tstatus\tfiled_at\tfiled_by"

    rendered = render_command_output(
        format_name="text",
        payload={"ignored": True},
        lines=(header,),
    )

    assert rendered.text == header
    assert "\tmodelo\t" in rendered.text
    assert CLI_BUCKET_ID_PLACEHOLDER not in rendered.text


def test_render_command_output_errors_use_registered_error_contract() -> None:
    cases: tuple[
        tuple[type[BaseException], str, object, tuple[str, ...], str, dict[str, str], str],
        ...,
    ] = (
        (
            OutputRenderingError,
            "json",
            object(),
            (),
            "INTERNAL_OUTPUT_RENDERING",
            {"type_name": "object"},
            "Internal. Internal error:",
        ),
        (
            OutputFormatRefusedError,
            "xml",
            {"ignored": True},
            ("ignored",),
            "REFUSED_OUTPUT_FORMAT",
            {"format_name": "xml", "expected": "text,json"},
            "Refused. The requested output format is not supported.",
        ),
    )

    for error_type, format_name, payload, lines, registered_code, expected_context, english_prefix in cases:
        assert get_registered_error_code(error_type).code == registered_code

        with pytest.raises(error_type) as excinfo:
            render_command_output(format_name=format_name, payload=payload, lines=lines)
        error = excinfo.value
        # args intentionally carries the translated_message key as fallback
        # text (CadrumoError.__init__), not the empty tuple -- see
        # test_error_message_never_blank.py for the pinned base-class contract.
        assert error.args == (error.translated_message,)
        assert error.context == expected_context
        with override_settings(cadrumo_output_language="en"):
            assert render_error_text(error).startswith(english_prefix)
