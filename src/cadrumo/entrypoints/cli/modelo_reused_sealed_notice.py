"""The notice a command shows when its inputs reproduced a checked or filed calculation.

A calculation is content addressed, so inputs equal to a sealed revision's yield
that revision rather than a new draft; the sealed revision stays as it is and
the declaration's current calculation is left where it was.
"""

from __future__ import annotations

from ...application.modelo.edit_apply_contracts import ModeloEditApplyPublicResultV1
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from .modelo_revision_rendering import calculation_revision_state_label


def reused_sealed_revision_message(revision_id: str, state: str) -> str:
    """The operator's words for a reproduced sealed calculation and its state."""
    return tr(
        "cli.app.modelo.work.calculate_reused_sealed",
        revision_id=revision_id,
        state=calculation_revision_state_label(state),
    )


def reused_sealed_revision_notice(
    *,
    command: str,
    revision_id: str,
    state: str,
    current_revision_id: str | None,
    context: dict[str, str] | None = None,
) -> Notice:
    """The typed notice naming the reproduced sealed calculation and the one that stays current."""
    return Notice(
        severity=NoticeSeverity.INFO,
        code=f"{command}.reused_sealed_revision",
        message=reused_sealed_revision_message(revision_id, state),
        context={
            "calculation_revision_id": revision_id,
            **({"current_calculation_revision_id": current_revision_id} if current_revision_id is not None else {}),
            **(context or {}),
        },
    )


def applied_edit_notices(command: str, applied: ModeloEditApplyPublicResultV1 | None) -> list[Notice]:
    """The notice an applied edit owes when it reproduced a sealed calculation, else none."""
    reused = None if applied is None else applied.reused_sealed_revision
    if reused is None:
        return []
    return [
        reused_sealed_revision_notice(
            command=command,
            revision_id=reused.calculation_revision_id,
            state=reused.state.value,
            current_revision_id=reused.current_calculation_revision_id,
            context={"state": reused.state.value},
        )
    ]


__all__ = ["applied_edit_notices", "reused_sealed_revision_message", "reused_sealed_revision_notice"]
