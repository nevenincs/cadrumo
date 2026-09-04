"""Focused proofs for installed-workbench search snapshot assembly."""

from __future__ import annotations

import ast
import pickle
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core.period import Period
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.filing_record import ExternalEvidenceKind, ModeloRecordStatus
from ....domain.modelos.work_unit import WorkUnitState
from ...aeat_sync.workspace import (
    AeatSyncDiscrepancyKind,
    AeatSyncDocumentCustodyState,
    AeatSyncNotificationCategory,
    AeatSyncNotificationReadState,
    AeatSyncReconciliationState,
    AeatSyncSourceState,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceReconciliationRowV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneStateV1,
)
from ...ledger.workspace import (
    LedgerAffectedDeclarationRefV1,
    LedgerWorkspaceArea,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceEntryRefV1,
    LedgerWorkspaceProjectionV1,
    LedgerWorkspaceSource,
    LedgerWorkspaceStatus,
)
from ...modelo.declarations_workspace import (
    DeclarationsLifecycleKind,
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceCalculationRevisionRefV1,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceFilingRefV1,
    DeclarationsWorkspaceLifecycleRefV1,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceSource,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneStateV1,
)
from ...modelo.workspace_models import (
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityV1,
    ModeloWorkspaceProjectionV1,
    ModeloWorkspaceResolvedTargetV1,
)
from ..installed_workbench import InstalledWorkbenchSearchInputsV1, assemble_installed_workbench_search_snapshot
from ..workbench import (
    WorkbenchDestinationAdmission,
    WorkbenchDestinationAdmissionState,
    WorkbenchSearchKind,
    WorkbenchSearchRequest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 9, 3, 10, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2026, "1T")
_BUCKET = "11111111-1111-4111-8111-111111111111"
_REVISION_ID = "c" * 64
_FILING_ID = "f" * 64
_WORK_ID = "d" * 64


def _admission(destination: str) -> WorkbenchDestinationAdmission:
    """Return an admitted destination owned by the installed catalogue."""
    return WorkbenchDestinationAdmission(
        destination=destination,
        state=WorkbenchDestinationAdmissionState.AVAILABLE,
    )


def _ledger() -> LedgerWorkspaceProjectionV1:
    """Return a current redacted Ledger projection."""
    return LedgerWorkspaceProjectionV1(
        bucket_id=_BUCKET,
        areas=tuple(
            LedgerWorkspaceAreaStateV1(
                area=area,
                sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
                availability=LedgerWorkspaceAvailability.AVAILABLE,
                status=LedgerWorkspaceStatus.READY,
                item_count=1,
            )
            for area in LedgerWorkspaceArea
        ),
        entries=(
            LedgerWorkspaceEntryRefV1(
                transaction_id="a" * 64,
                review_status="pending",
                date="2026-03-14",
                amount="1250.00",
                currency="EUR",
                direction="outgoing",
                counterparty="Suministros Delta SL",
                description="Material de oficina",
                business_classification="business",
            ),
        ),
        review_transaction_ids=("a" * 64,),
        invoice_reconciliations=(),
        link_inconsistencies=(),
        affected_declarations=(
            LedgerAffectedDeclarationRefV1(
                modelo=ModeloCode("130"),
                filing_year=2026,
                period=_PERIOD,
                calculation_revision_id=_REVISION_ID,
                changed_count=1,
                removed_count=0,
            ),
        ),
    )


def _declarations() -> DeclarationsWorkspaceProjectionV1:
    """Return current declaration, filing-history, and revision projections."""
    zones = tuple(
        DeclarationsWorkspaceZoneStateV1(
            zone=zone,
            availability=DeclarationsWorkspaceAvailability.AVAILABLE,
            observed_at=_NOW,
            sources=(DeclarationsWorkspaceSource.LOCAL_DECLARATIONS,),
            item_count=1,
        )
        for zone in DeclarationsWorkspaceZone
    )
    common = {"modelo": ModeloCode("130"), "filing_year": 2026, "period": _PERIOD}
    return DeclarationsWorkspaceProjectionV1(
        bucket_id=_BUCKET,
        zones=zones,
        declarations=(
            DeclarationsWorkspaceDeclarationRefV1(
                work_unit_id=_WORK_ID,
                state=WorkUnitState.BORRADOR,
                has_current_calculation=True,
                has_current_filing=False,
                **common,
            ),
        ),
        calculation_revisions=(
            DeclarationsWorkspaceCalculationRevisionRefV1(
                calculation_revision_id=_REVISION_ID,
                work_unit_id=_WORK_ID,
                state=CalculationRevisionState.VERIFICADO_COMPLETO,
                created_at=_NOW,
                updated_at=_NOW,
                is_current=True,
                is_filed=False,
                **common,
            ),
        ),
        filings=(
            DeclarationsWorkspaceFilingRefV1(
                filing_record_id=_FILING_ID,
                work_unit_id=_WORK_ID,
                calculation_revision_id=_REVISION_ID,
                filed_at=_NOW,
                local_status=ModeloRecordStatus.VIGENTE,
                aeat_accepted=True,
                evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                **common,
            ),
        ),
        lifecycle=(
            DeclarationsWorkspaceLifecycleRefV1(
                fact_id="private-lifecycle-fact",
                work_unit_id=_WORK_ID,
                occurred_at=_NOW,
                kind=DeclarationsLifecycleKind.FILED,
                **common,
            ),
        ),
    )


def _aeat_sync() -> AeatSyncWorkspaceProjectionV1:
    """Return current notification and reconciliation projections."""
    zones = tuple(
        AeatSyncWorkspaceZoneStateV1(
            zone=zone,
            availability=AeatSyncWorkspaceAvailability.AVAILABLE,
            sources=(),
            item_count=0,
        )
        for zone in AeatSyncWorkspaceZone
    )
    return AeatSyncWorkspaceProjectionV1(
        zones=zones,
        notifications=(
            AeatSyncWorkspaceNotificationRowV1(
                issued_on=_NOW.date(),
                read_state=AeatSyncNotificationReadState.UNREAD,
                category=AeatSyncNotificationCategory.FORMAL,
                document_custody_state=AeatSyncDocumentCustodyState.NOT_CAPTURED,
                selection_key="aeat_sync.notification." + "b" * 64,
            ),
        ),
        reconciliation=(
            AeatSyncWorkspaceReconciliationRowV1(
                modelo=ModeloCode("130"),
                filing_year=2026,
                period=_PERIOD,
                local_state=AeatSyncSourceState.PRESENT,
                aeat_state=AeatSyncSourceState.ABSENT,
                local_observed_at=_NOW,
                aeat_observed_at=_NOW,
                discrepancy_kind=AeatSyncDiscrepancyKind.LOCAL_ONLY,
                reconciliation_state=AeatSyncReconciliationState.UNRESOLVED,
            ),
        ),
    )


def _modelo() -> ModeloWorkspaceProjectionV1:
    """Return one preloaded Modelo workspace target without resolving readers."""
    return ModeloWorkspaceProjectionV1.model_construct(
        target=ModeloWorkspaceResolvedTargetV1.model_construct(
            modelo=ModeloCode("130"), filing_year=2026, period=_PERIOD
        ),
        capabilities=(
            ModeloWorkspaceCapabilityV1.model_construct(disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE),
        ),
    )


def test_snapshot_has_one_redacted_document_per_current_searchable_projection() -> None:
    """Current workspace rows become safe documents without retaining private IDs."""
    inputs = InstalledWorkbenchSearchInputsV1(
        ledger=_ledger(),
        declarations=_declarations(),
        aeat_sync=_aeat_sync(),
        modelo=(_modelo(),),
        ledger_admission=_admission("workbench.ledger"),
        declarations_admission=_admission("workbench.declarations"),
        aeat_sync_admission=_admission("workbench.aeat_sync"),
    )
    snapshot = inputs.snapshot()

    assert tuple(document.kind for document in snapshot.documents) == (
        WorkbenchSearchKind.LEDGER_ENTRY,
        WorkbenchSearchKind.LEDGER_EVIDENCE,
        WorkbenchSearchKind.DECLARATION,
        WorkbenchSearchKind.REVISION,
        WorkbenchSearchKind.FILING,
        WorkbenchSearchKind.HISTORY,
        WorkbenchSearchKind.RECONCILIATION,
        WorkbenchSearchKind.NOTIFICATION,
        WorkbenchSearchKind.MODELO,
    )
    rendered = " ".join(document.model_dump_json() for document in snapshot.documents)
    assert "private-lifecycle-fact" not in rendered
    assert _BUCKET not in rendered
    assert "aeat_sync.notification." not in rendered
    assert snapshot.service().search(WorkbenchSearchRequest(query="notification")).total_matches == 1
    with pytest.raises(TypeError, match="memory-only"):
        pickle.dumps(snapshot)


def test_snapshot_rejects_a_destination_admission_from_another_area() -> None:
    """Search cannot make a projection reachable through a different route."""
    with pytest.raises(ValueError, match=r"workbench\.ledger"):
        assemble_installed_workbench_search_snapshot(
            ledger=_ledger(),
            declarations=_declarations(),
            aeat_sync=_aeat_sync(),
            modelo=(),
            ledger_admission=_admission("workbench.declarations"),
            declarations_admission=_admission("workbench.declarations"),
            aeat_sync_admission=_admission("workbench.aeat_sync"),
        )


def test_snapshot_projects_modelo_availability_from_the_existing_capability_answer() -> None:
    """Modelo search preserves the workspace's declared capability disposition."""
    snapshot = assemble_installed_workbench_search_snapshot(
        ledger=_ledger(),
        declarations=_declarations(),
        aeat_sync=_aeat_sync(),
        modelo=(_modelo(),),
        ledger_admission=_admission("workbench.ledger"),
        declarations_admission=_admission("workbench.declarations"),
        aeat_sync_admission=_admission("workbench.aeat_sync"),
    )

    result = snapshot.service().search(WorkbenchSearchRequest(query="modelo")).results
    modelo_result = next(item for item in result if item.kind is WorkbenchSearchKind.MODELO)
    assert modelo_result.status.value == "modelo.available"
    assert modelo_result.address is not None
    assert modelo_result.address.modelo == ModeloCode("130")


def test_snapshot_assembly_has_no_io_network_or_token_reachability_import() -> None:
    """Assembly is a pure projection adapter, never an authority reader."""
    source = ast.parse((Path(__file__).parent.parent / "installed_workbench.py").read_text(encoding="utf-8"))
    imports = {
        module
        for node in ast.walk(source)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for module in (
            *((node.module or "",) if isinstance(node, ast.ImportFrom) else ()),
            *(alias.name for alias in node.names if isinstance(node, ast.Import)),
        )
    }
    forbidden = {"httpx", "pathlib", "requests", "socket", "sqlite3", "token", "urllib"}
    assert all(not any(part in forbidden for part in module.split(".")) for module in imports)
