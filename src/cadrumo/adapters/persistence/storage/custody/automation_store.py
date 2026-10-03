"""Credential admission and wipeable DEK borrowing from witnessed automation custody."""

from __future__ import annotations

import secrets
from collections.abc import Generator
from contextlib import contextmanager
from uuid import UUID

from pydantic import SecretBytes

from .....application.user_profile.access_contracts import (
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
)
from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationKeyVerifier,
)
from .....core.time.utc import UtcInstant
from .automation_crypto import (
    api_key_verifier,
    open_automation,
)
from .automation_denial_custody import AutomationDenialCustody
from .automation_native_identity import WRAP_NAMESPACE
from .automation_profile import validate_automation_profile_binding
from .automation_records import (
    AutomationControlPayload,
    AutomationRecordHeader,
)
from .filesystem import (
    profile_custody_root_lock,
)
from .zeroise import zeroise


class AutomationControlStore(AutomationDenialCustody):
    """One exact installation/profile binding and native-store dependency.

    Callers supply current identity from the trusted lifecycle owner. The store
    independently reads the committed password envelope and sentinel under the
    existing root lock. It never selects/unlocks the ambient human profile.
    """

    @contextmanager
    def unlocked(self, *, credential: SecretBytes, now: UtcInstant) -> Generator[bytearray]:
        """Lend verified material, wiping the mutable buffer on success or failure."""
        material = self.unwrap(credential=credential, now=now)
        try:
            yield material
        finally:
            zeroise(material)

    def unwrap(self, *, credential: SecretBytes, now: UtcInstant) -> bytearray:
        """Return a wipeable DEK only after credential, control and sentinel proof.

        Does not admit a connection or grant operation authority. The lifecycle
        owner must evaluate login eligibility and session policy separately.
        """
        key_id, verifier = api_key_verifier(credential)
        with profile_custody_root_lock(self.root):
            self._prepare()
            if self._local_lock().globally_locked:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            anchor = self._recover()
            if anchor is None:
                raise AutomationCustodyError(AutomationCustodyCode.MISSING)
            header, payload = self._load(anchor)
            for entry in payload.grants:
                for item in entry.keys:
                    if item.key.key_id != key_id:
                        continue
                    grant, key = entry.grant, item.key
                    if (
                        _unwrap_policy_refused(verifier, item, payload, grant, key)
                        or _unwrap_validity_refused(grant, key, now)
                        or entry.wrap_key_id is None
                        or entry.wrapped_dek is None
                    ):
                        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
                    return self._unwrap_grant_material(entry.wrap_key_id, entry.wrapped_dek, header, grant.grant_id)
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)

    def _unwrap_grant_material(
        self,
        wrap_key_id: UUID,
        wrapped_dek: str,
        header: AutomationRecordHeader,
        grant_id: UUID,
    ) -> bytearray:
        """Verify the live profile sentinel and wipe material if that proof fails."""
        wrapping_key = self.secrets.read(WRAP_NAMESPACE, self.account + "/" + str(wrap_key_id))
        if wrapping_key is None:
            raise AutomationCustodyError(AutomationCustodyCode.MISSING)
        dek = bytearray(open_automation(wrapped_dek, wrapping_key, self._aad(header, grant_id)))
        try:
            validate_automation_profile_binding(self.binding, root=self.root, dek=bytes(dek))
        except BaseException:
            zeroise(dek)
            raise
        return dek


def _unwrap_policy_refused(
    verifier: str,
    item: AutomationKeyVerifier,
    payload: AutomationControlPayload,
    grant: AutomationGrant,
    key: ApiKeyRecord,
) -> bool:
    """Check credential and current policy before considering time or wrapper material."""
    return (
        not secrets.compare_digest(verifier, item.verifier)
        or not payload.automation_enabled
        or (not grant.unattended)
        or (grant.state is not AuthorityState.ACTIVE)
        or (key.state is not AuthorityState.ACTIVE)
        or (grant.profile_lock_generation != payload.profile_lock_generation)
    )


def _unwrap_validity_refused(grant: AutomationGrant, key: ApiKeyRecord, now: UtcInstant) -> bool:
    """Require both the grant and the addressed key inside their exact live intervals."""
    return not grant.valid_from <= now < grant.expires_at or not key.valid_from <= now < key.expires_at
