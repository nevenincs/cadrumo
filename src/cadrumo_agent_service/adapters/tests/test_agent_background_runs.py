"""Background requests the adapter refuses before it reaches any gateway."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from pydantic import JsonValue, ValidationError

from cadrumo_client.contracts.model_runs import (
    ModelRunAttachment,
    ModelRunBody,
    ModelRunLane,
    ModelRunRefusal,
    ModelRunRefusalCode,
)

from ..agent_background_runs import BackgroundRunEndpoint, HostedBackgroundRuns

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_LANE = ModelRunLane(
    provider_id="example",
    transport="api",
    model="example-model-1",
    reads_off_host=True,
    licence=None,
    size_bytes=None,
    vision=None,
    context_length=None,
)


def _unreachable(tmp_path: Path) -> BackgroundRunEndpoint:
    """An endpoint nothing listens on: any exchange would fail rather than be answered."""
    return BackgroundRunEndpoint(port=1, workspace_root=tmp_path)


def _body(*attachments: ModelRunAttachment) -> ModelRunBody:
    return ModelRunBody(prompt="Read this.", attachments=attachments, max_output_tokens=16)


def test_a_format_no_background_request_carries_is_refused_as_unsupported(tmp_path: Path) -> None:
    endpoint = _unreachable(tmp_path)
    runs = HostedBackgroundRuns(
        endpoint=lambda: endpoint, bearer=bytearray(b"synthetic-bearer"), host_token=bytearray(b"synthetic-host")
    )
    text = ModelRunAttachment(media_type="text/plain", base64_data=base64.b64encode(b"x").decode())

    assert runs.run(lane=_LANE, body=_body(text), deadline_seconds=30) == ModelRunRefusal(
        code=ModelRunRefusalCode.INPUT_NOT_SUPPORTED
    )


def test_a_wiped_host_token_or_no_ready_agent_refuses_as_unavailable(tmp_path: Path) -> None:
    endpoint = _unreachable(tmp_path)
    wiped = HostedBackgroundRuns(
        endpoint=lambda: endpoint, bearer=bytearray(b"synthetic-bearer"), host_token=bytearray()
    )
    absent = HostedBackgroundRuns(
        endpoint=lambda: None, bearer=bytearray(b"synthetic-bearer"), host_token=bytearray(b"synthetic-host")
    )

    for runs in (wiped, absent):
        assert runs.run(lane=_LANE, body=_body(), deadline_seconds=30) == ModelRunRefusal(
            code=ModelRunRefusalCode.SERVICE_UNAVAILABLE
        )
    assert absent.accepted_media(_LANE) is None


@pytest.mark.parametrize(
    "options",
    [
        pytest.param({"context_tokens": 511}, id="context-below-floor"),
        pytest.param({"context_tokens": 1_048_577}, id="context-above-ceiling"),
        pytest.param({"response_schema": {"description": "x" * 32_768}}, id="schema-over-bound"),
    ],
)
def test_a_reply_option_outside_the_agent_s_bounds_is_refused_by_the_contract(options: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ModelRunBody.model_validate({"prompt": "Read this.", "max_output_tokens": 16, **options})


def test_reply_options_at_the_agent_s_bounds_are_accepted() -> None:
    schema: dict[str, JsonValue] = {"description": "x" * (32_768 - len('{"description":""}'))}
    body = ModelRunBody(
        prompt="Read this.", max_output_tokens=16, context_tokens=512, response_schema=schema, temperature=0.0
    )

    assert (body.context_tokens, body.response_schema) == (512, schema)
