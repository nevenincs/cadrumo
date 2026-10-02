"""Exact-reference client API-key custody in an explicitly supplied native store.

This is a private client persistence adapter, not evidence that a remote client
received a candidate or proved possession to the enrollment service. The
transport recipient owns that separate attestation.
"""

from __future__ import annotations

import base64
import secrets
from hashlib import sha256
from typing import Literal, override
from uuid import UUID

from pydantic import BaseModel, Field, SecretBytes

from .....application.user_profile.access_contracts import ProfileAccessBinding
from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
    NativeSecretBackend,
)
from .....core.identity.digest import ContentDigest
from .....core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .automation_crypto import CustodyAutomationKeyIssuer, canonical_record, parse_record
from .automation_store import CLIENT_NAMESPACE

# Bound the private envelope to the current native credential-blob budget
# before asking any composed native backend to write it.
MAX_CLIENT_CREDENTIAL_BYTES = 2560


class ClientCredentialMetadata(BaseModel):
    """Nonsecret identity of one exact credential reference."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    credential_reference: UUID
    profile_id: UUID
    client_id: UUID
    destination_id: UUID
    grant_id: UUID
    key_id: UUID
    review_digest: ContentDigest


class _ClientCredentialEnvelope(BaseModel):
    """Strict current-version private native item; never a public result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    schema_version: Literal[1] = 1
    binding: ProfileAccessBinding
    client_id: UUID
    destination_id: UUID
    credential_reference: UUID
    grant_id: UUID
    key_id: UUID
    review_digest: ContentDigest
    secret_b64: str = Field(min_length=1, max_length=512, repr=False)


def _native_read_exact(secrets_store: AutomationSecretStore, reference: UUID) -> bytes | None:
    if not isinstance(secrets_store.backend, NativeSecretBackend):
        raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
    try:
        stored = secrets_store.read(CLIENT_NAMESPACE, str(reference))
    except AutomationCustodyError:
        raise
    except Exception:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
    if stored is None:
        return None
    raw = stored.get_secret_value()
    if not 0 < len(raw) <= MAX_CLIENT_CREDENTIAL_BYTES:
        raise AutomationCustodyError(AutomationCustodyCode.INVALID)
    return raw


class NativeClientCredentialStore:
    """Read, replace and delete only one client's exact native references.

    The caller supplies an already selected non-prompting native store. No
    profile selector, keyring plugin or filesystem fallback is consulted here.
    A failed native replacement may have committed, so this adapter reads back
    the exact item before deciding whether the attempt succeeded.
    """

    def __init__(
        self,
        *,
        secrets_store: AutomationSecretStore,
        binding: ProfileAccessBinding,
        client_id: UUID,
        destination_id: UUID,
    ) -> None:
        """Bind one immutable client and custody identity to an explicit store."""
        if not isinstance(secrets_store.backend, NativeSecretBackend):
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        self._secrets = secrets_store
        self._binding = binding
        self._client_id = client_id
        self._destination_id = destination_id

    def _metadata(
        self, reference: UUID, grant_id: UUID, key_id: UUID, review_digest: ContentDigest
    ) -> ClientCredentialMetadata:
        return ClientCredentialMetadata(
            credential_reference=reference,
            profile_id=self._binding.profile_id,
            client_id=self._client_id,
            destination_id=self._destination_id,
            grant_id=grant_id,
            key_id=key_id,
            review_digest=review_digest,
        )

    def _native_read(self, reference: UUID) -> bytes | None:
        return _native_read_exact(self._secrets, reference)

    @staticmethod
    def _credential(envelope: _ClientCredentialEnvelope) -> SecretBytes:
        try:
            raw = base64.b64decode(envelope.secret_b64, validate=True)
            if base64.b64encode(raw).decode("ascii") != envelope.secret_b64:
                raise ValueError
        except (ValueError, UnicodeError):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
        credential = SecretBytes(raw)
        if CustodyAutomationKeyIssuer.verifier(credential)[0] != envelope.key_id:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return credential

    def _owned(self, raw: bytes, *, reference: UUID, mismatch: AutomationCustodyCode) -> _ClientCredentialEnvelope:
        envelope = parse_record(_ClientCredentialEnvelope, raw)
        if (
            envelope.binding != self._binding
            or envelope.client_id != self._client_id
            or envelope.destination_id != self._destination_id
            or envelope.credential_reference != reference
        ):
            raise AutomationCustodyError(mismatch)
        self._credential(envelope)
        return envelope

    def _verified(
        self,
        raw: bytes,
        *,
        reference: UUID,
        grant_id: UUID,
        key_id: UUID,
        review_digest: ContentDigest,
        mismatch: AutomationCustodyCode,
    ) -> tuple[_ClientCredentialEnvelope, SecretBytes]:
        envelope = self._owned(raw, reference=reference, mismatch=mismatch)
        if envelope.grant_id != grant_id or envelope.key_id != key_id or envelope.review_digest != review_digest:
            raise AutomationCustodyError(mismatch)
        return envelope, self._credential(envelope)

    def inspect(self, *, credential_reference: UUID) -> ClientCredentialMetadata:
        """Return only verified identity needed for exact later reconnection."""
        raw = self._native_read(credential_reference)
        if raw is None:
            raise AutomationCustodyError(AutomationCustodyCode.MISSING)
        envelope = self._owned(raw, reference=credential_reference, mismatch=AutomationCustodyCode.CREDENTIAL_REJECTED)
        return self._metadata(credential_reference, envelope.grant_id, envelope.key_id, envelope.review_digest)

    def read(
        self, *, credential_reference: UUID, grant_id: UUID, key_id: UUID, review_digest: ContentDigest
    ) -> SecretBytes:
        """Return private key material only after every expected binding matches."""
        raw = self._native_read(credential_reference)
        if raw is None:
            raise AutomationCustodyError(AutomationCustodyCode.MISSING)
        return self._verified(
            raw,
            reference=credential_reference,
            grant_id=grant_id,
            key_id=key_id,
            review_digest=review_digest,
            mismatch=AutomationCustodyCode.CREDENTIAL_REJECTED,
        )[1]

    def read_pinned(self, *, metadata: ClientCredentialMetadata, fingerprint: bytes) -> SecretBytes:
        """Read one unchanged native item with all original custody coordinates."""
        raw = self._native_read(metadata.credential_reference)
        if raw is None:
            raise AutomationCustodyError(AutomationCustodyCode.MISSING)
        if not secrets.compare_digest(sha256(raw).digest(), fingerprint):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return self._verified(
            raw,
            reference=metadata.credential_reference,
            grant_id=metadata.grant_id,
            key_id=metadata.key_id,
            review_digest=metadata.review_digest,
            mismatch=AutomationCustodyCode.CREDENTIAL_REJECTED,
        )[1]

    @classmethod
    def resolve_reference(
        cls, *, credential_reference: UUID, binding: ProfileAccessBinding, secrets_store: AutomationSecretStore
    ) -> ClientCredentialHandle:
        """Resolve exact current metadata without presupposing client IDs."""
        raw = _native_read_exact(secrets_store, credential_reference)
        if raw is None:
            raise AutomationCustodyError(AutomationCustodyCode.MISSING)
        envelope = parse_record(_ClientCredentialEnvelope, raw)
        if envelope.binding != binding or envelope.credential_reference != credential_reference:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        store = cls(
            secrets_store=secrets_store,
            binding=binding,
            client_id=envelope.client_id,
            destination_id=envelope.destination_id,
        )
        store._credential(envelope)
        metadata = store._metadata(credential_reference, envelope.grant_id, envelope.key_id, envelope.review_digest)
        return ClientCredentialHandle(store=store, metadata=metadata, fingerprint=sha256(raw).digest())

    def replace(
        self,
        *,
        credential_reference: UUID,
        grant_id: UUID,
        key_id: UUID,
        review_digest: ContentDigest,
        credential: SecretBytes,
    ) -> ClientCredentialMetadata:
        """Install once; same-secret retries succeed, while a rebound item refuses."""
        if CustodyAutomationKeyIssuer.verifier(credential)[0] != key_id:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        envelope = _ClientCredentialEnvelope(
            binding=self._binding,
            client_id=self._client_id,
            destination_id=self._destination_id,
            credential_reference=credential_reference,
            grant_id=grant_id,
            key_id=key_id,
            review_digest=review_digest,
            secret_b64=base64.b64encode(credential.get_secret_value()).decode("ascii"),
        )
        encoded = canonical_record(envelope)
        if not 0 < len(encoded) <= MAX_CLIENT_CREDENTIAL_BYTES:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        metadata = self._metadata(credential_reference, grant_id, key_id, review_digest)
        previous = self._native_read(credential_reference)
        if previous is not None:
            self._verified(
                previous,
                reference=credential_reference,
                grant_id=grant_id,
                key_id=key_id,
                review_digest=review_digest,
                mismatch=AutomationCustodyCode.CONFLICT,
            )
            if not secrets.compare_digest(previous, encoded):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            return metadata
        try:
            self._secrets.replace(CLIENT_NAMESPACE, str(credential_reference), SecretBytes(encoded))
        except Exception as error:
            # A native write error can occur after publication. Read only the
            # same reference; no enumeration, blind replay or secret output.
            try:
                observed = self._native_read(credential_reference)
            except AutomationCustodyError:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
            if observed is not None and secrets.compare_digest(observed, encoded):
                return metadata
            if observed is not None:
                self._verified(
                    observed,
                    reference=credential_reference,
                    grant_id=grant_id,
                    key_id=key_id,
                    review_digest=review_digest,
                    mismatch=AutomationCustodyCode.CONFLICT,
                )
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT) from None
            if isinstance(error, AutomationCustodyError):
                raise error from None
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
        observed = self._native_read(credential_reference)
        if observed is None or not secrets.compare_digest(observed, encoded):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        return metadata

    def delete(self, *, credential_reference: UUID, grant_id: UUID, key_id: UUID, review_digest: ContentDigest) -> None:
        """Delete only a matching reference; reconcile a possibly committed delete."""
        previous = self._native_read(credential_reference)
        if previous is None:
            return
        self._verified(
            previous,
            reference=credential_reference,
            grant_id=grant_id,
            key_id=key_id,
            review_digest=review_digest,
            mismatch=AutomationCustodyCode.CREDENTIAL_REJECTED,
        )
        try:
            self._secrets.delete(CLIENT_NAMESPACE, str(credential_reference))
        except Exception as error:
            try:
                observed = self._native_read(credential_reference)
            except AutomationCustodyError:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
            if observed is None:
                return
            if not secrets.compare_digest(observed, previous):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT) from None
            if isinstance(error, AutomationCustodyError):
                raise error from None
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
        if self._native_read(credential_reference) is not None:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)


class ClientCredentialHandle:
    """One verified reference; each secret read rechecks its exact native item."""

    __slots__ = ("_fingerprint", "_metadata", "_store")

    def __init__(
        self, *, store: NativeClientCredentialStore, metadata: ClientCredentialMetadata, fingerprint: bytes
    ) -> None:
        """Pin nonsecret metadata and record identity for later fresh reads."""
        self._store = store
        self._metadata = metadata
        self._fingerprint = fingerprint

    @property
    def metadata(self) -> ClientCredentialMetadata:
        """Return safe identity only; this does not prove an active grant."""
        return self._metadata

    def read(self) -> SecretBytes:
        """Read a current exact item, refusing any intervening replacement."""
        return self._store.read_pinned(metadata=self._metadata, fingerprint=self._fingerprint)

    @override
    def __repr__(self) -> str:
        """Never expose the store or private record fingerprint in diagnostics."""
        return f"ClientCredentialHandle(credential_reference={self._metadata.credential_reference})"


__all__ = [
    "MAX_CLIENT_CREDENTIAL_BYTES",
    "ClientCredentialHandle",
    "ClientCredentialMetadata",
    "NativeClientCredentialStore",
]
