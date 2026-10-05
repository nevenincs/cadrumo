"""Connection-bound enrollment before profile admission and protected delivery."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from threading import RLock
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import SecretBytes, ValidationError

from ...adapters.local_runtime.runtime_frame_io import read_document, read_secret, write_document, write_secret
from ...application.runtime.contracts import RuntimeByteChannel, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.enrollment_access import (
    RuntimeEnrollmentClientReply,
    RuntimeEnrollmentDelivery,
    RuntimeEnrollmentIdle,
    RuntimeEnrollmentInspect,
    RuntimeEnrollmentPoll,
    RuntimeEnrollmentPrepare,
    RuntimeEnrollmentPrepared,
    RuntimeEnrollmentReconcile,
    RuntimeEnrollmentRecorded,
    RuntimeEnrollmentRequest,
    RuntimeEnrollmentSubmit,
)
from ...application.runtime.enrollment_recipient import (
    EnrollmentMissing,
    EnrollmentPresent,
    EnrollmentRefused,
    EnrollmentStored,
    EnrollmentWork,
    EnrollmentWorkAction,
    EnrollmentWorkResult,
    VolatileEnrollmentRecipient,
)
from ...application.runtime.profile_access import RuntimeAccessRefusal, RuntimeSecretReady
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
)
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_administration import enrollment_receipt
from ...application.user_profile.automation_administration_service import AutomationAdministrationService
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentRequester,
    ProtectedEnrollmentRecipient,
)
from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant
from ...core.time.clock import now
from .enrollment_offer import RuntimeEnrollmentOffer, RuntimeEnrollmentRequestOwner

if TYPE_CHECKING:
    from .profile_host import ProfileConnection, RuntimeProfileHost


class RuntimeEnrollmentConnections:
    """Bounded volatile offers over the canonical protected enrollment service."""

    MAXIMUM_OFFERS = 32
    MAXIMUM_RECORDS = 128

    def __init__(
        self,
        *,
        prepare: Callable[
            [RuntimeConnectionContext, RuntimeByteChannel, RuntimeEnrollmentPrepare],
            tuple[ProfileConnection, RuntimeProfileHost],
        ],
        admitting: Callable[[], bool],
    ) -> None:
        """Receive host composition; never create a second profile or worker map."""
        self._prepare, self._admitting = prepare, admitting
        self._guard = RLock()
        self._offers: dict[UUID, RuntimeEnrollmentOffer] = {}

    def _offer(self, context: RuntimeConnectionContext, profile_id: UUID, request_id: UUID) -> RuntimeEnrollmentOffer:
        with self._guard:
            offer = self._offers.get(context.connection_id)
        if (
            not self._admitting()
            or offer is None
            or offer.connection.context != context
            or offer.prepared.profile_binding.profile_id != profile_id
            or offer.prepared.enrollment_request_id != request_id
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        offer.require_live()
        return offer

    def recipient(self, requester: EnrollmentRequester) -> ProtectedEnrollmentRecipient:
        """Resolve only the original still-live requesting connection."""
        with self._guard:
            offer = self._offers.get(requester.connection_id)
        if offer is None or offer.requester() != requester or offer.recipient is None or not self._admitting():
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        offer.require_live()
        return offer.recipient

    def _prepare_offer(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeEnrollmentPrepare
    ) -> RuntimeEnrollmentPrepared:
        connection, host = self._prepare(context, channel, request)
        with host.guard, self._guard:
            if context.connection_id in self._offers or len(self._offers) >= self.MAXIMUM_OFFERS:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            source = (
                None
                if request.session_id is None
                else host.authority.automation_request_session(
                    connection_id=context.connection_id, session_id=request.session_id
                )
            )
            instant = now()
            expires = instant + ACCESS_LEASE_MAXIMUM
            if source is not None:
                expires = min(expires, source.expires_at)
            prepared = RuntimeEnrollmentPrepared(
                request_id=request.request_id,
                runtime_boot_id=context.runtime_boot_id,
                connection_id=context.connection_id,
                enrollment_request_id=uuid4(),
                client_id=connection.client_id,
                destination_id=connection.client_id,
                profile_binding=host.store.binding,
                expires_at=expires,
            )
            offer = RuntimeEnrollmentOffer(
                prepared,
                connection,
                host,
                time.monotonic() + max(0, (expires - instant).total_seconds()),
                self._admitting,
                host.profile_lock_state().generation,
                source,
            )
            offer.require_live()
            self._offers[context.connection_id] = offer
            return prepared

    def _recorded(
        self, offer: RuntimeEnrollmentOffer, request: RuntimeEnrollmentSubmit | RuntimeEnrollmentInspect
    ) -> RuntimeEnrollmentRecorded:
        with offer.host.guard:
            offer.require_live()
            state = offer.host.store.enrollment_state()
            record = next((item for item in state.requests if item.request_id == request.enrollment_request_id), None)
            if (
                record is None
                or record.requester != offer.requester()
                or record.binding != offer.prepared.profile_binding
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            return RuntimeEnrollmentRecorded(
                request_id=request.request_id,
                runtime_boot_id=offer.prepared.runtime_boot_id,
                connection_id=offer.prepared.connection_id,
                receipt=AutomationReceiptProjection.model_validate(enrollment_receipt(record).model_dump()),
            )

    def _submit(
        self, offer: RuntimeEnrollmentOffer, channel: RuntimeByteChannel, request: RuntimeEnrollmentSubmit
    ) -> RuntimeEnrollmentRecorded:
        with offer.host.guard:
            offer.require_live()
            self._capacity(offer, request)
        write_document(
            channel,
            RuntimeSecretReady(
                request_id=request.request_id,
                runtime_boot_id=offer.prepared.runtime_boot_id,
                connection_id=offer.prepared.connection_id,
            ),
            deadline=time.monotonic() + 5,
        )
        with read_secret(channel, deadline=time.monotonic() + 10) as secret:
            try:
                document = json.loads(
                    secret, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
                )
                proposal = EnrollmentProposal.model_validate_json(canonical_json_bytes(document))
            except (ValueError, TypeError, RecursionError, ValidationError):
                raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
        source = offer.source_session
        if (source is None) != (proposal.kind is EnrollmentKind.ENROLL):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if source is not None and (
            proposal.target_grant_id != source.grant_id
            or (proposal.kind is EnrollmentKind.ROTATE and proposal.target_key_id != source.key_id)
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        with offer.host.guard:
            offer.require_live()
            # Another connection may have published while this peer supplied
            # its bounded secret frame; enforce the durable cap at publication.
            self._capacity(offer, request)
            service = AutomationAdministrationService(
                custody=offer.host.store,
                owner=RuntimeEnrollmentRequestOwner(offer),
                issuer=offer.host.issuer,
                storage_root=offer.host.store.root,
            )
            transition = service.request(request.enrollment_request_id, proposal)
            if offer.recipient is None:
                offer.recipient = VolatileEnrollmentRecipient(
                    requester=offer.requester(),
                    issuer=offer.host.issuer,
                    profile_binding=offer.prepared.profile_binding,
                    enrollment_request_id=request.enrollment_request_id,
                    review_digest=transition.receipt.review_digest,
                    offer_expires_at=offer.prepared.expires_at,
                )
            return self._recorded(offer, request)

    def _capacity(self, offer: RuntimeEnrollmentOffer, request: RuntimeEnrollmentSubmit) -> None:
        state = offer.host.store.enrollment_state()
        if len(state.requests) >= self.MAXIMUM_RECORDS and not any(
            item.request_id == request.enrollment_request_id for item in state.requests
        ):
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    def _poll(
        self, offer: RuntimeEnrollmentOffer, channel: RuntimeByteChannel, request: RuntimeEnrollmentPoll
    ) -> RuntimeEnrollmentIdle:
        recipient = offer.recipient
        if recipient is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        idle = RuntimeEnrollmentIdle(
            request_id=request.request_id,
            runtime_boot_id=offer.prepared.runtime_boot_id,
            connection_id=offer.prepared.connection_id,
        )
        with recipient.borrow() as work:
            if work is None:
                offer.require_live()
                return idle
            self._deliver_enrollment_work(offer, channel, request, work)
            result = self._read_enrollment_result(channel, work)
            with offer.host.guard:
                offer.require_live()
                work.complete(work.command_id, result)
        return idle

    def _deliver_enrollment_work(
        self,
        offer: RuntimeEnrollmentOffer,
        channel: RuntimeByteChannel,
        request: RuntimeEnrollmentPoll,
        work: EnrollmentWork,
    ) -> None:
        with offer.host.guard:
            offer.require_live()
            write_document(
                channel,
                RuntimeEnrollmentDelivery(
                    request_id=request.request_id,
                    runtime_boot_id=offer.prepared.runtime_boot_id,
                    connection_id=offer.prepared.connection_id,
                    command_id=work.command_id,
                    action="store" if work.action is EnrollmentWorkAction.STORE else "possession",
                    credential=work.credential_binding,
                ),
                deadline=time.monotonic() + 5,
            )
            if work.action is EnrollmentWorkAction.STORE:
                if work.candidate is None:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                write_secret(channel, bytearray(work.candidate.get_secret_value()), deadline=time.monotonic() + 5)

    def _read_enrollment_result(self, channel: RuntimeByteChannel, work: EnrollmentWork) -> EnrollmentWorkResult:
        reply = read_document(channel, RuntimeEnrollmentClientReply, deadline=time.monotonic() + 10)
        if reply.command_id != work.command_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if reply.outcome == "refused" and reply.code is not None:
            return EnrollmentRefused(reply.code)
        if reply.outcome == "stored" and work.action is EnrollmentWorkAction.STORE:
            return EnrollmentStored()
        if reply.outcome == "missing" and work.action is EnrollmentWorkAction.POSSESSION:
            return EnrollmentMissing()
        if reply.outcome == "present" and work.action is EnrollmentWorkAction.POSSESSION:
            with read_secret(channel, deadline=time.monotonic() + 5) as secret:
                return EnrollmentPresent(SecretBytes(bytes(secret)))
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

    def handle(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeEnrollmentRequest
    ) -> None:
        """Bound all secret phases to the verified connection and exact offer."""
        if context.peer != channel.peer or not self._admitting():
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if isinstance(request, RuntimeEnrollmentReconcile):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        try:
            if isinstance(request, RuntimeEnrollmentPrepare):
                result = self._prepare_offer(context, channel, request)
            else:
                offer = self._offer(context, request.profile_id, request.enrollment_request_id)
                if isinstance(request, RuntimeEnrollmentSubmit):
                    result = self._submit(offer, channel, request)
                elif isinstance(request, RuntimeEnrollmentInspect):
                    result = self._recorded(offer, request)
                else:
                    result = self._poll(offer, channel, request)
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            result = RuntimeAccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=context.runtime_boot_id,
                connection_id=context.connection_id,
                code=error.reason,
            )
        write_document(channel, result, deadline=time.monotonic() + 5)

    def disconnect(self, connection_id: UUID) -> None:
        """Retire only this connection's delivery capability."""
        with self._guard:
            offer = self._offers.pop(connection_id, None)
        if offer is not None:
            offer.close()

    def poll(self) -> None:
        """End offers on expiry and originating-login loss even without client calls."""
        with self._guard:
            offers = tuple(self._offers.values())
        for offer in offers:
            try:
                offer.require_live()
            except (AutomationCustodyError, ProfileAccessRefusedError):
                self.disconnect(offer.prepared.connection_id)

    def retire_profile(self, profile_id: UUID, *, host: RuntimeProfileHost | None = None) -> None:
        """An old host must not keep publishing after its guarded owner is replaced."""
        with self._guard:
            offers = tuple(
                offer
                for offer in self._offers.values()
                if offer.connection.profile_id == profile_id and (host is None or offer.host is host)
            )
            for offer in offers:
                self._offers.pop(offer.prepared.connection_id)
        for offer in offers:
            offer.close()

    def close(self) -> None:
        """Wake every producer before runtime shutdown attempts to settle it."""
        with self._guard:
            offers, self._offers = tuple(self._offers.values()), {}
        for offer in offers:
            offer.close()
