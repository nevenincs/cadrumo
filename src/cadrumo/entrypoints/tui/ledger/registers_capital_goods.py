"""The capital-goods (bienes de inversión) IVA register in the Ledger workspace.

The screen lists every capital good the registered list operation returns and
stages a new declaration for review. The deduction shown for a good is the one
the operation derived and reported; the screen never computes it.
"""

from __future__ import annotations

from typing import Final, Protocol, override
from uuid import UUID

from pydantic import BaseModel
from textual.app import ComposeResult
from textual.widgets import Static

from ....application.bienes_inversion.registered_requests import (
    BienesInversionDeclareRequest,
    BienesInversionListRequest,
)
from ....application.bienes_inversion.registered_result_contracts import (
    BienesInversionDeclareProjection,
    BienesInversionListProjection,
    BienesInversionRefusalProjection,
    BienInversionRecordProjection,
)
from ....application.ledger.workspace import LedgerWorkspaceArea
from ....core.i18n.render import tr
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
    parse_optional_whole_number,
    parse_public_decimal,
    parse_whole_number,
    request_summary,
    require_text,
)
from .tools import LedgerToolV1

CAPITAL_GOODS_TOOL_KEY: Final = "ledger.tool.registers.capital_goods"

_SCREEN_LOCALE_KEYS: Final[dict[str, str]] = {
    "title": "tui.ledger.registers.capital_goods.title",
    "prompt": "tui.ledger.registers.capital_goods.prompt",
    "empty": "tui.ledger.registers.capital_goods.empty",
    "tool": "tui.ledger.registers.capital_goods.tool",
    "list": "tui.ledger.registers.capital_goods.list",
}
_REFUSAL_LOCALE_KEYS: Final[dict[str, str]] = {
    "validation": "tui.ledger.registers.capital_goods.refusal.validation",
    "disposal_incomplete": "tui.ledger.registers.capital_goods.refusal.disposal_incomplete",
    "duplicate_identifier": "tui.ledger.registers.capital_goods.refusal.duplicate_identifier",
}
_MISSING_LOCALE_KEYS: Final[dict[str, str]] = {
    "year": "tui.ledger.registers.capital_goods.missing.year",
    "regime": "tui.ledger.registers.capital_goods.missing.regime",
}
_FIELD_LOCALE_KEYS: Final[dict[str, str]] = {
    "identifier": "tui.ledger.registers.capital_goods.field.identifier",
    "description": "tui.ledger.registers.capital_goods.field.description",
    "acquisition_year": "tui.ledger.registers.capital_goods.field.acquisition_year",
    "acquisition_ledger_id": "tui.ledger.registers.capital_goods.field.acquisition_ledger_id",
    "cuota_soportada": "tui.ledger.registers.capital_goods.field.cuota_soportada",
    "prorrata_inicial_pct": "tui.ledger.registers.capital_goods.field.prorrata_inicial_pct",
    "kind": "tui.ledger.registers.capital_goods.field.kind",
    "art108_elegible": "tui.ledger.registers.capital_goods.field.art108_elegible",
    "prorrata_sector_id": "tui.ledger.registers.capital_goods.field.prorrata_sector_id",
    "disposal_year": "tui.ledger.registers.capital_goods.field.disposal_year",
    "disposal_regime": "tui.ledger.registers.capital_goods.field.disposal_regime",
}
_INPUTS: Final = (
    "#capital-identifier",
    "#capital-description",
    "#capital-year",
    "#capital-ledger-id",
    "#capital-cuota",
    "#capital-prorrata",
    "#capital-kind",
    "#capital-sector",
    "#capital-disposal-year",
    "#capital-disposal-regime",
)
_COLUMN_LOCALE_KEYS: Final = (
    RegisterColumnV1("identifier", "tui.ledger.registers.capital_goods.column.identifier", 10),
    RegisterColumnV1("year", "tui.ledger.registers.capital_goods.column.year", 6),
    RegisterColumnV1("kind", "tui.ledger.registers.capital_goods.column.kind", 10),
    RegisterColumnV1("cuota", "tui.ledger.registers.capital_goods.column.cuota", 10),
    RegisterColumnV1("deduction", "tui.ledger.registers.capital_goods.column.deduction", 10),
    RegisterColumnV1("description", "tui.ledger.registers.capital_goods.column.description", 12),
)


class LedgerCapitalGoodsDoorV1(Protocol):
    """Injected door to the registered capital-goods operations of one admitted profile."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...

    async def read_register(self, request: BienesInversionListRequest) -> BienesInversionListProjection:
        """Read every declared capital good through ``ledger.bienes_inversion.list``."""
        ...

    async def declare(self, request: BienesInversionDeclareRequest) -> BienesInversionDeclareProjection:
        """Declare one capital good; a registered refusal is returned, not raised."""
        ...


def capital_goods_refusal_text(refusal: BienesInversionRefusalProjection) -> str:
    """The operation's own refusal, its reason in words with what it named."""
    lines = [tr(_REFUSAL_LOCALE_KEYS[refusal.reason])]
    if refusal.identifier is not None:
        lines.append(tr("tui.ledger.registers.capital_goods.refusal_identifier", identifier=refusal.identifier))
    if refusal.missing is not None:
        lines.append(tr(_MISSING_LOCALE_KEYS[refusal.missing]))
    return "\n".join(lines)


def _record_line(record: BienInversionRecordProjection) -> str:
    disposal = record.disposal
    return tr(
        "tui.ledger.registers.capital_goods.detail",
        identifier=record.identifier,
        description=record.description,
        year=record.acquisition_year,
        kind=record.kind,
        cuota=record.cuota_soportada.decimal,
        prorrata=record.prorrata_inicial_pct.decimal,
        deduction=record.deduccion_efectuada.decimal,
        ledger=record.acquisition_ledger_id,
        disposal="-" if disposal is None else f"{disposal.year} · {disposal.regime}",
    )


def capital_goods_outcome(result: BienesInversionDeclareProjection) -> RegisterOutcomeV1:
    """Describe one settled declaration exactly as the operation reported it."""
    if result.refusal is not None:
        return RegisterOutcomeV1(refusal=capital_goods_refusal_text(result.refusal))
    if result.record is None:
        return RegisterOutcomeV1()
    return RegisterOutcomeV1(
        lines=(
            tr("tui.ledger.registers.capital_goods.declared", count=result.count),
            _record_line(result.record),
        )
    )


class LedgerCapitalGoodsScreen(LedgerRegisterScreen):
    """List the capital-goods register and stage one declaration for review."""

    TITLE_LOCALE_KEY = _SCREEN_LOCALE_KEYS["title"]
    PROMPT_LOCALE_KEY = _SCREEN_LOCALE_KEYS["prompt"]
    EMPTY_LOCALE_KEY = _SCREEN_LOCALE_KEYS["empty"]

    def __init__(self, controller: LedgerWorkspaceController, door: LedgerCapitalGoodsDoorV1) -> None:
        """Keep the injected profile-bound door for every request this screen submits."""
        super().__init__(controller, id="ledger-capital-goods-screen")
        self.door = door
        self.records: tuple[BienInversionRecordProjection, ...] = ()

    @override
    def register_lists(self) -> tuple[RegisterListV1, ...]:
        return (RegisterListV1("capital-goods", _SCREEN_LOCALE_KEYS["list"], _COLUMN_LOCALE_KEYS, self._rows),)

    def _rows(self) -> tuple[RegisterRow, ...]:
        return tuple(
            (
                record.identifier,
                (
                    record.identifier,
                    str(record.acquisition_year),
                    record.kind,
                    record.cuota_soportada.decimal,
                    record.deduccion_efectuada.decimal,
                    record.description,
                ),
            )
            for record in self.records
        )

    @override
    def choice_options(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {
            "capital-art108": (
                (tr("tui.ledger.registers.yes"), "yes"),
                (tr("tui.ledger.registers.no"), "no"),
            )
        }

    @override
    def compose_form(self) -> ComposeResult:
        yield from labelled_input(_FIELD_LOCALE_KEYS["identifier"], "capital-identifier")
        yield from labelled_input(_FIELD_LOCALE_KEYS["description"], "capital-description")
        yield from labelled_input(_FIELD_LOCALE_KEYS["acquisition_year"], "capital-year")
        yield from labelled_input(_FIELD_LOCALE_KEYS["acquisition_ledger_id"], "capital-ledger-id")
        yield from labelled_input(_FIELD_LOCALE_KEYS["cuota_soportada"], "capital-cuota")
        yield from labelled_input(_FIELD_LOCALE_KEYS["prorrata_inicial_pct"], "capital-prorrata")
        yield from labelled_input(_FIELD_LOCALE_KEYS["kind"], "capital-kind")
        yield from labelled_select(
            _FIELD_LOCALE_KEYS["art108_elegible"], "capital-art108", self.choice_options()["capital-art108"]
        )
        yield from labelled_input(_FIELD_LOCALE_KEYS["prorrata_sector_id"], "capital-sector")
        yield from labelled_input(_FIELD_LOCALE_KEYS["disposal_year"], "capital-disposal-year")
        yield from labelled_input(_FIELD_LOCALE_KEYS["disposal_regime"], "capital-disposal-regime")

    @override
    def form_controls(self) -> tuple[str, ...]:
        return (*_INPUTS, "#capital-art108")

    @override
    async def read_register(self) -> None:
        result = await self.door.read_register(BienesInversionListRequest(profile_id=self.door.profile_id))
        self.records = result.rows

    @override
    def clear_register(self) -> None:
        self.records = ()

    @override
    def choose_row(self, table_id: str, key: str) -> None:
        record = next(item for item in self.records if item.identifier == key)
        self.query_one("#register-detail", Static).update(_record_line(record))

    @override
    async def stage(self) -> tuple[BaseModel, str]:
        request = BienesInversionDeclareRequest(
            profile_id=self.door.profile_id,
            identifier=require_text(
                self.input_value("#capital-identifier"), field_key=_FIELD_LOCALE_KEYS["identifier"]
            ),
            description=require_text(
                self.input_value("#capital-description"), field_key=_FIELD_LOCALE_KEYS["description"]
            ),
            acquisition_year=parse_whole_number(
                self.input_value("#capital-year"), field_key=_FIELD_LOCALE_KEYS["acquisition_year"]
            ),
            acquisition_ledger_id=require_text(
                self.input_value("#capital-ledger-id"), field_key=_FIELD_LOCALE_KEYS["acquisition_ledger_id"]
            ),
            cuota_soportada=parse_public_decimal(
                self.input_value("#capital-cuota"), field_key=_FIELD_LOCALE_KEYS["cuota_soportada"]
            ),
            prorrata_inicial_pct=parse_public_decimal(
                self.input_value("#capital-prorrata"),
                field_key=_FIELD_LOCALE_KEYS["prorrata_inicial_pct"],
                signed=False,
            ),
            kind=require_text(self.input_value("#capital-kind"), field_key=_FIELD_LOCALE_KEYS["kind"]),
            art108_elegible=self.select_value("#capital-art108") == "yes",
            prorrata_sector_id=blank_to_none(self.input_value("#capital-sector")),
            disposal_year=parse_optional_whole_number(
                self.input_value("#capital-disposal-year"), field_key=_FIELD_LOCALE_KEYS["disposal_year"]
            ),
            disposal_regime=blank_to_none(self.input_value("#capital-disposal-regime")),
        )
        return request, request_summary(request, field_keys=_FIELD_LOCALE_KEYS)

    @override
    async def send(self, request: BaseModel) -> RegisterOutcomeV1:
        if not isinstance(request, BienesInversionDeclareRequest):
            raise TypeError("the capital-goods register submits only declarations")
        result = await self.door.declare(request)
        if result.record is not None:
            self.selected_key = result.record.identifier
        return capital_goods_outcome(result)


def capital_goods_tool(door: LedgerCapitalGoodsDoorV1) -> LedgerToolV1:
    """Offer the capital-goods register from the Records overview."""

    def build(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
        return LedgerCapitalGoodsScreen(controller, door)

    return LedgerToolV1(
        key=CAPITAL_GOODS_TOOL_KEY,
        label_key=_SCREEN_LOCALE_KEYS["tool"],
        area=LedgerWorkspaceArea.OVERVIEW,
        build=build,
    )


__all__ = [
    "CAPITAL_GOODS_TOOL_KEY",
    "LedgerCapitalGoodsDoorV1",
    "LedgerCapitalGoodsScreen",
    "capital_goods_outcome",
    "capital_goods_refusal_text",
    "capital_goods_tool",
]
