"""The Modelo 232 related-party records of one ejercicio and what they decide.

The screen reads the ejercicio's listing through an injected door and draws
only what it serves: the verdict, its basis and note, each ground and its
state, the kind, direction, exclusion, state and source of every record are the
backend's words, and so are the amounts. A counterparty is named by name and
country only, as the listing serves it. A change is never assembled here. Each
one opens the registered operation's own request form, built from the request
schema the runtime serves, prefilled with the revision the listing showed for
the ejercicio or the row it acts on, so preflight, review and the receipt are
the ones every operation uses. A refusal is shown in the words the operation
result serves.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import ClassVar, Final, Protocol, override
from uuid import UUID

from pydantic import BaseModel, ValidationError
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Static

from ....application.m232_related_party.contracts import (
    M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID,
)
from ....application.m232_related_party.results import (
    Modelo232NoneStatementProjection,
    Modelo232OperationProjection,
    Modelo232RelatedPartyListProjection,
    Modelo232RelatedPartyMutationProjection,
    Modelo232TurnoverStatementProjection,
    Modelo232VerdictProjection,
    Modelo232YearProjection,
)
from ....application.operations.public_scalar import PublicDecimal
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....domain.modelos.m232_related_party import Modelo232StatementState
from ..account import AccountSessionExpiredError
from ..components.account_chrome import AccountChromeScreen
from ..components.language import localized
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from ..navigation import TuiScreenContextV1, TuiScreenFactoryV1
from ..operations.run_screen import OperationRunScreen
from ..operations.run_wording import failure_text

OPERACIONES_VINCULADAS_DESTINATION: Final = "workbench.operaciones_vinculadas"


class OperacionesVinculadasMutation(StrEnum):
    """One change the destination offers, named by the registered operation that makes it."""

    STATE_OPERATION = M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID
    WITHDRAW_OPERATION = M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID
    STATE_NONE = M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID
    WITHDRAW_NONE = M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID
    STATE_TURNOVER = M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID
    WITHDRAW_TURNOVER = M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID


class OperacionesVinculadasDoorV1(Protocol):
    """Injected door to the Modelo 232 related-party operations of one admitted profile session."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door names."""
        ...

    async def year(self, ejercicio: int) -> Modelo232RelatedPartyListProjection:
        """Read everything stated for ``ejercicio``, active and withdrawn, and what it decides."""
        ...

    def mutation_form(
        self, mutation: OperacionesVinculadasMutation, prefill: Mapping[str, object]
    ) -> OperationRunScreen:
        """Return the served request form of ``mutation``, its named fields filled from ``prefill``."""
        ...


type _StatedRow = Modelo232OperationProjection | Modelo232NoneStatementProjection | Modelo232TurnoverStatementProjection

_SECTION_LOCALE_KEYS: Final[Mapping[str, tuple[str, str, str]]] = {
    "operation": (
        "tui.operaciones_vinculadas.operations.title",
        "tui.operaciones_vinculadas.action.state_operation",
        "tui.operaciones_vinculadas.action.withdraw_operation",
    ),
    "none": (
        "tui.operaciones_vinculadas.none.title",
        "tui.operaciones_vinculadas.action.state_none",
        "tui.operaciones_vinculadas.action.withdraw_none",
    ),
    "turnover": (
        "tui.operaciones_vinculadas.turnover.title",
        "tui.operaciones_vinculadas.action.state_turnover",
        "tui.operaciones_vinculadas.action.withdraw_turnover",
    ),
}
"""Each list of records: its heading and the controls that state one and withdraw the one selected."""

_STATE_BUTTONS: Final[Mapping[str, OperacionesVinculadasMutation]] = {
    "ov-state-operation": OperacionesVinculadasMutation.STATE_OPERATION,
    "ov-state-none": OperacionesVinculadasMutation.STATE_NONE,
    "ov-state-turnover": OperacionesVinculadasMutation.STATE_TURNOVER,
}
"""The controls that state something new for the ejercicio read, each guarded by the listing's revision."""


def _amount(value: PublicDecimal | None) -> str:
    """An amount as the listing served it; one it does not state is left blank."""
    return "" if value is None else value.decimal


def _optional(text: str | None) -> str:
    return "" if text is None else text


def mutation_refusal_words(result: BaseModel | None) -> str | None:
    """Return the words a settled change's result serves for its refusal, or ``None`` when it was not refused.

    A refusal served without words keeps its registered code; nothing here words a code.
    """
    if not isinstance(result, Modelo232RelatedPartyMutationProjection):
        return None
    refusal = result.refusal
    if refusal is None:
        return None
    return refusal.refusal_words or refusal.code


def verdict_text(verdict: Modelo232VerdictProjection | None) -> str:
    """The verdict in the words it was served with, or the words saying the ejercicio decides nothing here."""
    if verdict is None:
        return tr("tui.operaciones_vinculadas.verdict.unsupported")
    lines = [verdict.obligation_label, verdict.basis_label]
    if verdict.note is not None:
        lines.append(verdict.note)
    lines.append(
        tr(
            "tui.operaciones_vinculadas.verdict.counts",
            counted=verdict.counted_operations,
            excluded=verdict.excluded_operations,
            excluded_total=verdict.excluded_total_eur.decimal,
        )
    )
    return "\n".join(lines)


def _text(key: str, *, classes: str = "") -> Static:
    return localized(Static(tr(key), classes=classes, markup=False), key)


def _button(key: str, button_id: str, *, primary: bool = False) -> Button:
    return localized(Button(tr(key), id=button_id, variant="primary" if primary else "default"), key)


def _section(subject: str, title_key: str, state_key: str, withdraw_key: str) -> ComposeResult:
    """One list of records under its heading, with the controls that state one and withdraw the one selected."""
    yield _text(title_key, classes="cadrumo-heading")
    yield ContentDataTable[str](id=f"ov-{subject}-table", cursor_type="row", zebra_stripes=True)
    with Horizontal(classes="ov-actions"):
        yield _button(state_key, f"ov-state-{subject}")
        yield _button(withdraw_key, f"ov-withdraw-{subject}")


class OperacionesVinculadasScreen(AccountChromeScreen):
    """List one ejercicio's Modelo 232 records and verdict, and open the form of each change."""

    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]
    CSS = BASE_CSS + tokenised("""
    #ov-page { width: 100%; height: 1fr; padding: $cadrumo-space-0 $cadrumo-gutter; }
    .ov-actions { height: auto; margin-bottom: $cadrumo-stack; }
    .ov-actions Button { margin-right: $cadrumo-space-1; }
    #ov-ejercicio { width: $cadrumo-control-min-width; }
    #ov-refusal { color: $warning; height: auto; }
    #ov-status { height: auto; }
    #ov-verdict { height: auto; margin-bottom: $cadrumo-stack; }
    """)

    def __init__(self, door: OperacionesVinculadasDoorV1) -> None:
        """Keep the profile-bound door every read and change goes through."""
        super().__init__(id="operaciones-vinculadas-screen")
        self.door = door
        self.ejercicio: int | None = None
        self.listing: Modelo232YearProjection | None = None
        self._busy = False

    @override
    def compose(self) -> ComposeResult:
        yield _text("tui.destination.operaciones_vinculadas", classes="cadrumo-banner")
        with ContentScroll(id="ov-page"):
            yield _text("tui.operaciones_vinculadas.prompt")
            with Horizontal(classes="ov-actions"):
                yield localized(
                    Input(placeholder=tr("tui.operaciones_vinculadas.ejercicio"), type="integer", id="ov-ejercicio"),
                    "tui.operaciones_vinculadas.ejercicio",
                )
                yield _button("tui.operaciones_vinculadas.action.read", "ov-read", primary=True)
            yield Static("", id="ov-status", markup=False)
            yield Static("", id="ov-refusal", markup=False)
            yield _text("tui.operaciones_vinculadas.verdict.title", classes="cadrumo-heading")
            yield Static("", id="ov-verdict", markup=False)
            yield ContentDataTable[str](id="ov-grounds", cursor_type="row", zebra_stripes=True)
            for subject, locale_keys in _SECTION_LOCALE_KEYS.items():
                yield from _section(subject, *locale_keys)

    def on_mount(self) -> None:
        """Head every table in the language now on screen."""
        self._draw()
        self.query_one("#ov-ejercicio", Input).focus()

    def _table(self, table_id: str) -> DataTable[str]:
        return self.query_one(f"#{table_id}", DataTable)

    def _draw(self) -> None:
        """Draw the verdict and every list as last read, under headings in the language now on screen."""
        listing = self.listing
        verdict = None if listing is None else listing.verdict
        self.query_one("#ov-verdict", Static).update("" if listing is None else verdict_text(verdict))
        self._draw_grounds(verdict)
        self._draw_operations(() if listing is None else listing.operations)
        self._draw_nones(() if listing is None else listing.none_statements)
        self._draw_turnovers(() if listing is None else listing.turnover_statements)

    def _draw_grounds(self, verdict: Modelo232VerdictProjection | None) -> None:
        table = self._table("ov-grounds")
        table.clear(columns=True)
        table.add_columns(
            tr("tui.operaciones_vinculadas.column.ground"),
            tr("tui.operaciones_vinculadas.column.ground_state"),
            tr("tui.operaciones_vinculadas.column.largest_total"),
            tr("tui.operaciones_vinculadas.column.limit"),
        )
        for index, ground in enumerate(() if verdict is None else verdict.grounds):
            table.add_row(
                ground.ground_label,
                ground.state_label,
                _amount(ground.largest_total_eur),
                _amount(ground.limit_eur),
                key=str(index),
            )

    def _draw_operations(self, rows: tuple[Modelo232OperationProjection, ...]) -> None:
        table = self._table("ov-operation-table")
        table.clear(columns=True)
        table.add_columns(
            tr("tui.operaciones_vinculadas.column.kind"),
            tr("tui.operaciones_vinculadas.column.counterparty"),
            tr("tui.operaciones_vinculadas.column.country"),
            tr("tui.operaciones_vinculadas.column.operation_type"),
            tr("tui.operaciones_vinculadas.column.direction"),
            tr("tui.operaciones_vinculadas.column.amount"),
            tr("tui.operaciones_vinculadas.column.exclusion"),
            tr("tui.operaciones_vinculadas.column.state"),
        )
        for index, row in enumerate(rows):
            table.add_row(
                row.operation_kind_label,
                row.counterparty_name,
                row.counterparty_country,
                _optional(row.tipo_operacion),
                _optional(row.direction_label),
                row.amount_eur.decimal,
                _optional(row.exclusion_label),
                row.state_label,
                key=str(index),
            )

    def _draw_nones(self, rows: tuple[Modelo232NoneStatementProjection, ...]) -> None:
        table = self._table("ov-none-table")
        table.clear(columns=True)
        table.add_columns(
            tr("tui.operaciones_vinculadas.column.state"),
            tr("tui.operaciones_vinculadas.column.stated_on"),
            tr("tui.operaciones_vinculadas.column.note"),
        )
        for index, row in enumerate(rows):
            table.add_row(row.state_label, row.stated_at.date().isoformat(), row.note, key=str(index))

    def _draw_turnovers(self, rows: tuple[Modelo232TurnoverStatementProjection, ...]) -> None:
        table = self._table("ov-turnover-table")
        table.clear(columns=True)
        table.add_columns(
            tr("tui.operaciones_vinculadas.column.state"),
            tr("tui.operaciones_vinculadas.column.stated_on"),
            tr("tui.operaciones_vinculadas.column.turnover"),
            tr("tui.operaciones_vinculadas.column.source"),
            tr("tui.operaciones_vinculadas.column.reference"),
        )
        for index, row in enumerate(rows):
            table.add_row(
                row.state_label,
                row.stated_at.date().isoformat(),
                row.turnover_eur.decimal,
                row.source_label,
                row.source_reference,
                key=str(index),
            )

    def _status(self, text: str) -> None:
        self.query_one("#ov-status", Static).update(text)

    def _refusal(self, text: str) -> None:
        self.query_one("#ov-refusal", Static).update(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Read the ejercicio typed in once Enter is pressed."""
        if event.input.id == "ov-ejercicio":
            self._start_read()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch the destination's own controls."""
        button_id = event.button.id or ""
        withdrawals: Mapping[str, Callable[[], None]] = {
            "ov-read": self._start_read,
            "ov-withdraw-operation": self._open_withdraw_operation,
            "ov-withdraw-none": self._open_withdraw_none,
            "ov-withdraw-turnover": self._open_withdraw_turnover,
        }
        state = _STATE_BUTTONS.get(button_id)
        if state is not None:
            self._open_state(state)
        elif button_id in withdrawals:
            withdrawals[button_id]()

    def action_back(self) -> None:
        """Leave the destination."""
        self.dismiss(None)

    def _typed_ejercicio(self) -> int | None:
        try:
            return int(self.query_one("#ov-ejercicio", Input).value.strip())
        except ValueError:
            return None

    def _start_read(self) -> None:
        if self._busy:
            return
        ejercicio = self._typed_ejercicio()
        if ejercicio is None:
            self._status(tr("tui.operaciones_vinculadas.status.ejercicio_invalid"))
            return
        self._busy = True
        self._refusal("")
        self._status(tr("tui.operaciones_vinculadas.status.reading"))
        self.run_worker(self._read(ejercicio), group="ov-read", exclusive=True)

    async def _read(self, ejercicio: int) -> None:
        """Read the listing of ``ejercicio`` and draw it once it was read."""
        try:
            listing = await self.door.year(ejercicio)
        except ValidationError:
            self._status(tr("tui.operaciones_vinculadas.status.ejercicio_invalid"))
            return
        except CadrumoError as error:
            if isinstance(error, AccountSessionExpiredError):
                self._forget()
            self._refusal(failure_text(error))
            self._status(tr("tui.operaciones_vinculadas.status.read_failed"))
            return
        finally:
            self._busy = False
        self.ejercicio = ejercicio
        self.listing = listing.year
        self._draw()
        year = listing.year
        empty = not (year.operations or year.none_statements or year.turnover_statements)
        self._status(tr("tui.operaciones_vinculadas.status.empty", ejercicio=ejercicio) if empty else "")

    def _forget(self) -> None:
        """Drop every row read under a session that has since lapsed."""
        self.ejercicio = None
        self.listing = None
        self._draw()

    def _selected_active[RowT: _StatedRow](self, table_id: str, rows: tuple[RowT, ...]) -> RowT | None:
        """The row under the cursor when it is in force; otherwise say a row in force must be chosen."""
        table = self._table(table_id)
        index = table.cursor_row
        row = rows[index] if rows and table.row_count and 0 <= index < len(rows) else None
        if row is None or row.state is not Modelo232StatementState.ACTIVE:
            self._status(tr("tui.operaciones_vinculadas.status.choose_active"))
            return None
        return row

    def _require_listing(self) -> tuple[int, Modelo232YearProjection] | None:
        if self.ejercicio is None or self.listing is None:
            self._status(tr("tui.operaciones_vinculadas.status.read_first"))
            return None
        return self.ejercicio, self.listing

    def _open_state(self, mutation: OperacionesVinculadasMutation) -> None:
        read = self._require_listing()
        if read is not None:
            ejercicio, listing = read
            # A statement is refused once the ejercicio changed since the listing it was made from.
            self._open(mutation, {"ejercicio": ejercicio, "expected_guard_revision_id": listing.guard_revision_id})

    def _open_withdraw_operation(self) -> None:
        read = self._require_listing()
        if read is None:
            return
        row = self._selected_active("ov-operation-table", read[1].operations)
        if row is not None:
            self._open(
                OperacionesVinculadasMutation.WITHDRAW_OPERATION,
                {"ejercicio": row.ejercicio, "operation_id": row.operation_id, "expected_revision_id": row.revision_id},
            )

    def _open_withdraw_none(self) -> None:
        read = self._require_listing()
        if read is None:
            return
        row = self._selected_active("ov-none-table", read[1].none_statements)
        if row is not None:
            self._open(
                OperacionesVinculadasMutation.WITHDRAW_NONE,
                {"ejercicio": row.ejercicio, "expected_revision_id": row.revision_id},
            )

    def _open_withdraw_turnover(self) -> None:
        read = self._require_listing()
        if read is None:
            return
        row = self._selected_active("ov-turnover-table", read[1].turnover_statements)
        if row is not None:
            self._open(
                OperacionesVinculadasMutation.WITHDRAW_TURNOVER,
                {"ejercicio": row.ejercicio, "expected_revision_id": row.revision_id},
            )

    def _open(self, mutation: OperacionesVinculadasMutation, prefill: Mapping[str, object]) -> None:
        if self._busy:
            return
        self._refusal("")
        self._status("")
        form = self.door.mutation_form(mutation, prefill)

        def settled(_dismissed: None) -> None:
            self._after_change(form)

        self.app.push_screen(form, settled)

    def _after_change(self, form: OperationRunScreen) -> None:
        """Show a refusal in the words its result served, then read the ejercicio again."""
        words = mutation_refusal_words(form.settled_result)
        if words is not None:
            self._refusal(words)
        ejercicio = self.ejercicio
        if ejercicio is None or self._busy:
            return
        self._busy = True
        self.run_worker(self._read(ejercicio), group="ov-read", exclusive=True)

    @override
    async def refresh_language(self) -> None:
        """Reword the chrome and re-head every table, keeping the rows read and the year typed."""
        await super().refresh_language()
        self._draw()


def operaciones_vinculadas_screen_factory(door: OperacionesVinculadasDoorV1) -> TuiScreenFactoryV1:
    """Bind the destination to one profile-bound door."""

    def create(context: TuiScreenContextV1) -> Screen[None]:
        if context.destination != OPERACIONES_VINCULADAS_DESTINATION:
            raise ValueError("the related-party operations factory requires its exact destination")
        return OperacionesVinculadasScreen(door)

    return create


__all__ = [
    "OPERACIONES_VINCULADAS_DESTINATION",
    "OperacionesVinculadasDoorV1",
    "OperacionesVinculadasMutation",
    "OperacionesVinculadasScreen",
    "mutation_refusal_words",
    "operaciones_vinculadas_screen_factory",
    "verdict_text",
]
