"""The setup screen renders the registry's rows, runs each row's one action, and reports an unreachable runtime.

The screen runs headless under Textual's test pilot. Its door is a recording
stand-in that answers with rows derived by the real registry, so what is
checked is the screen's own decisions: which rows and sentences it shows,
which action a row's button runs, and that an unreachable runtime is
reported as unavailable rather than acted around.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_ids import DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID

from .....application.dependency_contracts import (
    DependencyCheckMode,
    DependencyPlanPart,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencyStatusRow,
    combine_plan_parts,
)
from .....application.dependency_registry import (
    build_setup_plan,
    dependency_item_declarations,
    derive_dependency_row,
    is_setup_complete,
)
from .....application.dependency_setup_operation import (
    DEPENDENCIES_OPERATION_SUBJECT,
    DependencyPlanEntryViewV1,
    DependencyPlanPartViewV1,
    DependencySetupResultV1,
    DependencySetupReviewV2,
    DependencyStatusResultV1,
)
from .....application.dependency_wording import dependency_row_wording
from .....application.operations.frontend_projection import OperationPublicProjectionV1
from .....application.operations.models import OperationIdentity
from .....core.config import override_settings
from .....core.storage_taxonomy import StorageCategory
from .....tests.async_condition import until
from ...components.host import ScreenHostApp
from ...operations.controller_port import OperationControllerPort
from ..screen import SetupScreen, setup_review_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SIZE = (120, 40)


def _rows(*, absent: frozenset[str]) -> tuple[DependencyStatusRow, ...]:
    return tuple(
        derive_dependency_row(
            declaration,
            DependencyProbeReading(
                item_id=declaration.item_id,
                mode=DependencyCheckMode.QUICK,
                outcome=DependencyProbeOutcome.ABSENT
                if declaration.item_id in absent
                else DependencyProbeOutcome.PRESENT,
            ),
        )
        for declaration in dependency_item_declarations()
    )


def _status(rows: tuple[DependencyStatusRow, ...]) -> DependencyStatusResultV1:
    return DependencyStatusResultV1(
        mode=DependencyCheckMode.QUICK, rows=rows, complete=is_setup_complete(rows), hardware_limited=False
    )


@dataclass
class _Door:
    """Answers with registry rows and records each request; ``unreachable`` stands for a lost runtime."""

    absent: set[str]
    unreachable: bool = False
    calls: list[tuple[str, object]] = field(default_factory=list)

    def _answer(self) -> DependencyStatusResultV1:
        if self.unreachable:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        return _status(_rows(absent=frozenset(self.absent)))

    async def read_status(self, mode: DependencyCheckMode) -> DependencyStatusResultV1:
        self.calls.append(("status", mode))
        return self._answer()

    async def verify(self, item_ids: tuple[str, ...] | None) -> DependencyStatusResultV1:
        self.calls.append(("verify", item_ids))
        return self._answer()

    async def start_setup(self, item_ids: tuple[str, ...] | None) -> OperationControllerPort:
        self.calls.append(("setup", item_ids))
        raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    async def setup_result(
        self, controller: OperationControllerPort, projection: OperationPublicProjectionV1
    ) -> DependencySetupResultV1:
        raise AssertionError("no setup settles in these tests")


async def _settled(pilot: Pilot[object], screen: SetupScreen) -> None:
    await until(pilot, lambda: not screen.query_one("#btn-setup-check", Button).disabled)


@pytest.mark.asyncio
async def test_the_screen_shows_every_registry_row_with_its_plain_sentence_and_action() -> None:
    door = _Door(absent={"browser", "local_ai"})
    screen = SetupScreen(door)
    with override_settings(cadrumo_output_language="en"):
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            table = screen.query_one("#setup-items", DataTable)
            shown = [tuple(str(cell) for cell in table.get_row_at(index)) for index in range(table.row_count)]
            set_up_all = screen.query_one("#btn-setup-all", Button)

            assert [row.item_id for row in screen.rows] == [d.item_id for d in dependency_item_declarations()]
            for row, cells in zip(screen.rows, shown, strict=True):
                declaration = next(d for d in dependency_item_declarations() if d.item_id == row.item_id)
                wording = dependency_row_wording(row, declaration)
                assert cells[1] == wording.sentence
                assert cells[2] == (wording.action or "")
            assert screen.status_text == "Some components are not ready yet."
            assert set_up_all.disabled is False
            assert door.calls == [("status", DependencyCheckMode.QUICK)]


@pytest.mark.asyncio
async def test_the_rows_are_software_only_and_the_local_ai_is_one_row() -> None:
    door = _Door(absent={"local_ai"})
    screen = SetupScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            table = screen.query_one("#setup-items", DataTable)
            names = [str(table.get_row_at(index)[0]) for index in range(table.row_count)]

            assert names == ["Browser for the tax agency website", "Local AI"]
            assert all("Google" not in name for name in names)
            screen.act_on("google")
            await pilot.pause()
            assert [name for name, _ in door.calls] == ["status"]


@pytest.mark.asyncio
async def test_an_absent_item_row_starts_setup_for_that_item_only() -> None:
    door = _Door(absent={"browser"})
    screen = SetupScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)
            screen.act_on("browser")
            await pilot.pause()
            await _settled(pilot, screen)

            assert ("setup", ("browser",)) in door.calls
            assert "background service could not be reached" in screen.status_text


@pytest.mark.asyncio
async def test_an_unreachable_runtime_is_reported_and_nothing_is_set_up() -> None:
    door = _Door(absent={"browser"}, unreachable=True)
    screen = SetupScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=_SIZE) as pilot:
            await _settled(pilot, screen)

            assert screen.status_text.startswith("Cadrumo's background service could not be reached")
            assert screen.rows == ()
            assert screen.query_one("#btn-setup-all", Button).disabled is True
            assert [name for name, _ in door.calls] == ["status"]


def test_the_review_words_the_plan_and_shows_a_licence_notice_before_approval() -> None:
    parts = (
        DependencyPlanPart(
            part_id="program",
            download_bytes=None,
            source_hosts=("github.com",),
            destination=None,
            installs_outside_program=True,
        ),
        DependencyPlanPart(
            part_id="text_extraction",
            download_bytes=3 * 1024**3,
            source_hosts=("registry.example.org",),
            destination=StorageCategory.OLLAMA_MODELS,
            target_version="example-model:7b",
        ),
    )
    entry = combine_plan_parts("local_ai", parts, destination=StorageCategory.OLLAMA_MODELS)
    plan = build_setup_plan([entry], free_bytes=100 * 1024**3)
    part_views = (
        DependencyPlanPartViewV1(part_id="program", name="The program that runs the models", download_bytes=None),
        DependencyPlanPartViewV1(part_id="text_extraction", name="Model for document text", download_bytes=3 * 1024**3),
    )
    notice = "This model's licence does not permit commercial use."
    review = DependencySetupReviewV2(
        identity=OperationIdentity(
            operation_id="d" * 64,
            definition_id=DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID,
            subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
        ),
        revision=1,
        plan_digest="e" * 64,
        entries=(
            DependencyPlanEntryViewV1(
                entry=entry, destination_path="/storage/models", licence_notice=notice, parts=part_views
            ),
        ),
        known_download_bytes=plan.known_download_bytes,
        has_unknown_size=plan.has_unknown_size,
        installs_outside_program=plan.installs_outside_program,
        space=plan.space,
        space_sufficient=True,
        reviewed_proposal_digest="f" * 64,
    )

    with override_settings(cadrumo_output_language="en"):
        text = setup_review_text(review)

    assert text.splitlines() == [
        "Cadrumo will set up:",
        "Local AI: 3.0 GB from github.com, registry.example.org",
        "    The program that runs the models: size not known yet",
        "    Model for document text: 3.0 GB",
        "  Stored in /storage/models",
        "  This installs a program on this computer. Its installer may ask for your permission.",
        f"  {notice}",
        "Total download: at least 3.0 GB. Some sizes are only known once the download starts.",
    ]
