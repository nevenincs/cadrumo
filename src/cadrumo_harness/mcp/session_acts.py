"""Session acts of one profile, as the command line has them.

The acts a held session takes are its inventory, locks, automation denial and
the person's sign-out. The others need no held session: signing in, reading
the sign-in's status, resuming a locked profile, resetting or changing the
password, and deleting a profile. Every secret one of them takes arrives as a
mutable buffer and leaves on the runtime's protected secret frame.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.bucket_deletion_contracts import BucketDeletionFingerprint
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind

from .protocol_contract import public_value
from .runtime_admission import McpAdmission

NO_SESSION = "none"
"""What a reply's ``session`` says when the connection holds no session."""

SECRET_FIELDS: Final = ("secret", "new_secret", "new_secret_confirmation")
"""The write-only tool fields; each one's text travels only as a wiped buffer."""

UNADMITTED_SESSION_ACTIONS: Final = frozenset(
    {"sign_in", "sign_in_status", "resume", "reset_password", "change_password", "delete_profile"}
)
"""The acts that open their own connection instead of using the held session."""


class SessionActRefusedError(Exception):
    """A refusal with a stable code and the public facts the command line reports with it."""

    def __init__(self, code: str, **facts: object) -> None:
        """Keep only the code and nonsecret facts."""
        super().__init__(code)
        self.code, self.facts = code, facts

    def reply(self) -> dict[str, Any]:
        """Return the refusal as a tool reply."""
        return {"outcome": "refused", "code": self.code, **self.facts}


class SessionSecrets:
    """The secret texts of one call, taken out of its arguments as mutable buffers."""

    def __init__(self, args: dict[str, Any]) -> None:
        """Remove every secret field from the call, so nothing later can repeat its text."""
        self._buffers: dict[str, bytearray] = {}
        for name in SECRET_FIELDS:
            if name in args:
                self._buffers[name] = bytearray(args.pop(name), "utf-8")

    def require(self, action: str, *names: str) -> tuple[bytearray, ...]:
        """Return exactly the buffers the act takes, refusing a missing, empty or extra one."""
        if set(self._buffers) != set(names) or not all(self._buffers[name] for name in names):
            expected = ", ".join(names) if names else "no secret field"
            raise ValueError(f"{action} takes {expected}")
        return tuple(self._buffers[name] for name in names)

    def wipe(self) -> None:
        """Overwrite every buffer, whatever became of the call."""
        for buffer in self._buffers.values():
            buffer[:] = bytes(len(buffer))


def require_only(args: dict[str, Any], action: str, *allowed: str) -> None:
    """Refuse a field that the chosen act does not take."""
    if set(args) - {"action", *allowed}:
        raise ValueError(f"{action} takes no such field")


def act_on_sessions(client: RuntimeFrontendClient, admission: McpAdmission, args: dict[str, Any]) -> dict[str, Any]:
    """Ask the runtime for one act of the held session; it alone decides whether the session may take it.

    Each reply says in ``session`` how the connection's own session stands
    afterwards, so the adapter drops a lease the act ended.
    """
    action = args["action"]
    if action == "list":
        require_only(args, action)
        sessions = sorted(client.sessions(), key=lambda item: item.session_id)
        return {
            "outcome": "sessions",
            "session": admission.value,
            "sessions": [public_value(item) for item in sessions],
        }
    if action == "lock":
        return _lock(client, admission, args)
    if action == "deny_automation":
        return _deny_automation(client, admission, args)
    if action != "sign_out":
        raise ValueError("unsupported session act")
    require_only(args, action)
    signed_out = client.human_sign_out()
    return {
        "outcome": "signed_out",
        "session": NO_SESSION,
        "session_ids": [str(item) for item in signed_out.session_ids],
        "receipt_removed": signed_out.receipt_removed,
        "keychain_removed": signed_out.keychain_removed,
        "automation_enabled": signed_out.automation_enabled,
    }


def _lock(client: RuntimeFrontendClient, admission: McpAdmission, args: dict[str, Any]) -> dict[str, Any]:
    require_only(args, "lock", "target_session_id")
    own = client.session_id
    target = UUID(args["target_session_id"]) if "target_session_id" in args else own
    locked = client.lock() if target == own else client.revoke_session(target)
    return {
        "outcome": "locked",
        "session": NO_SESSION if own in locked.session_ids else admission.value,
        "target_session_id": str(target),
        "session_ids": [str(item) for item in locked.session_ids],
    }


def _deny_automation(client: RuntimeFrontendClient, admission: McpAdmission, args: dict[str, Any]) -> dict[str, Any]:
    require_only(args, "deny_automation", "kind", "target_id")
    kind = AutomationDenialKind(args["kind"])
    targeted = kind in {AutomationDenialKind.KEY, AutomationDenialKind.GRANT}
    if targeted != ("target_id" in args):
        raise ValueError("target_id names the key or the grant to deny, and nothing else takes one")
    target_id = UUID(args["target_id"]) if targeted else None
    receipt = client.deny_automation(kind, target_id=target_id)
    return {
        "outcome": "denied",
        # Locking the profile ends every session of it, this one included.
        "session": NO_SESSION if kind is AutomationDenialKind.PROFILE_LOCK else admission.value,
        "kind": kind.value,
        "target_id": None if target_id is None else str(target_id),
        "receipt": public_value(receipt),
    }


def resolve_named_profile(name: str) -> UUID:
    """Resolve a profile named as ``config login NAME`` names it, by its identifier or exact label."""
    from cadrumo.application.user_profile.login_session import resolve_login_target
    from cadrumo.domain.user_profile.errors import ProfileNotFoundError

    try:
        return UUID(resolve_login_target(name).bucket_id)
    except ProfileNotFoundError:
        raise SessionActRefusedError("unknown_profile") from None


def select_signed_in_profile(profile_id: UUID) -> None:
    """Make the profile just signed in to the installation's selection, as ``config login`` does."""
    from cadrumo.application.user_profile.profile_pointer import (
        active_profile_pointer_transaction,
        observe_active_profile_pointer,
    )

    captured = observe_active_profile_pointer()
    if captured.bucket_id == str(profile_id):
        return
    with active_profile_pointer_transaction() as selection:
        selection.compare_and_select(expected=captured, bucket_id=str(profile_id))


def read_sign_in_status(client: RuntimeFrontendClient) -> dict[str, Any]:
    """Observe the stored sign-in without presenting its proof or extending it."""
    return {
        "outcome": "sign_in_status",
        "profile_id": str(client.profile_id),
        "status": public_value(client.sign_in_status().status),
    }


def resume_profile(client: RuntimeFrontendClient, password: bytearray, grants: frozenset[UUID]) -> dict[str, Any]:
    """Unlock a locked profile with its password and reactivate only the grants named."""
    receipt = client.recover_profile(password, grants=grants)
    revocation = receipt.human_sign_in_revocation
    return {
        "outcome": "resumed",
        "profile_id": str(receipt.profile_id),
        "lock_generation": receipt.lock_generation,
        "reactivated_grants": sorted(str(item) for item in receipt.reactivated_grants),
        "receipt_removed": None if revocation is None else revocation.receipt_removed,
        "keychain_removed": None if revocation is None else revocation.keychain_removed,
    }


def reset_password(
    client: RuntimeFrontendClient, recovery_code: bytearray, replacement: bytearray, confirmation: bytearray
) -> dict[str, Any]:
    """Replace a forgotten password by proving the profile's recovery code."""
    from cadrumo.application.user_profile.login_session import ProfileLoginThrottledError
    from cadrumo.application.user_profile.recovery_custody import ProfileRecoveryError

    try:
        completion = client.reset_password(
            recovery_code=recovery_code, new_passphrase=replacement, new_passphrase_confirmation=confirmation
        )
    except ProfileLoginThrottledError as throttled:
        wait = (throttled.context or {}).get("seconds", "0")
        raise SessionActRefusedError("throttled", remaining_seconds=int(str(wait))) from None
    except ProfileRecoveryError as refused:
        password_refusal = refused.password_refusal
        if password_refusal is not None:
            raise SessionActRefusedError("invalid_password", reason=password_refusal.reason.value) from None
        key = refused.translated_message or ""
        raise SessionActRefusedError(key.rpartition(".")[2] or "recovery_refused") from None
    outcome = completion.outcome
    return {
        "outcome": "password_reset",
        "profile_id": str(outcome.profile_id),
        "password_generation": outcome.password_generation,
        "dek_epoch_preserved": outcome.dek_epoch_preserved,
        "recovery_enrollment_retained": outcome.recovery_enrollment_retained,
        "receipt_removed": completion.human_sign_in_revocation.receipt_removed,
        "keychain_removed": completion.human_sign_in_revocation.keychain_removed,
    }


def change_password(
    client: RuntimeFrontendClient,
    current: bytearray,
    replacement: bytearray,
    confirmation: bytearray,
    *,
    fresh_client: Callable[[], RuntimeFrontendClient],
) -> dict[str, Any]:
    """Rotate the password on a connection just proven with the current one.

    Once the rotation is submitted its outcome is the runtime's: a failure
    after that point keeps the operation's identity and claims neither success
    nor rollback.
    """
    from cadrumo.adapters.local_runtime.profile_mutations import ProfileMutationRunError
    from cadrumo.adapters.local_runtime.profile_password_rotation import run_profile_password_rotation

    proof = bytearray(current)
    try:
        client.login_password(proof)
    finally:
        proof[:] = bytes(len(proof))
    try:
        completion = run_profile_password_rotation(
            client,
            current_passphrase=current,
            new_passphrase=replacement,
            new_passphrase_confirmation=confirmation,
            fresh_client=fresh_client,
        )
    except ProfileMutationRunError as failed:
        return {"outcome": "unresolved", "code": failed.reason, "operation_id": failed.operation_id}
    outcome = completion.outcome
    return {
        "outcome": "password_changed",
        "operation_id": completion.operation_id,
        "profile_id": str(outcome.profile_id),
        "password_generation": outcome.password_generation,
        "dek_epoch_preserved": outcome.dek_epoch_preserved,
        "recovery_enrollment_retained": outcome.recovery_enrollment_retained,
    }


@dataclass(frozen=True, slots=True)
class ProfileDeletionPreflight:
    """What deleting one named profile would destroy, observed without unlocking it."""

    profile_id: UUID
    reply: dict[str, Any]
    fingerprint: BucketDeletionFingerprint | None


def assess_profile_deletion(name: str) -> ProfileDeletionPreflight:
    """Observe a named profile for deletion under the rules ``config profile delete`` applies.

    The selected profile is refused, and so is a profile whose filed records
    are still inside the legal retention floor; the maintenance authority and
    the retention rule are the ones the command line asks.
    """
    from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
    from cadrumo.application.bucket_maintenance.contracts import AssessBucketDeletionCommand
    from cadrumo.application.bucket_maintenance.service import BucketMaintenanceService
    from cadrumo.application.workflow.errors import ProfileLabelAmbiguousError
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket
    from cadrumo.core.bucket_pointer import resolve_active_bucket_id
    from cadrumo.domain.retention.floor import erase_is_blocked

    try:
        pointer = read_profile_bucket(name)
    except ProfileLabelAmbiguousError:
        raise SessionActRefusedError("profile_label_ambiguous") from None
    except ValueError:
        raise SessionActRefusedError("unknown_profile") from None
    if pointer is None:
        raise SessionActRefusedError("unknown_profile")
    if resolve_active_bucket_id() == pointer.bucket_id:
        raise SessionActRefusedError("profile_selected", profile_id=pointer.bucket_id)
    assessment = BucketMaintenanceService(bucket_storage=build_profile_custody_port().bucket_storage()).assess_deletion(
        AssessBucketDeletionCommand(bucket_id=pointer.bucket_id)
    )
    if not assessment.exists:
        raise SessionActRefusedError("unknown_profile")
    retention, fingerprint = assessment.retention, assessment.fingerprint
    safe_from = None if retention is None else retention.latest_safe_erase_date
    facts: dict[str, Any] = {
        "profile_id": pointer.bucket_id,
        "display_name": pointer.label,
        "fingerprint": None if fingerprint is None else public_value(fingerprint),
        "retained_record_count": 0 if retention is None else len(retention.retained),
        "earliest_safe_erase_date": None if safe_from is None else safe_from.date().isoformat(),
    }
    if retention is not None and erase_is_blocked(blocks_erase=retention.blocks_erase):
        raise SessionActRefusedError("retention_floor", **facts)
    return ProfileDeletionPreflight(UUID(pointer.bucket_id), facts, fingerprint)


def delete_assessed_profile(client: RuntimeFrontendClient, preflight: ProfileDeletionPreflight) -> dict[str, Any]:
    """Destroy the assessed profile through the runtime's deletion transaction."""
    if preflight.fingerprint is None:
        raise SessionActRefusedError("custody_changed")
    completed = client.delete_profile(preflight.fingerprint)
    return {
        "outcome": "profile_deleted",
        "deleted": True,
        **preflight.reply,
        "completed_at": completed.receipt.completed_at.isoformat(),
    }
