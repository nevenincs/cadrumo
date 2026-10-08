"""Modelo export dialog and result states for reviewing the own-account choice.

The dialog reads a synthetic in-memory own-account register through the
application's own-account logic, so its pickers show the masked projection and
the designations the registered operation publishes. The result is the public
projection of a synthetic export receipt; no file is written.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast, override

from textual.app import App
from textual.containers import VerticalScroll
from textual.events import Mount

from cadrumo.application.ledger.own_account_operation import LedgerOwnAccountRequest
from cadrumo.application.modelo.export import ModeloExportAccountReference, ModeloExportResult
from cadrumo.application.modelo.export_projection import (
    ModeloExportCompleteness,
    ModeloExportEvidenceStatus,
    ModeloExportPublicResultV3,
    ModeloFicheroBoePublicReceipt,
)
from cadrumo.core.modelo_export_artefact import ModeloExportArtefact
from cadrumo.core.period import Period
from cadrumo.domain.transactions.own_accounts import OwnAccountHolding, OwnAccountRole
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.ledger.own_accounts import LedgerOwnAccountDoorV1
from cadrumo.entrypoints.tui.ledger.tests.own_account_fixtures import (
    OWN_ACCOUNT_PROFILE_ID,
    SYNTHETIC_ES_IBAN,
    SYNTHETIC_ES_IBAN_2,
    MemoryOwnAccountDoor,
)
from cadrumo.entrypoints.tui.modelo.export_result import ModeloExportResultScreen
from cadrumo.entrypoints.tui.modelo.workbench.export import WorkbenchExportScreen
from cadrumo.entrypoints.tui.modelo.workbench.ports import WorkbenchExportOffer, WorkbenchExportRequest


class ModeloExportFixtureState(StrEnum):
    """The reviewable export states that carry an own-account choice."""

    ACCOUNTS = "accounts"
    RESULT_ACCOUNT = "result-account"


def _register() -> MemoryOwnAccountDoor:
    door = MemoryOwnAccountDoor()
    for label, iban in (("Cuenta nómina", SYNTHETIC_ES_IBAN), ("Ahorro compartido", SYNTHETIC_ES_IBAN_2)):
        door.apply(
            LedgerOwnAccountRequest(
                profile_id=OWN_ACCOUNT_PROFILE_ID,
                action="add",
                label=label,
                holding=OwnAccountHolding.TITULAR,
                iban=iban,
            )
        )
    for role, account, modelo in (
        (OwnAccountRole.CHARGE, "acc-01", None),
        (OwnAccountRole.REFUND, "acc-02", "303"),
    ):
        door.apply(
            LedgerOwnAccountRequest(
                profile_id=OWN_ACCOUNT_PROFILE_ID, action="designate", own_account_id=account, role=role, modelo=modelo
            )
        )
    return door


class ExportAccountsCaptureHost(ScreenHostApp[WorkbenchExportRequest]):
    """Hold the export dialog until its own-account pickers are filled."""

    @override
    async def on_mount(self, event: Mount | None = None) -> None:
        if event is not None:
            event.prevent_default()
        await super().on_mount()
        for _ in range(5):
            await asyncio.sleep(0.01)
        await self.workers.wait_for_complete()
        await asyncio.sleep(0.01)
        # The account pickers are what this state reviews; bring them into view.
        panel = self.screen.query_one("#export-panel", VerticalScroll)
        panel.call_after_refresh(
            panel.scroll_to_widget, self.screen.query_one("#export-charge-account"), top=True, animate=False
        )
        for _ in range(5):
            await asyncio.sleep(0.01)


def _result() -> ModeloExportPublicResultV3:
    filing = ModeloExportResult(
        calculation_revision_id="a" * 64,
        work_unit_id="b" * 64,
        bucket_id="synthetic-bucket",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        output_path=Path("modelo-303-2T.txt"),
        byte_size=1024,
        file_sha256="c" * 64,
        format="fichero-boe",
        exported_at=datetime(2026, 7, 10, 9, 0, tzinfo=UTC),
        actor="operator",
        bucket_event_id="event-1",
        selected_account=ModeloExportAccountReference(role=OwnAccountRole.CHARGE, own_account_id="acc-01"),
        domiciliation_cutoff_unverified=True,
        software_identity_grade=None,
        completeness_unverified=False,
    )
    return ModeloExportPublicResultV3(
        calculation_revision_id=filing.calculation_revision_id,
        artefact=ModeloExportArtefact.FICHERO_BOE,
        export_format=filing.format,
        output_path=str(filing.output_path),
        byte_size=filing.byte_size,
        file_sha256=filing.file_sha256,
        software_identity_grade=filing.software_identity_grade,
        evidence_status=ModeloExportEvidenceStatus(filing.local_evidence_status),
        completeness=ModeloExportCompleteness.NOT_FLAGGED,
        fichero_boe=ModeloFicheroBoePublicReceipt.from_result(filing),
    )


def build_modelo_export_fixture(state: ModeloExportFixtureState) -> App[Any]:
    """Open the export dialog over a synthetic register, or the result of a synthetic export."""
    if state is ModeloExportFixtureState.RESULT_ACCOUNT:
        return ScreenHostApp[None](ModeloExportResultScreen(_result()))
    offer = WorkbenchExportOffer(
        artefacts=(ModeloExportArtefact.FICHERO_BOE,),
        asks_elections=True,
        modelo="303",
        own_accounts=cast(LedgerOwnAccountDoorV1, _register()),
    )
    return ExportAccountsCaptureHost(WorkbenchExportScreen(offer))


def modelo_export_fixture_interfaces(state: ModeloExportFixtureState) -> tuple[str, ...]:
    """The production interface each state paints."""
    if state is ModeloExportFixtureState.RESULT_ACCOUNT:
        return ("cadrumo.entrypoints.tui.modelo.export_result.ModeloExportResultScreen",)
    return ("cadrumo.entrypoints.tui.modelo.workbench.export.WorkbenchExportScreen",)


__all__ = [
    "ExportAccountsCaptureHost",
    "ModeloExportFixtureState",
    "build_modelo_export_fixture",
    "modelo_export_fixture_interfaces",
]
