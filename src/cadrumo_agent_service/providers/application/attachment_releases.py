"""The person's decisions about attachment reads that would leave this computer.

A conversation attachment reaches a provider only when this service tells the
agent to release those exact bytes to that exact lane. The agent's own permission
never stands in for it. Each release checks eligibility and the grants as they are
now, and is recorded before the agent hears of it, so a failed record releases
nothing. Nothing here reads a document's content or returns it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal, Protocol
from uuid import uuid4

from cadrumo.core.json_contract import OutputSchema

RELEASE_SECONDS: Final = 300
"""How long the agent holds a release for a read it is about to retry."""

MAX_REMEMBERED_GRANTS: Final = 64
"""Grants one profile keeps, so their record stays inside its capability's size."""


class DisclosureRefusalCode(StrEnum):
    """Why a read was refused, in the closed vocabulary the window words."""

    ACKNOWLEDGEMENT_MISSING = "acknowledgement_missing"
    REFERENCE_UNKNOWN = "reference_unknown"
    DOCUMENT_REMOVED = "document_removed"
    GESTOR_MODE = "gestor_mode"
    CLOUD_UPLOAD_NOT_PERMITTED = "cloud_upload_not_permitted"
    PROFILE_NOT_ELIGIBLE = "profile_not_eligible"
    PROFILE_UNREADABLE = "profile_unreadable"
    FILE_CHANGED_DURING_READ = "file_changed_during_read"
    NOT_SIGNED_IN = "not_signed_in"
    GRANT_REVOKED = "grant_revoked"
    SERVICE_FAILED = "service_failed"


class ReleaseScope(StrEnum):
    """How far the person's approval reaches."""

    ONCE = "once"
    SESSION = "session"
    REMEMBER = "remember"


type ReleaseAction = Literal["document_text", "page_images"]


class ReleaseRefusal(StrEnum):
    """Why the service records a refusal with the agent, as the agent words it to the model."""

    HOST_POLICY = "host_policy"
    """A deployment bar keeps the file on this computer; the window shows no request."""
    PERSON_DECLINED = "person_declined"
    """The person was asked and declined this read."""


class AttachmentAdminRefusalCode(StrEnum):
    """Why an attachment administration request was refused before any decision was read."""

    SERVICE_STOPPING = "service_stopping"
    INVALID_REQUEST = "invalid_request"
    """The request named no run and read, or no action this surface answers."""
    BUSY = "busy"
    """Answered by the administration ingress when it has no place for the request; nothing was done."""


class AttachmentRefusal(OutputSchema):
    """A refused attachment request, by its closed code.

    Once the service has resolved the read it also names the file, so the window
    can say which file was not sent.
    """

    kind: Literal["refused"] = "refused"
    code: DisclosureRefusalCode | AttachmentAdminRefusalCode
    name: str | None = None
    """The attachment's name, when the service resolved the read."""


class AttachmentNotRequired(OutputSchema):
    """The read stays on this computer, so no decision of the person's is asked for."""

    kind: Literal["not_required"] = "not_required"


class AttachmentCard(OutputSchema):
    """What the approval card shows, from the agent's own record of the read and the stored document."""

    kind: Literal["card"] = "card"
    name: str
    media_type: str
    size_bytes: int
    provider: str
    transport: str
    model: str
    action: ReleaseAction
    existing_grant: bool
    """Whether a grant held now already covers this read, so it is released without asking."""


class AttachmentReleased(OutputSchema):
    """The read was recorded and released to the agent."""

    kind: Literal["released"] = "released"


class AttachmentDeclined(OutputSchema):
    """The person's refusal of the read was recorded with the agent, which tells the model."""

    kind: Literal["declined"] = "declined"


class AttachmentGrantEntry(OutputSchema):
    """One remembered grant as the settings list shows it; never the bytes' digest or conversation."""

    grant_id: str
    action: ReleaseAction
    lane: str
    model: str
    display_name: str | None
    """The attachment's name for a text grant; ``None`` for a page-image grant."""


class AttachmentGrantList(OutputSchema):
    """The remembered grants, in the order they were kept."""

    kind: Literal["grants"] = "grants"
    grants: tuple[AttachmentGrantEntry, ...]


class AttachmentGrantRevoked(OutputSchema):
    """The grant is gone, and what it released that nothing has read was taken back."""

    kind: Literal["revoked"] = "revoked"


class AttachmentConversationForgotten(OutputSchema):
    """The conversation's text grants are gone, kept or held for the session."""

    kind: Literal["forgotten"] = "forgotten"


type AttachmentCardAnswer = AttachmentCard | AttachmentNotRequired | AttachmentRefusal
type AttachmentReleaseAnswer = AttachmentReleased | AttachmentDeclined | AttachmentNotRequired | AttachmentRefusal
type AttachmentGrantsAnswer = AttachmentGrantList | AttachmentRefusal
type AttachmentGrantRevokeAnswer = AttachmentGrantRevoked | AttachmentRefusal
type AttachmentForgetAnswer = AttachmentConversationForgotten | AttachmentRefusal
type AttachmentAdminAnswer = (
    AttachmentCardAnswer
    | AttachmentReleaseAnswer
    | AttachmentGrantsAnswer
    | AttachmentGrantRevokeAnswer
    | AttachmentForgetAnswer
)


@dataclass(frozen=True, slots=True)
class PendingRead:
    """The read a run is parked on, from the agent's own record of that run."""

    conversation_id: str
    name: str
    action: ReleaseAction
    provider: str
    transport: str
    model: str

    @property
    def lane(self) -> str:
        """Name the lane as the agent names it when it matches a release."""
        return f"{self.provider}/{self.transport}"


@dataclass(frozen=True, slots=True)
class StoredDocument:
    """A stored attachment as its bytes stand now."""

    sha256: str
    media_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class DisclosureGrant:
    """One decision kept for later reads.

    A text grant names the exact bytes in one conversation. A page-image grant
    names only the lane and leaves both ``None``.
    """

    grant_id: str
    action: ReleaseAction
    lane: str
    model: str
    sha256: str | None
    conversation_id: str | None
    display_name: str | None


@dataclass(frozen=True, slots=True)
class StoredGrants:
    """The remembered grants, and the revision a change to them must name."""

    grants: tuple[DisclosureGrant, ...]
    revision: str


@dataclass(frozen=True, slots=True)
class DisclosureRecord:
    """The ledger's account of one release: no content, only what was decided."""

    record_id: str
    action: ReleaseAction
    lane: str
    model: str
    sha256: str
    conversation_id: str
    scope: str


class GatewayAnswer(StrEnum):
    """What the agent said to a release."""

    RELEASED = "released"
    CHANGED = "changed"
    UNAVAILABLE = "unavailable"


class AttachmentGateway(Protocol):
    """The agent's record of a run's read and of the document it names."""

    def pending_read(self, run_id: str, request_id: str) -> PendingRead | None:
        """Return the read the run is parked on under ``request_id``, or ``None``."""
        ...

    def document(self, conversation_id: str, name: str) -> StoredDocument | None:
        """Return the stored document, or ``None`` when it is gone."""
        ...

    def release(self, read: PendingRead, sha256: str, *, seconds: int) -> GatewayAnswer:
        """Tell the agent to let this read through for these bytes."""
        ...

    def refuse(self, read: PendingRead, sha256: str, refusal: ReleaseRefusal, *, seconds: int) -> GatewayAnswer:
        """Tell the agent this read will not be released, and why, so the model hears the truth."""
        ...

    def withdraw(self, conversation_id: str) -> None:
        """Take back whatever the conversation's reads have not used yet."""
        ...


class DisclosureStore(Protocol):
    """Encrypted custody of the remembered grants and the release ledger."""

    def read_grants(self) -> StoredGrants | None:
        """Return the grants; ``None`` when custody cannot answer."""
        ...

    def write_grants(self, grants: tuple[DisclosureGrant, ...], *, expected_revision: str) -> bool:
        """Replace the grants at the revision read; ``False`` commits nothing."""
        ...

    def append_release(self, record: DisclosureRecord) -> bool:
        """Add one ledger record; ``False`` means it may not be relied on."""
        ...


def _refused(code: DisclosureRefusalCode, read: PendingRead | None = None) -> AttachmentRefusal:
    return AttachmentRefusal(code=code, name=None if read is None else read.name)


def _covers(grant: DisclosureGrant, read: PendingRead, document: StoredDocument) -> bool:
    if (grant.action, grant.lane, grant.model) != (read.action, read.lane, read.model):
        return False
    if read.action == "page_images":
        return True
    return grant.sha256 == document.sha256 and grant.conversation_id == read.conversation_id


class AttachmentReleases:
    """Answer each read from the person's decisions as they stand at that moment."""

    def __init__(
        self,
        *,
        gateway: AttachmentGateway,
        store: DisclosureStore,
        off_host: Callable[[str, str], bool],
        eligibility: Callable[[], DisclosureRefusalCode | None],
        session: Callable[[], object | None],
    ) -> None:
        """Bind the agent, custody and the three facts each release re-reads.

        ``off_host`` reads the lane's typed catalogue flag, ``eligibility`` names the
        first bar to any off-host release, and ``session`` identifies the signed-in
        agent session a session grant is held for: ``None`` when there is none, and
        a different value after sign-out, lock, expiry or agent stop.
        """
        self._gateway = gateway
        self._store = store
        self._off_host = off_host
        self._eligibility = eligibility
        self._session = session
        self._session_held: object | None = None
        self._session_grants: tuple[DisclosureGrant, ...] = ()
        self._released_to: dict[str, set[str]] = {}

    def _current_session_grants(self, session: object) -> tuple[DisclosureGrant, ...]:
        if self._session_held != session:
            self._session_held, self._session_grants = session, ()
        return self._session_grants

    def _resolve(self, run_id: str, request_id: str) -> tuple[PendingRead, StoredDocument] | AttachmentRefusal:
        read = self._gateway.pending_read(run_id, request_id)
        if read is None:
            return _refused(DisclosureRefusalCode.REFERENCE_UNKNOWN)
        document = self._gateway.document(read.conversation_id, read.name)
        return _refused(DisclosureRefusalCode.DOCUMENT_REMOVED, read) if document is None else (read, document)

    def card(self, run_id: str, request_id: str) -> AttachmentCardAnswer:
        """Return what the approval card shows; none of it comes from the request's words."""
        session = self._session()
        if session is None:
            return _refused(DisclosureRefusalCode.NOT_SIGNED_IN)
        resolved = self._resolve(run_id, request_id)
        if isinstance(resolved, AttachmentRefusal):
            return resolved
        read, document = resolved
        if not self._off_host(read.provider, read.transport):
            return AttachmentNotRequired()
        barred = self._eligibility()
        if barred is not None:
            return self._barred(read, document, barred)
        stored = self._store.read_grants()
        if stored is None:
            return _refused(DisclosureRefusalCode.NOT_SIGNED_IN, read)
        held = (*self._current_session_grants(session), *stored.grants)
        return AttachmentCard(
            name=read.name,
            media_type=document.media_type,
            size_bytes=document.size_bytes,
            provider=read.provider,
            transport=read.transport,
            model=read.model,
            action=read.action,
            existing_grant=any(_covers(grant, read, document) for grant in held),
        )

    def release(self, run_id: str, request_id: str, scope: ReleaseScope | None) -> AttachmentReleaseAnswer:
        """Release one read under an existing grant, or under the person's answer in ``scope``."""
        session = self._session()
        if session is None:
            return _refused(DisclosureRefusalCode.NOT_SIGNED_IN)
        resolved = self._resolve(run_id, request_id)
        if isinstance(resolved, AttachmentRefusal):
            return resolved
        read, document = resolved
        if not self._off_host(read.provider, read.transport):
            return AttachmentNotRequired()
        barred = self._eligibility()
        if barred is not None:
            return self._barred(read, document, barred)
        stored = self._store.read_grants()
        if stored is None:
            return _refused(DisclosureRefusalCode.NOT_SIGNED_IN, read)
        held = (*self._current_session_grants(session), *stored.grants)
        covered = any(_covers(grant, read, document) for grant in held)
        if scope is None and not covered:
            return _refused(DisclosureRefusalCode.ACKNOWLEDGEMENT_MISSING, read)
        if not self._keep(read, document, scope, stored, covered=covered):
            return _refused(DisclosureRefusalCode.SERVICE_FAILED, read)
        return self._record_and_release(read, document, scope)

    def _barred(self, read: PendingRead, document: StoredDocument, bar: DisclosureRefusalCode) -> AttachmentRefusal:
        """Record the deployment's refusal with the agent, then answer it.

        The agent tells the model that no request will appear. A record that cannot
        be made leaves the answer unchanged: the refusal is the service's decision.
        """
        self._gateway.refuse(read, document.sha256, ReleaseRefusal.HOST_POLICY, seconds=RELEASE_SECONDS)
        return _refused(bar, read)

    def decline(self, run_id: str, request_id: str) -> AttachmentReleaseAnswer:
        """Record that the person declined this read, so the model is told so."""
        if self._session() is None:
            return _refused(DisclosureRefusalCode.NOT_SIGNED_IN)
        resolved = self._resolve(run_id, request_id)
        if isinstance(resolved, AttachmentRefusal):
            return resolved
        read, document = resolved
        if not self._off_host(read.provider, read.transport):
            return AttachmentNotRequired()
        self._gateway.refuse(read, document.sha256, ReleaseRefusal.PERSON_DECLINED, seconds=RELEASE_SECONDS)
        return AttachmentDeclined()

    def _keep(
        self,
        read: PendingRead,
        document: StoredDocument,
        scope: ReleaseScope | None,
        stored: StoredGrants,
        *,
        covered: bool,
    ) -> bool:
        if covered or scope in {None, ReleaseScope.ONCE}:
            return True
        text = read.action == "document_text"
        grant = DisclosureGrant(
            grant_id=uuid4().hex,
            action=read.action,
            lane=read.lane,
            model=read.model,
            sha256=document.sha256 if text else None,
            conversation_id=read.conversation_id if text else None,
            display_name=read.name if text else None,
        )
        if scope is ReleaseScope.SESSION:
            self._session_grants = (*self._session_grants, grant)
            return True
        if len(stored.grants) >= MAX_REMEMBERED_GRANTS:
            return False
        return self._store.write_grants((*stored.grants, grant), expected_revision=stored.revision)

    def _record_and_release(
        self, read: PendingRead, document: StoredDocument, scope: ReleaseScope | None
    ) -> AttachmentReleaseAnswer:
        recorded = self._store.append_release(
            DisclosureRecord(
                record_id=uuid4().hex,
                action=read.action,
                lane=read.lane,
                model=read.model,
                sha256=document.sha256,
                conversation_id=read.conversation_id,
                scope="grant" if scope is None else scope.value,
            )
        )
        if not recorded:
            return _refused(DisclosureRefusalCode.SERVICE_FAILED, read)
        answer = self._gateway.release(read, document.sha256, seconds=RELEASE_SECONDS)
        if answer is GatewayAnswer.CHANGED:
            return _refused(DisclosureRefusalCode.FILE_CHANGED_DURING_READ, read)
        if answer is GatewayAnswer.UNAVAILABLE:
            return _refused(DisclosureRefusalCode.SERVICE_FAILED, read)
        self._released_to.setdefault(f"{read.lane}\x1f{read.model}", set()).add(read.conversation_id)
        return AttachmentReleased()

    def grants(self) -> AttachmentGrantsAnswer:
        """List the remembered grants for the agent panel's settings."""
        if self._session() is None:
            return _refused(DisclosureRefusalCode.NOT_SIGNED_IN)
        stored = self._store.read_grants()
        if stored is None:
            return _refused(DisclosureRefusalCode.NOT_SIGNED_IN)
        return AttachmentGrantList(
            grants=tuple(
                AttachmentGrantEntry(
                    grant_id=grant.grant_id,
                    action=grant.action,
                    lane=grant.lane,
                    model=grant.model,
                    display_name=grant.display_name,
                )
                for grant in stored.grants
            )
        )

    def revoke(self, grant_id: str) -> AttachmentGrantRevokeAnswer:
        """Remove a remembered grant, and take back what it released and nothing has read."""
        if self._session() is None:
            return _refused(DisclosureRefusalCode.NOT_SIGNED_IN)
        stored = self._store.read_grants()
        if stored is None:
            return _refused(DisclosureRefusalCode.NOT_SIGNED_IN)
        grant = next((held for held in stored.grants if held.grant_id == grant_id), None)
        if grant is None:
            return _refused(DisclosureRefusalCode.GRANT_REVOKED)
        kept = tuple(held for held in stored.grants if held.grant_id != grant_id)
        if not self._store.write_grants(kept, expected_revision=stored.revision):
            return _refused(DisclosureRefusalCode.SERVICE_FAILED)
        for conversation in self._released_to.pop(f"{grant.lane}\x1f{grant.model}", set()):
            self._gateway.withdraw(conversation)
        return AttachmentGrantRevoked()

    def forget_conversation(self, conversation_id: str) -> AttachmentForgetAnswer:
        """Remove the conversation's text grants, kept or held for the session."""
        self._session_grants = tuple(
            grant for grant in self._session_grants if grant.conversation_id != conversation_id
        )
        self._gateway.withdraw(conversation_id)
        stored = self._store.read_grants()
        if stored is None:
            return _refused(DisclosureRefusalCode.NOT_SIGNED_IN)
        kept = tuple(grant for grant in stored.grants if grant.conversation_id != conversation_id)
        if kept != stored.grants and not self._store.write_grants(kept, expected_revision=stored.revision):
            return _refused(DisclosureRefusalCode.SERVICE_FAILED)
        return AttachmentConversationForgotten()


__all__ = [
    "MAX_REMEMBERED_GRANTS",
    "RELEASE_SECONDS",
    "AttachmentAdminAnswer",
    "AttachmentAdminRefusalCode",
    "AttachmentCard",
    "AttachmentCardAnswer",
    "AttachmentConversationForgotten",
    "AttachmentDeclined",
    "AttachmentForgetAnswer",
    "AttachmentGateway",
    "AttachmentGrantEntry",
    "AttachmentGrantList",
    "AttachmentGrantRevokeAnswer",
    "AttachmentGrantRevoked",
    "AttachmentGrantsAnswer",
    "AttachmentNotRequired",
    "AttachmentRefusal",
    "AttachmentReleaseAnswer",
    "AttachmentReleased",
    "AttachmentReleases",
    "DisclosureGrant",
    "DisclosureRecord",
    "DisclosureRefusalCode",
    "DisclosureStore",
    "GatewayAnswer",
    "PendingRead",
    "ReleaseRefusal",
    "ReleaseScope",
    "StoredDocument",
    "StoredGrants",
]
