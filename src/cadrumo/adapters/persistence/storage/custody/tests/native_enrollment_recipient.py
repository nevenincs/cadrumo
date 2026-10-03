"""Native-store enrollment recipient for tests.

Backs an exact client connection's delivery endpoint with an eligible native
credential store, so tests can drive enrollment delivery and possession checks
against a real store without the production client transport.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import SecretBytes

from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.automation_administration import enrollment_review_digest
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
    NativeSecretBackend,
)
from cadrumo.application.user_profile.automation_enrollment import EnrollmentRecord, EnrollmentRequester

from ..automation_client_credentials import NativeClientCredentialStore


class NativeEnrollmentRecipient:
    """An exact client connection's endpoint, backed by an eligible native store."""

    def __init__(self, *, requester: EnrollmentRequester, secrets_store: AutomationSecretStore) -> None:
        """Bind recipient facts obtained by the client's trusted transport owner."""
        if not isinstance(secrets_store.backend, NativeSecretBackend):
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        self.requester, self.secrets = requester, secrets_store

    def _store(self, binding: ProfileAccessBinding) -> NativeClientCredentialStore:
        return NativeClientCredentialStore(
            secrets_store=self.secrets,
            binding=binding,
            client_id=self.requester.client_id,
            destination_id=self.requester.destination_id,
        )

    def _candidate(self, request: EnrollmentRecord) -> tuple[UUID, UUID]:
        if (
            request.requester != self.requester
            or request.candidate_key_id is None
            or request.credential_reference is None
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return request.credential_reference, request.candidate_key_id

    def deliver(self, request: EnrollmentRecord, secret: SecretBytes) -> None:
        """Install the exact candidate without exposing it to ordinary output."""
        reference, key_id = self._candidate(request)
        self._store(request.binding).replace(
            credential_reference=reference,
            grant_id=request.grant_id,
            key_id=key_id,
            review_digest=enrollment_review_digest(request),
            credential=secret,
        )

    def possession(self, request: EnrollmentRecord) -> SecretBytes | None:
        """Read at the client for return solely on the authenticated secret channel."""
        reference, key_id = self._candidate(request)
        try:
            return self._store(request.binding).read(
                credential_reference=reference,
                grant_id=request.grant_id,
                key_id=key_id,
                review_digest=enrollment_review_digest(request),
            )
        except AutomationCustodyError as error:
            if error.reason is AutomationCustodyCode.MISSING:
                return None
            raise

    def credential(self, reference: UUID, *, binding: ProfileAccessBinding) -> SecretBytes:
        """Resolve a bound opaque reference for fresh admission on a later connection."""
        store = self._store(binding)
        metadata = store.inspect(credential_reference=reference)
        return store.read(
            credential_reference=reference,
            grant_id=metadata.grant_id,
            key_id=metadata.key_id,
            review_digest=metadata.review_digest,
        )
