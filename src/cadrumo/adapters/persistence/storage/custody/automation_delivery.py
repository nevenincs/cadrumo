"""Client-side native delivery endpoint for an authenticated local channel.

The server must reach this endpoint through a transport-verified recipient port.
Constructing a server-side instance does not prove a remote client's possession.
Only opaque references escape this boundary; native records never enter backups.
"""

from __future__ import annotations

import base64
import secrets
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, SecretBytes

from .....application.user_profile.access_contracts import ProfileAccessBinding
from .....application.user_profile.automation_administration import enrollment_review_digest
from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
    NativeSecretBackend,
)
from .....application.user_profile.automation_enrollment import EnrollmentRecord, EnrollmentRequester
from .....core.identity.digest import ContentDigest
from .....core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .automation_crypto import api_key_verifier, canonical_record, parse_record
from .automation_store import CLIENT_NAMESPACE


class ProtectedDeliveredCredential(BaseModel):
    """Native-only client record, bound independently of ephemeral login provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    schema_version: Literal[1] = 1
    binding: ProfileAccessBinding
    client_id: UUID
    destination_id: UUID
    key_id: UUID
    review_digest: ContentDigest
    secret_b64: str = Field(repr=False)


class NativeEnrollmentRecipient:
    """An exact client connection's endpoint, backed by an explicitly eligible store."""

    def __init__(self, *, requester: EnrollmentRequester, secrets_store: AutomationSecretStore) -> None:
        """Bind recipient facts obtained by the client's trusted transport owner."""
        if not isinstance(secrets_store.backend, NativeSecretBackend):
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        self.requester, self.secrets = requester, secrets_store

    def _account(self, request: EnrollmentRecord) -> str:
        if (
            request.requester != self.requester
            or request.candidate_key_id is None
            or request.credential_reference is None
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return str(request.credential_reference)

    def deliver(self, request: EnrollmentRecord, secret: SecretBytes) -> None:
        """Write/read-back the exact candidate without exposing it to normal output."""
        account = self._account(request)
        key_id = api_key_verifier(secret)[0]
        if key_id != request.candidate_key_id:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        record = ProtectedDeliveredCredential(
            binding=request.binding,
            client_id=self.requester.client_id,
            destination_id=self.requester.destination_id,
            key_id=key_id,
            review_digest=enrollment_review_digest(request),
            secret_b64=base64.b64encode(secret.get_secret_value()).decode("ascii"),
        )
        raw = canonical_record(record)
        previous = self.secrets.read(CLIENT_NAMESPACE, account)
        if previous is not None and not secrets.compare_digest(previous.get_secret_value(), raw):
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        self.secrets.replace(CLIENT_NAMESPACE, account, SecretBytes(raw))
        observed = self.secrets.read(CLIENT_NAMESPACE, account)
        if observed is None or not secrets.compare_digest(observed.get_secret_value(), raw):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)

    def possession(self, request: EnrollmentRecord) -> SecretBytes | None:
        """Read at the client for return solely on the authenticated secret channel."""
        value = self.secrets.read(CLIENT_NAMESPACE, self._account(request))
        if value is None:
            return None
        record = parse_record(ProtectedDeliveredCredential, value.get_secret_value())
        if record.review_digest != enrollment_review_digest(request) or record.key_id != request.candidate_key_id:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return self._credential(record, request.binding)

    def credential(self, reference: UUID, *, binding: ProfileAccessBinding) -> SecretBytes:
        """Resolve an opaque reference for fresh admission on a later connection."""
        value = self.secrets.read(CLIENT_NAMESPACE, str(reference))
        if value is None:
            raise AutomationCustodyError(AutomationCustodyCode.MISSING)
        return self._credential(parse_record(ProtectedDeliveredCredential, value.get_secret_value()), binding)

    def _credential(self, record: ProtectedDeliveredCredential, binding: ProfileAccessBinding) -> SecretBytes:
        if (
            record.binding != binding
            or record.client_id != self.requester.client_id
            or record.destination_id != self.requester.destination_id
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        try:
            raw = base64.b64decode(record.secret_b64, validate=True)
            if base64.b64encode(raw).decode("ascii") != record.secret_b64:
                raise ValueError
        except ValueError:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
        value = SecretBytes(raw)
        if api_key_verifier(value)[0] != record.key_id:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return value
