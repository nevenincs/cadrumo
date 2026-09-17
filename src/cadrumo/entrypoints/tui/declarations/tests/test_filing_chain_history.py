"""The filing history shows a period's chain and its reconciliation and override events."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from textual.widgets import DataTable, Static

from cadrumo.domain.modelos.tests.work_unit_catalogue_support import build_work_unit_catalogue

from .....application.modelo.declarations_workspace import (
    DeclarationsLifecycleKind,
    DeclarationsSanitizedLifecycleFactV1,
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneObservationV1,
    project_declarations_workspace,
)
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.period import Period
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.filing_record import (
    AeatConfirmationState,
    AeatRegisterRef,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from .....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...components.host import ScreenHostApp
from ...navigation import TuiScreenContextV1
from ...tests.frame import geometry_band
from ..controller import DeclarationsWorkspaceController, declarations_copy
from ..filing_history import DeclarationsFilingHistoryScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET = "22222222-2222-4222-8222-222222222222"
_ORIGINAL_AT = datetime(2026, 4, 20, 9, tzinfo=UTC)
_AMENDED_AT = datetime(2026, 5, 4, 9, tzinfo=UTC)
_RECONCILED_AT = datetime(2026, 5, 5, 9, tzinfo=UTC)
_OVERRIDDEN_AT = datetime(2026, 5, 6, 9, tzinfo=UTC)
_CLEARED_AT = datetime(2026, 5, 7, 9, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2026, "1T")


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Keep one indexed authority generation live for the projection."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _revision(
    work_unit_id: str,
    value: str,
    created_at: datetime,
    snapshot_ref: object,
    state: CalculationRevisionState,
    superseded_at: datetime | None = None,
) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={"01": value},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision.model_validate(
        {
            "calculation_revision_id": revision_id,
            "work_unit_id": work_unit_id,
            "registry_snapshot_ref": snapshot_ref,
            "state": state,
            "input_values_by_casilla_id": {"01": value},
            "casilla_values": {},
            "created_at": created_at,
            "updated_at": created_at,
            "verified_at": created_at,
            "verified_by": "operator",
            "filed_at": created_at,
            "filed_by": "operator",
            "filing_instance_evidence": None,
            "source_provenance": (),
            "superseded_at": superseded_at,
        }
    )


def _chain_projection(operation: PinnedAuthorityOperation) -> DeclarationsWorkspaceProjectionV1:
    """A confirmed AEAT original amended by a pending local complementaria."""
    snapshot_ref = operation.snapshot("130", filing_year=2026, period="1T").snapshot_ref
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET,
        modelo="130",
        filing_year=2026,
        period=_PERIOD,
        revision_id=snapshot_ref.revision_id,
    )
    original_revision = _revision(
        work_unit_id,
        "10.00",
        _ORIGINAL_AT,
        snapshot_ref,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
        superseded_at=_AMENDED_AT,
    )
    amended_revision = _revision(work_unit_id, "12.00", _AMENDED_AT, snapshot_ref, CalculationRevisionState.PRESENTADO)
    original_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=original_revision.calculation_revision_id,
        filed_by="aeat-import",
    )
    amended_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=amended_revision.calculation_revision_id,
        filed_by="operator",
    )
    original = ModeloRecord(
        filing_record_id=original_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=original_revision.calculation_revision_id,
        bucket_id=_BUCKET,
        modelo="130",
        filing_year=2026,
        period=_PERIOD,
        filed_at=_ORIGINAL_AT,
        filed_by="aeat-import",
        origin=FilingOrigin.AEAT,
        confirmation=AeatConfirmationState.CONFIRMADA,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        aeat_register=AeatRegisterRef(expediente_id="synthetic-expediente-1"),
        status=ModeloRecordStatus.SUPERSEDIDO,
        superseded_at=_AMENDED_AT,
        superseded_by_filing_record_id=amended_id,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            reference_id="synthetic-csv-reference",
            imported_at=_ORIGINAL_AT,
        ),
    )
    amended = ModeloRecord(
        filing_record_id=amended_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=amended_revision.calculation_revision_id,
        bucket_id=_BUCKET,
        modelo="130",
        filing_year=2026,
        period=_PERIOD,
        filed_at=_AMENDED_AT,
        filed_by="operator",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.COMPLEMENTARIA,
        amends_filing_record_id=original_id,
    )
    unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET,
        modelo="130",
        filing_year=2026,
        period=_PERIOD,
        revision_id=snapshot_ref.revision_id,
        name="synthetic chain",
        created_at=_ORIGINAL_AT,
        updated_at=_AMENDED_AT,
        current_calculation_revision_id=amended_revision.calculation_revision_id,
        filed_calculation_revision_id=amended_revision.calculation_revision_id,
        current_filing_record_id=amended_id,
    )
    lifecycle = tuple(
        DeclarationsSanitizedLifecycleFactV1(fact_id=fact_id, work_unit_id=work_unit_id, occurred_at=at, kind=kind)
        for fact_id, at, kind in (
            ("event-reconciled", _RECONCILED_AT, DeclarationsLifecycleKind.RECONCILED),
            ("event-overridden", _OVERRIDDEN_AT, DeclarationsLifecycleKind.OBSERVATION_OVERRIDDEN),
            ("event-override-cleared", _CLEARED_AT, DeclarationsLifecycleKind.OBSERVATION_OVERRIDE_CLEARED),
        )
    )
    return project_declarations_workspace(
        operation=operation,
        bucket_id=_BUCKET,
        work_units=build_work_unit_catalogue((unit,)),
        calculation_revisions=CalculationRevisionCatalogue(
            revisions={
                original_revision.calculation_revision_id: original_revision,
                amended_revision.calculation_revision_id: amended_revision,
            }
        ),
        filing_records=ModeloRecordCatalogue(records={original_id: original, amended_id: amended}),
        lifecycle_facts=lifecycle,
        zone_observations=tuple(
            DeclarationsWorkspaceZoneObservationV1(
                zone=zone,
                availability=DeclarationsWorkspaceAvailability.AVAILABLE,
                observed_at=_CLEARED_AT,
            )
            for zone in DeclarationsWorkspaceZone
        ),
    )


def _controller(projection: DeclarationsWorkspaceProjectionV1) -> DeclarationsWorkspaceController:
    return DeclarationsWorkspaceController(
        TuiScreenContextV1(destination="workbench.declarations"),
        projection,
        work_action=ActionReference(action_id=lookup_action("operator.modelo.work.list").action_id),
        revisions_action=ActionReference(action_id=lookup_action("operator.modelo.work.revisions").action_id),
        filing_action=ActionReference(action_id=lookup_action("operator.modelo.filing_record.list").action_id),
    )


@pytest.mark.asyncio
async def test_history_shows_chain_columns_and_reconciliation_and_override_events(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    projection = _chain_projection(authority_operation)
    by_kind = {row.declaration_kind: row for row in projection.filings}
    original = by_kind[FilingDeclarationKind.ORIGINAL]
    amendment = by_kind[FilingDeclarationKind.COMPLEMENTARIA]
    screen = DeclarationsFilingHistoryScreen(_controller(projection))
    async with ScreenHostApp[None](screen).run_test(size=(80, 30)) as pilot:
        await pilot.pause()
        table = screen.query_one("#declarations-filings", DataTable)

        detail = screen.query_one("#declarations-filing-chain", Static)
        for entry, local_state, confirmation, evidence, origin, kind, amends in (
            (original, "supersedido", "confirmada", "evidence.aeat_csv_register", "aeat", "original", "no"),
            (amendment, "vigente", "pendiente", "evidence.none", "local", "complementaria", "yes"),
        ):
            row_key = f"filing:{entry.filing_record_id}"
            cells = tuple(str(cell) for cell in table.get_row(row_key))
            assert cells[2:] == (
                declarations_copy(f"tui.declarations.filing_state.{local_state}"),
                declarations_copy(f"tui.declarations.confirmation.{confirmation}"),
                declarations_copy(f"tui.declarations.{evidence}"),
            )
            table.move_cursor(row=table.get_row_index(row_key))
            await pilot.pause()
            assert str(detail.render()) == declarations_copy(
                "tui.declarations.filing_history.chain_detail",
                origin=declarations_copy(f"tui.declarations.origin.{origin}"),
                kind=declarations_copy(f"tui.declarations.declaration_kind.{kind}"),
                confirmation=declarations_copy(f"tui.declarations.confirmation.{confirmation}"),
                amends=declarations_copy(f"tui.declarations.value.{amends}"),
            )

        keys = tuple(str(row.key.value) for row in table.ordered_rows)
        assert keys == (
            "lifecycle:event-override-cleared",
            "lifecycle:event-overridden",
            "lifecycle:event-reconciled",
            f"filing:{amendment.filing_record_id}",
            f"filing:{original.filing_record_id}",
        )
        event_labels = [str(table.get_row(key)[2]) for key in keys[:3]]
        assert event_labels == [
            declarations_copy("tui.declarations.lifecycle.observation_override_cleared"),
            declarations_copy("tui.declarations.lifecycle.observation_overridden"),
            declarations_copy("tui.declarations.lifecycle.reconciled"),
        ]
        assert all("tui.declarations." not in label for label in event_labels)
        table.move_cursor(row=table.get_row_index("lifecycle:event-reconciled"))
        await pilot.pause()
        assert str(detail.render()) == ""
        assert geometry_band(screen.app, 80) == []
