"""Focused checks for the installed-TUI child origin guard."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from .. import installed_tui_child as installed_child_module
from ..installed_tui_child import (
    InstalledTuiChildError,
    _public_surface_diagnostic,
    _wait_for_selector,
    is_installed_product_origin,
    open_profile_manager_field,
    public_surface_diagnostic,
    run_installed_tui_child_process,
    select_public_data_table_row,
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
