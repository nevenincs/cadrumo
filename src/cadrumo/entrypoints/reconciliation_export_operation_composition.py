"""Compose saved reconciliation publication with the offline workbook writer."""

from __future__ import annotations

from uuid import UUID

from ..application.modelo.reconciliation_export_operation import ReconciliationExportXlsxPorts
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def build_reconciliation_export_xlsx_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> ReconciliationExportXlsxPorts:
    """Bind publication to the admitted profile and pinned authority."""
    from ..adapters.outbound.workbook.calc_sheets_xlsx import materialize_export_plan

    return ReconciliationExportXlsxPorts(
        profile_id=profile_id, operation=operation, materialize=materialize_export_plan
    )
