"""The mounted Withholding destination over the real list projections and the real served request forms.

Each change opens the registered operation's own request form, built from the
request schema the registry publishes for it, so the prefill is proven through
the same form fields a person edits. The door holds the lists in memory: the
screen under test only reads them, and a change it never assembles itself.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID

import pytest
import yaml
from pydantic import BaseModel
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static, TextArea

from cadrumo_client.transport.frontend_client import FrontendClient

from .....application.operations.public_scalar import PublicDecimal
from .....application.operations.registry import OperationRegistry
from .....application.retencion_soportada_absence.ports import RetencionSoportadaAbsencePortsFactory
from .....application.retencion_soportada_absence.registered_operation import (
    build_retencion_soportada_absence_attest_definition,
    build_retencion_soportada_absence_registration,
    build_retencion_soportada_absence_withdraw_definition,
)
from .....application.retencion_soportada_absence.results import (
    RetencionSoportadaAbsenceListProjection,
    RetencionSoportadaAbsenceMutationProjection,
    RetencionSoportadaAbsenceRefusalProjection,
    RetencionSoportadaAbsenceRowProjection,
)
from .....application.retencion_soportada_certificado.ports import RetencionSoportadaCertificadoPortsFactory
from .....application.retencion_soportada_certificado.registered_operation import (
    build_retencion_soportada_mutation_registration,
    build_retencion_soportada_record_definition,
    build_retencion_soportada_remove_definition,
)
from .....application.retencion_soportada_certificado.results import (
    RetencionSoportadaListProjection,
    RetencionSoportadaRowProjection,
)
from .....application.retencion_soportada_certificado.row_words import (
    RetencionSoportadaAmountColumnProjection,
    amount_columns,
    origin_label,
    payer_display_name,
)
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.retencion_soportada import RetencionSoportadaClase
from .....core.retencion_soportada_label import retencion_soportada_clase_label
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.renta.retencion_soportada import RetencionSoportadaOrigen
from .....domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence, RetencionSoportadaAbsenceState
from ...account import AccountSessionExpiredError
from ...components.host import ScreenHostApp
from ...operations.catalogue import OperationCatalogueEntryV1, served_operation_entry
from ...operations.request_form import request_fields
from ...operations.run_screen import OperationRunScreen
from ...tests.settling import settle, settle_until
from ..screen import WithholdingMutation, WithholdingScreen, mutation_refusal_words

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
_YEAR = filing_year_envelope().horizon
_PAYER_REF = "c" * 64
_REFUSAL_WORDS = "The served sentence that explains this refusal."
_SCREEN = Path(__file__).resolve().parents[1] / "screen.py"
_LOCALES_ROOT = Path(__file__).resolve().parents[4] / "locales"


@lru_cache(maxsize=1)
def _registry() -> OperationRegistry:
    certificates = cast(RetencionSoportadaCertificadoPortsFactory, cast(object, lambda **_kwargs: None))
    absences = cast(RetencionSoportadaAbsencePortsFactory, cast(object, lambda **_kwargs: None))
    record = build_retencion_soportada_record_definition(certificates)
    remove = build_retencion_soportada_remove_definition(certificates)
    attest = build_retencion_soportada_absence_attest_definition(absences)
    withdraw = build_retencion_soportada_absence_withdraw_definition(absences)
    # The registry holds its definitions in identity order.
    return OperationRegistry(
        definitions=(attest, record, remove, withdraw),
        public_registrations=(
            build_retencion_soportada_absence_registration(attest),
            build_retencion_soportada_mutation_registration(record),
            build_retencion_soportada_mutation_registration(remove),
            build_retencion_soportada_absence_registration(withdraw),
        ),
    )


def _entry(mutation: WithholdingMutation) -> OperationCatalogueEntryV1:
    registry = _registry()
    description = registry.describe_public_definition(mutation.value)
    definition = registry.lookup(mutation.value)
    contract = description.contract
    assert contract.result_schema is not None
    return served_operation_entry(
        contract,
        description.request_json_schema,
        request_type=definition.request_type,
        result_type=registry.lookup_public_schema_binding(contract.result_schema).model_type,
    )


class _SettledForm(OperationRunScreen):
    """A run screen that reports a settled result once dismissed, standing in for a submitted run."""

    def __init__(self, entry: OperationCatalogueEntryV1, prefill: Mapping[str, object], result: BaseModel | None):
        client = cast(FrontendClient, SimpleNamespace(profile_id=_PROFILE_ID, session_id=_SESSION_ID))
        super().__init__(client, entry, initial=prefill)
        self._result = result

    @property
    @override
    def settled_result(self) -> BaseModel | None:
        return self._result


class _MemoryDoor:
    """Serve fixed lists, open the real served forms, and record every read and form opened."""

    def __init__(
        self,
        records: tuple[RetencionSoportadaRowProjection, ...] = (),
        absences: tuple[RetencionSoportadaAbsenceRowProjection, ...] = (),
    ) -> None:
        self.rows = records
        self.attestations = absences
        self.reads: list[int] = []
        self.columns: tuple[RetencionSoportadaAmountColumnProjection, ...] = amount_columns()
        self.years: tuple[int, ...] = tuple(sorted(filing_year_envelope().years))
        self.forms: list[tuple[WithholdingMutation, dict[str, object]]] = []
        self.settled: BaseModel | None = None
        self.expired = False

    @property
    def profile_id(self) -> UUID:
        return _PROFILE_ID

    async def records(self, ejercicio: int) -> RetencionSoportadaListProjection:
        self.reads.append(ejercicio)
        if self.expired:
            raise AccountSessionExpiredError()
        return RetencionSoportadaListProjection(
            profile_id=_PROFILE_ID,
            ejercicio=ejercicio,
            rows=self.rows,
            amount_columns=self.columns,
            ejercicios=self.years,
        )

    async def absences(self, ejercicio: int) -> RetencionSoportadaAbsenceListProjection:
        return RetencionSoportadaAbsenceListProjection(
            profile_id=_PROFILE_ID, ejercicio=ejercicio, attestations=self.attestations
        )

    def mutation_form(self, mutation: WithholdingMutation, prefill: Mapping[str, object]) -> OperationRunScreen:
        self.forms.append((mutation, dict(prefill)))
        return _SettledForm(_entry(mutation), prefill, self.settled)


def _amount(value: str) -> PublicDecimal:
    return PublicDecimal(decimal=value)


def _record(income_class: RetencionSoportadaClase, payer: str | None) -> RetencionSoportadaRowProjection:
    work = income_class is RetencionSoportadaClase.TRABAJO
    return RetencionSoportadaRowProjection(
        ejercicio=_YEAR,
        income_class=income_class,
        income_class_label=retencion_soportada_clase_label(income_class),
        payer_ref=_PAYER_REF,
        payer_legal_name=payer,
        payer_display_name=payer_display_name(payer),
        importe_integro_dinerario=_amount("1000.00"),
        valoracion_especie=_amount("0"),
        retencion=_amount("150.00"),
        ingreso_a_cuenta=_amount("0"),
        ingreso_a_cuenta_repercutido=_amount("0"),
        reducciones_aplicables=_amount("0") if work else None,
        gastos_deducibles=_amount("0") if work else None,
        pago_a_cuenta=_amount("150.00"),
        origin=RetencionSoportadaOrigen.OPERATOR_DECLARATION,
        origin_label=origin_label(RetencionSoportadaOrigen.OPERATOR_DECLARATION),
        evidence_fingerprint=None,
        revision_id="rev-record-1",
    )


def _absence(
    income_class: RetencionSoportadaClase, state: RetencionSoportadaAbsenceState
) -> RetencionSoportadaAbsenceRowProjection:
    withdrawn = state is RetencionSoportadaAbsenceState.WITHDRAWN
    return RetencionSoportadaAbsenceRowProjection.from_attestation(
        RetencionSoportadaAbsence(
            ejercicio=_YEAR,
            income_class=income_class,
            note="Synthetic note",
            state=state,
            attested_at=datetime(_YEAR, 3, 1, tzinfo=UTC),
            withdrawn_at=datetime(_YEAR, 4, 1, tzinfo=UTC) if withdrawn else None,
        ),
        revision_id=f"rev-absence-{state.value}",
    )


def _cells(table: DataTable[str]) -> list[list[str]]:
    return [[str(cell) for cell in table.get_row_at(row)] for row in range(table.row_count)]


def _headers(table: DataTable[str]) -> list[str]:
    return [str(column.label) for column in table.columns.values()]


def _form_texts(form: OperationRunScreen, entry: OperationCatalogueEntryV1) -> dict[str, str]:
    """Read every entered field of a mounted form from its own widgets."""
    texts: dict[str, str] = {}
    for index, field in enumerate(request_fields(entry.input_json_schema, profile_id=_PROFILE_ID)):
        if field.session_fixed:
            continue
        widget = form.query_one(f"#operation-field-{index}")
        if isinstance(widget, Select):
            value = cast("Select[str]", widget).value
            texts[field.name] = value if isinstance(value, str) else ""
        elif isinstance(widget, Input):
            texts[field.name] = widget.value
        elif isinstance(widget, TextArea):
            texts[field.name] = widget.text
    return texts


async def _read_year(pilot: Pilot[None], screen: WithholdingScreen, text: str) -> None:
    """Type the year while none are on offer; read again the one on offer once the list has served them."""
    if screen.query_one("#withholding-ejercicio", Input).display:
        screen.query_one("#withholding-ejercicio", Input).value = text
    screen.query_one("#withholding-read", Button).press()
    await settle(pilot)


async def _press(pilot: Pilot[None], screen: WithholdingScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await settle(pilot)


def _status(screen: WithholdingScreen) -> str:
    return str(screen.query_one("#withholding-status", Static).render())


@pytest.mark.asyncio
async def test_the_destination_lists_the_served_words_of_both_lists_of_the_year_read() -> None:
    record = _record(RetencionSoportadaClase.TRABAJO, "Synthetic Payer SL")
    absence = _absence(RetencionSoportadaClase.CAPITAL_MOBILIARIO, RetencionSoportadaAbsenceState.ACTIVE)
    door = _MemoryDoor(records=(record,), absences=(absence,))
    screen = WithholdingScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(_YEAR))

            assert door.reads == [_YEAR]
            records = cast("DataTable[str]", screen.query_one("#withholding-records", DataTable))
            assert _headers(records) == [
                tr("tui.withholding.column.income"),
                tr("tui.withholding.column.payer"),
                tr("tui.withholding.column.origin"),
                *(column.label for column in door.columns),
            ]
            # The class and the origin are named in the words the list served, whatever language they came in.
            assert _cells(records) == [
                [
                    record.income_class_label,
                    "Synthetic Payer SL",
                    record.origin_label,
                    "1000.00",
                    "0",
                    "150.00",
                    "0",
                    "0",
                    "0",
                    "0",
                    "150.00",
                ]
            ]
            absences = cast("DataTable[str]", screen.query_one("#withholding-absences", DataTable))
            assert _cells(absences) == [
                [
                    absence.income_class_label,
                    absence.state_label,
                    f"{_YEAR}-03-01",
                    "Synthetic note",
                ]
            ]
            assert _status(screen) == ""


@pytest.mark.asyncio
async def test_a_payer_without_a_name_shows_the_served_words_for_it_and_an_empty_year_says_so() -> None:
    door = _MemoryDoor(records=(_record(RetencionSoportadaClase.CAPITAL_MOBILIARIO, None),))
    screen = WithholdingScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(_YEAR))
            records = cast("DataTable[str]", screen.query_one("#withholding-records", DataTable))
            assert _cells(records)[0][1] == door.rows[0].payer_display_name
            # An amount the record does not state is left blank, not shown as zero.
            assert _cells(records)[0][3:] == ["1000.00", "0", "150.00", "0", "0", "", "", "150.00"]

            door.rows = ()
            await _read_year(pilot, screen, str(_YEAR))
            assert records.row_count == 0
            assert _status(screen) == tr("tui.withholding.status.empty", ejercicio=_YEAR)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["", "twenty", "99"])
async def test_a_year_that_is_not_four_digits_reads_nothing(text: str) -> None:
    door = _MemoryDoor()
    screen = WithholdingScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, text)
            assert _status(screen) == tr("tui.withholding.status.ejercicio_invalid")
            assert screen.ejercicio is None
            await _press(pilot, screen, "withholding-record")
            assert door.forms == []
            assert _status(screen) == tr("tui.withholding.status.read_first")


@pytest.mark.asyncio
async def test_record_opens_the_served_form_with_the_year_and_every_field_the_schema_requires() -> None:
    door = _MemoryDoor()
    screen = WithholdingScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(140, 80)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(_YEAR))
            await _press(pilot, screen, "withholding-record")
            form = pilot.app.screen
            assert isinstance(form, OperationRunScreen)
            entry = _entry(WithholdingMutation.RECORD)
            texts = _form_texts(form, entry)
            assert door.forms == [(WithholdingMutation.RECORD, {"ejercicio": _YEAR})]
            assert texts["ejercicio"] == str(_YEAR)
            # The two work-income figures are offered because the served schema declares them.
            assert {"reducciones_aplicables", "gastos_deducibles", "payer_tax_id"} <= set(texts)


@pytest.mark.asyncio
async def test_remove_prefills_the_selected_record_and_shows_the_served_refusal_words_then_reads_again() -> None:
    door = _MemoryDoor(records=(_record(RetencionSoportadaClase.TRABAJO, "Synthetic Payer SL"),))
    door.settled = RetencionSoportadaAbsenceMutationProjection(
        outcome="refused",
        profile_id=_PROFILE_ID,
        ejercicio=_YEAR,
        refusal=RetencionSoportadaAbsenceRefusalProjection(
            code="REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT",
            reason="stale_revision",
            ejercicio=_YEAR,
            income_class=RetencionSoportadaClase.TRABAJO,
            refusal_words=_REFUSAL_WORDS,
            refusal_words_language=OutputLanguage.EN,
        ),
    )
    screen = WithholdingScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(140, 80)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(_YEAR))
            await _press(pilot, screen, "withholding-remove")
            form = pilot.app.screen
            assert isinstance(form, OperationRunScreen)
            texts = _form_texts(form, _entry(WithholdingMutation.REMOVE))
            assert texts == {
                "ejercicio": str(_YEAR),
                "income_class": RetencionSoportadaClase.TRABAJO.value,
                "payer_ref": _PAYER_REF,
                "expected_revision_id": "rev-record-1",
            }

            form.query_one("#operation-close", Button).press()
            await settle_until(pilot, lambda: pilot.app.screen is screen, "the form returned to the destination")
            assert str(screen.query_one("#withholding-refusal", Static).render()) == _REFUSAL_WORDS
            assert door.reads == [_YEAR, _YEAR]


@pytest.mark.asyncio
async def test_absence_changes_prefill_the_selected_statement_and_withdraw_needs_an_active_one() -> None:
    door = _MemoryDoor(
        absences=(
            _absence(RetencionSoportadaClase.TRABAJO, RetencionSoportadaAbsenceState.WITHDRAWN),
            _absence(RetencionSoportadaClase.CAPITAL_MOBILIARIO, RetencionSoportadaAbsenceState.ACTIVE),
        )
    )
    screen = WithholdingScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(140, 80)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(_YEAR))
            absences = cast("DataTable[str]", screen.query_one("#withholding-absences", DataTable))

            absences.move_cursor(row=0)
            await _press(pilot, screen, "withholding-withdraw")
            assert door.forms == []
            assert _status(screen) == tr("tui.withholding.status.choose_active_absence")

            await _press(pilot, screen, "withholding-attest")
            form = pilot.app.screen
            assert isinstance(form, OperationRunScreen)
            texts = _form_texts(form, _entry(WithholdingMutation.ATTEST_ABSENCE))
            assert texts["income_class"] == RetencionSoportadaClase.TRABAJO.value
            assert texts["expected_revision_id"] == "rev-absence-withdrawn"
            assert texts["note"] == ""
            form.query_one("#operation-close", Button).press()
            await settle_until(pilot, lambda: pilot.app.screen is screen, "the attest form closed")

            absences.move_cursor(row=1)
            await _press(pilot, screen, "withholding-withdraw")
            form = pilot.app.screen
            assert isinstance(form, OperationRunScreen)
            assert door.forms[-1] == (
                WithholdingMutation.WITHDRAW_ABSENCE,
                {
                    "ejercicio": _YEAR,
                    "income_class": RetencionSoportadaClase.CAPITAL_MOBILIARIO.value,
                    "expected_revision_id": "rev-absence-active",
                },
            )
            texts = _form_texts(form, _entry(WithholdingMutation.WITHDRAW_ABSENCE))
            assert texts["expected_revision_id"] == "rev-absence-active"


@pytest.mark.asyncio
async def test_a_lapsed_session_drops_every_row_read_under_it() -> None:
    door = _MemoryDoor(records=(_record(RetencionSoportadaClase.TRABAJO, "Synthetic Payer SL"),))
    screen = WithholdingScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(_YEAR))
            assert screen.query_one("#withholding-records", DataTable).row_count == 1

            door.expired = True
            await _read_year(pilot, screen, str(_YEAR))
            assert screen.query_one("#withholding-records", DataTable).row_count == 0
            assert screen.ejercicio is None
            assert _status(screen) == tr("tui.withholding.status.read_failed")
            assert str(screen.query_one("#withholding-refusal", Static).render())


@pytest.mark.asyncio
async def test_the_amount_columns_are_the_served_ones_in_their_served_order_with_their_served_labels() -> None:
    record = _record(RetencionSoportadaClase.TRABAJO, "Synthetic Payer SL")
    door = _MemoryDoor(records=(record,))
    # A shorter, reordered list proves the screen holds no column list of its own.
    served = {column.field.value: column for column in door.columns}
    door.columns = (served["pago_a_cuenta"], served["retencion"], served["gastos_deducibles"])
    screen = WithholdingScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(_YEAR))
            records = cast("DataTable[str]", screen.query_one("#withholding-records", DataTable))
            assert _headers(records)[3:] == [column.label for column in door.columns]
            assert _cells(records)[0][3:] == ["150.00", "150.00", "0"]


@pytest.mark.asyncio
async def test_after_a_read_the_year_is_picked_from_the_served_ejercicios_and_picking_one_reads_it() -> None:
    door = _MemoryDoor()
    screen = WithholdingScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            typed = screen.query_one("#withholding-ejercicio", Input)
            picker = cast("Select[int]", screen.query_one("#withholding-ejercicio-select", Select))
            assert typed.display and not picker.display

            await _read_year(pilot, screen, str(_YEAR))
            assert picker.display and not typed.display
            assert [value for _label, value in picker._options if value is not Select.NULL] == list(door.years)
            assert picker.value == _YEAR

            other = door.years[0]
            assert other != _YEAR
            picker.value = other
            await settle_until(pilot, lambda: door.reads == [_YEAR, other], "the picked ejercicio was read")
            assert screen.ejercicio == other


@pytest.mark.asyncio
async def test_a_lapsed_session_takes_back_the_offered_ejercicios_for_a_typed_year() -> None:
    door = _MemoryDoor()
    screen = WithholdingScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(_YEAR))
            door.expired = True
            await _read_year(pilot, screen, str(_YEAR))
            assert screen.query_one("#withholding-ejercicio", Input).display
            assert not screen.query_one("#withholding-ejercicio-select", Select).display


def test_refusal_words_are_the_served_ones_and_a_success_has_none() -> None:
    assert mutation_refusal_words(None) is None
    refused = RetencionSoportadaAbsenceMutationProjection(
        outcome="refused",
        profile_id=_PROFILE_ID,
        ejercicio=_YEAR,
        refusal=RetencionSoportadaAbsenceRefusalProjection(
            code="REFUSED_RETENCION_SOPORTADA_ABSENCE",
            reason="records_present",
            ejercicio=_YEAR,
            income_class=RetencionSoportadaClase.TRABAJO,
        ),
    )
    # Served without words, the refusal keeps its registered code rather than a wording made here.
    assert mutation_refusal_words(refused) == "REFUSED_RETENCION_SOPORTADA_ABSENCE"


def _screen_keys() -> set[str]:
    tree = ast.parse(_SCREEN.read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("tui."):
            keys.add(node.value)
    return keys


def _leaf(catalogue: object, key: str) -> object:
    node = catalogue
    for part in key.split("."):
        if not isinstance(node, dict):
            return None
        node = cast("dict[str, object]", node).get(part)
    return node


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_every_chrome_key_the_destination_renders_is_worded_in_each_locale(locale: str) -> None:
    catalogue = yaml.safe_load((_LOCALES_ROOT / locale / "common.yml").read_text(encoding="utf-8"))
    keys = _screen_keys()
    assert {"tui.withholding.status.empty", "tui.withholding.column.origin"} <= keys
    missing = sorted(key for key in keys if not isinstance(_leaf(catalogue, key), str))
    assert missing == []
