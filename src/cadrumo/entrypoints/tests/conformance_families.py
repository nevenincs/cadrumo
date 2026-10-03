"""The operation families whose conformance scenarios live in their own support modules.

Enrol a family with one import and one entry below. Each definition id must
be owned by exactly one scenario across these families and the matrix's own
cases; the matrix refuses a second owner rather than letting one silently win.
"""

from __future__ import annotations

from .conformance_archive_support import ARCHIVE_CONFORMANCE_FAMILY
from .conformance_borrador_support import BORRADOR_CONFORMANCE_FAMILY
from .conformance_censo_support import CENSO_CONFORMANCE_FAMILY
from .conformance_diagnostics_support import DIAGNOSTICS_CONFORMANCE_FAMILY
from .conformance_family_contract import ConformanceFamily
from .conformance_google_support import GOOGLE_CONFORMANCE_FAMILY
from .conformance_ledger_extended_support import LEDGER_EXTENDED_CONFORMANCE_FAMILY
from .conformance_m145_support import M145_CONFORMANCE_FAMILY
from .conformance_maritime_quickfile_support import MARITIME_QUICKFILE_CONFORMANCE_FAMILY
from .conformance_modelo_reports_support import MODELO_REPORTS_CONFORMANCE_FAMILY
from .conformance_review_exchange_support import REVIEW_EXCHANGE_CONFORMANCE_FAMILY
from .conformance_workstation_support import WORKSTATION_CONFORMANCE_FAMILY

CONFORMANCE_FAMILIES: tuple[ConformanceFamily, ...] = (
    DIAGNOSTICS_CONFORMANCE_FAMILY,
    GOOGLE_CONFORMANCE_FAMILY,
    WORKSTATION_CONFORMANCE_FAMILY,
    M145_CONFORMANCE_FAMILY,
    ARCHIVE_CONFORMANCE_FAMILY,
    CENSO_CONFORMANCE_FAMILY,
    MODELO_REPORTS_CONFORMANCE_FAMILY,
    LEDGER_EXTENDED_CONFORMANCE_FAMILY,
    BORRADOR_CONFORMANCE_FAMILY,
    REVIEW_EXCHANGE_CONFORMANCE_FAMILY,
    MARITIME_QUICKFILE_CONFORMANCE_FAMILY,
)


def conformance_family_for(definition_id: str) -> ConformanceFamily | None:
    """Return the one family declaring ``definition_id``, or ``None`` when the matrix owns it."""
    owners = tuple(
        family for family in CONFORMANCE_FAMILIES if any(case.definition_id == definition_id for case in family.cases)
    )
    if len(owners) > 1:
        raise AssertionError(f"{definition_id} is declared by {len(owners)} conformance families")
    return owners[0] if owners else None
