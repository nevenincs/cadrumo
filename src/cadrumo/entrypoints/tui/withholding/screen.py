"""The payer records and statements of no withholding of one ejercicio.

The screen reads both lists through an injected door and draws only what they
serve: the income class's label, the payer's name and the statement's note are
the backend's words. A change is never assembled here. Each one opens the
registered operation's own request form, built from the request schema the
runtime serves, prefilled with the coordinates of the row it acts on, so
preflight, review and the receipt are the ones every operation uses. A refusal
is shown in the words the operation result serves.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar, Final, Protocol, override
from uuid import UUID

from pydantic import BaseModel, ValidationError
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Static

from ....application.retencion_soportada_absence.contracts import (
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
)
from ....application.retencion_soportada_absence.results import (
    RetencionSoportadaAbsenceListProjection,
    RetencionSoportadaAbsenceMutationProjection,
    RetencionSoportadaAbsenceRowProjection,
)
from ....application.retencion_soportada_certificado.contracts import (
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID,
)
from ....application.retencion_soportada_certificado.results import (
    RetencionSoportadaListProjection,
    RetencionSoportadaMutationProjection,
    RetencionSoportadaRowProjection,
)
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....domain.renta.retencion_soportada_absence import RetencionSoportadaAbsenceState
from ..account import AccountSessionExpiredError
from ..components.account_chrome import AccountChromeScreen
from ..components.language import localized
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from ..navigation import TuiScreenContextV1, TuiScreenFactoryV1
from ..operations.run_screen import OperationRunScreen
from ..operations.run_wording import failure_text

WITHHOLDING_DESTINATION: Final = "workbench.withholding"

_PAYER_REF_SHOWN: Final = 12
"""How many characters of a payer's keyed reference name a payer the record serves no name for."""


class WithholdingMutation(StrEnum):
    """One change the destination offers, named by the registered operation that makes it."""

    RECORD = RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID
    REMOVE = RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID
    ATTEST_ABSENCE = RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID
    WITHDRAW_ABSENCE = RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID


class WithholdingDoorV1(Protocol):
    """Injected door to the withholding operations of one admitted profile session."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door names."""
        ...

    async def records(self, ejercicio: int) -> RetencionSoportadaListProjection:
        """Read every payer record of ``ejercicio``."""
        ...

    async def absences(self, ejercicio: int) -> RetencionSoportadaAbsenceListProjection:
        """Read every statement of no withholding of ``ejercicio``, active and withdrawn."""
        ...

    def mutation_form(self, mutation: WithholdingMutation, prefill: Mapping[str, object]) -> OperationRunScreen:
        """Return the served request form of ``mutation``, its named fields filled from ``prefill``."""
        ...


def _payer(row: RetencionSoportadaRowProjection) -> str:
    return row.payer_legal_name or row.payer_ref[:_PAYER_REF_SHOWN]


_ABSENCE_STATE_LOCALE_KEYS: Final[Mapping[RetencionSoportadaAbsenceState, str]] = {
    RetencionSoportadaAbsenceState.ACTIVE: "tui.withholding.absence.state.active",
    RetencionSoportadaAbsenceState.WITHDRAWN: "tui.withholding.absence.state.withdrawn",
}


def _absence_state(state: RetencionSoportadaAbsenceState) -> str:
    return tr(_ABSENCE_STATE_LOCALE_KEYS[state])


def mutation_refusal_words(result: BaseModel | None) -> str | None:
    """Return the words a settled change's result serves for its refusal, or ``None`` when it was not refused.

    A refusal served without words keeps its registered code; nothing here words a code.
    """
    if not isinstance(result, (RetencionSoportadaMutationProjection, RetencionSoportadaAbsenceMutationProjection)):
        return None
    refusal = result.refusal
    if refusal is None:
        return None
    return refusal.refusal_words or refusal.code


class WithholdingScreen(AccountChromeScreen):
    """List one ejercicio's payer records and statements, and open the form of each change."""

    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]
    CSS = BASE_CSS + tokenised("""
    #withholding-page { width: 100%; height: 1fr; padding: $cadrumo-space-0 $cadrumo-gutter; }
    .withholding-actions { height: auto; margin-bottom: $cadrumo-stack; }
    .withholding-actions Button { margin-right: $cadrumo-space-1; }
    #withholding-ejercicio { width: 16; }
    #withholding-refusal { color: $warning; height: auto; }
    #withholding-status { height: auto; }
    """)

    def __init__(self, door: WithholdingDoorV1) -> None:
        """Keep the profile-bound door every read and change goes through."""
        super().__init__(id="withholding-screen")
        self.door = door
        self.ejercicio: int | None = None
        self.records: tuple[RetencionSoportadaRowProjection, ...] = ()
        self.absences: tuple[RetencionSoportadaAbsenceRowProjection, ...] = ()
        self._busy = False

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr("tui.destination.withholding"), classes="cadrumo-banner", markup=False),
            "tui.destination.withholding",
        )
        with ContentScroll(id="withholding-page"):
            yield localized(Static(tr("tui.withholding.prompt"), markup=False), "tui.withholding.prompt")
            with Horizontal(classes="withholding-actions"):
                yield localized(
                    Input(placeholder=tr("tui.withholding.ejercicio"), type="integer", id="withholding-ejercicio"),
                    "tui.withholding.ejercicio",
                )
                yield localized(
                    Button(tr("tui.withholding.action.read"), id="withholding-read", variant="primary"),
                    "tui.withholding.action.read",
                )
            yield Static("", id="withholding-status", markup=False)
            yield Static("", id="withholding-refusal", markup=False)
            yield localized(
                Static(tr("tui.withholding.records.title"), classes="cadrumo-heading", markup=False),
                "tui.withholding.records.title",
            )
            yield ContentDataTable[str](id="withholding-records", cursor_type="row", zebra_stripes=True)
            with Horizontal(classes="withholding-actions"):
                yield localized(
                    Button(tr("tui.withholding.action.record"), id="withholding-record"),
                    "tui.withholding.action.record",
                )
                yield localized(
                    Button(tr("tui.withholding.action.remove"), id="withholding-remove"),
                    "tui.withholding.action.remove",
                )
            yield localized(
                Static(tr("tui.withholding.absences.title"), classes="cadrumo-heading", markup=False),
                "tui.withholding.absences.title",
            )
            yield ContentDataTable[str](id="withholding-absences", cursor_type="row", zebra_stripes=True)
            with Horizontal(classes="withholding-actions"):
                yield localized(
                    Button(tr("tui.withholding.action.attest_absence"), id="withholding-attest"),
                    "tui.withholding.action.attest_absence",
                )
                yield localized(
                    Button(tr("tui.withholding.action.withdraw_absence"), id="withholding-withdraw"),
                    "tui.withholding.action.withdraw_absence",
                )

    def on_mount(self) -> None:
        """Head both tables in the language now on screen."""
        self._draw()
        self.query_one("#withholding-ejercicio", Input).focus()

    def _records_table(self) -> DataTable[str]:
        return self.query_one("#withholding-records", DataTable)

    def _absences_table(self) -> DataTable[str]:
        return self.query_one("#withholding-absences", DataTable)

    def _draw(self) -> None:
        """Draw both lists as last read, under headings in the language now on screen."""
        records = self._records_table()
        records.clear(columns=True)
        records.add_columns(tr("tui.withholding.column.income"), tr("tui.withholding.column.payer"))
        for index, row in enumerate(self.records):
            records.add_row(row.income_class_label, _payer(row), key=str(index))
        absences = self._absences_table()
        absences.clear(columns=True)
        absences.add_columns(
            tr("tui.withholding.column.income"),
            tr("tui.withholding.column.state"),
            tr("tui.withholding.column.attested_on"),
            tr("tui.withholding.column.note"),
        )
        for index, item in enumerate(self.absences):
            absences.add_row(
                item.income_class_label,
                _absence_state(item.state),
                item.attested_at.date().isoformat(),
                item.note,
                key=str(index),
            )

    def _status(self, text: str) -> None:
        self.query_one("#withholding-status", Static).update(text)

    def _refusal(self, text: str) -> None:
        self.query_one("#withholding-refusal", Static).update(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Read the ejercicio typed in once Enter is pressed."""
        if event.input.id == "withholding-ejercicio":
            self._start_read()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch the destination's own controls."""
        button_id = event.button.id
        if button_id == "withholding-read":
            self._start_read()
        elif button_id == "withholding-record":
            self._open_record()
        elif button_id == "withholding-remove":
            self._open_remove()
        elif button_id == "withholding-attest":
            self._open_attest()
        elif button_id == "withholding-withdraw":
            self._open_withdraw()

    def action_back(self) -> None:
        """Leave the destination."""
        self.dismiss(None)

    def _start_read(self) -> None:
        if self._busy:
            return
        text = self.query_one("#withholding-ejercicio", Input).value.strip()
        try:
            ejercicio = int(text)
        except ValueError:
            self._status(tr("tui.withholding.status.ejercicio_invalid"))
            return
        self._busy = True
        self._refusal("")
        self._status(tr("tui.withholding.status.reading"))
        self.run_worker(self._read(ejercicio), group="withholding-read", exclusive=True)

    async def _read(self, ejercicio: int) -> None:
        """Read both lists of ``ejercicio`` and draw them only once both were read."""
        try:
            records = await self.door.records(ejercicio)
            absences = await self.door.absences(ejercicio)
        except ValidationError:
            self._status(tr("tui.withholding.status.ejercicio_invalid"))
            return
        except CadrumoError as error:
            if isinstance(error, AccountSessionExpiredError):
                self._forget()
            self._refusal(failure_text(error))
            self._status(tr("tui.withholding.status.read_failed"))
            return
        finally:
            self._busy = False
        self.ejercicio = ejercicio
        self.records = records.rows
        self.absences = absences.attestations
        self._draw()
        empty = not self.records and not self.absences
        self._status(tr("tui.withholding.status.empty", ejercicio=ejercicio) if empty else "")

    def _forget(self) -> None:
        """Drop every row read under a session that has since lapsed."""
        self.ejercicio = None
        self.records = ()
        self.absences = ()
        self._draw()

    def _selected[RowT](self, table: DataTable[str], rows: tuple[RowT, ...]) -> RowT | None:
        if not rows or table.row_count == 0:
            return None
        index = table.cursor_row
        return rows[index] if 0 <= index < len(rows) else None

    def _require_ejercicio(self) -> int | None:
        if self.ejercicio is None:
            self._status(tr("tui.withholding.status.read_first"))
        return self.ejercicio

    def _open_record(self) -> None:
        ejercicio = self._require_ejercicio()
        if ejercicio is not None:
            self._open(WithholdingMutation.RECORD, {"ejercicio": ejercicio})

    def _open_remove(self) -> None:
        ejercicio = self._require_ejercicio()
        if ejercicio is None:
            return
        row = self._selected(self._records_table(), self.records)
        if row is None:
            self._status(tr("tui.withholding.status.choose_record"))
            return
        self._open(
            WithholdingMutation.REMOVE,
            {
                "ejercicio": row.ejercicio,
                "income_class": row.income_class.value,
                "payer_ref": row.payer_ref,
                "expected_revision_id": row.revision_id,
            },
        )

    def _open_attest(self) -> None:
        ejercicio = self._require_ejercicio()
        if ejercicio is None:
            return
        prefill: dict[str, object] = {"ejercicio": ejercicio}
        selected = self._selected(self._absences_table(), self.absences)
        if selected is not None and selected.state is RetencionSoportadaAbsenceState.WITHDRAWN:
            # Attesting again over a withdrawn statement replaces it at the revision it was left at.
            prefill.update(income_class=selected.income_class.value, expected_revision_id=selected.revision_id)
        self._open(WithholdingMutation.ATTEST_ABSENCE, prefill)

    def _open_withdraw(self) -> None:
        ejercicio = self._require_ejercicio()
        if ejercicio is None:
            return
        selected = self._selected(self._absences_table(), self.absences)
        if selected is None or selected.state is not RetencionSoportadaAbsenceState.ACTIVE:
            self._status(tr("tui.withholding.status.choose_active_absence"))
            return
        self._open(
            WithholdingMutation.WITHDRAW_ABSENCE,
            {
                "ejercicio": selected.ejercicio,
                "income_class": selected.income_class.value,
                "expected_revision_id": selected.revision_id,
            },
        )

    def _open(self, mutation: WithholdingMutation, prefill: Mapping[str, object]) -> None:
        if self._busy:
            return
        self._refusal("")
        self._status("")
        form = self.door.mutation_form(mutation, prefill)

        def settled(_dismissed: None) -> None:
            self._after_change(form)

        self.app.push_screen(form, settled)

    def _after_change(self, form: OperationRunScreen) -> None:
        """Show a refusal in the words its result served, then read the lists again."""
        words = mutation_refusal_words(form.settled_result)
        if words is not None:
            self._refusal(words)
        ejercicio = self.ejercicio
        if ejercicio is None or self._busy:
            return
        self._busy = True
        self.run_worker(self._read(ejercicio), group="withholding-read", exclusive=True)

    @override
    async def refresh_language(self) -> None:
        """Reword the chrome and re-head both tables, keeping the rows read and the year typed."""
        await super().refresh_language()
        self._draw()


def withholding_screen_factory(door: WithholdingDoorV1) -> TuiScreenFactoryV1:
    """Bind the destination to one profile-bound door."""

    def create(context: TuiScreenContextV1) -> Screen[None]:
        if context.destination != WITHHOLDING_DESTINATION:
            raise ValueError("the withholding factory requires its exact destination")
        return WithholdingScreen(door)

    return create


__all__ = [
    "WITHHOLDING_DESTINATION",
    "WithholdingDoorV1",
    "WithholdingMutation",
    "WithholdingScreen",
    "mutation_refusal_words",
    "withholding_screen_factory",
]
