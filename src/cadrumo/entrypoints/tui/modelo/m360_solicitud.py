"""The Modelo 360 solicitud register in the Ledger workspace.

The screen lists the solicitudes the registered operation reports, masked, and
stages a declaration or a removal for review. A declaration takes its facts
from a typed file, as the command line takes them from its document, and one
account: the id of an own account, or a representante account typed into
secret fields. Whether the account is admissible, and every other rule of the
solicitud, belongs to the operation; the screen collects typed input and shows
the operation's own result and refusals.
"""

from __future__ import annotations

from typing import Final, Protocol, override
from uuid import UUID

from pydantic import BaseModel
from textual.app import ComposeResult
from textual.widgets import Input, Static

from ....application.ledger.workspace import LedgerWorkspaceArea
from ....application.modelo.m360_solicitud_input import Modelo360ProfileInput
from ....application.modelo.m360_solicitud_operation import (
    Modelo360RepresentanteAccountInput,
    Modelo360SolicitudProjection,
    Modelo360SolicitudRequest,
    Modelo360SolicitudResult,
)
from ....core.i18n.render import tr
from ....core.iban import mask_iban
from ..ledger.controller import LedgerWorkspaceController
from ..ledger.registers_input import parse_whole_number, require_text
from ..ledger.registers_presentation import (
    LedgerRegisterScreen,
    RegisterColumnV1,
    RegisterListV1,
    RegisterOutcomeV1,
    RegisterRow,
    labelled_input,
    labelled_select,
    show_fields,
)
from ..ledger.tools import LedgerToolV1
from ..ledger.workspace_screen import LedgerWorkspaceScreen

SOLICITUD_360_TOOL_KEY: Final = "ledger.tool.modelo.m360_solicitud"

_SCREEN_LOCALE_KEYS: Final[dict[str, str]] = {
    "title": "tui.modelo.m360_solicitud.title",
    "prompt": "tui.modelo.m360_solicitud.prompt",
    "empty": "tui.modelo.m360_solicitud.empty",
    "tool": "tui.modelo.m360_solicitud.tool",
    "list": "tui.modelo.m360_solicitud.list",
}
_FIELD_LOCALE_KEYS: Final[dict[str, str]] = {
    "action": "tui.modelo.m360_solicitud.field.action",
    "filing_year": "tui.modelo.m360_solicitud.field.filing_year",
    "facts_path": "tui.modelo.m360_solicitud.field.facts_path",
    "account_kind": "tui.modelo.m360_solicitud.field.account_kind",
    "own_account_id": "tui.modelo.m360_solicitud.field.own_account_id",
    "iban": "tui.modelo.m360_solicitud.field.iban",
    "swift_bic": "tui.modelo.m360_solicitud.field.swift_bic",
    "bank_name": "tui.modelo.m360_solicitud.field.bank_name",
    "bank_address": "tui.modelo.m360_solicitud.field.bank_address",
    "bank_city": "tui.modelo.m360_solicitud.field.bank_city",
    "bank_country_code": "tui.modelo.m360_solicitud.field.bank_country_code",
}
_ACTION_LOCALE_KEYS: Final[dict[str, str]] = {
    "declare": "tui.modelo.m360_solicitud.action.declare",
    "remove": "tui.modelo.m360_solicitud.action.remove",
}
_ACCOUNT_KIND_LOCALE_KEYS: Final[dict[str, str]] = {
    "own_account": "tui.modelo.m360_solicitud.account_kind.own_account",
    "representante": "tui.modelo.m360_solicitud.account_kind.representante",
}
_COLUMN_LOCALE_KEYS: Final = (
    RegisterColumnV1("year", "tui.modelo.m360_solicitud.column.year", 6),
    RegisterColumnV1("destination", "tui.modelo.m360_solicitud.column.destination", 12),
    RegisterColumnV1("cause", "tui.modelo.m360_solicitud.column.cause", 14),
    RegisterColumnV1("holder", "tui.modelo.m360_solicitud.column.holder", 14),
    RegisterColumnV1("account", "tui.modelo.m360_solicitud.column.account", 20),
)
_REPRESENTANTE_FIELDS: Final = (
    "m360-iban",
    "m360-bic",
    "m360-bank-name",
    "m360-bank-address",
    "m360-bank-city",
    "m360-bank-country",
)
_ALL_FIELDS: Final = ("m360-year", "m360-facts-path", "m360-account-kind", "m360-own-account", *_REPRESENTANTE_FIELDS)
_REMOVE_FIELDS: Final = frozenset({"m360-year"})
_OWN_ACCOUNT_FIELDS: Final = frozenset({"m360-year", "m360-facts-path", "m360-account-kind", "m360-own-account"})
_REPRESENTANTE_ACCOUNT_FIELDS: Final = frozenset(
    {"m360-year", "m360-facts-path", "m360-account-kind", *_REPRESENTANTE_FIELDS}
)
_SECRET_INPUTS: Final = ("#m360-iban", "#m360-bic")


class Modelo360SolicitudDoorV1(Protocol):
    """Injected door to the registered Modelo 360 solicitud operation of one admitted profile."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...

    async def __call__(self, request: Modelo360SolicitudRequest) -> Modelo360SolicitudResult:
        """Submit one request and return its masked, receipt-correlated result."""
        ...

    async def read_facts(self, path: str) -> Modelo360ProfileInput:
        """Read one typed facts file off the event loop and validate it as the command line does."""
        ...


def _account_text(solicitud: Modelo360SolicitudProjection) -> str:
    return solicitud.own_account_id or solicitud.masked_iban or "-"


def _detail_line(solicitud: Modelo360SolicitudProjection) -> str:
    return tr(
        "tui.modelo.m360_solicitud.detail",
        year=solicitud.filing_year,
        destination=solicitud.pais_destino,
        cause=solicitud.causa_presentacion,
        holder=solicitud.titular_en_calidad_de,
        representante=tr("tui.ledger.registers.yes" if solicitud.has_representante else "tui.ledger.registers.no"),
        account=_account_text(solicitud),
    )


class Modelo360SolicitudScreen(LedgerRegisterScreen):
    """List the declared solicitudes and stage a declaration or removal for review."""

    TITLE_LOCALE_KEY = _SCREEN_LOCALE_KEYS["title"]
    PROMPT_LOCALE_KEY = _SCREEN_LOCALE_KEYS["prompt"]
    EMPTY_LOCALE_KEY = _SCREEN_LOCALE_KEYS["empty"]

    def __init__(self, controller: LedgerWorkspaceController, door: Modelo360SolicitudDoorV1) -> None:
        """Keep the injected profile-bound door for every request this screen submits."""
        super().__init__(controller, id="modelo-360-solicitud-screen")
        self.door = door
        self.solicitudes: tuple[Modelo360SolicitudProjection, ...] = ()

    @override
    def register_lists(self) -> tuple[RegisterListV1, ...]:
        return (RegisterListV1("m360-solicitudes", _SCREEN_LOCALE_KEYS["list"], _COLUMN_LOCALE_KEYS, self._rows),)

    def _rows(self) -> tuple[RegisterRow, ...]:
        return tuple(
            (
                str(item.filing_year),
                (
                    str(item.filing_year),
                    item.pais_destino,
                    item.causa_presentacion,
                    item.titular_en_calidad_de,
                    _account_text(item),
                ),
            )
            for item in self.solicitudes
        )

    @override
    def choice_options(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {
            "m360-action": tuple((tr(key), action) for action, key in _ACTION_LOCALE_KEYS.items()),
            "m360-account-kind": tuple((tr(key), kind) for kind, key in _ACCOUNT_KIND_LOCALE_KEYS.items()),
        }

    @override
    def compose_form(self) -> ComposeResult:
        options = self.choice_options()
        yield from labelled_select(_FIELD_LOCALE_KEYS["action"], "m360-action", options["m360-action"])
        yield from labelled_input(_FIELD_LOCALE_KEYS["filing_year"], "m360-year")
        yield from labelled_input(_FIELD_LOCALE_KEYS["facts_path"], "m360-facts-path")
        yield from labelled_select(
            _FIELD_LOCALE_KEYS["account_kind"], "m360-account-kind", options["m360-account-kind"]
        )
        yield from labelled_input(_FIELD_LOCALE_KEYS["own_account_id"], "m360-own-account")
        yield from labelled_input(_FIELD_LOCALE_KEYS["iban"], "m360-iban")
        yield from labelled_input(_FIELD_LOCALE_KEYS["swift_bic"], "m360-bic")
        yield from labelled_input(_FIELD_LOCALE_KEYS["bank_name"], "m360-bank-name")
        yield from labelled_input(_FIELD_LOCALE_KEYS["bank_address"], "m360-bank-address")
        yield from labelled_input(_FIELD_LOCALE_KEYS["bank_city"], "m360-bank-city")
        yield from labelled_input(_FIELD_LOCALE_KEYS["bank_country_code"], "m360-bank-country")

    @override
    def form_mounted(self) -> None:
        # Account numbers are typed as secrets, as on the own-account screen.
        for selector in _SECRET_INPUTS:
            self.query_one(selector, Input).password = True
        self._show_action_fields()

    def on_select_changed(self) -> None:
        """Show only the fields the chosen action and account kind take."""
        self._show_action_fields()

    def _show_action_fields(self) -> None:
        if self.select_value("#m360-action") == "remove":
            shown = _REMOVE_FIELDS
        elif self.select_value("#m360-account-kind") == "own_account":
            shown = _OWN_ACCOUNT_FIELDS
        else:
            shown = _REPRESENTANTE_ACCOUNT_FIELDS
        show_fields(self, _ALL_FIELDS, shown)

    @override
    def form_controls(self) -> tuple[str, ...]:
        return ("#m360-action", *(f"#{field}" for field in _ALL_FIELDS))

    @override
    async def read_register(self) -> None:
        result = await self.door(Modelo360SolicitudRequest(profile_id=self.door.profile_id, action="list"))
        self.solicitudes = result.solicitudes

    @override
    def clear_register(self) -> None:
        self.solicitudes = ()
        for selector in _SECRET_INPUTS:
            self.query_one(selector, Input).value = ""

    @override
    def choose_row(self, table_id: str, key: str) -> None:
        chosen = next(item for item in self.solicitudes if str(item.filing_year) == key)
        self.query_one("#register-detail", Static).update(_detail_line(chosen))
        self.set_input("#m360-year", key)

    @override
    async def stage(self) -> tuple[BaseModel, str]:
        year = parse_whole_number(self.input_value("#m360-year"), field_key=_FIELD_LOCALE_KEYS["filing_year"])
        if self.select_value("#m360-action") == "remove":
            removal = Modelo360SolicitudRequest(profile_id=self.door.profile_id, action="remove", filing_year=year)
            return removal, "\n".join(
                (
                    tr(_ACTION_LOCALE_KEYS["remove"]),
                    f"{tr(_FIELD_LOCALE_KEYS['filing_year'])}: {year}",
                )
            )
        path = require_text(self.input_value("#m360-facts-path"), field_key=_FIELD_LOCALE_KEYS["facts_path"])
        facts = await self.door.read_facts(path)
        lines = [
            tr(_ACTION_LOCALE_KEYS["declare"]),
            f"{tr(_FIELD_LOCALE_KEYS['filing_year'])}: {year}",
            tr("tui.modelo.m360_solicitud.source", path=path),
        ]
        if self.select_value("#m360-account-kind") == "own_account":
            own_account_id = require_text(
                self.input_value("#m360-own-account"), field_key=_FIELD_LOCALE_KEYS["own_account_id"]
            )
            declaration = Modelo360SolicitudRequest(
                profile_id=self.door.profile_id,
                action="declare",
                filing_year=year,
                facts=facts,
                own_account_id=own_account_id,
            )
            lines.append(f"{tr(_FIELD_LOCALE_KEYS['own_account_id'])}: {own_account_id}")
            return declaration, "\n".join(lines)
        iban = require_text(self.input_value("#m360-iban"), field_key=_FIELD_LOCALE_KEYS["iban"])
        account = Modelo360RepresentanteAccountInput(
            iban=iban,
            swift_bic=require_text(self.input_value("#m360-bic"), field_key=_FIELD_LOCALE_KEYS["swift_bic"]),
            bank_name=self.input_value("#m360-bank-name").strip(),
            bank_address=self.input_value("#m360-bank-address").strip(),
            bank_city=self.input_value("#m360-bank-city").strip(),
            bank_country_code=self.input_value("#m360-bank-country").strip(),
        )
        declaration = Modelo360SolicitudRequest(
            profile_id=self.door.profile_id,
            action="declare",
            filing_year=year,
            facts=facts,
            representante_account=account,
        )
        lines.append(f"{tr(_FIELD_LOCALE_KEYS['iban'])}: {mask_iban(iban)}")
        return declaration, "\n".join(lines)

    @override
    async def send(self, request: BaseModel) -> RegisterOutcomeV1:
        if not isinstance(request, Modelo360SolicitudRequest) or request.action == "list":
            raise TypeError("the Modelo 360 solicitud screen submits only declarations and removals")
        result = await self.door(request)
        key = str(request.filing_year)
        if request.action == "declare":
            self.selected_key = key
        elif self.selected_key == key:
            self.selected_key = None
        if not result.changed:
            return RegisterOutcomeV1(lines=(tr("tui.modelo.m360_solicitud.unchanged"),))
        done = (
            tr("tui.modelo.m360_solicitud.done_declare")
            if request.action == "declare"
            else tr("tui.modelo.m360_solicitud.done_remove")
        )
        return RegisterOutcomeV1(lines=(done,))


def solicitud_360_tool(door: Modelo360SolicitudDoorV1) -> LedgerToolV1:
    """Offer the Modelo 360 solicitudes from the Records overview."""

    def build(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
        return Modelo360SolicitudScreen(controller, door)

    return LedgerToolV1(
        key=SOLICITUD_360_TOOL_KEY,
        label_key=_SCREEN_LOCALE_KEYS["tool"],
        area=LedgerWorkspaceArea.OVERVIEW,
        build=build,
    )


__all__ = [
    "SOLICITUD_360_TOOL_KEY",
    "Modelo360SolicitudDoorV1",
    "Modelo360SolicitudScreen",
    "solicitud_360_tool",
]
