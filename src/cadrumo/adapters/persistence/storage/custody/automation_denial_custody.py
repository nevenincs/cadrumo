"""AutomationDenialCustody for exact witnessed profile automation custody."""

from __future__ import annotations

from collections.abc import Iterable

from cadrumo_client.contracts.access_vocabulary import AuthorityState
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

from .....application.user_profile.automation_enrollment import (
    EnrollmentControlState,
    EnrollmentGrant,
    EnrollmentRecord,
)
from .....application.user_profile.automation_lifecycle import (
    AutomationDenial,
    AutomationDenialKind,
    AutomationDenialReceipt,
)
from .automation_crypto import (
    canonical_record,
    parse_record,
)
from .automation_denial_projection import denied_enrollment_grant, denied_enrollment_requests
from .automation_enrollment_custody import AutomationEnrollmentCustody
from .automation_native_identity import CLIENT_NAMESPACE
from .automation_records import (
    AutomationControlPayload,
    ProtectedControlAnchor,
    StoredAutomationGrant,
)
from .filesystem import (
    clear_profile_custody_local_record,
    profile_custody_root_lock,
)


class AutomationDenialCustody(AutomationEnrollmentCustody):
    """Own the native custody stages for this capability."""

    def deny(self, change: AutomationDenial) -> AutomationDenialReceipt:
        """Fence durably before attempting native reads, updates or deletion.

        Until protected publication and cleanup both complete, every ordinary
        custody door refuses. Password authentication uses its independent door.
        """
        with profile_custody_root_lock(self.root):
            self._prepare()
            if change.binding != self.binding:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            raw = self._read_file("denial.json")
            if raw is not None and parse_record(AutomationDenial, raw) != change:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            self._write_file("denial.json", canonical_record(change))
            if change.kind is AutomationDenialKind.PROFILE_LOCK:
                self._record_profile_lock(change)
            return self._finish_denial(change)

    def reconcile_denial(self) -> AutomationDenialReceipt | None:
        """Retry only the surviving exact change; missing means no pending denial."""
        with profile_custody_root_lock(self.root):
            self._prepare()
            raw = self._read_file("denial.json")
            return None if raw is None else self._finish_denial(parse_record(AutomationDenial, raw))

    def _finish_denial(self, change: AutomationDenial) -> AutomationDenialReceipt:
        revision, generation = None, None
        try:
            if change.binding != self.binding:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            if change.kind is AutomationDenialKind.PROFILE_LOCK:
                generation = self._record_profile_lock(change).generation
            anchor = self._recover_publication()
            payload = None if anchor is None else self._load(anchor)[1]
            if payload is None or payload.last_denial != change:
                state = self._denied_state(change, anchor, payload)
                revision = self._publish_enrollment(state, denial=change)
                generation = state.profile_lock_generation
                self._delete_revoked_client_keys(state.grants, state.requests)
            else:
                revision = anchor.witness.revision if anchor is not None else None
                generation = payload.profile_lock_generation
                self._delete_revoked_client_keys(payload.grants, payload.requests)
            clear_profile_custody_local_record(self.directory / "denial.json")
        except AutomationCustodyError:
            return AutomationDenialReceipt(
                request_id=change.request_id,
                profile_id=self.binding.profile_id,
                access_denied=True,
                cleanup_pending=True,
                revision=revision,
                profile_lock_generation=generation,
            )
        return AutomationDenialReceipt(
            request_id=change.request_id,
            profile_id=self.binding.profile_id,
            access_denied=True,
            cleanup_pending=False,
            revision=revision,
            profile_lock_generation=generation,
        )

    def _delete_revoked_client_keys(
        self,
        grants: Iterable[EnrollmentGrant | StoredAutomationGrant],
        requests: Iterable[EnrollmentRecord],
    ) -> None:
        """Delete the client's stored copy of every delivered key the published denial revoked.

        The enrolling client keeps each delivered key in the same account's
        native store, named by the credential reference this custody minted
        for the enrollment and sealed in its record, so the exact name is the
        whole proof of ownership and nothing is read or decoded first. The
        exact delete is idempotent: it runs before the denial intent is
        cleared, so a store that cannot answer keeps the denial pending and a
        reconciliation retries it, and a completed one finds nothing left. A
        suspended key, which a resume can restore, is kept.
        """
        revoked = {
            item.key.key_id
            for entry in grants
            for item in entry.keys
            if item.key.state is AuthorityState.REVOKED or entry.grant.state is AuthorityState.REVOKED
        }
        for record in requests:
            if record.credential_reference is not None and record.candidate_key_id in revoked:
                self.secrets.delete(CLIENT_NAMESPACE, str(record.credential_reference))

    def _denied_state(
        self,
        change: AutomationDenial,
        anchor: ProtectedControlAnchor | None,
        payload: AutomationControlPayload | None,
    ) -> EnrollmentControlState:
        locking = change.kind is AutomationDenialKind.PROFILE_LOCK
        generation = (
            self._local_lock().generation if locking else (0 if payload is None else payload.profile_lock_generation)
        )
        if payload is not None and generation < payload.profile_lock_generation:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        entries: list[EnrollmentGrant] = []
        for stored in () if payload is None else payload.grants:
            entries.append(denied_enrollment_grant(stored, change, locking))
        return EnrollmentControlState(
            revision=0 if anchor is None else anchor.witness.revision,
            binding=self.binding,
            profile_lock_generation=generation,
            automation_enabled=not locking and (payload is None or payload.automation_enabled),
            grants=tuple(entries),
            requests=denied_enrollment_requests(payload),
        )
