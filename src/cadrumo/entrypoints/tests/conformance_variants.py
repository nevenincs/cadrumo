"""Distinct seeded behavioral variants supplement the one-owner registered matrix.

These use the same real supervisor as the primary cases. Separate variants preserve
successful material operations and independently specified refusal/DTO witnesses
when the two source snapshots deliberately exercise different premises.
"""

from __future__ import annotations

from .conformance_auth_apoderado_support import AUTH_APODERADO_ALL_CONFORMANCE_FAMILY
from .conformance_auth_diagnostic_report_support import AUTH_DIAGNOSTIC_ABSENT_CONFORMANCE_FAMILY
from .conformance_family_contract import ConformanceFamily
from .conformance_google_support import GOOGLE_MATERIAL_CONFORMANCE_FAMILY
from .conformance_ledger_seed_support import LEDGER_MATERIAL_CONFORMANCE_FAMILY
from .conformance_live_borrador_support import BORRADOR_MATERIAL_CONFORMANCE_FAMILY
from .conformance_m036_support import M036_MATERIAL_CONFORMANCE_FAMILY
from .conformance_m145_support import M145_WIRE_REFUSAL_CONFORMANCE_FAMILY
from .conformance_maritime_preview_support import MARITIME_QUICKFILE_MATERIAL_CONFORMANCE_FAMILY
from .conformance_modelo_spreadsheet_support import MODELO_REPORTS_MATERIAL_CONFORMANCE_FAMILY
from .conformance_profile_archive_support import ARCHIVE_MATERIAL_CONFORMANCE_FAMILY
from .conformance_review_package_exchange_support import REVIEW_EXCHANGE_MATERIAL_CONFORMANCE_FAMILY
from .conformance_workstation_check_support import WORKSTATION_MATERIAL_CONFORMANCE_FAMILY

CONFORMANCE_VARIANT_FAMILIES: tuple[ConformanceFamily, ...] = (
    ARCHIVE_MATERIAL_CONFORMANCE_FAMILY,
    BORRADOR_MATERIAL_CONFORMANCE_FAMILY,
    M036_MATERIAL_CONFORMANCE_FAMILY,
    LEDGER_MATERIAL_CONFORMANCE_FAMILY,
    MARITIME_QUICKFILE_MATERIAL_CONFORMANCE_FAMILY,
    MODELO_REPORTS_MATERIAL_CONFORMANCE_FAMILY,
    REVIEW_EXCHANGE_MATERIAL_CONFORMANCE_FAMILY,
    WORKSTATION_MATERIAL_CONFORMANCE_FAMILY,
    GOOGLE_MATERIAL_CONFORMANCE_FAMILY,
    M145_WIRE_REFUSAL_CONFORMANCE_FAMILY,
    AUTH_APODERADO_ALL_CONFORMANCE_FAMILY,
    AUTH_DIAGNOSTIC_ABSENT_CONFORMANCE_FAMILY,
)
