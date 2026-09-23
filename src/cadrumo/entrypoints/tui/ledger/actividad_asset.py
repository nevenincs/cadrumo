"""Host-neutral activity-asset actions for the Ledger TUI."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import override

from textual.app import ComposeResult
from textual.widgets import Button, Input, Static

from ....application.actividad_asset.history import ActivityAssetHistoryClaimResult
from ....application.actividad_asset.operations import ActivityAssetFilingHandoff, ActivityAssetOperations
from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ....core.period import Period
from ....domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ....domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from .models_actividad_asset import (
    ActivityAssetClaimRequestV1,
    ActivityAssetCorrectionRequestV1,
    ActivityAssetCreationRequestV1,
    ActivityAssetFilingRequestV1,
    ActivityAssetForecastRequestV1,
    ActivityAssetInspectionV1,
)


@dataclass(frozen=True, slots=True)
class _ActivityAssetScreenResult:
    """One shared-operation response projected into public screen controls."""

    message: str
    current_revision_id: str | None = None


def _optional_amount(value: str) -> Decimal | None:
    """Parse the optional free-depreciation amount; an empty field elects none."""
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return Decimal(stripped)
    except InvalidOperation as exc:
        raise ValueError("free-depreciation amount must be a decimal euro amount") from exc


class ActivityAssetTuiActionsV1:
    """TUI interaction boundary with no depreciation arithmetic of its own."""

    def __init__(self, *, operations: ActivityAssetOperations) -> None:
        """Bind actions to the shared application operations."""
        self._operations = operations

    def create(self, request: ActivityAssetCreationRequestV1) -> ActivityAssetInspectionV1:
        """Create an asset and return its persisted revision chain."""
        self._operations.create(request.revision)
        return self.inspect(request.revision.asset_id)

    def inspect(self, asset_id: str) -> ActivityAssetInspectionV1:
        """Inspect one asset's immutable revision chain."""
        return ActivityAssetInspectionV1(asset_id=asset_id, revisions=self._operations.inspect(asset_id))

    def correct(self, request: ActivityAssetCorrectionRequestV1) -> ActivityAssetInspectionV1:
        """Append a correction and return the resulting chain."""
        self._operations.correct(request.revision)
        return self.inspect(request.revision.asset_id)

    def forecast(self, request: ActivityAssetForecastRequestV1) -> ScheduledAmortizationCharge:
        """Preview a schedule through the application boundary."""
        return self._operations.forecast(
            asset_id=request.asset_id,
            covered_from=request.covered_from,
            covered_until=request.covered_until,
            requested_free_amount=request.requested_free_amount,
        )

    def record_claim(self, request: ActivityAssetClaimRequestV1) -> ActivityAssetHistoryClaimResult:
        """Record an explicit claim through the application boundary."""
        return self._operations.record_claim(
            request.forecast,
            creating_operation=request.creating_operation,
            supersedes_claim_id=request.supersedes_claim_id,
        )

    def filing_handoff(self, request: ActivityAssetFilingRequestV1) -> ActivityAssetFilingHandoff:
        """Build non-consuming filing projections."""
        return self._operations.filing_handoff(tax_year=request.tax_year, m130_period=request.m130_period)


class ActivityAssetScreen(LedgerWorkspaceScreen):
    """Installed interaction surface over the shared asset operations."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the injected action door and refuse direct construction without it."""
        super().__init__(controller, id="ledger-activity-asset-screen")
        if controller.activity_asset_actions is None:
            raise ValueError("activity-asset screen requires an injected application door")
        self._actions = controller.activity_asset_actions
        self._last_forecast: ScheduledAmortizationCharge | None = None

    @override
    def compose(self) -> ComposeResult:
        """Render typed JSON boundaries while keeping all arithmetic in application code."""
        yield Static("Activos amortizables", classes="cadrumo-banner")
        yield Input(placeholder="Identificador del activo", id="asset-id")
        yield Input(placeholder="Revisión del activo (JSON)", id="asset-revision-json")
        yield Button("Crear", id="asset-create")
        yield Button("Inspeccionar", id="asset-inspect")
        yield Button("Corregir", id="asset-correct")
        yield Static("", id="asset-current-revision-id", markup=False)
        yield Input(placeholder="Importe de libertad de amortización (opcional)", id="asset-free-amount")
        yield Input(value="2025-01-01", id="asset-covered-from")
        yield Input(value="2026-01-01", id="asset-covered-until")
        yield Button("Calcular previsión", id="asset-forecast")
        yield Input(value="actividad_asset.tui.claim", id="asset-creating-operation")
        yield Button("Registrar amortización", id="asset-claim")
        yield Input(value="2025", id="asset-filing-tax-year")
        yield Input(value="4T", id="asset-filing-m130-period")
        yield Button("Preparar traslado a modelos", id="asset-filing-handoff")
        yield Static("", id="asset-result", markup=False)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch every mutation through the injected shared operations."""
        # A visible neutral state prevents a following public action from being
        # mistaken for the previous result while its shared operation is still
        # running on the worker thread.  It has no accounting meaning and is
        # always replaced by either the operation result or a refusal below.
        self.query_one("#asset-result", Static).update(f"pending\t{event.button.id or 'unknown'}")
        try:
            result = await asyncio.to_thread(self._dispatch, event.button.id)
        except (CadrumoError, ValueError) as exc:
            self.query_one("#asset-result", Static).update(f"refused\t{exc}")
            return
        self.query_one("#asset-result", Static).update(result.message)
        if result.current_revision_id is not None:
            self.query_one("#asset-current-revision-id", Static).update(
                f"current_revision_id\t{result.current_revision_id}"
            )

    def _dispatch(self, button_id: str | None) -> _ActivityAssetScreenResult:
        """Delegate one public action, retaining no screen-local tax arithmetic."""
        asset_id = self.query_one("#asset-id", Input).value
        revision_json = self.query_one("#asset-revision-json", Input).value
        if button_id == "asset-create":
            result = self._actions.create(
                ActivityAssetCreationRequestV1(revision=ActivityAssetRevision.model_validate_json(revision_json)),
            )
            return self._inspection_result(prefix="created", result=result)
        if button_id == "asset-inspect":
            result = self._actions.inspect(asset_id)
            return self._inspection_result(prefix="asset", result=result)
        if button_id == "asset-correct":
            result = self._actions.correct(
                ActivityAssetCorrectionRequestV1(revision=ActivityAssetRevision.model_validate_json(revision_json)),
            )
            return self._inspection_result(prefix="corrected", result=result)
        if button_id == "asset-forecast":
            self._last_forecast = self._actions.forecast(
                ActivityAssetForecastRequestV1(
                    asset_id=asset_id,
                    covered_from=date.fromisoformat(self.query_one("#asset-covered-from", Input).value),
                    covered_until=date.fromisoformat(self.query_one("#asset-covered-until", Input).value),
                    requested_free_amount=_optional_amount(self.query_one("#asset-free-amount", Input).value),
                ),
            )
            return _ActivityAssetScreenResult(
                message=f"forecast\t{self._last_forecast.amount}\t{self._last_forecast.source_reference}"
            )
        if button_id == "asset-claim":
            if self._last_forecast is None:
                raise ValueError("calculate a forecast before recording a claim")
            result = self._actions.record_claim(
                ActivityAssetClaimRequestV1(
                    forecast=self._last_forecast,
                    creating_operation=self.query_one("#asset-creating-operation", Input).value,
                ),
            )
            return _ActivityAssetScreenResult(
                message=f"claim\t{result.claim.claim_id}\treused={str(result.reused_existing_claim).lower()}"
            )
        if button_id == "asset-filing-handoff":
            tax_year = int(self.query_one("#asset-filing-tax-year", Input).value)
            m130_period = Period.from_year_and_code(
                tax_year,
                self.query_one("#asset-filing-m130-period", Input).value,
            )
            result = self._actions.filing_handoff(
                ActivityAssetFilingRequestV1(tax_year=tax_year, m130_period=m130_period),
            )
            return _ActivityAssetScreenResult(
                message=(
                    "filing_handoff"
                    f"\tm100_material={result.material_m100.amount}"
                    f"\tm100_intangible={result.intangible_m100.amount}"
                    f"\tm130_material={result.material_m130.amount}"
                    f"\tm130_intangible={result.intangible_m130.amount}"
                )
            )
        raise ValueError("unknown activity-asset action")

    @staticmethod
    def _inspection_result(*, prefix: str, result: ActivityAssetInspectionV1) -> _ActivityAssetScreenResult:
        """Project the current immutable revision identity alongside its count."""
        if not result.revisions:  # pragma: no cover - application inspection invariant
            raise InternalInvariantError("activity-asset inspection returned no current revision")
        return _ActivityAssetScreenResult(
            message=f"{prefix}\t{result.asset_id}\trevisions={len(result.revisions)}",
            current_revision_id=result.revisions[-1].revision_id,
        )


__all__ = ["ActivityAssetScreen", "ActivityAssetTuiActionsV1"]
