from __future__ import annotations

import json

import pytest
import typer
from typer.core import TyperGroup

from ....core.redaction import (
    CLI_BUCKET_ID_PLACEHOLDER,
    CLI_OBJECT_KEY_PLACEHOLDER,
    CLI_PROFILE_ID_PLACEHOLDER,
)
from ....tests.cli_runner import aeat_click_command
from .._common import _emit

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "123e4567-e89b-12d3-a456-426614174000"
_BUCKET_ID = "bucket-alpha"
_NIF = "12345678Z"
_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaaaaaaaaaa.bbbbbbbbbbbb"
_URL = "https://example.test/private/path?token=secret"
_OBJECT_KEY = "wallet:2026-secret"


def _context(format_name: str) -> typer.Context:
    # Get the aeat CLI command and narrow it to TyperGroup for compatibility with typer.Context.
    root_cmd = aeat_click_command()
    assert isinstance(root_cmd, TyperGroup)
    ctx = typer.Context(root_cmd)
    ctx.ensure_object(dict)["format"] = format_name
    return ctx


def _payload() -> dict[str, object]:
    return {
        "profile_id": _PROFILE_ID,
        "bucket_id": _BUCKET_ID,
        "tax_id": _NIF,
        "callback": _URL,
        "authorization": f"bearer {_JWT}",
        "object_key": _OBJECT_KEY,
    }


def _lines() -> tuple[str, ...]:
    return (
        f"profile_id={_PROFILE_ID}",
        f"bucket_id={_BUCKET_ID}",
        f"tax_id={_NIF}",
        f"callback={_URL}",
        f"authorization bearer {_JWT}",
        f"object_key={_OBJECT_KEY}",
    )


def test_emit_text_redacts_command_output_canary_matrix(capsys: pytest.CaptureFixture[str]) -> None:
    _emit(_context("text"), _payload(), _lines())

    output = capsys.readouterr().out

    for raw in (_PROFILE_ID, _BUCKET_ID, _NIF, _JWT, _URL, _OBJECT_KEY):
        assert raw not in output
    assert f"profile_id={CLI_PROFILE_ID_PLACEHOLDER}" in output
    assert f"bucket_id={CLI_BUCKET_ID_PLACEHOLDER}" in output
    assert "sha256:1c9f9632" in output
    assert "callback=https://example.test" in output
    assert "private/path" not in output
    assert "token:sha256:0a2c77ea" in output
    assert f"object_key={CLI_OBJECT_KEY_PLACEHOLDER}" in output


def test_emit_json_redacts_command_output_canary_matrix(capsys: pytest.CaptureFixture[str]) -> None:
    _emit(_context("json"), _payload(), _lines())

    output = capsys.readouterr().out
    payload = json.loads(output)

    for raw in (_PROFILE_ID, _BUCKET_ID, _NIF, _JWT, _URL, _OBJECT_KEY):
        assert raw not in output
    assert payload == {
        "profile_id": CLI_PROFILE_ID_PLACEHOLDER,
        "bucket_id": CLI_BUCKET_ID_PLACEHOLDER,
        "tax_id": "sha256:1c9f9632",
        "callback": "https://example.test",
        "authorization": "token:sha256:0a2c77ea",
        "object_key": CLI_OBJECT_KEY_PLACEHOLDER,
    }
