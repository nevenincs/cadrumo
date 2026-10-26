"""Activity inventories in the Ledger workspace.

The screen lists every activity inventory the registered list operation
returns and stages a new inventory, a movement, a valuation preview or a
closing-authority record for review. Valuations, closing values and costs of
goods sold are the operation's own figures; the screen never computes one.
Purchase-cost evidence and closing-authority records are typed source files
that the door reads and validates, as the command line reads them, so their
amounts never pass through a screen field.
"""

from __future__ import annotations

from typing import Final, Protocol, override
from uuid import UUID

from pydantic import BaseModel
from textual.app import ComposeResult
from textual.widgets import Static

from ....application.inventory.registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryCreateProjection,
    InventoryLedgerProjection,
    InventoryListProjection,
    InventoryListRowProjection,
    InventoryMovementAddProjection,
    InventoryRefusalProjection,
    InventoryValuationOperationProjection,
)
from ....application.inventory.registered_requests import (
    InventoryAcquisitionCostRequest,
    InventoryClosingAuthorityRecordInput,
    InventoryClosingAuthorityRecordRequest,
    InventoryCreateRequest,
    InventoryListRequest,
    InventoryMovementAddRequest,
    InventoryValuationPreviewRequest,
)
from ....application.ledger.workspace import LedgerWorkspaceArea
from ....core.i18n.render import tr
from ....domain.contribuyente.inventory.records import MovementKind, ValuationMethod
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from .registers_presentation import (
    LedgerRegisterScreen,
    RegisterColumnV1,
    RegisterListV1,
    RegisterOutcomeV1,
    RegisterRow,
    blank_to_none,
    labelled_input,
    labelled_select,
    parse_date,
    parse_optional_public_decimal,
    parse_public_decimal,
    parse_whole_number,
    request_summary,
    require_text,
    show_fields,
)
from .tools import LedgerToolV1

INVENTORY_TOOL_KEY: Final = "ledger.tool.registers.inventory"

type InventoryRequestV1 = (
    InventoryCreateRequest
    | InventoryMovementAddRequest
    | InventoryValuationPreviewRequest
    | InventoryClosingAuthorityRecordRequest
)
"""Every inventory change, each its own registered operation."""

_SCREEN_LOCALE_KEYS: Final[dict[str, str]] = {
    "title": "tui.ledger.registers.inventory.title",
    "prompt": "tui.ledger.registers.inventory.prompt",
    "empty": "tui.ledger.registers.inventory.empty",
    "tool": "tui.ledger.registers.inventory.tool",
    "list": "tui.ledger.registers.inventory.list",
}
_ACTION_LOCALE_KEYS: Final[dict[str, str]] = {
    "create": "tui.ledger.registers.inventory.action.create",
    "movement_add": "tui.ledger.registers.inventory.action.movement_add",
    "valuation_preview": "tui.ledger.registers.inventory.action.valuation_preview",
    "closing_authority": "tui.ledger.registers.inventory.action.closing_authority",
}
_DONE_LOCALE_KEYS: Final[dict[str, str]] = {
    "create": "tui.ledger.registers.inventory.done.create",
    "movement_add": "tui.ledger.registers.inventory.done.movement_add",
}
_METHOD_LOCALE_KEYS: Final[dict[str, str]] = {
    "fifo": "tui.ledger.registers.inventory.method.fifo",
    "pmp": "tui.ledger.registers.inventory.method.pmp",
    "coste_medio": "tui.ledger.registers.inventory.method.coste_medio",
}
_KIND_LOCALE_KEYS: Final[dict[str, str]] = {
    "opening": "tui.ledger.registers.inventory.kind.opening",
    "purchase": "tui.ledger.registers.inventory.kind.purchase",
    "cogs": "tui.ledger.registers.inventory.kind.cogs",
    "count": "tui.ledger.registers.inventory.kind.count",
}
_REFUSAL_LOCALE_KEYS: Final[dict[str, str]] = {
    "activity_conflict": "tui.ledger.registers.inventory.refusal.activity_conflict",
    "activity_not_found": "tui.ledger.registers.inventory.refusal.activity_not_found",
    "invalid_valuation_method": "tui.ledger.registers.inventory.refusal.invalid_valuation_method",
    "duplicate_movement_id": "tui.ledger.registers.inventory.refusal.duplicate_movement_id",
    "inventory_validation": "tui.ledger.registers.inventory.refusal.inventory_validation",
    "closing_authority_conflict": "tui.ledger.registers.inventory.refusal.closing_authority_conflict",
    "closing_authority_invalid": "tui.ledger.registers.inventory.refusal.closing_authority_invalid",
}
_FIELD_LOCALE_KEYS: Final[dict[str, str]] = {
    "action": "tui.ledger.registers.inventory.field.action",
    "actividad_id": "tui.ledger.registers.inventory.field.actividad_id",
    "year": "tui.ledger.registers.inventory.field.year",
    "valuation_method": "tui.ledger.registers.inventory.field.valuation_method",
    "opening_stock": "tui.ledger.registers.inventory.field.opening_stock",
    "movement_id": "tui.ledger.registers.inventory.field.movement_id",
    "movement_date": "tui.ledger.registers.inventory.field.movement_date",
    "kind": "tui.ledger.registers.inventory.field.kind",
    "quantity": "tui.ledger.registers.inventory.field.quantity",
    "unit_cost": "tui.ledger.registers.inventory.field.unit_cost",
    "taxable_base": "tui.ledger.registers.inventory.field.taxable_base",
    "acquisition_cost": "tui.ledger.registers.inventory.field.acquisition_cost",
    "authority_record": "tui.ledger.registers.inventory.field.authority_record",
}
_FIELDS: Final = (
    "inventory-actividad",
    "inventory-year",
    "inventory-method",
    "inventory-opening",
    "inventory-movement-id",
    "inventory-movement-date",
    "inventory-movement-kind",
    "inventory-quantity",
    "inventory-unit-cost",
    "inventory-taxable-base",
    "inventory-acquisition-path",
    "inventory-authority-path",
)
_SCOPE: Final = frozenset({"inventory-actividad", "inventory-year"})
_ACTION_FIELDS: Final[dict[str, frozenset[str]]] = {
    "create": _SCOPE | {"inventory-method", "inventory-opening"},
    "movement_add": _SCOPE
    | {
        "inventory-movement-id",
        "inventory-movement-date",
        "inventory-movement-kind",
        "inventory-quantity",
        "inventory-unit-cost",
        "inventory-taxable-base",
        "inventory-acquisition-path",
    },
    "valuation_preview": _SCOPE,
    "closing_authority": _SCOPE | {"inventory-authority-path"},
}
_COLUMN_LOCALE_KEYS: Final = (
    RegisterColumnV1("actividad", "tui.ledger.registers.inventory.column.actividad", 14),
    RegisterColumnV1("year", "tui.ledger.registers.inventory.column.year", 6),
    RegisterColumnV1("method", "tui.ledger.registers.inventory.column.method", 10),
    RegisterColumnV1("opening", "tui.ledger.registers.inventory.column.opening", 10),
    RegisterColumnV1("movements", "tui.ledger.registers.inventory.column.movements", 8),
)


class LedgerInventoryDoorV1(Protocol):
    """Injected door to the registered inventory operations of one admitted profile."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...

    async def read_register(self, request: InventoryListRequest) -> InventoryListProjection:
        """Read every activity inventory through ``ledger.inventory.list``."""
        ...

    async def create(self, request: InventoryCreateRequest) -> InventoryCreateProjection:
        """Create one activity inventory; a registered refusal is returned, not raised."""
        ...

    async def add_movement(self, request: InventoryMovementAddRequest) -> InventoryMovementAddProjection:
        """Append one movement; a registered refusal is returned, not raised."""
        ...

    async def preview_valuation(
        self, request: InventoryValuationPreviewRequest
    ) -> InventoryValuationOperationProjection:
        """Run and record one valuation preview; a registered refusal is returned, not raised."""
        ...

    async def record_closing_authority(
        self, request: InventoryClosingAuthorityRecordRequest
    ) -> InventoryClosingAuthorityOperationProjection:
        """Record one closing authority; a registered refusal is returned, not raised."""
        ...

    async def read_acquisition_cost(self, path: str) -> InventoryAcquisitionCostRequest:
        """Read and validate one typed purchase-cost file the operator named."""
        ...

    async def read_closing_authority(self, path: str) -> InventoryClosingAuthorityRecordInput:
        """Read and validate one typed closing-authority file the operator named."""
        ...


def inventory_key(actividad_id: str, year: int) -> str:
    """The register's own identity of one inventory: its activity and year."""
    return f"{actividad_id}|{year}"


def inventory_refusal_text(refusal: InventoryRefusalProjection) -> str:
    """The operation's own refusal, its reason in words with what it named."""
    named = [
        f"{tr(_FIELD_LOCALE_KEYS[name])}: {value}"
        for name, value in (
            ("actividad_id", refusal.actividad_id),
            ("year", refusal.year),
            ("movement_id", refusal.movement_id),
            ("valuation_method", refusal.valuation_method),
        )
        if value is not None
    ]
    return "\n".join((tr(_REFUSAL_LOCALE_KEYS[refusal.reason]), *named))


def _ledger_line(ledger: InventoryLedgerProjection) -> str:
    return tr(
        "tui.ledger.registers.inventory.result.ledger",
        actividad=ledger.actividad_id,
        year=ledger.year,
        method=ledger.valuation_method.value,
        opening=ledger.opening_stock.decimal,
        movements=len(ledger.period_movements),
    )


def _yes_no(value: bool) -> str:
    return tr("tui.ledger.registers.yes" if value else "tui.ledger.registers.no")


def inventory_outcome(
    result: InventoryCreateProjection
    | InventoryMovementAddProjection
    | InventoryValuationOperationProjection
    | InventoryClosingAuthorityOperationProjection,
) -> RegisterOutcomeV1:
    """Describe one settled inventory request exactly as the operation reported it."""
    if result.refusal is not None:
        return RegisterOutcomeV1(refusal=inventory_refusal_text(result.refusal))
    if isinstance(result, InventoryValuationOperationProjection):
        preview = result.preview
        if preview is None:
            return RegisterOutcomeV1()
        return RegisterOutcomeV1(
            lines=(
                tr(
                    "tui.ledger.registers.inventory.result.valuation",
                    actividad=preview.actividad_id,
                    year=preview.year,
                    method=preview.valuation_method.value,
                    closing=preview.derived_closing_value.decimal,
                    cogs=preview.cogs.decimal,
                ),
            )
        )
    if isinstance(result, InventoryClosingAuthorityOperationProjection):
        record = result.record
        if record is None:
            return RegisterOutcomeV1()
        return RegisterOutcomeV1(
            lines=(
                tr(
                    "tui.ledger.registers.inventory.result.closing",
                    actividad=record.actividad_id,
                    year=record.year,
                    changed=_yes_no(record.changed),
                ),
                tr(
                    "tui.ledger.registers.inventory.result.fingerprint",
                    fingerprint=record.authority_record_fingerprint,
                ),
            )
        )
    ledger = result.ledger
    if ledger is None:
        return RegisterOutcomeV1()
    done = "create" if isinstance(result, InventoryCreateProjection) else "movement_add"
    return RegisterOutcomeV1(lines=(tr(_DONE_LOCALE_KEYS[done]), _ledger_line(ledger)))


class LedgerInventoryScreen(LedgerRegisterScreen):
    """List activity inventories and stage each registered inventory request for review."""

    TITLE_LOCALE_KEY = _SCREEN_LOCALE_KEYS["title"]
    PROMPT_LOCALE_KEY = _SCREEN_LOCALE_KEYS["prompt"]
    EMPTY_LOCALE_KEY = _SCREEN_LOCALE_KEYS["empty"]

    def __init__(self, controller: LedgerWorkspaceController, door: LedgerInventoryDoorV1) -> None:
        """Keep the injected profile-bound door for every request this screen submits."""
        super().__init__(controller, id="ledger-inventory-screen")
        self.door = door
        self.inventories: tuple[InventoryListRowProjection, ...] = ()

    @override
    def register_lists(self) -> tuple[RegisterListV1, ...]:
        return (RegisterListV1("inventory-list", _SCREEN_LOCALE_KEYS["list"], _COLUMN_LOCALE_KEYS, self._rows),)

    def _rows(self) -> tuple[RegisterRow, ...]:
        return tuple(
            (
                inventory_key(row.actividad_id, row.year),
                (
                    row.actividad_id,
                    str(row.year),
                    row.valuation_method.value,
                    row.opening_stock.decimal,
                    str(row.movement_count),
                ),
            )
            for row in self.inventories
        )

    @override
    def choice_options(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {
            "inventory-action": tuple((tr(key), action) for action, key in _ACTION_LOCALE_KEYS.items()),
            "inventory-method": tuple(
                (tr(_METHOD_LOCALE_KEYS[method.value]), method.value) for method in ValuationMethod
            ),
            "inventory-movement-kind": tuple((tr(_KIND_LOCALE_KEYS[kind.value]), kind.value) for kind in MovementKind),
        }

    @override
    def compose_form(self) -> ComposeResult:
        options = self.choice_options()
        yield from labelled_select(_FIELD_LOCALE_KEYS["action"], "inventory-action", options["inventory-action"])
        yield from labelled_input(_FIELD_LOCALE_KEYS["actividad_id"], "inventory-actividad")
        yield from labelled_input(_FIELD_LOCALE_KEYS["year"], "inventory-year")
        yield from labelled_select(
            _FIELD_LOCALE_KEYS["valuation_method"], "inventory-method", options["inventory-method"]
        )
        yield from labelled_input(_FIELD_LOCALE_KEYS["opening_stock"], "inventory-opening")
        yield from labelled_input(_FIELD_LOCALE_KEYS["movement_id"], "inventory-movement-id")
        yield from labelled_input(
            _FIELD_LOCALE_KEYS["movement_date"],
            "inventory-movement-date",
            placeholder=tr("tui.ledger.registers.date_placeholder"),
        )
        yield from labelled_select(
            _FIELD_LOCALE_KEYS["kind"], "inventory-movement-kind", options["inventory-movement-kind"]
        )
        yield from labelled_input(_FIELD_LOCALE_KEYS["quantity"], "inventory-quantity")
        yield from labelled_input(_FIELD_LOCALE_KEYS["unit_cost"], "inventory-unit-cost")
        yield from labelled_input(_FIELD_LOCALE_KEYS["taxable_base"], "inventory-taxable-base")
        yield from labelled_input(_FIELD_LOCALE_KEYS["acquisition_cost"], "inventory-acquisition-path")
        yield from labelled_input(_FIELD_LOCALE_KEYS["authority_record"], "inventory-authority-path")

    @override
    def form_mounted(self) -> None:
        self._show_action_fields()

    def on_select_changed(self) -> None:
        """Show only the fields the chosen request takes."""
        self._show_action_fields()

    def _show_action_fields(self) -> None:
        show_fields(self, _FIELDS, _ACTION_FIELDS[self.select_value("#inventory-action")])

    @override
    def form_controls(self) -> tuple[str, ...]:
        return ("#inventory-action", *(f"#{field}" for field in _FIELDS))

    @override
    async def read_register(self) -> None:
        result = await self.door.read_register(InventoryListRequest(profile_id=self.door.profile_id))
        self.inventories = result.rows

    @override
    def clear_register(self) -> None:
        self.inventories = ()

    @override
    def choose_row(self, table_id: str, key: str) -> None:
        row = next(item for item in self.inventories if inventory_key(item.actividad_id, item.year) == key)
        self.set_input("#inventory-actividad", row.actividad_id)
        self.set_input("#inventory-year", str(row.year))
        self.query_one("#register-detail", Static).update(
            tr(
                "tui.ledger.registers.inventory.detail",
                actividad=row.actividad_id,
                year=row.year,
                method=row.valuation_method.value,
                opening=row.opening_stock.decimal,
                movements=row.movement_count,
            )
        )

    async def _request(self, action: str) -> tuple[InventoryRequestV1, str | None]:
        """Build the chosen request from the visible fields; a named source file is read by the door."""
        profile_id = self.door.profile_id
        actividad = require_text(self.input_value("#inventory-actividad"), field_key=_FIELD_LOCALE_KEYS["actividad_id"])
        year = parse_whole_number(self.input_value("#inventory-year"), field_key=_FIELD_LOCALE_KEYS["year"])
        if action == "create":
            opening = parse_optional_public_decimal(
                self.input_value("#inventory-opening"), field_key=_FIELD_LOCALE_KEYS["opening_stock"]
            )
            fields: dict[str, object] = {
                "profile_id": profile_id,
                "actividad_id": actividad,
                "year": year,
                "valuation_method": self.select_value("#inventory-method"),
            }
            if opening is not None:
                fields["opening_stock"] = opening
            return InventoryCreateRequest.model_validate(fields), None
        if action == "valuation_preview":
            return InventoryValuationPreviewRequest(profile_id=profile_id, actividad_id=actividad, year=year), None
        if action == "closing_authority":
            path = require_text(
                self.input_value("#inventory-authority-path"), field_key=_FIELD_LOCALE_KEYS["authority_record"]
            )
            record = await self.door.read_closing_authority(path)
            request = InventoryClosingAuthorityRecordRequest(
                profile_id=profile_id, actividad_id=actividad, year=year, authority_record=record
            )
            return request, path
        path = blank_to_none(self.input_value("#inventory-acquisition-path"))
        acquisition = None if path is None else await self.door.read_acquisition_cost(path)
        request = InventoryMovementAddRequest(
            profile_id=profile_id,
            actividad_id=actividad,
            year=year,
            movement_id=require_text(
                self.input_value("#inventory-movement-id"), field_key=_FIELD_LOCALE_KEYS["movement_id"]
            ),
            movement_date=parse_date(
                self.input_value("#inventory-movement-date"), field_key=_FIELD_LOCALE_KEYS["movement_date"]
            ),
            kind=MovementKind(self.select_value("#inventory-movement-kind")),
            quantity=parse_public_decimal(
                self.input_value("#inventory-quantity"), field_key=_FIELD_LOCALE_KEYS["quantity"]
            ),
            unit_cost=parse_optional_public_decimal(
                self.input_value("#inventory-unit-cost"), field_key=_FIELD_LOCALE_KEYS["unit_cost"]
            ),
            taxable_base=parse_optional_public_decimal(
                self.input_value("#inventory-taxable-base"), field_key=_FIELD_LOCALE_KEYS["taxable_base"]
            ),
            acquisition_cost=acquisition,
        )
        return request, path

    @override
    async def stage(self) -> tuple[BaseModel, str]:
        action = self.select_value("#inventory-action")
        request, source = await self._request(action)
        lines = [tr(_ACTION_LOCALE_KEYS[action]), request_summary(request, field_keys=_FIELD_LOCALE_KEYS)]
        if source is not None:
            lines.append(tr("tui.ledger.registers.inventory.source", path=source))
        return request, "\n".join(lines)

    @override
    async def send(self, request: BaseModel) -> RegisterOutcomeV1:
        if isinstance(request, InventoryCreateRequest):
            outcome = inventory_outcome(await self.door.create(request))
        elif isinstance(request, InventoryMovementAddRequest):
            outcome = inventory_outcome(await self.door.add_movement(request))
        elif isinstance(request, InventoryValuationPreviewRequest):
            outcome = inventory_outcome(await self.door.preview_valuation(request))
        elif isinstance(request, InventoryClosingAuthorityRecordRequest):
            outcome = inventory_outcome(await self.door.record_closing_authority(request))
        else:
            raise TypeError("the inventory screen submits only its own inventory requests")
        if outcome.refusal is None:
            self.selected_key = inventory_key(request.actividad_id, request.year)
        return outcome


def inventory_tool(door: LedgerInventoryDoorV1) -> LedgerToolV1:
    """Offer activity inventories from the Records overview."""

    def build(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
        return LedgerInventoryScreen(controller, door)

    return LedgerToolV1(
        key=INVENTORY_TOOL_KEY,
        label_key=_SCREEN_LOCALE_KEYS["tool"],
        area=LedgerWorkspaceArea.OVERVIEW,
        build=build,
    )


__all__ = [
    "INVENTORY_TOOL_KEY",
    "InventoryRequestV1",
    "LedgerInventoryDoorV1",
    "LedgerInventoryScreen",
    "inventory_key",
    "inventory_outcome",
    "inventory_refusal_text",
    "inventory_tool",
]
