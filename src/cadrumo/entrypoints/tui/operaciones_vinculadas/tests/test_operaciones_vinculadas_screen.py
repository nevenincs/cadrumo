"""The mounted related-party operations destination over the real write path, listing and served request forms.

The door keeps the statements in memory behind the application's own guarded
write path and pinned write authority, and lists them with the listing's own
projections and the verdict the pinned registry derives. Each change opens the
registered operation's own request form, built from the request schema the
registry publishes for it, so the prefill is proven through the same form
fields a person edits; the test then makes the change the run would make with
the values read back from that form.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID, uuid4

import pytest
import yaml
from pydantic import BaseModel
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static, TextArea

from cadrumo_client.transport.frontend_client import FrontendClient

from .....application.aggregation.m232_related_party_repository import (
    Modelo232PinnedWriteAuthority,
    Modelo232RelatedPartyRefusedError,
    Modelo232RelatedPartyRevisionConflictError,
    Modelo232RelatedPartyWritePorts,
    Modelo232Row,
    Modelo232YearView,
    state_m232_none,
    state_m232_operation,
    state_m232_turnover,
    withdraw_m232_none,
    withdraw_m232_operation,
    withdraw_m232_turnover,
)
from .....application.m232_related_party.contracts import (
    M232_RELATED_PARTY_REFUSAL_CODE,
    M232_RELATED_PARTY_REVISION_REFUSAL_CODE,
    Modelo232RelatedPartyOperationRefusalReason,
)
from .....application.m232_related_party.ports import Modelo232RelatedPartyPortsFactory
from .....application.m232_related_party.refusal_words import served_m232_related_party_refusal_words
from .....application.m232_related_party.registered_operation import (
    build_m232_related_party_definition,
    build_m232_related_party_registration,
)
from .....application.m232_related_party.results import (
    Modelo232NoneStatementProjection,
    Modelo232OperationProjection,
    Modelo232RelatedPartyListProjection,
    Modelo232RelatedPartyMutationProjection,
    Modelo232RelatedPartyRefusalProjection,
    Modelo232TurnoverStatementProjection,
    Modelo232YearProjection,
)
from .....application.m232_related_party.verdict import modelo_232_verdict
from .....application.operations.registry import OperationRegistry
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.modelos.m232_related_party import (
    Modelo232Direction,
    Modelo232NoneStatement,
    Modelo232Operation,
    Modelo232OperationKind,
    Modelo232TurnoverSource,
    Modelo232TurnoverStatement,
)
from ...account import AccountSessionExpiredError
from ...components.host import ScreenHostApp
from ...operations.catalogue import OperationCatalogueEntryV1, served_operation_entry
from ...operations.request_form import request_fields
from ...operations.run_screen import OperationRunScreen
from ...tests.settling import settle, settle_until
from ..screen import OperacionesVinculadasMutation, OperacionesVinculadasScreen, mutation_refusal_words, verdict_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
_YEAR = filing_year_envelope().horizon
_TAX_ID = "B99999991"
_NAME = "Synthetic Related Holding SL"
_SCREEN = Path(__file__).resolve().parents[1] / "screen.py"
_LOCALES_ROOT = Path(__file__).resolve().parents[4] / "locales"


@pytest.fixture
def authority() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


@lru_cache(maxsize=1)
def _registry() -> OperationRegistry:
    ports = cast(Modelo232RelatedPartyPortsFactory, cast(object, lambda **_kwargs: None))
    # The registry holds its definitions in identity order.
    definitions = tuple(
        build_m232_related_party_definition(definition_id, ports)
        for definition_id in sorted(mutation.value for mutation in OperacionesVinculadasMutation)
    )
    return OperationRegistry(
        definitions=definitions,
        public_registrations=tuple(build_m232_related_party_registration(item) for item in definitions),
    )


def _entry(mutation: OperacionesVinculadasMutation) -> OperationCatalogueEntryV1:
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


def _row_key(row: Modelo232Row) -> tuple[str, str]:
    if isinstance(row, Modelo232Operation):
        return "operation", row.operation_id
    return row.kind, row.statement_id


@dataclass
class _MemoryStore:
    """Keep each ejercicio's rows and guard revision in memory, committing as the encrypted store does."""

    rows: dict[tuple[str, str], tuple[Modelo232Row, str]] = field(default_factory=dict)
    guards: dict[int, str] = field(default_factory=dict)

    def _stored[RowT: Modelo232Row](self, ejercicio: int, kind: type[RowT]) -> tuple[tuple[RowT, str], ...]:
        return tuple(
            (row, revision)
            for _key, (row, revision) in sorted(self.rows.items())
            if isinstance(row, kind) and row.ejercicio == ejercicio
        )

    def load_operations(self, ejercicio: int) -> tuple[Modelo232Operation, ...]:
        return tuple(row for row, _revision in self._stored(ejercicio, Modelo232Operation))

    def load_none_statements(self, ejercicio: int) -> tuple[Modelo232NoneStatement, ...]:
        return tuple(row for row, _revision in self._stored(ejercicio, Modelo232NoneStatement))

    def load_turnover_statements(self, ejercicio: int) -> tuple[Modelo232TurnoverStatement, ...]:
        return tuple(row for row, _revision in self._stored(ejercicio, Modelo232TurnoverStatement))

    def revision_marker(self, ejercicios: Sequence[int]) -> str:
        return "|".join(self.guards.get(year, ABSENT_SECURE_OBJECT_REVISION_ID) for year in ejercicios)

    def read_year(self, ejercicio: int) -> Modelo232YearView:
        return Modelo232YearView(
            ejercicio=ejercicio,
            guard=None,
            guard_revision_id=self.guards.get(ejercicio, ABSENT_SECURE_OBJECT_REVISION_ID),
            operations=self._stored(ejercicio, Modelo232Operation),
            nones=self._stored(ejercicio, Modelo232NoneStatement),
            turnovers=self._stored(ejercicio, Modelo232TurnoverStatement),
        )

    def commit(self, view: Modelo232YearView, row: Modelo232Row, *, row_expected_revision_id: str) -> str:
        key = _row_key(row)
        stored = self.rows.get(key)
        current = ABSENT_SECURE_OBJECT_REVISION_ID if stored is None else stored[1]
        if self.guards.get(view.ejercicio, ABSENT_SECURE_OBJECT_REVISION_ID) != view.guard_revision_id:
            raise Modelo232RelatedPartyRevisionConflictError
        if current != row_expected_revision_id:
            raise Modelo232RelatedPartyRevisionConflictError
        revision = uuid4().hex
        self.rows[key] = (row, revision)
        self.guards[view.ejercicio] = uuid4().hex
        return revision


class _SettledForm(OperationRunScreen):
    """A run screen that reports the run's settled result once dismissed, standing in for a submitted run.

    The result is the one the test's change produced while the form was open.
    """

    def __init__(
        self,
        entry: OperationCatalogueEntryV1,
        prefill: Mapping[str, object],
        result: Callable[[], BaseModel | None],
    ) -> None:
        client = cast(FrontendClient, SimpleNamespace(profile_id=_PROFILE_ID, session_id=_SESSION_ID))
        super().__init__(client, entry, initial=prefill)
        self._result = result

    @property
    @override
    def settled_result(self) -> BaseModel | None:
        return self._result()


class _RecordsDoor:
    """List the stored statements as the listing operation does, and open the real served forms."""

    def __init__(self, authority: PinnedAuthorityOperation) -> None:
        self.authority = authority
        self.store = _MemoryStore()
        self.ports = Modelo232RelatedPartyWritePorts(
            store=self.store, authority=Modelo232PinnedWriteAuthority(authority)
        )
        self.reads: list[int] = []
        self.forms: list[tuple[OperacionesVinculadasMutation, dict[str, object]]] = []
        self.settled: BaseModel | None = None
        self.expired = False

    @property
    def profile_id(self) -> UUID:
        return _PROFILE_ID

    async def year(self, ejercicio: int) -> Modelo232RelatedPartyListProjection:
        self.reads.append(ejercicio)
        if self.expired:
            raise AccountSessionExpiredError()
        view = self.store.read_year(ejercicio)
        return Modelo232RelatedPartyListProjection(
            profile_id=_PROFILE_ID,
            ejercicio=ejercicio,
            year=Modelo232YearProjection(
                guard_revision_id=view.guard_revision_id,
                operations=tuple(
                    Modelo232OperationProjection.from_operation(row, revision_id=revision)
                    for row, revision in view.operations
                ),
                none_statements=tuple(
                    Modelo232NoneStatementProjection.from_statement(row, revision_id=revision)
                    for row, revision in view.nones
                ),
                turnover_statements=tuple(
                    Modelo232TurnoverStatementProjection.from_statement(row, revision_id=revision)
                    for row, revision in view.turnovers
                ),
                verdict=modelo_232_verdict(self.store, ejercicio, operation=self.authority),
            ),
        )

    def mutation_form(
        self, mutation: OperacionesVinculadasMutation, prefill: Mapping[str, object]
    ) -> OperationRunScreen:
        self.forms.append((mutation, dict(prefill)))
        return _SettledForm(_entry(mutation), prefill, lambda: self.settled)


def _now() -> datetime:
    return datetime(_YEAR, 4, 2, 9, 0, tzinfo=UTC)


def _operation() -> Modelo232Operation:
    return Modelo232Operation(
        operation_id=uuid4().hex,
        ejercicio=_YEAR,
        operation_kind=Modelo232OperationKind.RELATED_PARTY,
        counterparty_tax_id=_TAX_ID,
        counterparty_name=_NAME,
        counterparty_country="DE",
        tipo_vinculacion="D",
        tipo_operacion="06",
        valuation_method="1A",
        direction=Modelo232Direction.PAGO,
        amount_eur=Decimal("1000.00"),
        stated_at=_now(),
    )


def _refused(
    reason: Modelo232RelatedPartyOperationRefusalReason,
) -> Modelo232RelatedPartyMutationProjection:
    """The result a refused run serves, with the words the operation serves for ``reason``."""
    code = M232_RELATED_PARTY_REVISION_REFUSAL_CODE if reason == "stale_revision" else M232_RELATED_PARTY_REFUSAL_CODE
    words, language = served_m232_related_party_refusal_words(reason, error_code=code)
    return Modelo232RelatedPartyMutationProjection(
        outcome="refused",
        profile_id=_PROFILE_ID,
        ejercicio=_YEAR,
        refusal=Modelo232RelatedPartyRefusalProjection.model_validate(
            {
                "code": code,
                "reason": reason,
                "ejercicio": _YEAR,
                "refusal_words": words,
                "refusal_words_language": language,
            }
        ),
    )


def _cells(table: DataTable[str]) -> list[list[str]]:
    return [[str(cell) for cell in table.get_row_at(row)] for row in range(table.row_count)]


def _form_texts(form: OperationRunScreen, entry: OperationCatalogueEntryV1) -> dict[str, str]:
    """Read every entered field of a mounted form from its own widgets."""
    texts: dict[str, str] = {}
    for index, item in enumerate(request_fields(entry.input_json_schema, profile_id=_PROFILE_ID)):
        if item.session_fixed:
            continue
        widget = form.query_one(f"#operation-field-{index}")
        if isinstance(widget, Select):
            value = cast("Select[str]", widget).value
            texts[item.name] = value if isinstance(value, str) else ""
        elif isinstance(widget, Input):
            texts[item.name] = widget.value
        elif isinstance(widget, TextArea):
            texts[item.name] = widget.text
    return texts


async def _read_year(pilot: Pilot[None], screen: OperacionesVinculadasScreen, text: str) -> None:
    screen.query_one("#ov-ejercicio", Input).value = text
    screen.query_one("#ov-read", Button).press()
    await settle(pilot)


async def _press(pilot: Pilot[None], screen: OperacionesVinculadasScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await settle(pilot)


async def _open_form(
    pilot: Pilot[None], screen: OperacionesVinculadasScreen, button_id: str, mutation: OperacionesVinculadasMutation
) -> tuple[OperationRunScreen, dict[str, str]]:
    await _press(pilot, screen, button_id)
    form = pilot.app.screen
    assert isinstance(form, OperationRunScreen)
    return form, _form_texts(form, _entry(mutation))


async def _close(pilot: Pilot[None], screen: OperacionesVinculadasScreen, form: OperationRunScreen) -> None:
    form.query_one("#operation-close", Button).press()
    await settle_until(pilot, lambda: pilot.app.screen is screen, "the form returned to the destination")
    await settle(pilot)


def _text(screen: OperacionesVinculadasScreen, widget_id: str) -> str:
    return str(screen.query_one(f"#{widget_id}", Static).render())


def _rendered(screen: OperacionesVinculadasScreen) -> str:
    """Every word the destination shows: its tables' headings and cells and its own lines."""
    parts: list[str] = [str(widget.render()) for widget in screen.query(Static)]
    for table in screen.query(DataTable):
        parts.extend(str(column.label) for column in table.columns.values())
        parts.extend(cell for row in _cells(cast("DataTable[str]", table)) for cell in row)
    return "\n".join(parts)


@pytest.mark.asyncio
async def test_a_stated_operation_is_listed_by_name_only_and_withdrawn_at_the_revision_listed(
    authority: PinnedAuthorityOperation,
) -> None:
    door = _RecordsDoor(authority)
    screen = OperacionesVinculadasScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(160, 90)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(_YEAR))
            assert door.reads == [_YEAR]
            assert _text(screen, "ov-status") == tr("tui.operaciones_vinculadas.status.empty", ejercicio=_YEAR)
            assert screen.listing is not None and screen.listing.verdict is not None
            assert _text(screen, "ov-verdict") == verdict_text(screen.listing.verdict)
            guard = screen.listing.guard_revision_id

            form, texts = await _open_form(
                pilot, screen, "ov-state-operation", OperacionesVinculadasMutation.STATE_OPERATION
            )
            assert door.forms == [
                (
                    OperacionesVinculadasMutation.STATE_OPERATION,
                    {"ejercicio": _YEAR, "expected_guard_revision_id": guard},
                )
            ]
            assert texts["ejercicio"] == str(_YEAR)
            assert texts["expected_guard_revision_id"] == guard
            # The served schema asks for the counterparty's tax ID, which the listing never shows back.
            assert {"counterparty_tax_id", "counterparty_name", "operation_kind"} <= set(texts)
            stated = _operation()
            revision = state_m232_operation(
                stated, ports=door.ports, expected_guard_revision_id=texts["expected_guard_revision_id"]
            )
            await _close(pilot, screen, form)

            assert door.reads == [_YEAR, _YEAR]
            listed = screen.listing.operations[0]
            table = cast("DataTable[str]", screen.query_one("#ov-operation-table", DataTable))
            assert _cells(table) == [
                [
                    listed.operation_kind_label,
                    _NAME,
                    "DE",
                    "06",
                    listed.direction_label,
                    "1000.00",
                    "",
                    listed.state_label,
                ]
            ]
            assert listed.revision_id == revision
            assert _text(screen, "ov-verdict") == verdict_text(screen.listing.verdict)
            shown = _rendered(screen)
            assert _TAX_ID not in shown

            form, texts = await _open_form(
                pilot, screen, "ov-withdraw-operation", OperacionesVinculadasMutation.WITHDRAW_OPERATION
            )
            assert door.forms[-1] == (
                OperacionesVinculadasMutation.WITHDRAW_OPERATION,
                {"ejercicio": _YEAR, "operation_id": stated.operation_id, "expected_revision_id": revision},
            )
            assert texts["operation_id"] == stated.operation_id
            assert texts["expected_revision_id"] == revision
            withdrawn, _revision = withdraw_m232_operation(
                (_YEAR, texts["operation_id"]),
                at=_now(),
                ports=door.ports,
                expected_revision_id=texts["expected_revision_id"],
            )
            await _close(pilot, screen, form)

            assert _cells(table)[0][-1] == screen.listing.operations[0].state_label
            assert screen.listing.operations[0].state is withdrawn.state
            await _press(pilot, screen, "ov-withdraw-operation")
            assert len(door.forms) == 2
            assert _text(screen, "ov-status") == tr("tui.operaciones_vinculadas.status.choose_active")


@pytest.mark.asyncio
async def test_a_refused_change_shows_the_words_its_result_served_then_reads_again(
    authority: PinnedAuthorityOperation,
) -> None:
    door = _RecordsDoor(authority)
    state_m232_none(
        Modelo232NoneStatement(statement_id=uuid4().hex, ejercicio=_YEAR, note="Synthetic note", stated_at=_now()),
        ports=door.ports,
    )
    screen = OperacionesVinculadasScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(160, 90)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(_YEAR))
            assert screen.listing is not None
            nones = cast("DataTable[str]", screen.query_one("#ov-none-table", DataTable))
            listed = screen.listing.none_statements[0]
            assert _cells(nones) == [[listed.state_label, f"{_YEAR}-04-02", "Synthetic note"]]

            # The write path refuses an operation while the statement of none stands.
            form, texts = await _open_form(
                pilot, screen, "ov-state-operation", OperacionesVinculadasMutation.STATE_OPERATION
            )
            with pytest.raises(Modelo232RelatedPartyRefusedError) as refused:
                state_m232_operation(
                    _operation(), ports=door.ports, expected_guard_revision_id=texts["expected_guard_revision_id"]
                )
            none_stated = _refused(refused.value.reason)
            door.settled = none_stated
            await _close(pilot, screen, form)
            served = none_stated.refusal
            assert served is not None and served.refusal_words is not None
            assert _text(screen, "ov-refusal") == served.refusal_words
            assert door.reads == [_YEAR, _YEAR]

            # A withdrawal made against a revision that moved since is refused in the words served for it.
            door.settled = None
            form, texts = await _open_form(
                pilot, screen, "ov-withdraw-none", OperacionesVinculadasMutation.WITHDRAW_NONE
            )
            assert texts["expected_revision_id"] == listed.revision_id
            with pytest.raises(Modelo232RelatedPartyRevisionConflictError):
                withdraw_m232_none(_YEAR, at=_now(), ports=door.ports, expected_revision_id="moved")
            stale = _refused("stale_revision")
            door.settled = stale
            await _close(pilot, screen, form)
            assert stale.refusal is not None and stale.refusal.refusal_words is not None
            assert _text(screen, "ov-refusal") == stale.refusal.refusal_words
            assert stale.refusal.refusal_words != served.refusal_words


@pytest.mark.asyncio
async def test_a_stated_turnover_is_listed_with_its_served_source_and_withdrawn_at_its_revision(
    authority: PinnedAuthorityOperation,
) -> None:
    door = _RecordsDoor(authority)
    screen = OperacionesVinculadasScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(160, 90)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(_YEAR))
            form, texts = await _open_form(
                pilot, screen, "ov-state-turnover", OperacionesVinculadasMutation.STATE_TURNOVER
            )
            assert screen.listing is not None
            assert texts["expected_guard_revision_id"] == screen.listing.guard_revision_id
            assert {"turnover_eur", "source", "source_reference"} <= set(texts)
            statement = Modelo232TurnoverStatement(
                statement_id=uuid4().hex,
                ejercicio=_YEAR,
                turnover_eur=Decimal("2500000.00"),
                source=Modelo232TurnoverSource.ANNUAL_ACCOUNTS,
                source_reference="Synthetic annual accounts",
                stated_at=_now(),
            )
            revision = state_m232_turnover(
                statement, ports=door.ports, expected_guard_revision_id=texts["expected_guard_revision_id"]
            )
            await _close(pilot, screen, form)

            listed = screen.listing.turnover_statements[0]
            table = cast("DataTable[str]", screen.query_one("#ov-turnover-table", DataTable))
            assert _cells(table) == [
                [listed.state_label, f"{_YEAR}-04-02", "2500000.00", listed.source_label, "Synthetic annual accounts"]
            ]

            form, texts = await _open_form(
                pilot, screen, "ov-withdraw-turnover", OperacionesVinculadasMutation.WITHDRAW_TURNOVER
            )
            assert door.forms[-1] == (
                OperacionesVinculadasMutation.WITHDRAW_TURNOVER,
                {"ejercicio": _YEAR, "expected_revision_id": revision},
            )
            assert texts["expected_revision_id"] == revision
            withdraw_m232_turnover(
                _YEAR, at=_now(), ports=door.ports, expected_revision_id=texts["expected_revision_id"]
            )
            await _close(pilot, screen, form)
            assert _cells(table)[0][0] == screen.listing.turnover_statements[0].state_label
            assert _cells(table)[0][0] != listed.state_label


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["", "twenty", "99"])
async def test_a_year_that_is_not_four_digits_reads_nothing(authority: PinnedAuthorityOperation, text: str) -> None:
    door = _RecordsDoor(authority)
    screen = OperacionesVinculadasScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(160, 90)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, text)
            assert _text(screen, "ov-status") == tr("tui.operaciones_vinculadas.status.ejercicio_invalid")
            assert screen.ejercicio is None
            await _press(pilot, screen, "ov-state-turnover")
            assert door.forms == []
            assert _text(screen, "ov-status") == tr("tui.operaciones_vinculadas.status.read_first")


@pytest.mark.asyncio
async def test_a_year_the_registry_decides_nothing_for_says_so(authority: PinnedAuthorityOperation) -> None:
    door = _RecordsDoor(authority)
    screen = OperacionesVinculadasScreen(door)
    below_floor = filing_year_envelope().floor - 1
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(160, 90)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(below_floor))
            assert screen.listing is not None and screen.listing.verdict is None
            assert _text(screen, "ov-verdict") == tr("tui.operaciones_vinculadas.verdict.unsupported")
            assert screen.query_one("#ov-grounds", DataTable).row_count == 0


@pytest.mark.asyncio
async def test_a_lapsed_session_drops_every_row_read_under_it(authority: PinnedAuthorityOperation) -> None:
    door = _RecordsDoor(authority)
    state_m232_operation(_operation(), ports=door.ports)
    screen = OperacionesVinculadasScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(160, 90)) as pilot:
            await settle(pilot)
            await _read_year(pilot, screen, str(_YEAR))
            assert screen.query_one("#ov-operation-table", DataTable).row_count == 1

            door.expired = True
            await _read_year(pilot, screen, str(_YEAR))
            assert screen.query_one("#ov-operation-table", DataTable).row_count == 0
            assert screen.listing is None and screen.ejercicio is None
            assert _text(screen, "ov-verdict") == ""
            assert _text(screen, "ov-status") == tr("tui.operaciones_vinculadas.status.read_failed")
            assert _text(screen, "ov-refusal")


def test_refusal_words_are_the_served_ones_and_a_success_has_none() -> None:
    assert mutation_refusal_words(None) is None
    refused = Modelo232RelatedPartyMutationProjection(
        outcome="refused",
        profile_id=_PROFILE_ID,
        ejercicio=_YEAR,
        refusal=Modelo232RelatedPartyRefusalProjection(
            code=M232_RELATED_PARTY_REFUSAL_CODE, reason="not_stated", ejercicio=_YEAR
        ),
    )
    # Served without words, the refusal keeps its registered code rather than a wording made here.
    assert mutation_refusal_words(refused) == M232_RELATED_PARTY_REFUSAL_CODE


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
    assert {"tui.operaciones_vinculadas.verdict.counts", "tui.operaciones_vinculadas.action.withdraw_turnover"} <= keys
    missing = sorted(key for key in keys if not isinstance(_leaf(catalogue, key), str))
    assert missing == []
