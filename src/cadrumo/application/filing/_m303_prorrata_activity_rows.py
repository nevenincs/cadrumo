"""Modelo 303 per-activity prorrata completeness gate.

The five DP30305 activity rows are canonical children of the encrypted
``ProrrataRegister``.  This module deliberately does not build a second filing
payload, calculate a global prorrata percentage, or own the revision-specific
box geometry.  It only turns the register's typed applicability decision into
the export refusal required before a target file can exist.
"""

from __future__ import annotations

from ...core import Modelo, Period
from ...domain.filing import FilingExportError
from ...domain.prorrata_register import ProrrataRegister


def assert_m303_prorrata_activity_rows_complete(
    *,
    period: Period,
    register: ProrrataRegister,
) -> None:
    """Refuse an applicable Modelo 303 export without all five activity rows.

    An absent row is honest only when the recorded register regime says that
    prorrata does not apply for the filing year.  When it does apply, a partial
    row collection must fail before the withdrawn-layout check or any target
    file write can mask the under-declaration.
    """
    if not register.requires_activity_rows_for(period.filing_year):
        return
    if not register.activity_rows_complete_for(period.filing_year):
        raise FilingExportError(
            translated_message="application.filing.m303_prorrata_activity_rows.errors.activity_rows_incomplete",
            context={
                "modelo": Modelo.M303.value,
                "filing_year": period.filing_year,
                "period": period.registry_token,
                "required_slot_first": 1,
                "required_slot_last": 5,
            },
        )


__all__ = ["assert_m303_prorrata_activity_rows_complete"]
