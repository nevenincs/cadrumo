"""The operation families whose conformance scenarios live in their own support modules.

Enrol a family with one import and one entry below. Each definition id must
be owned by exactly one scenario across these families and the matrix's own
cases; the matrix refuses a second owner rather than letting one silently win.
"""

from __future__ import annotations

from .conformance_auth_apoderado_support import AUTH_APODERADO_CONFORMANCE_FAMILY
from .conformance_auth_diagnostic_report_support import AUTH_DIAGNOSTIC_REPORT_CONFORMANCE_FAMILY
from .conformance_diagnostics_support import DIAGNOSTICS_CONFORMANCE_FAMILY
from .conformance_diagnostics_telemetry_support import DIAGNOSTICS_TELEMETRY_CONFORMANCE_FAMILY
from .conformance_family_contract import ConformanceFamily
from .conformance_google_support import GOOGLE_CONFORMANCE_FAMILY
from .conformance_invoice_intake_support import INVOICE_INTAKE_CONFORMANCE_FAMILY
from .conformance_ledger_classification_support import LEDGER_CLASSIFICATION_CONFORMANCE_FAMILY
from .conformance_ledger_evidence_ingestion_support import LEDGER_EVIDENCE_INGESTION_CONFORMANCE_FAMILY
from .conformance_ledger_export_link_support import LEDGER_EXPORT_LINK_CONFORMANCE_FAMILY
from .conformance_live_borrador_support import LIVE_BORRADOR_CONFORMANCE_FAMILY
from .conformance_m036_support import M036_CONFORMANCE_FAMILY
from .conformance_m145_support import M145_CONFORMANCE_FAMILY
from .conformance_maritime_preview_support import MARITIME_PREVIEW_CONFORMANCE_FAMILY
from .conformance_modelo_audit_support import MODELO_AUDIT_CONFORMANCE_FAMILY
from .conformance_modelo_spreadsheet_support import MODELO_SPREADSHEET_CONFORMANCE_FAMILY
from .conformance_profile_archive_support import PROFILE_ARCHIVE_CONFORMANCE_FAMILY
from .conformance_profile_history_support import PROFILE_HISTORY_CONFORMANCE_FAMILY
from .conformance_quickfile_support import QUICKFILE_CONFORMANCE_FAMILY
from .conformance_review_package_exchange_support import REVIEW_PACKAGE_EXCHANGE_CONFORMANCE_FAMILY
from .conformance_workstation_check_support import WORKSTATION_CHECK_CONFORMANCE_FAMILY

CONFORMANCE_FAMILIES: tuple[ConformanceFamily, ...] = (
    AUTH_APODERADO_CONFORMANCE_FAMILY,
    AUTH_DIAGNOSTIC_REPORT_CONFORMANCE_FAMILY,
    DIAGNOSTICS_CONFORMANCE_FAMILY,
    DIAGNOSTICS_TELEMETRY_CONFORMANCE_FAMILY,
    GOOGLE_CONFORMANCE_FAMILY,
    INVOICE_INTAKE_CONFORMANCE_FAMILY,
    LEDGER_CLASSIFICATION_CONFORMANCE_FAMILY,
    LEDGER_EVIDENCE_INGESTION_CONFORMANCE_FAMILY,
    LEDGER_EXPORT_LINK_CONFORMANCE_FAMILY,
    LIVE_BORRADOR_CONFORMANCE_FAMILY,
    M036_CONFORMANCE_FAMILY,
    M145_CONFORMANCE_FAMILY,
    MARITIME_PREVIEW_CONFORMANCE_FAMILY,
    MODELO_AUDIT_CONFORMANCE_FAMILY,
    MODELO_SPREADSHEET_CONFORMANCE_FAMILY,
    PROFILE_ARCHIVE_CONFORMANCE_FAMILY,
    PROFILE_HISTORY_CONFORMANCE_FAMILY,
    QUICKFILE_CONFORMANCE_FAMILY,
    REVIEW_PACKAGE_EXCHANGE_CONFORMANCE_FAMILY,
    WORKSTATION_CHECK_CONFORMANCE_FAMILY,
)


def conformance_family_for(definition_id: str) -> ConformanceFamily | None:
    """Return the one family declaring ``definition_id``, or ``None`` when the matrix owns it."""
    owners = tuple(
        family for family in CONFORMANCE_FAMILIES if any(case.definition_id == definition_id for case in family.cases)
    )
    if len(owners) > 1:
        raise AssertionError(f"{definition_id} is declared by {len(owners)} conformance families")
    return owners[0] if owners else None
