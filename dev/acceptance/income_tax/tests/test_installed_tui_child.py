"""Focused checks for the installed-TUI child origin guard."""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import pytest
from textual.widgets import OptionList

from .. import installed_tui_child as installed_child_module
from ..installed_tui_child import (
    InstalledTuiChildError,
    _public_surface_diagnostic,
    _wait_for_selector,
    admit_installed_session,
    is_installed_product_origin,
    open_profile_manager_field,
    public_surface_diagnostic,
    run_installed_tui_child_process,
    select_public_data_table_row,
    set_profile_manager_field,
    wait_for_public_selector,
    write_installed_tui_failure_receipt,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_installed_origin_guard_refuses_checkout_source_and_accepts_site_packages(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    source_init = workspace / "src" / "cadrumo" / "__init__.py"
    source_init.parent.mkdir(parents=True)
    source_init.write_text("", encoding="utf-8")
    installed_init = tmp_path / "venv" / "Lib" / "site-packages" / "cadrumo" / "__init__.py"
    installed_init.parent.mkdir(parents=True)
    installed_init.write_text("", encoding="utf-8")

    assert is_installed_product_origin(product_init=source_init, workspace_root=workspace) is False
    assert is_installed_product_origin(product_init=installed_init, workspace_root=workspace) is True


class _Widget:
    def __init__(self, widget_id: str | None) -> None:
        self.id = widget_id


class _Screen:
    id = "root-shell"

    def query(self, selector: str) -> tuple[_Widget, ...]:
        assert selector == "*"
        return ()


class _App:
    def __init__(self) -> None:
        self.screen = _Screen()
        self.queries: list[str] = []

    def query_one(self, selector: str) -> object:
        self.queries.append(selector)
        return object()

    def query(self, selector: str) -> tuple[_Widget, ...]:
        assert selector == "*"
        return (_Widget("home-agenda"), _Widget(None), _Widget("field-passphrase"))


class _Pilot:
    def __init__(self, app: _App) -> None:
        self.app = app

    async def pause(self) -> None:
        raise AssertionError("the selector should be found through the app root")


def test_child_uses_app_root_selectors_and_reports_value_free_surface_ids() -> None:
    app = _App()
    pilot = _Pilot(app)

    asyncio.run(_wait_for_selector(pilot, "#home-agenda", polls=1))

    assert app.queries == ["#home-agenda"]
    assert _public_surface_diagnostic(pilot) == {
        "current_screen_class": "_Screen",
        "current_screen_id": "root-shell",
        "mounted_widget_ids": ["field-passphrase", "home-agenda"],
    }
    assert public_surface_diagnostic is _public_surface_diagnostic
    assert wait_for_public_selector is _wait_for_selector


def test_shared_failure_writer_drops_non_public_diagnostic_values(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    write_installed_tui_failure_receipt(
        path=receipt,
        schema_version="income-01-installed-tui-financial-v1",
        error=InstalledTuiChildError(
            "installed TUI did not expose #ledger-flow-status",
            diagnostic={
                "current_screen_class": "LedgerImportScreen",
                "current_screen_id": "ledger.import",
                "mounted_widget_ids": ["ledger-flow-status", "ledger-flow-status"],
                "rendered_text": "synthetic private invoice fact",
            },
        ),
    )

    assert json.loads(receipt.read_text(encoding="utf-8")) == {
        "diagnostic": {
            "current_screen_class": "LedgerImportScreen",
            "current_screen_id": "ledger.import",
            "mounted_widget_ids": ["ledger-flow-status"],
        },
        "error": "installed TUI did not expose #ledger-flow-status",
        "schema_version": "income-01-installed-tui-financial-v1",
        "status": "failed",
    }


def test_profile_manager_field_opens_the_visible_canonical_row_without_field_selector() -> None:
    class Table:
        rows = (SimpleNamespace(value="identity.tax_id"), SimpleNamespace(value="activities.description"))

        def __init__(self) -> None:
            self.focused = False
            self.cursor_row: int | None = None

        def focus(self) -> None:
            self.focused = True

        def get_row_index(self, row_key: object) -> int:
            return self.rows.index(row_key)

        def move_cursor(self, *, row: int) -> None:
            self.cursor_row = row

    class ManagerScreen:
        def __init__(self, table: Table) -> None:
            self.table = table

        def query(self, expected_type: object) -> tuple[Table, ...]:
            return (self.table,)

    class ManagerPilot:
        def __init__(self, table: Table) -> None:
            self.app = SimpleNamespace(screen=ManagerScreen(table))
            self.keys: list[str] = []

        async def press(self, key: str) -> None:
            self.keys.append(key)

    table = Table()
    pilot = ManagerPilot(table)
    asyncio.run(open_profile_manager_field(pilot=pilot, path="activities.description"))

    assert table.focused is True
    assert table.cursor_row == 1
    assert pilot.keys == ["enter"]


def test_child_process_runner_uses_stdin_credentials_and_hash_only_artifacts(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executable = tmp_path / "venv" / "Scripts" / "python.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    receipt = tmp_path / "artifacts" / "financial.json"
    credential = f"{tmp_path.name}-test-credential"
    observed: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        observed["environment"] = kwargs["env"]
        observed["input"] = kwargs["input"]
        receipt.parent.mkdir(parents=True)
        receipt.write_text('{"status":"proven","private":"not retained by outer evidence"}', encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="child output", stderr="child diagnostic")

    monkeypatch.setenv("PYTHONPATH", "should-not-cross-to-child")
    monkeypatch.setenv("CADRUMO_UNRELATED", "should-not-cross-to-child")
    monkeypatch.setattr(installed_child_module.subprocess, "run", fake_run)

    evidence = run_installed_tui_child_process(
        python_executable=executable,
        workspace_root=workspace,
        child_module="dev.acceptance.income_tax.installed_tui_financial_child",
        child_args=("--receipt", str(receipt)),
        storage_root=tmp_path / "store",
        receipt_path=receipt,
        passphrase=credential,
    )

    environment = observed["environment"]
    assert isinstance(environment, dict)
    assert "PYTHONPATH" not in environment
    assert "CADRUMO_UNRELATED" not in environment
    assert environment["CADRUMO_LOCAL_STORAGE_ROOT"] == str((tmp_path / "store").resolve())
    assert json.loads(str(observed["input"])) == {"profile_passphrase": credential}
    assert evidence.returncode == 0
    assert evidence.receipt_status == "proven"
    assert "private" not in evidence.to_dict()
    assert evidence.receipt_sha256 != ""


def test_child_process_runner_starts_the_interpreter_its_launcher_named(tmp_path: Path, monkeypatch) -> None:
    """The interpreter path is passed through, never canonicalised.

    A POSIX environment's ``bin/python`` is an absolute symlink to the base
    installation, so canonicalising it starts the bare interpreter that seeded
    the environment and the child imports no product at all.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("", encoding="utf-8")
    named = interpreter.parent / ".." / "bin" / interpreter.name
    receipt = tmp_path / "artifacts" / "child.json"
    observed: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        receipt.parent.mkdir(parents=True)
        receipt.write_text('{"status":"proven"}', encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(installed_child_module.subprocess, "run", fake_run)

    run_installed_tui_child_process(
        python_executable=named,
        workspace_root=workspace,
        child_module="dev.acceptance.income_tax.installed_tui_financial_child",
        child_args=("--receipt", str(receipt)),
        storage_root=tmp_path / "store",
        receipt_path=receipt,
        passphrase=secrets.token_urlsafe(16),
    )

    argv = observed["argv"]
    assert isinstance(argv, list)
    assert argv[0] == str(named)


def test_child_process_runner_refuses_an_interpreter_that_is_not_there(tmp_path: Path) -> None:
    """An absent interpreter is refused before a child is started."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(InstalledTuiChildError, match="existing absolute path"):
        run_installed_tui_child_process(
            python_executable=tmp_path / "venv" / "bin" / "python",
            workspace_root=workspace,
            child_module="dev.acceptance.income_tax.installed_tui_financial_child",
            child_args=(),
            storage_root=tmp_path / "store",
            receipt_path=tmp_path / "artifacts" / "child.json",
            passphrase=secrets.token_urlsafe(16),
        )


def test_public_table_row_selection_uses_semantic_key_not_position() -> None:
    class Table:
        rows = (SimpleNamespace(value="ledger.overview"), SimpleNamespace(value="ledger.import"))

        def __init__(self) -> None:
            self.focused = False
            self.cursor_row: int | None = None

        def focus(self) -> None:
            self.focused = True

        def get_row_index(self, row_key: object) -> int:
            return self.rows.index(row_key)

        def move_cursor(self, *, row: int) -> None:
            self.cursor_row = row

    class Screen:
        def query(self, selector: str) -> tuple[object, ...]:
            raise AssertionError(f"screen fallback should not be used for {selector}")

    class App:
        def __init__(self, table: Table) -> None:
            self.table = table
            self.screen = Screen()

        def query_one(self, selector: str, expected_type: object | None = None) -> object:
            assert selector == "#ledger-navigation"
            return self.table

    class Pilot:
        def __init__(self, table: Table) -> None:
            self.app = App(table)
            self.keys: list[str] = []

        async def press(self, key: str) -> None:
            self.keys.append(key)

        async def pause(self) -> None:
            raise AssertionError("public table should be immediately visible")

    table = Table()
    pilot = Pilot(table)
    asyncio.run(
        select_public_data_table_row(
            pilot=pilot,
            table_selector="#ledger-navigation",
            row_key="ledger.import",
        )
    )

    assert table.focused is True
    assert table.cursor_row == 1
    assert pilot.keys == ["enter"]


class _ScriptedSurface:
    """The public selectors an installed session mounts, turn by turn.

    Each ordinary pilot pause moves to the next scripted turn and the last one
    persists, which is how the launcher behaves: the root opens with nothing
    mounted, the first Home arrives, and an unfinished profile's queued setup
    walk then replaces it.  Escape switches to the surface the walk returns to.
    """

    def __init__(self, turns: Sequence[Sequence[str]], *, after_escape: Sequence[str] = ()) -> None:
        self._turns = [frozenset(turn) for turn in turns]
        self._after_escape = frozenset(after_escape)
        self._escaped = False
        self._widgets: dict[str, SimpleNamespace] = {}
        self.keys: list[str] = []
        self.clicks: list[str] = []

    @property
    def mounted(self) -> frozenset[str]:
        return self._after_escape if self._escaped else self._turns[0]

    def widget(self, selector: str) -> SimpleNamespace:
        return self._widgets.setdefault(selector, SimpleNamespace(value=""))

    def advance(self) -> None:
        if not self._escaped and len(self._turns) > 1:
            del self._turns[0]

    def escape(self) -> None:
        self._escaped = True


class _ScriptedApp:
    """Resolve public selectors against whichever scripted turn is mounted."""

    id = "scripted-screen"

    def __init__(self, surface: _ScriptedSurface) -> None:
        self.surface = surface

    @property
    def screen(self) -> _ScriptedApp:
        return self

    def query_one(self, selector: str, expected_type: type[object] | None = None) -> object:
        from textual.css.query import NoMatches

        if selector not in self.surface.mounted:
            raise NoMatches(selector)
        return self.surface.widget(selector)

    def query(self, selector: str) -> tuple[SimpleNamespace, ...]:
        assert selector == "*"
        return tuple(SimpleNamespace(id=item.removeprefix("#")) for item in sorted(self.surface.mounted))


class _ScriptedPilot:
    """Drive a scripted surface through the same pilot calls the harness uses."""

    def __init__(self, surface: _ScriptedSurface) -> None:
        self.app = _ScriptedApp(surface)
        self.surface = surface

    async def pause(self) -> None:
        self.surface.advance()

    async def press(self, key: str) -> None:
        self.surface.keys.append(key)
        if key == "escape":
            self.surface.escape()

    async def click(self, selector: str) -> None:
        self.surface.clicks.append(selector)


def test_admission_leaves_the_setup_walk_an_unfinished_profile_is_handed_to() -> None:
    """A walk that takes the first Home before it can be seen is left, not waited on."""
    surface = _ScriptedSurface(
        [(), (), ("#onboarding-continue",)],
        after_escape=("#home-agenda",),
    )
    pilot = _ScriptedPilot(surface)

    asyncio.run(admit_installed_session(pilot=pilot, passphrase=secrets.token_urlsafe(16), polls=8))

    assert surface.keys == ["escape"]
    assert surface.mounted == frozenset({"#home-agenda"})


def test_admission_leaves_a_setup_walk_that_replaces_an_already_visible_home() -> None:
    """The hand-off is queued with the first Home, so a visible Home is not yet settled."""
    surface = _ScriptedSurface(
        [("#home-agenda",), ("#onboarding-continue",)],
        after_escape=("#home-agenda",),
    )
    pilot = _ScriptedPilot(surface)

    asyncio.run(admit_installed_session(pilot=pilot, passphrase=secrets.token_urlsafe(16), polls=8))

    assert surface.keys == ["escape"]


def test_admission_of_a_settled_profile_touches_no_setup_control() -> None:
    """A profile that has declared setup complete is never offered the walk."""
    surface = _ScriptedSurface([("#home-agenda",)])
    pilot = _ScriptedPilot(surface)

    asyncio.run(admit_installed_session(pilot=pilot, passphrase=secrets.token_urlsafe(16), polls=4))

    assert surface.keys == []
    assert surface.clicks == []


def test_admission_unlocks_through_login_before_leaving_the_setup_walk() -> None:
    """The Login branch types into the visible field, then leaves the walk behind it."""
    surface = _ScriptedSurface(
        [("#field-passphrase", "#btn-unlock"), ("#onboarding-continue",)],
        after_escape=("#home-agenda",),
    )
    credential = secrets.token_urlsafe(16)
    pilot = _ScriptedPilot(surface)

    asyncio.run(admit_installed_session(pilot=pilot, passphrase=credential, polls=8))

    assert surface.clicks == ["#btn-unlock"]
    assert surface.keys == ["escape"]
    assert surface.widget("#field-passphrase").value == credential


def test_profile_manager_choice_uses_visible_option_list_highlight_and_save(monkeypatch) -> None:
    class Options:
        option_count = 3

        def __init__(self) -> None:
            self.highlighted: int | None = None

    class Workers:
        async def wait_for_complete(self) -> None:
            return None

    class Pilot:
        app = SimpleNamespace(workers=Workers())

        def __init__(self) -> None:
            self.clicks: list[str] = []

        async def click(self, selector: str) -> None:
            self.clicks.append(selector)

    async def open_field(*, pilot: object, path: str) -> None:
        assert path == "tax_residence.ccaa"

    async def wait_for_any(pilot: object, selectors: tuple[str, ...], *, polls: int = 80) -> str:
        assert selectors == ("#edit-input", "#edit-options")
        return "#edit-options"

    async def wait_for_selector(pilot: object, selector: str, *, polls: int = 80) -> None:
        assert selector == "#manager-status"

    options = Options()

    def query(pilot: object, selector: str, expected_type: type[object] | None = None) -> object:
        assert selector == "#edit-options"
        assert expected_type is OptionList
        return options

    monkeypatch.setattr(installed_child_module, "open_profile_manager_field", open_field)
    monkeypatch.setattr(installed_child_module, "wait_for_any_public_selector", wait_for_any)
    monkeypatch.setattr(installed_child_module, "wait_for_public_selector", wait_for_selector)
    monkeypatch.setattr(installed_child_module, "query_public_selector", query)

    pilot = Pilot()
    asyncio.run(
        set_profile_manager_field(
            pilot=pilot,
            path="tax_residence.ccaa",
            option_index=1,
        )
    )

    assert options.highlighted == 1
    assert pilot.clicks == ["#btn-edit-save"]
