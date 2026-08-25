"""Shared exact-review projection for CLI and manager censal apply."""

from __future__ import annotations

from collections.abc import Mapping

from ....application.user_profile import CensalReviewProjectionV1
from ....core.i18n import tr
from ....entrypoints.tui.components.forms import FormChoice, FormField, FormFieldKind, FormPage
from ._manager_frontend import present_form

_DECISION_KEY = "censo-review-decision"


def confirm_censal_review(projection: CensalReviewProjectionV1) -> bool:
    """Present every exact projected value and return explicit apply intent."""
    return censal_review_decision(present_form(build_censal_review_page(projection)))


def build_censal_review_page(projection: CensalReviewProjectionV1) -> FormPage:
    """Build the one immutable page containing every exact reviewed value."""
    rows = "\n".join(
        f"{field.path}: {field.observed_value or '—'} [{field.intent.value}]" for field in projection.fields
    )
    return FormPage(
        title=tr("flows.manager.censal_review.title"),
        section=rows,
        fields=(
            FormField(
                key=_DECISION_KEY,
                label=tr("flows.manager.censal_review.decision"),
                kind=FormFieldKind.SINGLE_CHOICE,
                choices=(
                    FormChoice("apply", tr("flows.manager.censal_review.apply")),
                    FormChoice("reject", tr("flows.manager.censal_review.reject")),
                ),
                validate=lambda value: (
                    None if value in {"apply", "reject"} else tr("flows.manager.censal_review.required")
                ),
            ),
        ),
    )


def censal_review_decision(answers: object) -> bool:
    """Return apply only for the exact committed choice mapping."""
    if not isinstance(answers, Mapping):
        return False
    decision: object = answers.get(_DECISION_KEY)
    return decision == "apply"


__all__ = ["build_censal_review_page", "censal_review_decision", "confirm_censal_review"]
