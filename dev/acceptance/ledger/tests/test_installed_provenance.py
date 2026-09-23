"""Focused checks for the installed Ledger import provenance driver."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from textual.css.query import NoMatches

from dev.acceptance.income_tax.installed_tui_child import InstalledTuiChildError

from ..installed_provenance import (
    _parse_child_receipt,
    _tui_login_session_mode,
    _wait_with_deadline,
    assert_detail_provenance,
    assert_json_provenance,
    assert_track_text_provenance,
    main,
)
from ..installed_tui_journey import LedgerInstalledTuiError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FILE = "ledger-provenance-statement.csv"


def test_track_text_requires_exact_source_and_row_lines() -> None:
    assert_track_text_provenance(f"id\tabc\nimport_source\t{_FILE}\nimport_source_row\t2\n", filename=_FILE, row=2)

    with pytest.raises(LedgerInstalledTuiError, match="track text"):
        assert_track_text_provenance(f"id\tabc\nimport_source\t{_FILE}\n", filename=_FILE, row=2)
    with pytest.raises(LedgerInstalledTuiError, match="track text"):
        assert_track_text_provenance(
            f"import_source\t{_FILE}.bak\nimport_source_row\t2\n",
            filename=_FILE,
            row=2,
        )
    with pytest.raises(LedgerInstalledTuiError, match="track text"):
        assert_track_text_provenance(f"import_source\t{_FILE}\nimport_source_row\t21\n", filename=_FILE, row=2)


def test_json_provenance_refuses_the_older_envelope_without_filename_or_row() -> None:
    assert_json_provenance({"source_filename": _FILE, "source_row_index": 2}, filename=_FILE, row=2, stage="track")

    with pytest.raises(LedgerInstalledTuiError, match="track did not expose"):
        assert_json_provenance({"transaction": {}}, filename=_FILE, row=2, stage="track")
    with pytest.raises(LedgerInstalledTuiError, match="track did not expose"):
        assert_json_provenance({"source_filename": _FILE, "source_row_index": 3}, filename=_FILE, row=2, stage="track")


def test_detail_provenance_requires_the_row_beside_the_filename() -> None:
    assert_detail_provenance(f"Source  {_FILE}:2", filename=_FILE, row=2, stage="detail")

    with pytest.raises(LedgerInstalledTuiError, match="detail did not display"):
        assert_detail_provenance(f"Source  {_FILE}", filename=_FILE, row=2, stage="detail")
    with pytest.raises(LedgerInstalledTuiError, match=r"shown: ledger-prov-cli-ofx\.ofx:3\)"):
        assert_detail_provenance("Source  ledger-prov-cli-ofx.ofx:3", filename=_FILE, row=2, stage="detail")


def test_child_receipt_requires_every_expected_case_observation(tmp_path: Path) -> None:
    receipt = tmp_path / "child.json"
    document = {
        "schema_version": "ledger-01-installed-provenance-v2",
        "status": "proven",
        "mode": "inspect",
        "product_origin": "site-packages",
        "product_init_path": "site-packages/cadrumo/__init__.py",
        "product_init_sha256": "a" * 64,
        "observations": ["tui_detail:cli-csv"],
    }
    receipt.write_text(json.dumps(document), encoding="utf-8")

    parsed = _parse_child_receipt(receipt, mode="inspect", expected=["tui_detail:cli-csv"])
    assert parsed["observations"] == ["tui_detail:cli-csv"]
    with pytest.raises(LedgerInstalledTuiError, match="did not prove every case"):
        _parse_child_receipt(receipt, mode="inspect", expected=["tui_detail:cli-csv", "tui_detail:tui-ofx"])
    with pytest.raises(LedgerInstalledTuiError, match="did not prove every case"):
        _parse_child_receipt(receipt, mode="import", expected=["tui_detail:cli-csv"])


def test_outer_run_refuses_a_used_output_root_with_a_value_free_failed_receipt(tmp_path: Path) -> None:
    environment = tmp_path / "venv" / "Scripts"
    environment.mkdir(parents=True)
    (environment / "aeat.exe").write_bytes(b"synthetic")
    (environment / "python.exe").write_bytes(b"synthetic")
    wheel = tmp_path / "cadrumo-0.0.0-py3-none-any.whl"
    wheel.write_bytes(b"synthetic wheel")
    authority = tmp_path / "authority"
    authority.mkdir()
    output_root = tmp_path / "prior-run"
    output_root.mkdir()
    marker = output_root / "prior-receipt.json"
    marker.write_text("synthetic", encoding="utf-8")
    receipt = tmp_path / "receipt.json"

    exit_code = main(
        [
            "--cli",
            str(environment / "aeat.exe"),
            "--python",
            str(environment / "python.exe"),
            "--wheel",
            str(wheel),
            "--workspace-root",
            str(tmp_path),
            "--authority-root",
            str(authority),
            "--output-root",
            str(output_root),
            "--source-commit",
            "0" * 40,
            "--receipt",
            str(receipt),
        ]
    )

    document = json.loads(receipt.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert document == {
        "diagnostic": "Ledger provenance output root must be fresh and empty",
        "error_type": "LedgerInstalledTuiError",
        "schema_version": "ledger-01-installed-provenance-v2",
        "status": "failed",
    }
    assert marker.read_text(encoding="utf-8") == "synthetic"


def test_outer_run_without_wheel_identity_fails_closed(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"

    exit_code = main(["--workspace-root", str(tmp_path), "--receipt", str(receipt)])

    document = json.loads(receipt.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert document["status"] == "failed"
    assert document["diagnostic"] == "installed provenance outer run lacks its wheel and source inputs"


class _Scope:
    """A widget scope that exposes one selector only after enough loop pauses."""

    def __init__(self, pilot: _SlowRootPilot) -> None:
        self.pilot = pilot
        self.id = "_default"

    def query_one(self, selector: str, *_: object) -> object:
        if self.pilot.pauses >= self.pilot.ready_after and selector == self.pilot.surface:
            return object()
        raise NoMatches(selector)

    def query(self, _selector: str) -> list[object]:
        return []


class _App(_Scope):
    """The root scope, carrying the pushed screen as Textual's app does."""

    def __init__(self, pilot: _SlowRootPilot) -> None:
        super().__init__(pilot)
        self.screen = _Scope(pilot)


class _SlowRootPilot:
    """Pure-logic double for a root that mounts its admission surface late."""

    def __init__(self, *, surface: str, ready_after: int) -> None:
        self.surface = surface
        self.ready_after = ready_after
        self.pauses = 0
        self.app = _App(self)

    async def pause(self, _delay: float | None = None) -> None:
        self.pauses += 1


def test_admission_wait_outlasts_a_slow_root_open() -> None:
    pilot = _SlowRootPilot(surface="#home-agenda", ready_after=400)

    found = asyncio.run(_wait_with_deadline(pilot, ("#field-passphrase", "#home-agenda"), seconds=600.0))

    assert found == "#home-agenda"
    assert pilot.pauses == 400


def test_admission_wait_still_fails_when_the_surface_never_mounts() -> None:
    pilot = _SlowRootPilot(surface="#home-agenda", ready_after=10**9)

    with pytest.raises(InstalledTuiChildError, match="did not expose one of"):
        asyncio.run(_wait_with_deadline(pilot, ("#field-passphrase", "#home-agenda"), seconds=0.0))


class _ProbeCli:
    """Pure-logic double returning one public envelope to the session probe."""

    def __init__(self, document: dict[str, object]) -> None:
        self.document = document
        self.calls: list[dict[str, object]] = []

    def run(
        self, arguments: Sequence[str], /, *, command: str, authenticated: bool, allow_error: bool
    ) -> dict[str, Any]:
        self.calls.append({"arguments": arguments, "command": command, "authenticated": authenticated})
        return self.document


def test_the_session_probe_resumes_when_the_tui_login_persisted_its_session() -> None:
    cli = _ProbeCli({"status": "success", "result": {"rows": []}})

    assert _tui_login_session_mode(cli) == "resumed_tui_session"
    assert cli.calls[0]["authenticated"] is False


def test_the_session_probe_authenticates_when_the_host_had_no_usable_keychain() -> None:
    cli = _ProbeCli({"status": "error", "error": {"code": "AUTH_STORAGE_KEYRING_UNAVAILABLE"}})

    assert _tui_login_session_mode(cli) == "stdin_secret"


def test_the_session_probe_refuses_any_other_error() -> None:
    cli = _ProbeCli({"status": "error", "error": {"code": "REFUSED_CLI_BOUNDARY"}})

    with pytest.raises(LedgerInstalledTuiError, match="unexpected code: REFUSED_CLI_BOUNDARY"):
        _tui_login_session_mode(cli)
