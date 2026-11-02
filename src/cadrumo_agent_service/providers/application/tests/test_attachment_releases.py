"""What the service tells the agent about a read, over the real gateway adapter.

The adapter speaks real HTTP to a local stand-in that holds one synthetic run
parked on one read and counts every release it is told of, so "nothing leaves"
is observed at the only door a release has.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, Final, override

import pytest

from ....adapters.agent_attachment_gateway import GatewayAttachments
from ....adapters.agent_background_runs import HOST_ADMISSION_HEADER, BackgroundRunEndpoint
from ..attachment_releases import (
    AttachmentReleases,
    DisclosureGrant,
    DisclosureRecord,
    DisclosureRefusalCode,
    DisclosureStore,
    ReleaseScope,
    StoredGrants,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BEARER: Final = "synthetic-bearer"
_HOST: Final = "synthetic-host-token"
_RUN: Final = "run-1"
_CONVERSATION: Final = "chain-1"
_REQUEST: Final = "perm-1"
_CONTENT: Final = "SYNTHETIC-CONTENT-7731"
_BYTES: Final = f"La factura sintetica dice {_CONTENT}.".encode()


@dataclass
class _Agent:
    """The gateway's answers for one parked run, and every release it heard."""

    digest: str = hashlib.sha256(_BYTES).hexdigest()
    document_present: bool = True
    description: str = 'Permission required: read_attachment; attachment: "nota.txt"'
    tool_call: str = "read_attachment"
    provider: str = "claude"
    releases: list[dict[str, Any]] = field(default_factory=list)
    withdrawn: list[str] = field(default_factory=list)
    release_status: int = 204


def _handler(agent: _Agent) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: dict[str, object] | None = None) -> None:
            encoded = b"" if body is None else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _admitted(self) -> bool:
            return self.headers.get("Authorization") == f"Bearer {_BEARER}"

        def do_GET(self) -> None:
            if not self._admitted():
                self._send(401)
            elif self.path == f"/v1/runs/{_RUN}":
                selection = {"provider": agent.provider, "transport": "api", "model": "model-a"}
                self._send(200, {"conversation_id": _CONVERSATION, "selection": selection})
            elif self.path == f"/v1/runs/{_RUN}/history":
                request = {
                    "request_id": _REQUEST,
                    "description": agent.description,
                    "tool_call": agent.tool_call,
                    "tool_server": None,
                }
                self._send(200, {"state": {"pending_permissions": [request]}})
            elif self.path.endswith("/attachments/nota.txt") and agent.document_present:
                self._send(200, {"sha256": agent.digest, "media_type": "text/plain", "size_bytes": len(_BYTES)})
            else:
                self._send(404)

        def do_PUT(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            if self.headers.get(HOST_ADMISSION_HEADER) != _HOST:
                self._send(403)
                return
            agent.releases.append(body)
            self._send(agent.release_status)

        def do_DELETE(self) -> None:
            agent.withdrawn.append(self.path)
            self._send(204 if self.headers.get(HOST_ADMISSION_HEADER) == _HOST else 403)

        @override
        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


class _Store(DisclosureStore):
    def __init__(self) -> None:
        self.grants: tuple[DisclosureGrant, ...] = ()
        self.revision = 0
        self.ledger: list[DisclosureRecord] = []
        self.ledger_fails = False
        self.unreadable = False
        self.write_fails = False

    @override
    def read_grants(self) -> StoredGrants | None:
        return None if self.unreadable else StoredGrants(grants=self.grants, revision=str(self.revision))

    @override
    def write_grants(self, grants: tuple[DisclosureGrant, ...], *, expected_revision: str) -> bool:
        if self.write_fails or expected_revision != str(self.revision):
            return False
        self.grants, self.revision = grants, self.revision + 1
        return True

    @override
    def append_release(self, record: DisclosureRecord) -> bool:
        if self.ledger_fails:
            return False
        self.ledger.append(record)
        return True


@dataclass
class _World:
    agent: _Agent
    store: _Store
    releases: AttachmentReleases
    session: list[object | None]
    bar: list[DisclosureRefusalCode | None]
    off_host: list[bool]

    def card(self) -> dict[str, Any]:
        return self.releases.card(_RUN, _REQUEST)

    def release(self, scope: ReleaseScope | None) -> dict[str, Any]:
        return self.releases.release(_RUN, _REQUEST, scope)


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    agent = _Agent()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(agent))
    Thread(target=server.serve_forever, daemon=True).start()
    endpoint = BackgroundRunEndpoint(port=server.server_address[1], workspace_root=tmp_path)
    store = _Store()
    session: list[object | None] = ["session-1"]
    bar: list[DisclosureRefusalCode | None] = [None]
    off_host = [True]
    releases = AttachmentReleases(
        gateway=GatewayAttachments(
            endpoint=lambda: endpoint, bearer=bytearray(_BEARER, "ascii"), host_token=bytearray(_HOST, "ascii")
        ),
        store=store,
        off_host=lambda _provider, _transport: off_host[0],
        eligibility=lambda: bar[0],
        session=lambda: session[0],
    )
    try:
        yield _World(agent, store, releases, session, bar, off_host)
    finally:
        server.shutdown()
        server.server_close()


def _code(answer: dict[str, Any]) -> str:
    assert answer["kind"] == "refused", answer
    return str(answer["code"])


def test_nothing_leaves_without_the_persons_answer(world: _World) -> None:
    assert _code(world.release(None)) == "acknowledgement_missing"
    assert world.agent.releases == []
    assert world.store.ledger == []


def test_allow_once_is_ledgered_before_release_and_covers_no_later_read(world: _World) -> None:
    assert world.release(ReleaseScope.ONCE) == {"kind": "released"}

    assert world.agent.releases == [
        {
            "sha256": world.agent.digest,
            "provider": "claude/api",
            "model": "model-a",
            "action": "document_text",
            "expires_in_seconds": 300,
        }
    ]
    assert [record.scope for record in world.store.ledger] == ["once"]
    assert _code(world.release(None)) == "acknowledgement_missing"
    assert world.card()["existing_grant"] is False


def test_a_failed_ledger_append_releases_nothing(world: _World) -> None:
    world.store.ledger_fails = True
    assert _code(world.release(ReleaseScope.ONCE)) == "service_failed"
    assert world.agent.releases == []


def test_a_session_grant_ends_with_the_session(world: _World) -> None:
    world.release(ReleaseScope.SESSION)
    assert world.release(None) == {"kind": "released"}
    assert world.card()["existing_grant"] is True

    world.session[0] = "session-2"

    assert _code(world.release(None)) == "acknowledgement_missing"
    world.session[0] = None
    assert _code(world.release(ReleaseScope.ONCE)) == "not_signed_in"
    assert len(world.agent.releases) == 2


def test_a_remembered_grant_lasts_until_revoked(world: _World) -> None:
    world.release(ReleaseScope.REMEMBER)
    world.session[0] = "session-after-restart"
    assert world.release(None) == {"kind": "released"}

    (grant,) = world.releases.grants()["grants"]
    assert grant["display_name"] == "nota.txt"
    assert world.releases.revoke(grant["grant_id"]) == {"kind": "revoked"}

    assert world.agent.withdrawn == [f"/v1/conversations/{_CONVERSATION}/attachment-releases"]
    assert _code(world.release(None)) == "acknowledgement_missing"
    assert _code(world.releases.revoke(grant["grant_id"])) == "grant_revoked"
    assert len(world.agent.releases) == 2


def test_a_text_grant_does_not_survive_the_bytes_changing(world: _World) -> None:
    world.release(ReleaseScope.REMEMBER)
    world.agent.digest = hashlib.sha256(b"Other synthetic bytes.").hexdigest()

    assert world.card()["existing_grant"] is False
    assert _code(world.release(None)) == "acknowledgement_missing"
    assert len(world.agent.releases) == 1


def test_a_text_grant_does_not_cover_another_provider(world: _World) -> None:
    world.release(ReleaseScope.REMEMBER)
    world.agent.provider = "codex"
    assert _code(world.release(None)) == "acknowledgement_missing"
    assert len(world.agent.releases) == 1


def test_a_page_image_grant_is_its_own_and_follows_the_lane_alone(world: _World) -> None:
    world.release(ReleaseScope.REMEMBER)
    world.agent.description += "; page images"
    assert world.card()["action"] == "page_images"
    assert _code(world.release(None)) == "acknowledgement_missing"

    world.release(ReleaseScope.REMEMBER)
    world.agent.digest = hashlib.sha256(b"Another document.").hexdigest()
    assert world.release(None) == {"kind": "released"}
    assert world.agent.releases[-1]["action"] == "page_images"


def test_the_agent_finding_other_bytes_refuses_as_changed(world: _World) -> None:
    world.agent.release_status = 409
    assert _code(world.release(ReleaseScope.ONCE)) == "file_changed_during_read"


@pytest.mark.parametrize(
    "code",
    [
        DisclosureRefusalCode.GESTOR_MODE,
        DisclosureRefusalCode.CLOUD_UPLOAD_NOT_PERMITTED,
        DisclosureRefusalCode.PROFILE_NOT_ELIGIBLE,
    ],
)
def test_each_eligibility_bar_refuses_even_a_stored_grant(world: _World, code: DisclosureRefusalCode) -> None:
    world.release(ReleaseScope.REMEMBER)
    world.bar[0] = code

    assert _code(world.release(None)) == code.value
    assert _code(world.release(ReleaseScope.ONCE)) == code.value
    assert _code(world.card()) == code.value
    assert len(world.agent.releases) == 1


def test_a_lane_that_stays_here_needs_no_grant_and_records_nothing(world: _World) -> None:
    world.off_host[0] = False
    world.bar[0] = DisclosureRefusalCode.GESTOR_MODE

    assert world.card() == {"kind": "not_required"}
    assert world.release(None) == {"kind": "not_required"}
    assert world.agent.releases == []
    assert world.store.ledger == []


def test_a_removed_document_and_an_unknown_request_are_named(world: _World) -> None:
    assert _code(world.releases.release(_RUN, "perm-other", ReleaseScope.ONCE)) == "reference_unknown"
    world.agent.tool_call = "read_file"
    assert _code(world.release(ReleaseScope.ONCE)) == "reference_unknown"
    world.agent.tool_call = "read_attachment"
    world.agent.description = "Permission required: read_attachment"
    assert _code(world.release(ReleaseScope.ONCE)) == "reference_unknown"
    world.agent.description = 'Permission required: read_attachment; attachment: "nota.txt"'
    world.agent.document_present = False
    assert _code(world.release(ReleaseScope.ONCE)) == "document_removed"
    assert world.agent.releases == []


def test_unreadable_custody_grants_nothing(world: _World) -> None:
    world.store.unreadable = True
    assert _code(world.release(ReleaseScope.ONCE)) == "not_signed_in"
    assert world.agent.releases == []


def test_a_grant_that_could_not_be_kept_releases_nothing(world: _World) -> None:
    world.store.write_fails = True
    assert _code(world.release(ReleaseScope.REMEMBER)) == "service_failed"
    assert world.agent.releases == []


def test_forgetting_a_conversation_ends_its_text_grants_and_keeps_page_image_ones(world: _World) -> None:
    world.release(ReleaseScope.REMEMBER)
    world.release(ReleaseScope.SESSION)
    text = world.agent.description
    world.agent.description += "; page images"
    world.release(ReleaseScope.REMEMBER)

    assert world.releases.forget_conversation(_CONVERSATION) == {"kind": "forgotten"}

    assert [grant.action for grant in world.store.grants] == ["page_images"]
    assert world.agent.withdrawn == [f"/v1/conversations/{_CONVERSATION}/attachment-releases"]
    world.agent.description = text
    assert _code(world.release(None)) == "acknowledgement_missing"


def test_no_answer_carries_document_content(world: _World) -> None:
    answers = [
        world.card(),
        world.release(None),
        world.release(ReleaseScope.REMEMBER),
        world.releases.grants(),
    ]
    assert _CONTENT not in json.dumps(answers)
    assert all(_CONTENT not in repr(record) for record in world.store.ledger)
