"""Shared exact-review projection for CLI and manager censal apply."""

from __future__ import annotations

from ....application.user_profile import CensalReviewProjectionV1
from ....core.i18n import tr
from ....entrypoints.tui.components import FormChoice, FormField, FormFieldKind, FormPage
from ._manager_frontend import present_form

_DECISION_KEY = "censo-review-decision"


def confirm_censal_review(projection: CensalReviewProjectionV1) -> bool:
    """Present every exact projected value and return explicit apply intent."""
    rows = "\n".join(
        f"{field.path}: {field.observed_value or '—'} [{field.intent.value}]" for field in projection.fields
    )
    answers = present_form(
        FormPage(
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
    )
    return answers is not None and answers.get(_DECISION_KEY) == "apply"


__all__ = ["confirm_censal_review"]
