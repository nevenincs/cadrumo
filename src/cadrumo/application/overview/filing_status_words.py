"""The words a calendar row serves for its one decided filing status.

Each :class:`~cadrumo.application.overview.calendar_models.OverviewFilingStatus`
has one locale key here, so every frontend shows the status in the operator's
language instead of wording a filing claim of its own. A local record is never
worded as an AEAT submission.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from .calendar_models import OverviewFilingStatus

__all__ = ["filing_status_words"]

_FILING_STATUS_LOCALE_KEYS: Final[Mapping[OverviewFilingStatus, str]] = MappingProxyType(
    {
        OverviewFilingStatus.RECEIPT_VERIFIED: "overview.filing_status.receipt_verified",
        OverviewFilingStatus.ACCEPTED: "overview.filing_status.accepted",
        OverviewFilingStatus.SUBMITTED: "overview.filing_status.submitted",
        OverviewFilingStatus.IMPORTED: "overview.filing_status.imported",
        OverviewFilingStatus.RECORDED_LOCALLY: "overview.filing_status.recorded_locally",
        OverviewFilingStatus.EVIDENCE_WITHHELD: "overview.filing_status.evidence_withheld",
        OverviewFilingStatus.DUE: "overview.filing_status.due",
        OverviewFilingStatus.OVERDUE: "overview.filing_status.overdue",
        OverviewFilingStatus.UNKNOWN: "overview.filing_status.unknown",
    }
)


def filing_status_words(status: OverviewFilingStatus, language: OutputLanguage) -> str:
    """Return the words of ``status`` in ``language``."""
    return tr(_FILING_STATUS_LOCALE_KEYS[status], locale=language.value)
