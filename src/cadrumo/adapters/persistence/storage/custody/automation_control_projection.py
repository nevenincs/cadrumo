"""Typed successor facts for witnessed automation custody publication."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, SecretBytes

from .....application.user_profile.access_contracts import (
    ProfileAccessBinding,
)
from .....application.user_profile.automation_enrollment import (
    EnrollmentGrant,
    EnrollmentRecord,
)
from .....application.user_profile.automation_lifecycle import (
    AutomationDenial,
)
from .automation_records import (
    AutomationControlPayload,
    AutomationRecordHeader,
    ControlPublicationIntent,
    ControlWitness,
    ProtectedControlAnchor,
    StoredAutomationGrant,
)


def changed_control_model[T: BaseModel](value: T, **changes: object) -> T:
    """Validate changed custody facts through the original typed model."""
    model_type = value.__class__
    return model_type.model_validate({**{name: getattr(value, name) for name in model_type.model_fields}, **changes})


def publication_payload(
    binding: ProfileAccessBinding,
    profile_lock_generation: int,
    automation_enabled: bool,
    entries: list[StoredAutomationGrant],
    requests: tuple[EnrollmentRecord, ...] | None,
    old_payload: AutomationControlPayload | None,
    denial: AutomationDenial | None,
) -> AutomationControlPayload:
    """Select explicit successor facts while retaining omitted requests and denial history."""
    return AutomationControlPayload(
        binding=binding,
        profile_lock_generation=profile_lock_generation,
        automation_enabled=automation_enabled,
        grants=tuple(entries),
        requests=requests if requests is not None else (() if old_payload is None else old_payload.requests),
        last_denial=denial if denial is not None else (None if old_payload is None else old_payload.last_denial),
    )


def publication_intent(
    previous: ProtectedControlAnchor | None,
    witness: ControlWitness,
    wraps: dict[UUID, SecretBytes],
    old_payload: AutomationControlPayload | None,
) -> ControlPublicationIntent:
    """Record exact predecessor and new or retired wrapper identities before native writes."""
    return ControlPublicationIntent(
        predecessor=None if previous is None else previous.witness,
        successor=witness,
        created_wrap_keys=tuple(wraps),
        retired_wrap_keys=()
        if old_payload is None
        else tuple(item.wrap_key_id for item in old_payload.grants if item.wrap_key_id is not None),
    )


def previous_enrollment_grant(
    previous: tuple[AutomationRecordHeader, AutomationControlPayload] | None,
    entry: EnrollmentGrant,
) -> StoredAutomationGrant | None:
    """Find only the exact grant in the already verified predecessor payload."""
    return (
        None
        if previous is None
        else next((item for item in previous[1].grants if item.grant.grant_id == entry.grant.grant_id), None)
    )
