"""Historical export selects retained filing content through the real command route."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from typer.core import TyperCommand

from .. import historical_export_cli as bridge
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_historical_export_help_exposes_exact_filing_selection() -> None:
    result = invoke_cached_cli(["--language", "en", "app", "modelo", "filing-record", "export", "--help"])
    assert result.exit_code == 0, result.output
    assert "{filing_record_id}" in result.output
    assert "--output" in result.output


def test_historical_export_routes_retained_revision_without_current_fallback(monkeypatch, tmp_path: Path) -> None:
    calls = []
    context = typer.Context(TyperCommand("test"))
    monkeypatch.setattr(
        bridge,
        "read_modelo_filing_record_view",
        lambda _ctx, **kw: (
            SimpleNamespace(calculation_revision_id="b" * 64),
            SimpleNamespace(effective="newer-current-observations"),
            SimpleNamespace(availability="available"),
        ),
    )
    monkeypatch.setattr(bridge, "export_calculation_review_cli", lambda *args, **kwargs: calls.append((args, kwargs)))
    bridge.export_historical_filing_cli(context, "a" * 64, tmp_path / "history.xlsx")
    assert calls[0][0][1] == "b" * 64
    assert calls[0][1]["filing_record_id"] == "a" * 64


def test_missing_historical_content_refuses_without_publishing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        bridge,
        "read_modelo_filing_record_view",
        lambda _ctx, **kw: (
            SimpleNamespace(calculation_revision_id="b" * 64),
            None,
            SimpleNamespace(availability="missing"),
        ),
    )
    monkeypatch.setattr(bridge, "export_calculation_review_cli", lambda *args: pytest.fail("must not publish"))
    with pytest.raises(typer.BadParameter):
        bridge.export_historical_filing_cli(typer.Context(TyperCommand("test")), "a" * 64, tmp_path / "missing.xlsx")
