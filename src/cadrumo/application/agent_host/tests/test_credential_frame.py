"""The agent's credential frame: exact bytes, typed refusals and wiping."""

from __future__ import annotations

import json

import pytest

from ..credential_frame import (
    CREDENTIAL_FRAME_MAX_BYTES,
    AgentCredential,
    CredentialFrameError,
    CredentialFrameRefusal,
    build_credential_frame,
    wipe,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FAKE = b"sk-test-NOT-A-REAL-KEY"


def test_the_frame_is_one_json_line_naming_each_provider_and_its_base_url() -> None:
    frame = build_credential_frame(
        {
            "zai": AgentCredential(bytearray(b"zai-test-NOT-A-REAL-KEY"), "https://api.z.ai/api/anthropic"),
            "anthropic": AgentCredential(bytearray(_FAKE)),
        }
    )
    assert frame.endswith(b"\n") and frame.count(b"\n") == 1
    assert json.loads(frame) == {
        "version": 1,
        "credentials": {
            "anthropic": {"secret": _FAKE.decode()},
            "zai": {"secret": "zai-test-NOT-A-REAL-KEY", "base_url": "https://api.z.ai/api/anthropic"},
        },
    }


@pytest.mark.parametrize(
    ("provider", "credential", "reason"),
    (
        ("Anthropic", AgentCredential(bytearray(_FAKE)), CredentialFrameRefusal.PROVIDER_ID_INVALID),
        ("anthropic", AgentCredential(bytearray()), CredentialFrameRefusal.VALUE_INVALID),
        ("anthropic", AgentCredential(bytearray(b'sk-"quoted"')), CredentialFrameRefusal.VALUE_INVALID),
        ("anthropic", AgentCredential(bytearray(b"sk-\\escape")), CredentialFrameRefusal.VALUE_INVALID),
        ("anthropic", AgentCredential(bytearray(b"sk-line\nbreak")), CredentialFrameRefusal.VALUE_INVALID),
        ("qwen", AgentCredential(bytearray(_FAKE), "http://plain.example"), CredentialFrameRefusal.BASE_URL_INVALID),
        ("qwen", AgentCredential(bytearray(_FAKE), 'https://x"y'), CredentialFrameRefusal.BASE_URL_INVALID),
        ("qwen", AgentCredential(bytearray(_FAKE), "https://exámple"), CredentialFrameRefusal.BASE_URL_INVALID),
    ),
)
def test_values_json_would_have_to_escape_are_refused_not_escaped(
    provider: str, credential: AgentCredential, reason: CredentialFrameRefusal
) -> None:
    with pytest.raises(CredentialFrameError) as refused:
        build_credential_frame({provider: credential})
    assert refused.value.reason is reason
    assert _FAKE.decode() not in str(refused.value)


def test_a_frame_past_the_bound_is_refused() -> None:
    oversized = bytearray(b"k" * CREDENTIAL_FRAME_MAX_BYTES)
    with pytest.raises(CredentialFrameError) as refused:
        build_credential_frame({"anthropic": AgentCredential(oversized)})
    assert refused.value.reason is CredentialFrameRefusal.TOO_LARGE


def test_wipe_overwrites_and_empties_the_buffer() -> None:
    buffer = bytearray(_FAKE)
    alias = buffer
    wipe(buffer)
    assert alias == bytearray() and buffer == bytearray()


def test_a_credential_never_shows_its_secret() -> None:
    credential = AgentCredential(bytearray(_FAKE), "https://api.z.ai/api/anthropic")
    assert _FAKE.decode() not in repr(credential)
    assert _FAKE.decode() not in str(credential)


def test_the_gateway_bearer_rides_the_same_frame_under_the_same_rules() -> None:
    bearer = bytearray(b"bearer-test-NOT-A-REAL-TOKEN")
    frame = build_credential_frame({"anthropic": AgentCredential(bytearray(_FAKE))}, gateway_bearer=bearer)
    assert json.loads(frame) == {
        "version": 1,
        "credentials": {"anthropic": {"secret": _FAKE.decode()}},
        "gateway_bearer": "bearer-test-NOT-A-REAL-TOKEN",
    }
    with pytest.raises(CredentialFrameError) as refused:
        build_credential_frame({}, gateway_bearer=bytearray(b'bad"bearer'))
    assert refused.value.reason is CredentialFrameRefusal.BEARER_INVALID
    assert "bad" not in str(refused.value)
