"""The owned credential request speaks the agent service's own admin wire: metadata, ``secret_ready``, one frame.

The server here is the service's real :class:`AdminServer`, which authenticates
the bearer, validates the request, asks for the credential frame and wipes it;
only the service behind it is a recorder of what the server dispatched.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import JsonValue

from cadrumo_agent_service.admin import ADMIN_SECRET_MAX_BYTES, AdminAction, AdminServer
from dev.runtime_lifecycle.agent_service_session import AgentServiceSession
from dev.runtime_lifecycle.caller_owned_root import AcceptanceError
from dev.runtime_lifecycle.packaged_service_process import PackagedServiceProcess
from dev.runtime_lifecycle.service_admin_channel import owned_service_credential, owned_service_settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LANE = "gateway_cli"
_REVISION = "0" * 64
_CREDENTIAL = b"synthetic-gateway-credential-0001"
_STORED: dict[str, JsonValue] = {"entry": {"id": _LANE, "credential_saved": True}}


class _Service:
    """What the admin server dispatched after authenticating, credential bytes as the dispatch saw them."""

    def __init__(self, *answers: dict[str, JsonValue]) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[AdminAction, dict[str, Any], bytes | None]] = []

    def admin(self, action: AdminAction, **fields: Any) -> JsonValue:
        secret = fields.pop("secret", None)
        stated = {key: value for key, value in fields.items() if value is not None}
        # The server wipes the frame once the dispatch returns; keep what it carried.
        self.calls.append((action, stated, None if secret is None else bytes(secret)))
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


@pytest.fixture
def bearer() -> bytearray:
    return bytearray(b"synthetic-parent-admin-authority")


def _serve(service: _Service, bearer: bytearray) -> AdminServer:
    return AdminServer(service, bearer=bearer)


def test_the_credential_travels_as_the_one_frame_after_secret_ready_and_is_wiped(bearer: bytearray) -> None:
    service = _Service(_STORED)
    server = _serve(service, bearer)
    secret = bytearray(_CREDENTIAL)
    try:
        answer = owned_service_credential(
            bearer, server.port, provider=_LANE, expected_revision=_REVISION, base_url=None, secret=secret
        )
    finally:
        server.close()
    assert answer == _STORED
    assert service.calls == [("set", {"provider": _LANE, "expected_revision": _REVISION}, _CREDENTIAL)]
    assert secret == bytearray(len(_CREDENTIAL))
    assert _CREDENTIAL.decode() not in json.dumps(answer)


def test_a_base_url_travels_in_the_metadata_never_in_the_frame(bearer: bytearray) -> None:
    service = _Service(_STORED)
    server = _serve(service, bearer)
    try:
        owned_service_credential(
            bearer,
            server.port,
            provider=_LANE,
            expected_revision=_REVISION,
            base_url="https://gateway.example.invalid/v1",
            secret=bytearray(_CREDENTIAL),
        )
    finally:
        server.close()
    ((action, fields, frame),) = service.calls
    assert (action, fields["base_url"], frame) == ("set", "https://gateway.example.invalid/v1", _CREDENTIAL)


def test_a_busy_answer_is_asked_again_with_the_same_credential_then_wiped(bearer: bytearray) -> None:
    service = _Service({"kind": "refused", "code": "busy"}, _STORED)
    server = _serve(service, bearer)
    secret = bytearray(_CREDENTIAL)
    try:
        answer = owned_service_credential(
            bearer, server.port, provider=_LANE, expected_revision=_REVISION, base_url=None, secret=secret
        )
    finally:
        server.close()
    assert answer == _STORED
    assert [frame for _action, _fields, frame in service.calls] == [_CREDENTIAL, _CREDENTIAL]
    assert not any(secret)


@pytest.mark.parametrize(
    "refusal",
    [{"code": "revision_conflict"}, {"code": "invalid_key_format"}, {"kind": "refused", "code": "signed_out"}],
)
def test_a_refusal_is_returned_as_answered_and_the_credential_wiped(
    bearer: bytearray, refusal: dict[str, JsonValue]
) -> None:
    service = _Service(refusal)
    server = _serve(service, bearer)
    secret = bytearray(_CREDENTIAL)
    try:
        answer = owned_service_credential(
            bearer, server.port, provider=_LANE, expected_revision=_REVISION, base_url=None, secret=secret
        )
    finally:
        server.close()
    assert answer == refusal
    assert len(service.calls) == 1
    assert not any(secret)


def test_a_request_outside_its_contract_or_bound_is_refused_unsent_and_wiped(bearer: bytearray) -> None:
    service = _Service(_STORED)
    server = _serve(service, bearer)
    try:
        for revision, secret in (
            ("not-a-revision", bytearray(_CREDENTIAL)),
            (_REVISION, bytearray(b"x" * (ADMIN_SECRET_MAX_BYTES + 1))),
            (_REVISION, bytearray()),
        ):
            with pytest.raises(AcceptanceError) as refused:
                owned_service_credential(
                    bearer, server.port, provider=_LANE, expected_revision=revision, base_url=None, secret=secret
                )
            assert not any(secret)
            assert _CREDENTIAL.decode() not in str(refused.value)
            assert refused.value.__cause__ is None
    finally:
        server.close()
    assert service.calls == []


def test_a_wrong_bearer_dispatches_nothing_and_the_credential_is_wiped(bearer: bytearray) -> None:
    service = _Service(_STORED)
    server = _serve(service, bearer)
    secret = bytearray(_CREDENTIAL)
    try:
        with pytest.raises(AcceptanceError):
            owned_service_credential(
                bytearray(b"another-authority"),
                server.port,
                provider=_LANE,
                expected_revision=_REVISION,
                base_url=None,
                secret=secret,
            )
    finally:
        server.close()
    assert service.calls == []
    assert not any(secret)


def test_the_settings_channel_still_carries_no_credential_frame(bearer: bytearray) -> None:
    with pytest.raises(AcceptanceError, match="local-model settings reads and choices only"):
        owned_service_settings(bearer, 1, "set")
    with pytest.raises(AcceptanceError, match="credential frames"):
        owned_service_settings(bearer, 1, "provider_lanes", secret_bytes=len(_CREDENTIAL))


def test_the_session_and_process_route_the_credential_and_a_shared_session_refuses_it(bearer: bytearray) -> None:
    service = _Service(_STORED)
    server = _serve(service, bearer)
    process = object.__new__(PackagedServiceProcess)
    process._bearer = bearer
    owned = object.__new__(AgentServiceSession)
    owned._owned = True
    owned._service = process
    owned.service_ready = {"admin_port": server.port}
    secret = bytearray(_CREDENTIAL)
    try:
        assert owned.credential(provider=_LANE, expected_revision=_REVISION, base_url=None, secret=secret) == _STORED
    finally:
        server.close()
    assert not any(secret)

    shared = object.__new__(AgentServiceSession)
    shared._owned = False
    secret = bytearray(_CREDENTIAL)
    with pytest.raises(AcceptanceError, match="does not store provider credentials"):
        shared.credential(provider=_LANE, expected_revision=_REVISION, base_url=None, secret=secret)
    assert not any(secret)
