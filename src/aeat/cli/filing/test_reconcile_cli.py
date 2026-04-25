"""Unit tests for the ``aeat filing reconcile`` subcommand (#239)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from ...filing.reconciliation import ReconciliationStatus
from .. import app as root_app
from ._reconcile import _exit_code_for, _infer_ejercicio, reject_forbidden_flags

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


class TestRejectForbiddenFlags:
    @pytest.mark.parametrize(
        "flag",
        [
            "--write",
            "--submit",
            "--enviar",
            "--presentar",
            "--firmar",
            "--modificar",
            "--anular",
            "--send",
            "--commit",
        ],
    )
    def test_forbidden_flag_exits_two(self, flag: str) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            reject_forbidden_flags((flag,))
        assert exc_info.value.exit_code == 2

    def test_equal_form_is_rejected(self) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            reject_forbidden_flags(("--submit=1",))
        assert exc_info.value.exit_code == 2

    def test_read_only_flags_pass(self) -> None:
        # No exception, no exit.
        reject_forbidden_flags(("--json", "--last", "--modelo=100"))

    def test_forbidden_flag_json_mode_raises_cli_boundary_error(self) -> None:
        from .._errors import CliRefusedBoundaryError

        with pytest.raises(CliRefusedBoundaryError):
            reject_forbidden_flags(("--write",), emit_json=True)


class TestInferEjercicio:
    @pytest.mark.parametrize(
        ("period", "expected"),
        [
            ("2023", 2023),
            ("2024", 2024),
            ("2024Q1", 2024),
            ("2024-03", 2024),
            ("2024-1T", 2024),
            ("impositi", None),
            ("", None),
            ("99", None),
        ],
    )
    def test_draft_period_resolution(self, period: str, expected: int | None) -> None:
        assert _infer_ejercicio(period, "100") == expected


class TestExitCodeMapping:
    def test_match_exits_zero(self) -> None:
        assert _exit_code_for(ReconciliationStatus.MATCH) == 0

    def test_divergent_exits_three(self) -> None:
        assert _exit_code_for(ReconciliationStatus.DIVERGENT) == 3

    def test_not_yet_found_exits_four(self) -> None:
        assert _exit_code_for(ReconciliationStatus.NOT_YET_FOUND) == 4


class TestCliSmoke:
    def test_reconcile_help_lists_subcommand(self) -> None:
        from . import app as filing_app

        runner = CliRunner()
        result = runner.invoke(filing_app, ["reconcile", "--help"])
        clean_stdout = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        assert result.exit_code == 0
        assert "reconcile" in clean_stdout.lower()
        assert "--last" in clean_stdout
        assert "--json" in clean_stdout

    def test_write_flag_refused(self) -> None:
        from . import app as filing_app

        runner = CliRunner()
        result = runner.invoke(filing_app, ["reconcile", "--write"])
        assert result.exit_code == 2

    def test_last_without_modelo_period_errors(self, tmp_path) -> None:
        from . import app as filing_app

        runner = CliRunner()
        # Typer's --last uncommitted + no modelo/period triggers BadParameter.
        result = runner.invoke(filing_app, ["reconcile", "--last"])
        # Non-zero exit signals rejection (could be 1 or 2 depending on typer version).
        assert result.exit_code != 0

    def test_root_json_reconcile_missing_drafts_dir_writes_only_stderr(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "missing-drafts"))

        runner = CliRunner()
        result = runner.invoke(root_app, ["--json", "filing", "reconcile", "missing-draft"])

        assert result.exit_code == 2
        assert result.stdout == ""
        payload = json.loads(result.stderr)
        assert payload["error"]["category"] == "REFUSED"
        assert payload["error"]["context"]["drafts_dir"].endswith("missing-drafts")


# ── Helpers ────────────────────────────────────────────────────────────────
#
# Pytest fixtures below are light — the CliRunner-based tests don't touch
# disk or auth. Smoke-level behaviour verification only; full reconcile
# flow coverage lives in aeat.filing.reconciliation.test_reconcile.


def _fixed_now() -> datetime:
    return datetime(2026, 4, 24, 20, 0, 0, tzinfo=UTC)
