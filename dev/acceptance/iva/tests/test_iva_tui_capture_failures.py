"""Failure receipts at the IVA child boundary, without proving product admission."""

from __future__ import annotations

import asyncio
import json
import secrets
from contextlib import nullcontext
from pathlib import Path
from typing import Any, override

import pytest
from rich.console import RenderableType
from textual.app import App, ComposeResult
from textual.widgets import Static

from dev.acceptance.income_tax.installed_tui_child import InstalledTuiChildError

from .. import installed_tui_capture_reopen as child
from .. import iva_tui_child_lifecycle as lifecycle

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _PublicRoot(App[None]):
    """Expose one public identity and private rendered text for receipt filtering."""

    exit_calls = 0

    @override
    def compose(self) -> ComposeResult:
        yield Static("private-rendered-value", id="public-ledger-root")

    @override
    def exit(self, result: None = None, return_code: int = 0, message: RenderableType | None = None) -> None:
        self.exit_calls += 1
        super().exit(result=result, return_code=return_code, message=message)


@pytest.mark.parametrize("failure", ["missing_second_classification", "typed_import_refusal"])
def test_capture_failure_exits_and_writes_failed_receipt_even_when_launcher_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """Exercise the real callback and receipt writer; installed/runtime guards are passive seams."""
    from cadrumo.entrypoints import adapter_composition, exchange_rate_composition
    from cadrumo_runtime.host.frontend.tui import launcher

    app = _PublicRoot()
    passphrase = secrets.token_urlsafe(32)
    classifications: list[str] = []

    async def register(**_kwargs: Any) -> None:
        return None

    async def import_statement(_pilot: Any, **_kwargs: Any) -> None:
        if failure == "typed_import_refusal":
            raise InstalledTuiChildError("installed IVA import refused")

    async def resolve_entries(_pilot: Any, _rows: Any) -> tuple[str, str]:
        return "first-entry", "second-entry"

    async def classify(pilot: Any, *, transaction_id: str, scenario_row: Any) -> None:
        del scenario_row
        classifications.append(transaction_id)
        if transaction_id == "second-entry":
            pilot.app.query_one("#absent-classification-control")

    def launch(*, headless: bool, auto_pilot: Any) -> int:
        assert headless
        asyncio.run(app.run_async(headless=True, auto_pilot=auto_pilot))
        return 0

    monkeypatch.setattr(lifecycle, "installed_product_evidence", lambda **_kwargs: None)
    monkeypatch.setattr(lifecycle, "_assert_installed_source_modules", lambda **_kwargs: None)
    monkeypatch.setattr(lifecycle, "_child_authority", lambda: None)
    monkeypatch.setattr(lifecycle, "_assert_bundled_authority", lambda _authority: None)
    monkeypatch.setattr(lifecycle, "register_profile_through_installed_tui", register)
    monkeypatch.setattr(lifecycle, "_import_statement", import_statement)
    monkeypatch.setattr(lifecycle, "_resolve_imported_transaction_ids", resolve_entries)
    monkeypatch.setattr(lifecycle, "_classify_transaction", classify)
    monkeypatch.setattr(lifecycle, "admitted_session_autopilot", lambda **kwargs: kwargs["drive_after_home"])
    monkeypatch.setattr(adapter_composition, "profile_adapter_composition", nullcontext)
    monkeypatch.setattr(exchange_rate_composition, "live_exchange_rate_composition", nullcontext)
    monkeypatch.setattr(launcher, "main", launch)
    monkeypatch.setattr(child, "read_passphrase_from_stdin", lambda: passphrase)
    receipt_path = tmp_path / "failure.json"

    result = child.main(
        (
            "--child-mode",
            "capture",
            "--workspace-root",
            str(tmp_path),
            "--receipt",
            str(receipt_path),
            "--year",
            "2025",
            "--scratch",
            str(tmp_path / "transient"),
            "--source-manifest-sha256",
            "a" * 64,
            "--source-module",
            "cadrumo.public_module=" + "b" * 64,
        )
    )

    assert result == 2
    assert app.exit_calls == 1
    document = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert document["status"] == "failed"
    if failure == "missing_second_classification":
        assert classifications == ["first-entry", "second-entry"]
        assert document["error"] == "installed IVA TUI public control was absent (stage=classifying_entry_2)"
        assert "public-ledger-root" in document["diagnostic"]["mounted_widget_ids"]
    else:
        assert classifications == []
        assert document["error"] == "installed IVA import refused"
    rendered = receipt_path.read_text(encoding="utf-8")
    assert passphrase not in rendered
    assert "private-rendered-value" not in rendered
    assert "transaction_ids" not in document
