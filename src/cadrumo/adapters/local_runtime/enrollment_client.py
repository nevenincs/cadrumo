"""Exact-client protected enrollment over one verified native connection."""

from __future__ import annotations

from typing import Never
from uuid import UUID, uuid4

from pydantic import SecretBytes

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import deadline_after
from ...application.runtime.enrollment_access import (
    EnrollmentCredentialBinding,
    RuntimeEnrollmentDelivery,
    RuntimeEnrollmentIdle,
    RuntimeEnrollmentInspect,
    RuntimeEnrollmentPoll,
    RuntimeEnrollmentPrepared,
    RuntimeEnrollmentRecorded,
    RuntimeEnrollmentSubmit,
)
from ...application.runtime.profile_access import RuntimeAccessRefusal
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from ...application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentProposal,
    EnrollmentStage,
)
from ...core.time.clock import now
from ..persistence.storage.custody.automation_client_credentials import (
    ClientCredentialMetadata,
    NativeClientCredentialStore,
)
from .framing import VerifiedRuntimeConnection


def _raise_refusal(reply: RuntimeAccessRefusal) -> Never:
    """Keep one allowlisted reason without copying transport input."""
    code = reply.code
    if isinstance(code, AccessDenialCode):
        raise ProfileAccessRefusedError(code)
    if isinstance(code, AutomationCustodyCode):
        raise AutomationCustodyError(code)
    raise RuntimeRefusalError(code)


class NativeEnrollmentClient:
    """Borrow one verified connection and store only its prepared safe identity.

    The connection performs native peer validation and separate secret frames.
    This wrapper enforces the requester binding before client-side storage or
    possession and never retains a candidate, proposal buffer or API key.
    """

    def __init__(
        self,
        *,
        connection: VerifiedRuntimeConnection,
        prepared: RuntimeEnrollmentPrepared,
        secrets_store: AutomationSecretStore,
    ) -> None:
        """Bind an exact prepared request to the current verified connection."""
        if prepared.runtime_boot_id != connection.hello.boot_id or prepared.connection_id != connection.connection_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._connection, self.prepared = connection, prepared
        self._store = NativeClientCredentialStore(
            secrets_store=secrets_store,
            binding=prepared.profile_binding,
            client_id=prepared.client_id,
            destination_id=prepared.destination_id,
        )
        self._receipt: AutomationReceiptProjection | None = None
        self._offer: EnrollmentCredentialBinding | None = None

    @property
    def receipt(self) -> AutomationReceiptProjection | None:
        """Expose only the latest validated safe receipt."""
        return self._receipt

    def _live(self) -> None:
        if now() >= self.prepared.expires_at:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)

    def _checked[ReplyT: RuntimeEnrollmentRecorded | RuntimeEnrollmentIdle | RuntimeEnrollmentDelivery](
        self,
        reply: ReplyT | RuntimeAccessRefusal,
        *,
        request_id: UUID,
    ) -> ReplyT:
        if (
            reply.request_id != request_id
            or reply.runtime_boot_id != self.prepared.runtime_boot_id
            or reply.connection_id != self.prepared.connection_id
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if isinstance(reply, RuntimeAccessRefusal):
            _raise_refusal(reply)
        return reply

    def _pin_receipt(self, receipt: AutomationReceiptProjection) -> AutomationReceiptProjection:
        prepared = self.prepared
        _require_prepared_receipt(receipt, prepared)
        earlier = self._receipt
        if earlier is not None and _receipt_changed(receipt, earlier):
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        offer = self._offer
        if offer is not None and _receipt_differs_from_offer(receipt, offer):
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        if (
            earlier is not None
            and earlier.stage in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}
            and receipt.stage is not earlier.stage
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        self._receipt = receipt
        return receipt

    def _pin_offer(self, offer: EnrollmentCredentialBinding) -> None:
        prepared, receipt = self.prepared, self._receipt
        if (
            receipt is None
            or _offer_differs_from_prepared(offer, prepared)
            or offer.review_digest != receipt.review_digest
            or offer.grant_id != receipt.grant_id
            or (
                receipt.key_id is not None
                and (offer.key_id != receipt.key_id or offer.credential_reference != receipt.credential_reference)
            )
            or (self._offer is not None and offer != self._offer)
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        # Pin before a native write: failure can follow a committed replacement.
        self._offer = offer

    def _store_candidate(self, offer: EnrollmentCredentialBinding, secret: SecretBytes) -> None:
        self._pin_offer(offer)
        self._store.replace(
            credential_reference=offer.credential_reference,
            grant_id=offer.grant_id,
            key_id=offer.key_id,
            review_digest=offer.review_digest,
            credential=secret,
        )

    def _possession(self, offer: EnrollmentCredentialBinding) -> SecretBytes | None:
        self._pin_offer(offer)
        try:
            return self._store.read(
                credential_reference=offer.credential_reference,
                grant_id=offer.grant_id,
                key_id=offer.key_id,
                review_digest=offer.review_digest,
            )
        except AutomationCustodyError as error:
            if error.reason is AutomationCustodyCode.MISSING:
                return None
            raise

    def submit(self, proposal: EnrollmentProposal, *, timeout: float = 10.0) -> AutomationReceiptProjection:
        """Submit only protected proposal bytes, then pin the first safe review."""
        self._live()
        request = RuntimeEnrollmentSubmit(
            request_id=uuid4(),
            profile_id=self.prepared.profile_binding.profile_id,
            enrollment_request_id=self.prepared.enrollment_request_id,
        )
        secret = bytearray(proposal.model_dump_json().encode("utf-8"))
        try:
            reply = self._connection.enrollment_submit(request, secret, deadline=deadline_after(timeout))
        finally:
            secret[:] = bytes(len(secret))
        return self._pin_receipt(self._checked(reply, request_id=request.request_id).receipt)

    def inspect(self, *, timeout: float = 10.0) -> AutomationReceiptProjection | None:
        """Read a current safe receipt without touching login or candidate custody."""
        self._live()
        request = RuntimeEnrollmentInspect(
            request_id=uuid4(),
            profile_id=self.prepared.profile_binding.profile_id,
            enrollment_request_id=self.prepared.enrollment_request_id,
        )
        reply = self._checked(
            self._connection.enrollment_inspect(request, deadline=deadline_after(timeout)),
            request_id=request.request_id,
        )
        if isinstance(reply, RuntimeEnrollmentIdle):
            return None
        return self._pin_receipt(reply.receipt)

    def poll(self, *, timeout: float = 10.0) -> RuntimeEnrollmentDelivery | None:
        """Respond to one exact delivery command using the current native store."""
        self._live()
        if self._receipt is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        request = RuntimeEnrollmentPoll(
            request_id=uuid4(),
            profile_id=self.prepared.profile_binding.profile_id,
            enrollment_request_id=self.prepared.enrollment_request_id,
        )
        reply = self._checked(
            self._connection.enrollment_poll(
                request,
                store=self._store_candidate,
                possession=self._possession,
                deadline=deadline_after(timeout),
            ),
            request_id=request.request_id,
        )
        if isinstance(reply, RuntimeEnrollmentIdle):
            return None
        if self._offer != reply.credential:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply

    def accept_reconciled_terminal(self, receipt: AutomationReceiptProjection) -> None:
        """Pin a terminal receipt obtained by fresh exact-client runtime reconciliation.

        This only validates safe facts. The caller's reconciliation must have
        authenticated afresh; this method cannot confer that authority.
        """
        if self._receipt is None or receipt.stage not in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        self._pin_receipt(receipt)

    def delivered_credential_metadata(self) -> ClientCredentialMetadata:
        """Verify a pinned delivery's current native item without asserting activation."""
        offer = self._offer
        if offer is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        metadata = self._store.inspect(credential_reference=offer.credential_reference)
        if (
            metadata.profile_id != self.prepared.profile_binding.profile_id
            or metadata.client_id != self.prepared.client_id
            or metadata.destination_id != self.prepared.destination_id
            or metadata.grant_id != offer.grant_id
            or metadata.key_id != offer.key_id
            or metadata.review_digest != offer.review_digest
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return metadata

    def verified_terminal(self) -> ClientCredentialMetadata | None:
        """Verify terminal delivery against current native custody without exporting a key."""
        receipt = self._receipt
        if receipt is None or receipt.stage not in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if receipt.stage is EnrollmentStage.DECLINED:
            # A declined CANDIDATE retains its published key/reference as
            # review history; it never makes that key usable by this client.
            return None
        if receipt.key_id is None:
            return None
        offer = self._offer
        if offer is None or receipt.credential_reference is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if offer.key_id != receipt.key_id or offer.credential_reference != receipt.credential_reference:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        return self.delivered_credential_metadata()

    def credential(self) -> SecretBytes:
        """Read an exact completed API key afresh for a protected future login."""
        receipt = self._receipt
        if (
            receipt is None
            or receipt.stage is not EnrollmentStage.COMPLETE
            or receipt.key_id is None
            or receipt.credential_reference is None
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return self._store.read(
            credential_reference=receipt.credential_reference,
            grant_id=receipt.grant_id,
            key_id=receipt.key_id,
            review_digest=receipt.review_digest,
        )


def _receipt_changed(receipt: AutomationReceiptProjection, earlier: AutomationReceiptProjection) -> bool:
    """Preserve the review and any previously pinned key identity."""
    return (
        receipt.review_digest != earlier.review_digest
        or receipt.grant_id != earlier.grant_id
        or (
            earlier.key_id is not None
            and (receipt.key_id != earlier.key_id or receipt.credential_reference != earlier.credential_reference)
        )
    )


def _receipt_differs_from_offer(receipt: AutomationReceiptProjection, offer: EnrollmentCredentialBinding) -> bool:
    """Require delivered credential identity to match the same reviewed enrollment."""
    return (
        receipt.review_digest != offer.review_digest
        or receipt.grant_id != offer.grant_id
        or (
            receipt.key_id is not None
            and (receipt.key_id != offer.key_id or receipt.credential_reference != offer.credential_reference)
        )
    )


def _offer_differs_from_prepared(offer: EnrollmentCredentialBinding, prepared: RuntimeEnrollmentPrepared) -> bool:
    """Require the exact prepared profile, client and destination before pinning a delivery."""
    return (
        offer.profile_binding != prepared.profile_binding
        or offer.client_id != prepared.client_id
        or offer.destination_id != prepared.destination_id
    )


def _require_prepared_receipt(receipt: AutomationReceiptProjection, prepared: RuntimeEnrollmentPrepared) -> None:
    """Require the original prepared enrollment and paired credential coordinates."""
    if (
        receipt.profile_id != prepared.profile_binding.profile_id
        or receipt.request_id != prepared.enrollment_request_id
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if (receipt.key_id is None) != (receipt.credential_reference is None):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
