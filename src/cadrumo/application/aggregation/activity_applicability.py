"""Whether the activity ledgers apply to a filer, read from the typed profile alone.

The rendimientos de actividades economicas (LIRPF arts. 27 and 30) are earned by
a filer who carries on an activity. A profile that declares its income
categories without one states that no activity ledger applies: its income,
expense and inventory sources are not-applicable rather than missing. Only that
typed declaration counts; undeclared categories, or no profile at all, are
unknown, and the activity sources then report their gaps as before.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from pydantic import ValidationError

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.applicability import derive_taxpayer_files_economic_activity
from ...domain.calculations.registry.ids import BindingId
from ...domain.deadlines.errors import ProfileError
from ...domain.user_profile.errors import UserProfileValidationError
from . import shared_issue_reasons
from .source_mesh import CalculationSourceContext

NOT_ACTIVITY_ROW_REASONS: Final[frozenset[str]] = frozenset(
    {
        shared_issue_reasons.UNSUPPORTED_DIRECTION,
        shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE,
        shared_issue_reasons.PERSONAL_TRANSACTION,
    }
)
"""Row rejections that say only that a ledger row is not an activity row, which says nothing to a filer without one."""


def profile_declares_no_activity_income(context: CalculationSourceContext) -> bool:
    """Whether the filer's profile declares income categories that exclude an economic activity.

    A profile whose taxpayer facts do not project states nothing typed, so it
    is unknown and its activity sources keep reporting their gaps.
    """
    if context.profile is None:
        return False
    from ..user_profile.projections import projection_for_taxpayer

    try:
        taxpayer = projection_for_taxpayer(context.profile.record, schema=context.profile.profile_decode_context.schema)
    except (ProfileError, UserProfileValidationError, ValidationError):
        return False
    return derive_taxpayer_files_economic_activity(taxpayer) is False


@dataclass(frozen=True, slots=True)
class ActivityLedgerApplicability:
    """What an activity-ledger resolver drops and settles for a filer the profile places outside its source."""

    not_activity_row_reasons: frozenset[str]
    """Row rejections that are not findings for this filer."""
    inapplicable_binding_ids: tuple[BindingId, ...]
    """The resolver's bindings that do not apply to this filer."""


def activity_ledger_applicability(
    context: CalculationSourceContext, owned_sources: Iterable[BindingSourceKind]
) -> ActivityLedgerApplicability:
    """Read the applicability of the bindings on ``owned_sources`` for ``context``'s filer.

    A filer the profile states has no activity gets the not-activity row
    rejections and every binding on those sources; any other filer gets none,
    so its rows and gaps are reported exactly as before.
    """
    if not profile_declares_no_activity_income(context):
        return ActivityLedgerApplicability(not_activity_row_reasons=frozenset(), inapplicable_binding_ids=())
    sources = frozenset(owned_sources)
    return ActivityLedgerApplicability(
        not_activity_row_reasons=NOT_ACTIVITY_ROW_REASONS,
        inapplicable_binding_ids=tuple(
            sorted({binding.id for binding in context.revision.bindings if binding.source in sources})
        ),
    )


__all__ = [
    "NOT_ACTIVITY_ROW_REASONS",
    "ActivityLedgerApplicability",
    "activity_ledger_applicability",
    "profile_declares_no_activity_income",
]
