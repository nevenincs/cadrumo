"""Shared typed question construction for setup sections."""

from __future__ import annotations

from ...core.i18n.translatable import Translatable as tr
from .models import WizardCondition, WizardQuestion, WizardVisibility, WizardWidget


def confirmation_question(
    qid: str,
    profile_key: str,
    *,
    suffix: str,
    default: str | None = "false",
    required: bool = False,
    visible_when: WizardCondition | WizardVisibility | None = None,
) -> WizardQuestion:
    """Build a CONFIRM question that persists into ``profile_key``."""
    return WizardQuestion(
        id=qid,
        profile_key=profile_key,
        widget=WizardWidget.CONFIRM,
        prompt=tr(f"wizard.setup.{suffix}.{qid}.prompt"),
        default=default,
        required=required,
        visible_when=visible_when,
        answer_type=bool,
    )
