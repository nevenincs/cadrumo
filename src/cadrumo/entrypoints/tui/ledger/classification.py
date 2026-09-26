"""Explicit, command-backed classification flow for one selected transaction."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Input, Static

from ....application.ledger.models import ManualLedgerTransactionPatch
from ....core.decimal.constants import ONE
from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ....core.iva_deduction_fact import IvaDeductionFactKind
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.model_validation import validate_business_pct_coupling, validate_non_negative_decimal
from ..components.widgets import ContentDataTable
from .controller import LedgerWorkspaceController, ledger_copy
from .models import LedgerFlowState
from .workspace_presentation import LedgerConfirmationFlowScreen, door_refusal_text, ledger_workspace_page

_CHOICES = (
    (BusinessClassification.BUSINESS, "tui.ledger.classification.business"),
    (BusinessClassification.PERSONAL, "tui.ledger.classification.personal"),
    (BusinessClassification.MIXED, "tui.ledger.classification.mixed"),
    (BusinessClassification.REVIEWED_EXCLUDED, "tui.ledger.classification.excluded"),
)

#: The classification capture fields, each labelled by ``tui.ledger.classification.field.<name>``.
CLASSIFICATION_FIELD_NAMES: Final[tuple[str, ...]] = (
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "iva_category",
    "deduction_fact_kind",
    "irpf_category",
    "business_pct",
    "usage_ratio_id",
    "prorrata_reference",
)


def _input_id(field_name: str) -> str:
    return f"ledger-classification-{field_name.replace('_', '-')}"


def _optional_decimal(field_name: str, raw: str) -> Decimal | None:
    """Parse one optional decimal without turning blank or unknown into zero."""
    value = raw.strip()
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise TransactionValidationError(f"{field_name} must be a decimal") from error
    if not parsed.is_finite():
        raise TransactionValidationError(f"{field_name} must be a finite decimal")
    if field_name != "business_pct":
        validate_non_negative_decimal(parsed, field_name=field_name)
    return parsed


def _validate_iva_rate(value: Decimal | None) -> Decimal | None:
    """Apply the domain rate convention before the submitter is called."""
    if value is not None and value > ONE:
        raise TransactionValidationError(
            f"iva_rate is a decimal fraction, not a percentage: got {value}. Express 21% IVA as 0.21.",
        )
    return value


class LedgerClassificationScreen(LedgerConfirmationFlowScreen):
    """Let an operator explicitly edit, confirm, or cancel one classification."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain an injected command-capable workspace controller."""
        super().__init__(controller, id="ledger-classification-screen")
        self.selected_classification: BusinessClassification | None = None
        self._pending_patch: ManualLedgerTransactionPatch | None = None

    FLOW_NAME = "classification"

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.classification.title"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            position, total, short_id = self.controller.classification_target_coordinate()
            yield Static(
                ledger_copy(
                    "tui.ledger.classification.target",
                    position=position,
                    total=total,
                    short_id=short_id,
                ),
                id="ledger-classification-target",
                markup=False,
            )
            yield Static(ledger_copy("tui.ledger.classification.prompt"), markup=False)
            yield Static(
                ledger_copy("tui.ledger.classification.boundary"),
                id="ledger-classification-boundary",
                markup=False,
            )
            for field_name in CLASSIFICATION_FIELD_NAMES:
                yield Static(ledger_copy(f"tui.ledger.classification.field.{field_name}"), markup=False)
                yield Input(id=_input_id(field_name))
            yield ContentDataTable[str](id="ledger-classifications", cursor_type="row", zebra_stripes=True)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Button(
                ledger_copy("tui.ledger.classification.confirm"),
                id="ledger-classification-confirm",
                disabled=True,
            )
            yield Button(ledger_copy("tui.ledger.classification.cancel"), id="ledger-classification-cancel")
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate explicit authored choices without inferring a classification."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-classifications", DataTable))
        # The rows are classifications to choose from, not states, so the
        # column is named after what the operator is choosing.
        table.add_column(ledger_copy("tui.ledger.area.classification"))
        for classification, key in _CHOICES:
            table.add_row(ledger_copy(key), key=classification.value)
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Move an explicit choice into confirmation state."""
        if self.handle_navigation_selection(event):
            return
        event_table = cast("DataTable[str]", event.data_table)
        if (
            self.flow_state is not LedgerFlowState.EDITING
            or event_table.id != "ledger-classifications"
            or event.row_key.value is None
        ):
            return
        self.selected_classification = BusinessClassification(str(event.row_key.value))
        self._transition(LedgerFlowState.CONFIRMING)
        self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.classification.confirming"))
        confirm = self.query_one("#ledger-classification-confirm", Button)
        confirm.disabled = False
        confirm.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Confirm through the injected door or cancel without mutation."""
        if event.button.id == "ledger-classification-cancel" and self.flow_state in {
            LedgerFlowState.EDITING,
            LedgerFlowState.CONFIRMING,
        }:
            self._cancel_flow()
            return
        if (
            self.flow_state is not LedgerFlowState.CONFIRMING
            or event.button.id != "ledger-classification-confirm"
            or self.selected_classification is None
        ):
            return
        try:
            self._pending_patch = self._build_patch()
        except (CadrumoError, ValidationError) as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            return
        self._transition(LedgerFlowState.SUBMITTING)
        event.button.disabled = True
        self.query_one("#ledger-classification-cancel", Button).disabled = True
        status = self.query_one("#ledger-flow-status", Static)
        status.update(ledger_copy("tui.ledger.classification.progress"))
        self.run_worker(self._submit(), exclusive=True)

    async def _submit(self) -> None:
        """Await the injected door without blocking keyboard message handling."""
        status = self.query_one("#ledger-flow-status", Static)
        selected = self.selected_classification
        if selected is None:  # pragma: no cover - guarded before worker creation
            raise InternalInvariantError("classification selection disappeared before submission")
        patch = self._pending_patch
        if patch is None:  # pragma: no cover - guarded before worker creation
            raise InternalInvariantError("classification patch disappeared before submission")
        try:
            await self.controller.submit_classification(patch)
        except Exception:
            self._transition(LedgerFlowState.FAILED)
            status.update(ledger_copy("tui.ledger.classification.failure"))
        else:
            self._transition(LedgerFlowState.SUCCEEDED)
            status.update(ledger_copy("tui.ledger.classification.success"))

    def _field_value(self, field_name: str) -> str:
        return self.query_one(f"#{_input_id(field_name)}", Input).value

    def _optional_text(self, field_name: str) -> str | None:
        value = self._field_value(field_name).strip()
        return value or None

    def _build_patch(self) -> ManualLedgerTransactionPatch:
        """Build the shared typed patch, leaving every blank input unset."""
        selected = self.selected_classification
        if selected is None:  # pragma: no cover - guarded by the button handler
            raise InternalInvariantError("classification selection is required before reading the form")

        values: dict[str, object] = {"business_classification": selected}
        decimals = {
            "taxable_base": _optional_decimal("taxable_base", self._field_value("taxable_base")),
            "iva_rate": _validate_iva_rate(_optional_decimal("iva_rate", self._field_value("iva_rate"))),
            "iva_amount": _optional_decimal("iva_amount", self._field_value("iva_amount")),
            "business_pct": _optional_decimal("business_pct", self._field_value("business_pct")),
        }
        validate_business_pct_coupling(selected, decimals["business_pct"])
        values.update({field_name: value for field_name, value in decimals.items() if value is not None})

        category = self._optional_text("iva_category")
        if category is not None:
            values["iva_category"] = IvaCategory(category)
        deduction_kind = self._optional_text("deduction_fact_kind")
        if deduction_kind is not None:
            values["deduction_fact_kind"] = deduction_kind
        for field_name in ("irpf_category", "usage_ratio_id", "prorrata_reference"):
            value = self._optional_text(field_name)
            if value is not None:
                values[field_name] = value

        patch = ManualLedgerTransactionPatch.model_validate(values)
        # The shared patch resolves deduction membership; the screen never
        # imports calculation registry internals or manufactures tax arithmetic.
        if "iva_category" in patch.model_fields_set and not isinstance(patch.iva_category, IvaCategory):
            raise InternalInvariantError("classification IVA category is not canonical")
        if "deduction_fact_kind" in patch.model_fields_set and not isinstance(
            patch.deduction_fact_kind, IvaDeductionFactKind
        ):
            raise InternalInvariantError("classification deduction kind is not canonical")
        return patch

    @override
    def _cancel_flow(self) -> None:
        if self.flow_state not in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
            return
        self.selected_classification = None
        self._pending_patch = None
        self._transition(LedgerFlowState.CANCELLED)
        self.query_one("#ledger-flow-status", Static).update("")
        self.query_one("#ledger-classification-confirm", Button).disabled = True
        self.query_one("#ledger-classification-cancel", Button).disabled = True


__all__ = ["CLASSIFICATION_FIELD_NAMES", "LedgerClassificationScreen"]
