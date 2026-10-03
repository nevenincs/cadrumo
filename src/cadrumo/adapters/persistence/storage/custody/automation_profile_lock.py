"""AutomationProfileLock for exact witnessed profile automation custody."""

from __future__ import annotations

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
)
from .....application.user_profile.automation_lifecycle import (
    AutomationDenial,
    AutomationDenialKind,
    ProfileGlobalLockState,
)
from .automation_control_projection import changed_control_model
from .automation_control_storage import AutomationControlStorage
from .automation_crypto import (
    canonical_record,
    parse_record,
)
from .automation_profile import validate_automation_profile_binding
from .automation_records import (
    AutomationRetirementIntent,
    ProfileGlobalLockRecord,
)
from .filesystem import (
    profile_custody_root_lock,
)


class AutomationProfileLock(AutomationControlStorage):
    """Own the native custody stages for this capability."""

    def _local_lock(self) -> ProfileGlobalLockRecord:
        raw = self._read_file("profile-lock.json")
        if raw is None:
            return ProfileGlobalLockRecord(binding=self.binding, generation=0, globally_locked=False)
        record = parse_record(ProfileGlobalLockRecord, raw)
        if record.binding != self.binding:
            # A password/recovery transition can finish while native retirement
            # remains pending. Old automation stays denied; fresh human custody
            # is independent. Never accept an unexplained identity mismatch.
            retirement = self._read_file("retirement.json")
            if retirement is None:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            intent = parse_record(AutomationRetirementIntent, retirement)
            if (
                intent.profile_id != self.binding.profile_id
                or intent.installation_id != self.binding.installation_id
                or record.binding.profile_id != self.binding.profile_id
                or record.binding.installation_id != self.binding.installation_id
            ):
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            return ProfileGlobalLockRecord(binding=self.binding, generation=0, globally_locked=False)
        return record

    def _record_profile_lock(self, change: AutomationDenial) -> ProfileGlobalLockRecord:
        record = self._local_lock()
        if record.request_id != change.request_id:
            record = changed_control_model(
                record, request_id=change.request_id, generation=record.generation + 1, globally_locked=True
            )
            self._write_file("profile-lock.json", canonical_record(record))
        return record

    def profile_lock_state(self) -> ProfileGlobalLockState:
        """Observe human-access fencing even while optional credentials are unavailable."""
        with profile_custody_root_lock(self.root):
            self._prepare_directories()
            validate_automation_profile_binding(self.binding, root=self.root)
            raw = self._read_file("denial.json")
            change = None if raw is None else parse_record(AutomationDenial, raw)
            record = self._local_lock()
            if (
                change is not None
                and change.binding == self.binding
                and change.kind is AutomationDenialKind.PROFILE_LOCK
            ):
                record = self._record_profile_lock(change)
            return ProfileGlobalLockState(
                binding=record.binding, generation=record.generation, globally_locked=record.globally_locked
            )

    def unlock_profile(self, *, generation: int) -> ProfileGlobalLockState:
        """CAS the human lock only; the caller must supply fresh password authority."""
        with profile_custody_root_lock(self.root):
            state = self.profile_lock_state()
            if state.generation != generation:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            record = changed_control_model(self._local_lock(), globally_locked=False)
            self._write_file("profile-lock.json", canonical_record(record))
            return ProfileGlobalLockState(binding=self.binding, generation=generation, globally_locked=False)
