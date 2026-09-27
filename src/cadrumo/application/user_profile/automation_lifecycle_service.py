"""Authorization, live fencing and durable denial share one lifecycle boundary."""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Annotated, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, SecretBytes

from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .access_administration import (
    AccessAdministrationAction,
    AccessAdministrationRequest,
    evaluate_access_administration,
)
from .access_contracts import ACCESS_LEASE_MAXIMUM, AccessDenied, AuthorityState
from .automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .automation_enrollment import AdministrationFacts, EnrollmentCustodyPort, EnrollmentGrant
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
        actions = {
            AutomationDenialKind.KEY: AccessAdministrationAction.REVOKE_KEY,
            AutomationDenialKind.GRANT: AccessAdministrationAction.REVOKE_GRANT,
            AutomationDenialKind.ALL: AccessAdministrationAction.REVOKE_ALL_AUTOMATION,
            AutomationDenialKind.PROFILE_LOCK: AccessAdministrationAction.LOCK_PROFILE,
        }
        with self.owner.administration_guard():
            facts = self.owner.facts()
            if change.binding != facts.profile.binding or change.binding != self.sessions.binding:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            request = AccessAdministrationRequest(
                request_id=change.request_id,
                profile_id=change.binding.profile_id,
                action=actions[change.kind],
                request_digest=sha256_hex(canonical_json_bytes(change.model_dump(mode="json"))),
            )
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
                self.owner.set_profile_lock(generation=facts.profile.lock_generation + 1, locked=True)
            cleanup_pending = False
            try:
                self.sessions.invalidate_automation(change)
            except ExceptionGroup:
                # Authority is already removed for the complete cascade. Keep
                # persisting denial even if a worker's physical cleanup failed.
                cleanup_pending = True
            receipt = self.custody.deny(change)
            return _changed(receipt, cleanup_pending=receipt.cleanup_pending or cleanup_pending)

    def resume(self, selection: AutomationResumeRequest, *, password: SecretBytes) -> AutomationResumeReceipt:
        """Prove the password for this selection; API possession cannot unlock globally."""
        with self.owner.administration_guard():
            facts = self.owner.facts()
            if (
                selection.profile_id != facts.profile.binding.profile_id
                or facts.profile.binding != self.sessions.binding
                or selection.lock_generation != facts.profile.lock_generation
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            value = selection.model_dump(mode="json")
            value["grants"] = sorted(str(identity) for identity in selection.grants)
            request = AccessAdministrationRequest(
                request_id=selection.request_id,
                profile_id=selection.profile_id,
                action=AccessAdministrationAction.RESUME_PROFILE,
                request_digest=sha256_hex(canonical_json_bytes(value)),
            )
        proof, dek = prove_automation_administration(
            request=request,
            facts=facts,
            password=password,
            storage_root=self.storage_root,
            deadline=facts.context.now + ACCESS_LEASE_MAXIMUM,
        )
        with self.owner.administration_guard():
            current = self.owner.facts()
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
            local = self.custody.profile_lock_state()
            if local.binding != proof.binding or local.generation != selection.lock_generation:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            if not selection.grants:
                # Human unlock is independent of optional automation custody.
                # Pending denial still blocks every key until reconciliation and
                # explicit password-authorized grant selection complete.
                self.custody.unlock_profile(generation=selection.lock_generation)
                self.owner.set_profile_lock(generation=selection.lock_generation, locked=False)
                return AutomationResumeReceipt(
                    request_id=selection.request_id,
                    profile_id=selection.profile_id,
                    revision=None,
                    lock_generation=selection.lock_generation,
                    reactivated_grants=frozenset(),
                )
            state = self.custody.enrollment_state()
            if state.binding != proof.binding or state.profile_lock_generation != selection.lock_generation:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            selected = tuple(entry for entry in state.grants if entry.grant.grant_id in selection.grants)
            if len(selected) != len(selection.grants):
                raise AutomationCustodyError(AutomationCustodyCode.MISSING)
            replacements: dict[UUID, EnrollmentGrant] = {}
            for entry in selected:
                grant = entry.grant
                if (
                    grant.state is not AuthorityState.SUSPENDED
                    or not grant.valid_from <= current.context.now < grant.expires_at
                ):
                    raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
                keys = tuple(
                    _changed(
                        item, key=_changed(item.key, state=AuthorityState.ACTIVE, generation=item.key.generation + 1)
                    )
                    if item.key.state is AuthorityState.SUSPENDED
                    and item.key.valid_from <= current.context.now < item.key.expires_at
                    else item
                    for item in entry.keys
                )
                if grant.unattended and not any(item.key.state is AuthorityState.ACTIVE for item in keys):
                    raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
                replacements[grant.grant_id] = _changed(
                    entry,
                    keys=keys,
                    grant=_changed(
                        grant,
                        state=AuthorityState.ACTIVE,
                        generation=grant.generation + 1,
                        profile_lock_generation=selection.lock_generation,
                    ),
                )
            successor = _changed(
                state,
                automation_enabled=True,
                grants=tuple(replacements.get(entry.grant.grant_id, entry) for entry in state.grants),
            )
            revision = self.custody.publish_enrollment(successor, fresh_dek=dek)
            self.custody.unlock_profile(generation=selection.lock_generation)
            self.owner.set_profile_lock(generation=selection.lock_generation, locked=False)
            return AutomationResumeReceipt(
                request_id=selection.request_id,
                profile_id=selection.profile_id,
                revision=revision,
                lock_generation=selection.lock_generation,
                reactivated_grants=selection.grants,
            )
