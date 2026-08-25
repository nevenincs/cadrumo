"""Canonical active-profile projection, mutation, and value-refusal service."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from ...core import require_active_bucket_id
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.user_profile import (
    NUMERIC_PROFILE_FIELD_TYPES,
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileValueRefusalKind,
    UserProfileFact,
    UserProfileNotFoundError,
    UserProfileRecord,
    load_user_profile_schema,
    profile_value_refusal,
    section_field_key,
)
from ..wizard import profile_next_step_modelo
from ._fact_write import apply_manager_profile_field_mutation
from ._overview import ProfileOverview, build_profile_overview
from ._profile_record_repository import ProfileRecordRepository
from ._profile_repository import CommittedProfileRepository
from ._projections import record_to_path_values
from .status_projection import build_active_profile_notices


def _profile_next_action_notice(record: UserProfileRecord) -> Notice | None:
    modelo = profile_next_step_modelo(record_to_path_values(record))
    if modelo is None:
        return None
    return Notice(
        severity=NoticeSeverity.INFO,
        code="config.profile.manager.next_step_modelo",
        message=tr(
            "flows.manager.next_step_modelo",
            default="This profile's declared facts route it to Modelo {modelo}.",
            modelo=modelo,
        ),
        context={"modelo": modelo},
    )


def _manager_notices(record: UserProfileRecord) -> tuple[Notice, ...]:
    notices = list(build_active_profile_notices(record))
    next_action = _profile_next_action_notice(record)
    if next_action is not None:
        notices.append(next_action)
    return tuple(notices)


@dataclass(frozen=True, slots=True)
class ActiveProfileManagerProjection:
    """One active-profile session's canonical projection and mutation boundary."""

    profile_id: str
    label: str
    profiles: ProfileRecordRepository

    def _project(self, record: UserProfileRecord) -> ProfileOverview:
        overview = build_profile_overview(record, label=self.label, schema=load_user_profile_schema())
        return overview.model_copy(update={"notices": _manager_notices(record)})

    def inspect(self) -> ProfileOverview:
        """Project the current persisted profile without frontend-owned policy."""
        return self._project(self.profiles.load(self.profile_id))

    def replace_field(self, path: str, value: str) -> ProfileOverview:
        """Apply one canonical manager mutation and project its committed record."""
        record = apply_manager_profile_field_mutation(profile_id=self.profile_id, path=path, value=value)
        return self._project(record)


def open_active_profile_manager_projection(*, label: str | None = None) -> ActiveProfileManagerProjection:
    """Bind projection reads and writes to the exact active profile session."""
    profile_id = require_active_bucket_id()
    resolved_label = label if label is not None else CommittedProfileRepository().load(profile_id).label
    return ActiveProfileManagerProjection(
        profile_id=profile_id,
        label=resolved_label,
        profiles=ProfileRecordRepository.for_current_session(profile_id),
    )


def build_active_profile_manager_overview(*, label: str | None = None) -> ProfileOverview:
    """Project the exact active profile for a stateless consumer."""
    return open_active_profile_manager_projection(label=label).inspect()


def persist_active_profile_manager_field(
    path: str,
    value: str,
    *,
    label: str | None = None,
) -> ProfileOverview:
    """Apply and project one active-profile field mutation."""
    return open_active_profile_manager_projection(label=label).replace_field(path, value)


def _accepted_clause(field: ProfileFieldDefinition) -> str:
    if field.type is ProfileFieldType.ENUM:
        return ", ".join(field.enum_values)
    if field.type not in NUMERIC_PROFILE_FIELD_TYPES:
        return ""
    minimum, maximum = field.minimum, field.maximum
    if minimum is not None and maximum is not None:
        return f" ({minimum} - {maximum})"
    if minimum is not None:
        return f" (>= {minimum})"
    if maximum is not None:
        return f" (<= {maximum})"
    return ""


def _refusal_sentence(kind: ProfileValueRefusalKind, *, value: str, accepted: str) -> str:
    match kind:
        case ProfileValueRefusalKind.ENUM:
            return tr("flows.manager.edit.refused.enum", value=value, accepted=accepted)
        case ProfileValueRefusalKind.DATE:
            return tr("flows.manager.edit.refused.date", value=value)
        case ProfileValueRefusalKind.NUMERIC:
            return tr("flows.manager.edit.refused.numeric", value=value, accepted=accepted)
        case ProfileValueRefusalKind.BOOLEAN:
            return tr("flows.manager.edit.refused.boolean", value=value)
        case ProfileValueRefusalKind.EMAIL:
            return tr("flows.manager.edit.refused.email", value=value)


def profile_manager_field_value_refusal(path: str, value: str) -> str | None:
    """Return the canonical localized refusal for one proposed field value."""
    stripped = value.strip()
    if not stripped:
        return None
    try:
        declared = load_user_profile_schema().field(section_field_key(path))
        coerced = UserProfileFact(path=path, value=stripped).value
    except (UserProfileNotFoundError, ValidationError):
        return None
    refusal = profile_value_refusal(declared, coerced)
    if refusal is None:
        return None
    return _refusal_sentence(refusal.kind, value=stripped, accepted=_accepted_clause(declared))


__all__ = [
    "ActiveProfileManagerProjection",
    "build_active_profile_manager_overview",
    "open_active_profile_manager_projection",
    "persist_active_profile_manager_field",
    "profile_manager_field_value_refusal",
]
