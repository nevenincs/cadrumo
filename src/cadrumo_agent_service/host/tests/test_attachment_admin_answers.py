"""Each attachment administration answer crosses the admin socket as the document its typed model dumps.

The answers are read as a plain client reads them, then validated against the model each action
declares, so a handler that answers a shape its model does not state fails here.
"""

from __future__ import annotations

import json
import socket
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Final, override
from uuid import uuid4

import pytest
from pydantic import TypeAdapter

from ...admin import AdminServer
from ...providers.application.attachment_releases import (
    AttachmentCard,
    AttachmentCardAnswer,
    AttachmentDeclined,
    AttachmentGateway,
    AttachmentGrantList,
    AttachmentGrantRevokeAnswer,
    AttachmentGrantRevoked,
    AttachmentGrantsAnswer,
    AttachmentNotRequired,
    AttachmentRefusal,
    AttachmentReleaseAnswer,
    AttachmentReleased,
    AttachmentReleases,
    DisclosureGrant,
    DisclosureRecord,
    DisclosureStore,
    GatewayAnswer,
    PendingRead,
    ReleaseRefusal,
    StoredDocument,
    StoredGrants,
)
from ...service_attachment_admin import answer_attachment_admin
from .admin_wire_support import read_frame, send_frame

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BEARER: Final = b"b" * 64
_RUN: Final = "run-1"
_REQUEST: Final = "perm-1"
_READ: Final = PendingRead(
    conversation_id="chain-1",
    name="nota.txt",
    action="document_text",
    provider="claude",
    transport="api",
    model="model-a",
)
_DOCUMENT: Final = StoredDocument(sha256="0" * 64, media_type="text/plain", size_bytes=42)


@dataclass
class _Gateway(AttachmentGateway):
    """One synthetic run parked on one read of one stored document."""

    released: list[str] = field(default_factory=list)
    refused: list[ReleaseRefusal] = field(default_factory=list)

    @override
    def pending_read(self, run_id: str, request_id: str) -> PendingRead | None:
        return _READ if (run_id, request_id) == (_RUN, _REQUEST) else None

    @override
    def document(self, conversation_id: str, name: str) -> StoredDocument | None:
        return _DOCUMENT

    @override
    def release(self, read: PendingRead, sha256: str, *, seconds: int) -> GatewayAnswer:
        self.released.append(sha256)
        return GatewayAnswer.RELEASED

    @override
    def refuse(self, read: PendingRead, sha256: str, refusal: ReleaseRefusal, *, seconds: int) -> GatewayAnswer:
        self.refused.append(refusal)
        return GatewayAnswer.RELEASED

    @override
    def withdraw(self, conversation_id: str) -> None:
        return None


@dataclass
class _Store(DisclosureStore):
    grants: tuple[DisclosureGrant, ...] = ()
    revision: int = 0

    @override
    def read_grants(self) -> StoredGrants | None:
        return StoredGrants(grants=self.grants, revision=str(self.revision))

    @override
    def write_grants(self, grants: tuple[DisclosureGrant, ...], *, expected_revision: str) -> bool:
        if expected_revision != str(self.revision):
            return False
        self.grants, self.revision = grants, self.revision + 1
        return True

    @override
    def append_release(self, record: DisclosureRecord) -> bool:
        return True


@dataclass
class _Target:
    """The service's attachment dispatch, behind the admin socket."""

    releases: AttachmentReleases
    closing: bool = False

    def admin(
        self,
        action: str,
        *,
        run_id: str | None = None,
        permission_request_id: str | None = None,
        scope: str | None = None,
        grant_id: str | None = None,
        conversation_id: str | None = None,
        **_metadata: object,
    ) -> dict[str, Any]:
        return answer_attachment_admin(
            self.releases,
            closing=self.closing,
            action=action,
            run_id=run_id,
            request_id=permission_request_id,
            scope=scope,
            grant_id=grant_id,
            conversation_id=conversation_id,
        )


@dataclass
class _Admin:
    target: _Target
    server: AdminServer
    off_host: list[bool]
    gateway: _Gateway

    def ask(self, action: str, **metadata: str) -> object:
        request = {"version": 1, "request_id": str(uuid4()), "action": action, **metadata}
        with socket.create_connection(("127.0.0.1", self.server.port), timeout=5) as stream:
            send_frame(stream, _BEARER)
            send_frame(stream, json.dumps(request).encode())
            return read_frame(stream)["result"]

    def read(self, action: str, **metadata: str) -> object:
        return self.ask(action, run_id=_RUN, permission_request_id=_REQUEST, **metadata)


@pytest.fixture
def admin() -> Iterator[_Admin]:
    off_host = [True]
    gateway = _Gateway()
    releases = AttachmentReleases(
        gateway=gateway,
        store=_Store(),
        off_host=lambda _provider, _transport: off_host[0],
        eligibility=lambda: None,
        session=lambda: "session-1",
    )
    target = _Target(releases)
    server = AdminServer(target, bearer=bytearray(_BEARER))
    try:
        yield _Admin(target, server, off_host, gateway)
    finally:
        server.close()


def _typed(answer_type: Any, document: object) -> object:
    """``document`` read as ``answer_type``, after checking the typed answer dumps back to the same document."""
    adapter = TypeAdapter[object](answer_type)
    typed = adapter.validate_json(json.dumps(document))
    assert adapter.dump_python(typed, mode="json") == document
    return typed


def test_card_and_release_answers_are_their_declared_models(admin: _Admin) -> None:
    card = _typed(AttachmentCardAnswer, admin.read("attachment_card"))
    assert card == AttachmentCard(
        name="nota.txt",
        media_type="text/plain",
        size_bytes=42,
        provider="claude",
        transport="api",
        model="model-a",
        action="document_text",
        existing_grant=False,
    )
    assert isinstance(
        _typed(AttachmentReleaseAnswer, admin.read("attachment_release", scope="once")), AttachmentReleased
    )

    admin.off_host[0] = False
    assert isinstance(_typed(AttachmentCardAnswer, admin.read("attachment_card")), AttachmentNotRequired)
    assert isinstance(_typed(AttachmentReleaseAnswer, admin.read("attachment_release")), AttachmentNotRequired)


def test_grant_answers_are_their_declared_models(admin: _Admin) -> None:
    admin.read("attachment_release", scope="remember")

    listed = _typed(AttachmentGrantsAnswer, admin.ask("attachment_grants"))
    assert isinstance(listed, AttachmentGrantList)
    (grant,) = listed.grants
    assert (grant.action, grant.lane, grant.model, grant.display_name) == (
        "document_text",
        "claude/api",
        "model-a",
        "nota.txt",
    )
    revoked = _typed(AttachmentGrantRevokeAnswer, admin.ask("attachment_grant_revoke", grant_id=grant.grant_id))
    assert isinstance(revoked, AttachmentGrantRevoked)


@pytest.mark.parametrize(
    ("ask", "answer_type", "code", "name"),
    [
        (
            lambda admin: admin.read("attachment_release"),
            AttachmentReleaseAnswer,
            "acknowledgement_missing",
            "nota.txt",
        ),
        (
            lambda admin: admin.ask("attachment_card", run_id=_RUN, permission_request_id="perm-other"),
            AttachmentCardAnswer,
            "reference_unknown",
            None,
        ),
        (
            lambda admin: admin.ask("attachment_grant_revoke", grant_id="f" * 32),
            AttachmentGrantRevokeAnswer,
            "grant_revoked",
            None,
        ),
        (lambda admin: admin.ask("attachment_card"), AttachmentCardAnswer, "invalid_request", None),
    ],
    ids=["no-acknowledgement", "unknown-read", "unknown-grant", "no-run"],
)
def test_a_refusal_keeps_its_code(
    admin: _Admin, ask: Callable[[_Admin], object], answer_type: object, code: str, name: str | None
) -> None:
    document = ask(admin)
    assert isinstance(document, dict)
    assert document["kind"] == "refused"
    assert document == {"kind": "refused", "code": code, "name": name}
    refusal = _typed(answer_type, document)
    assert isinstance(refusal, AttachmentRefusal)
    assert refusal.code == code
    assert refusal.name == name


def test_a_decline_is_an_answer_of_its_own_and_tells_the_agent(admin: _Admin) -> None:
    answer = _typed(AttachmentReleaseAnswer, admin.read("attachment_release", scope="decline"))
    assert isinstance(answer, AttachmentDeclined)
    assert admin.gateway.refused == [ReleaseRefusal.PERSON_DECLINED]
    assert admin.gateway.released == []


def test_a_stopping_service_refuses_every_action_with_its_code(admin: _Admin) -> None:
    admin.target.closing = True
    for action in ("attachment_card", "attachment_release", "attachment_grants"):
        document = admin.read(action)
        assert document == {"kind": "refused", "code": "service_stopping", "name": None}
        assert isinstance(_typed(AttachmentCardAnswer, document), AttachmentRefusal)
