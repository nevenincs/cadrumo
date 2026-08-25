"""Frontend-neutral profile presentation helpers."""

from __future__ import annotations

from ...core.i18n import tr
from ...core.json_contract import Notice, ResolvedNoticeAction
from ...core.presentation import NoticePresentation
from ...domain.user_profile.schema import ProfileFieldType


def profile_field_shape_hint(field_type: ProfileFieldType) -> str:
    """Return the localized accepted-shape hint for a typed profile field."""
    match field_type:
        case ProfileFieldType.DATE:
            return tr("flows.manager.edit.shape.date")
        case ProfileFieldType.EMAIL:
            return tr("flows.manager.edit.shape.email")
        case ProfileFieldType.INTEGER:
            return tr("flows.manager.edit.shape.integer")
        case ProfileFieldType.DECIMAL:
            return tr("flows.manager.edit.shape.decimal")
        case ProfileFieldType.MONEY:
            return tr("flows.manager.edit.shape.money")
        case _:
            return ""


def notice_presentation(notice: Notice) -> NoticePresentation:
    """Project one resolved notice into the inert cross-entrypoint shape."""
    action = notice.action
    action_target = None
    if isinstance(action, ResolvedNoticeAction) and action.action.cli_path is not None and not action.argument_bindings:
        action_target = "aeat " + " ".join(action.action.cli_path)
    return NoticePresentation(
        severity=notice.severity.value,
        message=notice.message,
        action_target=action_target,
    )


__all__ = ["notice_presentation", "profile_field_shape_hint"]
