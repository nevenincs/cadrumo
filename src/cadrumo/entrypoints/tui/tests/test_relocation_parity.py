"""Real parity proofs for the completed canonical TUI relocations.

The feature packages deliberately expose no convenience facade.  These tests
therefore name each defining module directly, drive the shipped Textual apps
through real application doors, and inspect the live source AST for the
retired topology.  They deliberately stop before the future root application
and navigation join: that join must consume these independent feature
surfaces, rather than becoming a substitute for proving them.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest
from pydantic import BaseModel
from textual.css.query import NoMatches
from textual.widgets import DataTable, Input, Static

from ....application.flows import CopyRef, FlowDefinition, FlowPage, FlowSection
from ....application.user_profile import build_profile_overview, login_profile, logout_active_profile
from ....application.user_profile.login_interaction import attempt_profile_login, profile_login_choices
from ....core import assess_profile_password, require_active_bucket_id
from ....core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from ....entrypoints.cli import attempt_registration, persist_active_profile_field
from ....tests.modelo_work_review import build_real_modelo_work_review
from ....tests.profile_capsule import load_test_profile_record
from ....tests.secure_sql import isolated_profile_storage_root
from ..devtools._journal import Session, read_session, write_session
from ..devtools._replay import replay, screenshot
from ..flows.app import FlowTuiApp
from ..modelo.view.work_review import ModeloWorkReviewApp
from ..profile.overview import ProfileManagerApp
from ..secret.app import LoginApp, RecoveryWordsScreen, RegistrationApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TERMINAL_SIZE = (140, 60)
_LABEL = "Relocation parity operator"
_PASSPHRASE = "relocation-parity-operator-secret"  # noqa: S105 - synthetic test fixture

_CANONICAL_DEFINITIONS = (
    ("cadrumo.entrypoints.tui.profile.overview", "ProfileManagerApp"),
    ("cadrumo.entrypoints.tui.profile.status", "StatusApp"),
    ("cadrumo.entrypoints.tui.secret.app", "LoginApp"),
    ("cadrumo.entrypoints.tui.secret.app", "RegistrationApp"),
    ("cadrumo.entrypoints.tui.secret.app", "RecoveryWordsScreen"),
    ("cadrumo.entrypoints.tui.flows.app", "FlowTuiApp"),
    ("cadrumo.entrypoints.tui.modelo.view.work_review", "ModeloWorkReviewApp"),
    ("cadrumo.entrypoints.tui.modelo.view.work_review", "ModeloWorkReviewScreen"),
    ("cadrumo.entrypoints.tui.devtools._journal", "Session"),
    ("cadrumo.entrypoints.tui.devtools._replay", "replay"),
    ("cadrumo.entrypoints.tui.devtools._replay", "screenshot"),
)

_INERT_NAMESPACES = (
    "cadrumo.entrypoints.tui",
    "cadrumo.entrypoints.tui.components",
    "cadrumo.entrypoints.tui.profile",
    "cadrumo.entrypoints.tui.secret",
    "cadrumo.entrypoints.tui.flows",
    "cadrumo.entrypoints.tui.modelo",
    "cadrumo.entrypoints.tui.modelo.view",
    "cadrumo.entrypoints.tui.devtools",
)


class _FlowAnswers(BaseModel):
    """A one-field flow model used to exercise the real renderer."""


def _copy() -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="wizard.setup.title")


def _flow_definition() -> FlowDefinition:
    copy = _copy()
    return FlowDefinition(
        id="flows.test.relocation-parity",
        title=copy,
        description=copy,
        sections=(
            FlowSection(
                id="relocation-parity",
                title=copy,
                items=(
                    FlowPage(
                        id="operator_name",
                        widget=FlowWidgetKind.TEXT,
                        prompt=copy,
                        answer_type=str,
                    ),
                ),
            ),
        ),
        answers_model=_FlowAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


def _import_targets(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            targets.append(node.module)
    return tuple(targets)


def test_relocated_symbols_have_single_canonical_defining_modules_and_inert_facades() -> None:
    """Every completed relocation is reached through its defining module only."""
    for module_name, symbol_name in _CANONICAL_DEFINITIONS:
        module = importlib.import_module(module_name)
        symbol = getattr(module, symbol_name)
        assert symbol.__module__ == module_name

    for namespace_name in _INERT_NAMESPACES:
        namespace = importlib.import_module(namespace_name)
        assert namespace.__all__ == ()
        source_path = Path(namespace.__file__ or "")
        imports = [
            target
            for target in _import_targets(source_path)
            if target != "__future__" and not target.startswith("from __future__")
        ]
        assert not imports, f"{namespace_name} is a forwarding facade: {imports}"


@pytest.mark.asyncio
async def test_profile_and_secret_apps_preserve_the_real_custody_path(tmp_path: Path) -> None:
    """Register, unlock, and render an actual encrypted profile through relocated apps."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        registration = RegistrationApp(assess=assess_profile_password, register=attempt_registration)
        async with registration.run_test(size=_TERMINAL_SIZE) as pilot:
            registration.query_one("#field-username", Input).value = _LABEL
            registration.query_one("#field-password", Input).value = _PASSPHRASE
            registration.query_one("#field-confirm", Input).value = _PASSPHRASE
            await pilot.click("#btn-create")
            for _ in range(100):
                if isinstance(registration.screen, RecoveryWordsScreen):
                    candidate = registration.screen
                    if candidate.query("#words-value") and candidate.query("#btn-confirm-words"):
                        break
                await pilot.pause(0.1)
            assert isinstance(registration.screen, RecoveryWordsScreen)
            recovery = registration.screen
            words = recovery.query_one("#words-value", Static)
            assert str(words.render())
            recovery.query_one("#field-recovery-verification", Input).value = str(words.render())
            await pilot.click("#btn-confirm-words")
            await registration.workers.wait_for_complete()
            await pilot.pause()

        assert registration.error is None
        assert registration.outcome is not None
        profile_id = str(registration.outcome.profile_id)
        logout_active_profile()

        login = LoginApp(choices=profile_login_choices(), authenticate=attempt_profile_login)
        async with login.run_test(size=_TERMINAL_SIZE) as pilot:
            login.query_one("#field-passphrase", Input).value = _PASSPHRASE
            await pilot.click("#btn-unlock")
            await login.workers.wait_for_complete()
            await pilot.pause()

        assert login.outcome is not None
        assert login.outcome.bucket_id == profile_id
        # Textual executes the authentication request on a worker, whose
        # context-local session cannot become this test task's session.  Enter
        # the same public login door here before asking the real record store
        # for the manager's injected projection.
        login_profile(name=_LABEL, passphrase_callback=lambda: _PASSPHRASE)
        record = load_test_profile_record(require_active_bucket_id())
        overview = build_profile_overview(record, label=_LABEL)
        manager = ProfileManagerApp(overview, persist=persist_active_profile_field)
        async with manager.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            rendered_rows = sum(table.row_count for table in manager.query(DataTable))
            assert rendered_rows == overview.total_count
            assert overview.total_count > overview.present_count
            manager.exit(None)


@pytest.mark.asyncio
async def test_flow_and_modelo_review_project_real_application_contracts(tmp_path: Path) -> None:
    """The relocated flow and read-only review render authoritative application data."""
    flow = FlowTuiApp(_flow_definition(), mode=FlowMode.MODIFY, registered_values={})
    async with flow.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"Ada")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.click("#btn-submit")
        await pilot.pause()

    assert flow.final_state is not None
    assert dict(flow.final_state.answers) == {"operator_name": "Ada"}

    review = build_real_modelo_work_review(tmp_path, modelo="100", filing_year=2024, period_code="0A")
    review_app = ModeloWorkReviewApp(review)
    async with review_app.run_test(size=(160, 48)) as pilot:
        await pilot.pause()
        casillas = review_app.screen.query_one("#modelo-review-casillas-table", DataTable)
        assert review.casillas
        assert casillas.row_count == len(review.casillas)
        with pytest.raises(NoMatches):
            review_app.screen.query_one(Input)
        review_app.exit(None)


def test_devtool_journal_replays_and_exports_a_live_canonical_surface(tmp_path: Path) -> None:
    """The moved harness owns a durable gesture journal and reads the real compositor."""
    session = Session(surface="registration", width=100, height=30, theme="dark", locale="en")
    journal = tmp_path / "relocation-parity.jsonl"
    write_session(journal, session)

    restored = read_session(journal)
    assert restored == session
    frame = replay(restored)
    assert frame.surface == session.surface
    assert frame.width == session.width
    assert frame.height == session.height
    assert frame.text
    assert frame.chain

    rendered = tmp_path / "relocation-parity.svg"
    assert screenshot(restored, str(rendered)) == str(rendered)
    svg = rendered.read_text(encoding="utf-8")
    assert "<svg" in svg
