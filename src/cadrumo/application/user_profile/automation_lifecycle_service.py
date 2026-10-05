"""Authorization, live fencing and durable denial share one lifecycle boundary."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, SecretBytes

from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .access_administration import (
    AccessAdministrationAction,
    AccessAdministrationRequest,
    FreshPasswordAuthorization,
    evaluate_access_administration,
)
from .access_contracts import ACCESS_LEASE_MAXIMUM, AccessDenied, ApiKeyRecord, AuthorityState, ProfileAccessBinding
from .automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .automation_enrollment import (
    AdministrationFacts,
    EnrollmentControlState,
    EnrollmentCustodyPort,
    EnrollmentGrant,
)
from .automation_lifecycle import (
    AutomationDenial,
    AutomationDenialCustody,
    AutomationDenialKind,
    AutomationDenialReceipt,
)
from .automation_password import prove_automation_administration
from .session_authority import ProfileSessionAuthority


class AutomationLifecycleCustody(EnrollmentCustodyPort, AutomationDenialCustody, Protocol):
    """The existing protected store, with its reduction-only denial capability."""


class AutomationLifecycleOwner(Protocol):
    """Trusted connection and profile owner; shared with live session authority."""

    def facts(self) -> AdministrationFacts:
        """Reobserve current connection, human authority, clocks and login provenance."""
        ...

    def administration_guard(self) -> AbstractContextManager[None]:
        """Hold the same fence as session admission and private effects."""
        ...

    def set_profile_lock(self, *, generation: int, locked: bool) -> None:
        """Publish host lock facts under the guard; never alter another profile."""
        ...


class AutomationResumeRequest(BaseModel):
    """One exact reviewed selection, bounded by the suspended control generation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    profile_id: UUID
    lock_generation: Annotated[int, Field(ge=0)]
    grants: frozenset[UUID]


class AutomationResumeReceipt(BaseModel):
    """Selected grants retain their original permissions and calendar deadlines."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    profile_id: UUID
    revision: Annotated[int, Field(ge=1)] | None
    lock_generation: Annotated[int, Field(ge=0)]
    reactivated_grants: frozenset[UUID]


def _changed[T: BaseModel](value: T, **changes: object) -> T:
    model_type = value.__class__
    return model_type.model_validate({**{name: getattr(value, name) for name in model_type.model_fields}, **changes})


def _denial_request(
    change: AutomationDenial,
    facts: AdministrationFacts,
    session_binding: object,
) -> AccessAdministrationRequest:
    if change.binding != facts.profile.binding or change.binding != session_binding:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    actions = {
        AutomationDenialKind.KEY: AccessAdministrationAction.REVOKE_KEY,
        AutomationDenialKind.GRANT: AccessAdministrationAction.REVOKE_GRANT,
        AutomationDenialKind.ALL: AccessAdministrationAction.REVOKE_ALL_AUTOMATION,
        AutomationDenialKind.PROFILE_LOCK: AccessAdministrationAction.LOCK_PROFILE,
    }
    return AccessAdministrationRequest(
        request_id=change.request_id,
        profile_id=change.binding.profile_id,
        action=actions[change.kind],
        request_digest=sha256_hex(canonical_json_bytes(change.model_dump(mode="json"))),
    )


def _deny_automation(
    *,
    custody: AutomationLifecycleCustody,
    owner: AutomationLifecycleOwner,
    sessions: ProfileSessionAuthority,
    change: AutomationDenial,
) -> AutomationDenialReceipt:
    with owner.administration_guard():
        facts = owner.facts()
        request = _denial_request(change, facts, sessions.binding)
        decision = evaluate_access_administration(
            request=request,
            session=facts.session,
            ancestors=(),
            grant=None,
            key=None,
            profile=facts.profile,
            context=facts.context,
        )
        if isinstance(decision, AccessDenied):
            raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
        if change.kind is AutomationDenialKind.PROFILE_LOCK:
            owner.set_profile_lock(generation=facts.profile.lock_generation + 1, locked=True)
        try:
            sessions.invalidate_automation(change)
        except ExceptionGroup:
            # Authority is already removed for the complete cascade. Keep
            # persisting denial even if a worker's physical cleanup failed.
            cleanup_pending = True
        else:
            cleanup_pending = False
        receipt = custody.deny(change)
        return _changed(receipt, cleanup_pending=receipt.cleanup_pending or cleanup_pending)


def _resume_request(
    selection: AutomationResumeRequest,
    facts: AdministrationFacts,
    session_binding: ProfileAccessBinding,
) -> AccessAdministrationRequest:
    if (
        selection.profile_id != facts.profile.binding.profile_id
        or facts.profile.binding != session_binding
        or selection.lock_generation != facts.profile.lock_generation
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    value = selection.model_dump(mode="json")
    value["grants"] = sorted(str(identity) for identity in selection.grants)
    return AccessAdministrationRequest(
        request_id=selection.request_id,
        profile_id=selection.profile_id,
        action=AccessAdministrationAction.RESUME_PROFILE,
        request_digest=sha256_hex(canonical_json_bytes(value)),
    )


def _require_resume_authority(
    *,
    custody: AutomationLifecycleCustody,
    selection: AutomationResumeRequest,
    request: AccessAdministrationRequest,
    current: AdministrationFacts,
    proof: FreshPasswordAuthorization,
) -> None:
    decision = evaluate_access_administration(
        request=request,
        session=current.session,
        ancestors=(),
        grant=None,
        key=None,
        profile=current.profile,
        context=current.context,
        password_proof=proof,
    )
    if isinstance(decision, AccessDenied):
        raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
    local = custody.profile_lock_state()
    if local.binding != proof.binding or local.generation != selection.lock_generation:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)


def _resume_suspended_key(key: ApiKeyRecord, *, now: datetime) -> ApiKeyRecord:
    if key.state is AuthorityState.SUSPENDED and key.valid_from <= now < key.expires_at:
        return _changed(key, state=AuthorityState.ACTIVE, generation=key.generation + 1)
    return key


def _reactivated_enrollment_grant(
    entry: EnrollmentGrant,
    *,
    now: datetime,
    lock_generation: int,
) -> EnrollmentGrant:
    grant = entry.grant
    if grant.state is not AuthorityState.SUSPENDED or not grant.valid_from <= now < grant.expires_at:
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    keys = tuple(_changed(item, key=_resume_suspended_key(item.key, now=now)) for item in entry.keys)
    if grant.unattended and not any(item.key.state is AuthorityState.ACTIVE for item in keys):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    return _changed(
        entry,
        keys=keys,
        grant=_changed(
            grant,
            state=AuthorityState.ACTIVE,
            generation=grant.generation + 1,
            profile_lock_generation=lock_generation,
        ),
    )


def _selected_enrollment_state(
    custody: AutomationLifecycleCustody,
    selection: AutomationResumeRequest,
    *,
    binding: ProfileAccessBinding,
    now: datetime,
) -> EnrollmentControlState:
    state = custody.enrollment_state()
    if state.binding != binding or state.profile_lock_generation != selection.lock_generation:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    selected = tuple(entry for entry in state.grants if entry.grant.grant_id in selection.grants)
    if len(selected) != len(selection.grants):
        raise AutomationCustodyError(AutomationCustodyCode.MISSING)
    replacements = {
        entry.grant.grant_id: _reactivated_enrollment_grant(entry, now=now, lock_generation=selection.lock_generation)
        for entry in selected
    }
    return _changed(
        state,
        automation_enabled=True,
        grants=tuple(replacements.get(entry.grant.grant_id, entry) for entry in state.grants),
    )


def _unlock_without_automation(
    custody: AutomationLifecycleCustody,
    owner: AutomationLifecycleOwner,
    selection: AutomationResumeRequest,
) -> AutomationResumeReceipt:
    # Human unlock is independent of optional automation custody. Pending denial
    # still blocks every key until reconciliation and explicit selection complete.
    custody.unlock_profile(generation=selection.lock_generation)
    owner.set_profile_lock(generation=selection.lock_generation, locked=False)
    return AutomationResumeReceipt(
        request_id=selection.request_id,
        profile_id=selection.profile_id,
        revision=None,
        lock_generation=selection.lock_generation,
        reactivated_grants=frozenset(),
    )


def _publish_selected_resume(
    *,
    custody: AutomationLifecycleCustody,
    owner: AutomationLifecycleOwner,
    selection: AutomationResumeRequest,
    state: EnrollmentControlState,
    dek: SecretBytes,
) -> AutomationResumeReceipt:
    revision = custody.publish_enrollment(state, fresh_dek=dek)
    custody.unlock_profile(generation=selection.lock_generation)
    owner.set_profile_lock(generation=selection.lock_generation, locked=False)
    return AutomationResumeReceipt(
        request_id=selection.request_id,
        profile_id=selection.profile_id,
        revision=revision,
        lock_generation=selection.lock_generation,
        reactivated_grants=selection.grants,
    )


def _finish_resume(
    *,
    custody: AutomationLifecycleCustody,
    owner: AutomationLifecycleOwner,
    selection: AutomationResumeRequest,
    request: AccessAdministrationRequest,
    proof: FreshPasswordAuthorization,
    dek: SecretBytes,
) -> AutomationResumeReceipt:
    with owner.administration_guard():
        current = owner.facts()
        _require_resume_authority(
            custody=custody,
            selection=selection,
            request=request,
            current=current,
            proof=proof,
        )
        if not selection.grants:
            return _unlock_without_automation(custody, owner, selection)
        state = _selected_enrollment_state(
            custody,
            selection,
            binding=proof.binding,
            now=current.context.now,
        )
        return _publish_selected_resume(
            custody=custody,
            owner=owner,
            selection=selection,
            state=state,
            dek=dek,
        )


class AutomationLifecycleService:
    """One exact profile; no ambient active-profile selector or frontend policy."""

    def __init__(
        self,
        *,
        custody: AutomationLifecycleCustody,
        owner: AutomationLifecycleOwner,
        sessions: ProfileSessionAuthority,
        storage_root: Path,
    ) -> None:
        """Compose one trusted authority owner and its existing protected custody."""
        self.custody, self.owner, self.sessions, self.storage_root = custody, owner, sessions, storage_root

    def deny(self, change: AutomationDenial) -> AutomationDenialReceipt:
        """Authorize a reduction, fence live leases, then persist before acknowledging."""
        return _deny_automation(custody=self.custody, owner=self.owner, sessions=self.sessions, change=change)

    def resume(self, selection: AutomationResumeRequest, *, password: SecretBytes) -> AutomationResumeReceipt:
        """Prove the password for this selection; API possession cannot unlock globally."""
        with self.owner.administration_guard():
            facts = self.owner.facts()
            request = _resume_request(selection, facts, self.sessions.binding)
        proof, dek = prove_automation_administration(
            request=request,
            facts=facts,
            password=password,
            storage_root=self.storage_root,
            deadline=facts.context.now + ACCESS_LEASE_MAXIMUM,
        )
        return _finish_resume(
            custody=self.custody,
            owner=self.owner,
            selection=selection,
            request=request,
            proof=proof,
            dek=dek,
        )
