"""Authorization, live fencing and durable denial share one lifecycle boundary."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, SecretBytes

from cadrumo.application.user_profile.access_administration import (
    AccessAdministrationAction,
    AccessAdministrationRequest,
    FreshPasswordAuthorization,
    evaluate_access_administration,
)
from cadrumo.application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessDenied,
    ApiKeyRecord,
    AuthorityState,
    ProfileAccessBinding,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import (
    AdministrationFacts,
    EnrollmentControlState,
    EnrollmentCustodyPort,
    EnrollmentGrant,
)
from cadrumo.application.user_profile.automation_lifecycle import (
    AutomationDenial,
    AutomationDenialCustody,
    AutomationDenialKind,
    AutomationDenialReceipt,
)
from cadrumo.application.user_profile.automation_password import prove_automation_administration
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo_client.contracts.automation_lifecycle import (
    AutomationResumeReceipt as _AutomationResumeReceipt,
)
from cadrumo_client.contracts.automation_lifecycle import (
    AutomationResumeRequest as _AutomationResumeRequest,
)
from cadrumo_client.contracts.automation_lifecycle import (
    HumanSignInRevocationResult as _HumanSignInRevocationResult,
)

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

    def revoke_human_sign_in(self) -> _HumanSignInRevocationResult:
        """Fence saved human proof and retire human/attended sessions before recovery."""
        ...

    def set_profile_lock(self, *, generation: int, locked: bool) -> None:
        """Publish host lock facts under the guard; never alter another profile."""
        ...


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
    selection: _AutomationResumeRequest,
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
    selection: _AutomationResumeRequest,
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
    if (
        grant.state not in {AuthorityState.SUSPENDED, AuthorityState.ACTIVE}
        or not grant.valid_from <= now < grant.expires_at
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    # Enrollment publication and unlock are separate durable writes. Retry may
    # observe already-published grants for this exact lock generation. Preserve
    # their authority; fresh password and current generation were checked first.
    if grant.state is AuthorityState.ACTIVE and grant.profile_lock_generation != lock_generation:
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    keys = (
        entry.keys
        if grant.state is AuthorityState.ACTIVE
        else tuple(_changed(item, key=_resume_suspended_key(item.key, now=now)) for item in entry.keys)
    )
    if grant.unattended and not any(
        item.key.state is AuthorityState.ACTIVE and item.key.valid_from <= now < item.key.expires_at for item in keys
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    if grant.state is AuthorityState.ACTIVE:
        return entry
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
    selection: _AutomationResumeRequest,
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
    selection: _AutomationResumeRequest,
) -> _AutomationResumeReceipt:
    # Human unlock is independent of optional automation custody. Pending denial
    # still blocks every key until reconciliation and explicit selection complete.
    custody.unlock_profile(generation=selection.lock_generation)
    owner.set_profile_lock(generation=selection.lock_generation, locked=False)
    return _AutomationResumeReceipt(
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
    selection: _AutomationResumeRequest,
    state: EnrollmentControlState,
    dek: SecretBytes,
) -> _AutomationResumeReceipt:
    revision = custody.publish_enrollment(state, fresh_dek=dek)
    custody.unlock_profile(generation=selection.lock_generation)
    owner.set_profile_lock(generation=selection.lock_generation, locked=False)
    return _AutomationResumeReceipt(
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
    selection: _AutomationResumeRequest,
    request: AccessAdministrationRequest,
    proof: FreshPasswordAuthorization,
    dek: SecretBytes,
) -> _AutomationResumeReceipt:
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
            revocation = owner.revoke_human_sign_in()
            return _changed(_unlock_without_automation(custody, owner, selection), human_sign_in_revocation=revocation)
        state = _selected_enrollment_state(
            custody,
            selection,
            binding=proof.binding,
            now=current.context.now,
        )
        # Validate the requested grants before revoking any human sign-in.
        # Publication follows the durable fence under this same admission guard.
        revocation = owner.revoke_human_sign_in()
        result = _publish_selected_resume(
            custody=custody,
            owner=owner,
            selection=selection,
            state=state,
            dek=dek,
        )
        return _changed(result, human_sign_in_revocation=revocation)


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

    def resume(self, selection: _AutomationResumeRequest, *, password: SecretBytes) -> _AutomationResumeReceipt:
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
