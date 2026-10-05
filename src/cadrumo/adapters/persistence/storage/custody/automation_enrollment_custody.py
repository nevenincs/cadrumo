"""AutomationEnrollmentCustody for exact witnessed profile automation custody."""

from __future__ import annotations

from pydantic import SecretBytes

from .....application.user_profile.access_contracts import (
    AuthorityState,
)
from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationGrantMaterial,
)
from .....application.user_profile.automation_enrollment import (
    EnrollmentControlState,
    EnrollmentGrant,
)
from .....application.user_profile.automation_lifecycle import (
    AutomationDenial,
)
from .automation_control_projection import previous_enrollment_grant
from .automation_control_publication import AutomationControlPublication
from .automation_crypto import (
    open_automation,
)
from .automation_native_identity import WRAP_NAMESPACE
from .automation_records import (
    AutomationControlPayload,
    AutomationRecordHeader,
)
from .filesystem import (
    profile_custody_root_lock,
)


class AutomationEnrollmentCustody(AutomationControlPublication):
    """Own the native custody stages for this capability."""

    def enrollment_state(self) -> EnrollmentControlState:
        """Read verified administration facts without releasing DEKs or native keys."""
        with profile_custody_root_lock(self.root):
            self._prepare()
            anchor = self._recover()
            payload = None if anchor is None else self._load(anchor)[1]
            return EnrollmentControlState(
                revision=0 if anchor is None else anchor.witness.revision,
                binding=self.binding,
                profile_lock_generation=0 if payload is None else payload.profile_lock_generation,
                automation_enabled=True if payload is None else payload.automation_enabled,
                grants=()
                if payload is None
                else tuple(EnrollmentGrant(grant=item.grant, keys=item.keys) for item in payload.grants),
                requests=() if payload is None else payload.requests,
            )

    def publish_enrollment(self, state: EnrollmentControlState, *, fresh_dek: SecretBytes | None = None) -> int:
        """CAS administration facts without bypassing a surviving denial."""
        return self._publish_enrollment(state, fresh_dek=fresh_dek)

    def _publish_enrollment(
        self,
        state: EnrollmentControlState,
        *,
        fresh_dek: SecretBytes | None = None,
        denial: AutomationDenial | None = None,
    ) -> int:
        """CAS enrollment alongside grants using the existing staged publication.

        Existing grant DEKs are rewrapped inside custody. A new grant requires a
        fresh password-proven DEK. Filesystem and native writes remain separate
        durability boundaries, and the same recovery witness chooses the winner.
        """
        with profile_custody_root_lock(self.root):
            self._prepare()
            anchor = self._recover() if denial is None else self._recover_publication()
            revision = 0 if anchor is None else anchor.witness.revision
            if state.binding != self.binding or state.revision != revision:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            previous = None if anchor is None else self._load(anchor)
            materials: list[AutomationGrantMaterial] = []
            for entry in state.grants:
                materials.append(self._enrollment_grant_material(entry, previous, fresh_dek))
            return self._publish(
                grants=tuple(materials),
                expected_revision=revision,
                profile_lock_generation=state.profile_lock_generation,
                automation_enabled=state.automation_enabled,
                requests=state.requests,
                denial=denial,
            )

    def _enrollment_grant_material(
        self,
        entry: EnrollmentGrant,
        previous: tuple[AutomationRecordHeader, AutomationControlPayload] | None,
        fresh_dek: SecretBytes | None,
    ) -> AutomationGrantMaterial:
        """Use fresh password proof or unwrap only the exact previous grant material."""
        if entry.grant.state in {AuthorityState.SUSPENDED, AuthorityState.REVOKED}:
            return AutomationGrantMaterial(grant=entry.grant, keys=entry.keys, dek=None)
        old = previous_enrollment_grant(previous, entry)
        dek = fresh_dek
        if (
            dek is None
            and old is not None
            and previous is not None
            and old.wrap_key_id is not None
            and old.wrapped_dek is not None
        ):
            key = self.secrets.read(WRAP_NAMESPACE, self.account + "/" + str(old.wrap_key_id))
            if key is None:
                raise AutomationCustodyError(AutomationCustodyCode.MISSING)
            dek = SecretBytes(open_automation(old.wrapped_dek, key, self._aad(previous[0], old.grant.grant_id)))
        if dek is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return AutomationGrantMaterial(grant=entry.grant, keys=entry.keys, dek=dek)
