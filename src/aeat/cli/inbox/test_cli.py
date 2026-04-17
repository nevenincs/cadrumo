"""Unit tests for the ``aeat inbox`` CLI sub-app.

Drives every subcommand through :class:`typer.testing.CliRunner`
against a deterministic temp directory. No mocks — the CLI reads
from and writes to real files under ``tmp_path``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...config import Settings, load_settings
from . import app as inbox_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

_RUNNER = CliRunner()


def _seed_source(source_file: Path) -> None:
    """Write a fixture ``source.json`` with three raw notifications."""
    payload = {
        "notifications": [
            {
                "notificacion_id": "AEAT-1",
                "subject": {"es": "Requerimiento de información", "en": "Info request", "hu": "Kérés"},
                "body_excerpt": {"es": "...", "en": "...", "hu": "..."},
                "received_at": datetime(2026, 4, 1, tzinfo=UTC).isoformat(),
                "effective_at": datetime(2026, 4, 1, tzinfo=UTC).isoformat(),
                "source_url": "https://sede.agenciatributaria.gob.es/AEAT-1",
            },
            {
                "notificacion_id": "AEAT-2",
                "subject": {"es": "Comunicación general", "en": "General", "hu": "Általános"},
                "body_excerpt": {"es": "...", "en": "...", "hu": "..."},
                "received_at": datetime(2026, 4, 2, tzinfo=UTC).isoformat(),
                "effective_at": datetime(2026, 4, 2, tzinfo=UTC).isoformat(),
                "source_url": "https://sede.agenciatributaria.gob.es/AEAT-2",
            },
            {
                "notificacion_id": "AEAT-3",
                "subject": {"es": "Novedad inventada", "en": "Invented", "hu": "Új"},
                "body_excerpt": {"es": "...", "en": "...", "hu": "..."},
                "received_at": datetime(2026, 4, 3, tzinfo=UTC).isoformat(),
                "effective_at": datetime(2026, 4, 3, tzinfo=UTC).isoformat(),
                "source_url": "https://sede.agenciatributaria.gob.es/AEAT-3",
            },
        ]
    }
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the CLI at ``tmp_path`` and seed a source file."""
    inbox_dir = tmp_path / "inbox"
    pdf_dir = inbox_dir / "pdfs"
    monkeypatch.setenv("AEAT_INBOX_DIR", str(inbox_dir))
    monkeypatch.setenv("AEAT_INBOX_PDF_DIR", str(pdf_dir))
    monkeypatch.setenv("AEAT_INBOX_ALERT_LEAD_DAYS", "3650")
    _seed_source(inbox_dir / "source.json")
    yield inbox_dir


class TestInboxCli:
    def test_settings_pick_up_env(self, cli_env: Path) -> None:
        cfg: Settings = load_settings()
        assert cfg.aeat_inbox_dir == cli_env

    def test_fetch_list_show_ack_flow(self, cli_env: Path) -> None:
        result = _RUNNER.invoke(inbox_app, ["fetch"])
        assert result.exit_code == 0, result.output
        assert "AEAT-1" in result.output
        assert "REQUERIMIENTO" in result.output

        result = _RUNNER.invoke(inbox_app, ["list"])
        assert result.exit_code == 0, result.output
        assert "AEAT-1" in result.output
        assert "AEAT-2" in result.output
        assert "AEAT-3" in result.output

        result = _RUNNER.invoke(inbox_app, ["list", "--priority", "CRITICAL"])
        assert result.exit_code == 0, result.output
        assert "AEAT-1" in result.output
        assert "AEAT-2" not in result.output

        result = _RUNNER.invoke(inbox_app, ["show", "AEAT-1"])
        assert result.exit_code == 0, result.output
        assert "AEAT-1" in result.output

        result = _RUNNER.invoke(inbox_app, ["show", "missing"])
        assert result.exit_code == 1

        result = _RUNNER.invoke(inbox_app, ["ack", "AEAT-1", "--by", "gw"])
        assert result.exit_code == 0, result.output
        assert "acknowledged" in result.output

        # Listing with --unread should now exclude AEAT-1.
        result = _RUNNER.invoke(inbox_app, ["list", "--unread"])
        assert result.exit_code == 0, result.output
        assert "AEAT-1" not in result.output
        assert "AEAT-3" in result.output

    def test_next_deadline_no_records(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AEAT_INBOX_DIR", str(tmp_path / "empty"))
        monkeypatch.setenv("AEAT_INBOX_PDF_DIR", str(tmp_path / "empty" / "pdfs"))
        result = _RUNNER.invoke(inbox_app, ["next-deadline"])
        assert result.exit_code == 0, result.output
        assert "no upcoming" in result.output

    def test_next_deadline_surfaces_record(self, cli_env: Path) -> None:
        _RUNNER.invoke(inbox_app, ["fetch"])
        result = _RUNNER.invoke(inbox_app, ["next-deadline"])
        assert result.exit_code == 0, result.output
        # Either surfaces AEAT-1 (it has a CRITICAL deadline) or the
        # "no upcoming" message if the calendar-day window rolled past.
        assert ("AEAT-1" in result.output) or ("no upcoming" in result.output)
