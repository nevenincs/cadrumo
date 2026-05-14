"""CLI surface tests for `aeat app live {expedientes, verify, borrador} ...`."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.application.live._borrador import BorradorPrefillEntry, BorradorService
from aeat.application.live._verify import VerifyService, VerifySurface
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.entrypoints.cli._app_live import (
    borrador_100_app,
    expedientes_app,
    verify_app,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'live.db').as_posix()}")
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_AUDIT_DIR", str(tmp_path / "audit"))
    dispose_engine()
    try:
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="default"),
        )
        yield
    finally:
        dispose_engine()


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


class TestExpedientesSubgroup:
    def test_expedientes_list_is_empty_on_fresh_bucket(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(expedientes_app, ["list"])
        assert result.exit_code == 0, result.output
        assert "count\t0" in result.output

    def test_expedientes_show_refuses_unknown_snapshot(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(expedientes_app, ["show", "no-such-id"])
        assert result.exit_code != 0

    def test_expedientes_latest_is_dash_on_fresh_bucket(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(expedientes_app, ["latest"])
        assert result.exit_code == 0, result.output
        assert "snapshot_id\t-" in result.output


class TestVerifySubgroup:
    def test_verify_list_is_empty_on_fresh_bucket(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(verify_app, ["list"])
        assert result.exit_code == 0, result.output
        assert "count\t0" in result.output

    def test_verify_list_refuses_unknown_surface(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(verify_app, ["list", "--surface", "not-a-surface"])
        assert result.exit_code != 0

    def test_verify_list_accepts_known_surface(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(verify_app, ["list", "--surface", "nif_iva"])
        assert result.exit_code == 0, result.output

    def test_verify_show_refuses_unknown_observation(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(verify_app, ["show", "no-such-observation"])
        assert result.exit_code != 0

    def test_verify_latest_renders_persisted_observation(self, cli_runner: CliRunner) -> None:
        # Seed an observation via the service surface so the CLI has
        # something to render.
        bucket_id = "default"
        VerifyService().record(
            bucket_id=bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="ESB12345678",
            verdict="valid",
            checked_at=datetime(2025, 3, 15, tzinfo=UTC),
        )
        result = cli_runner.invoke(
            verify_app, ["latest", "--surface", "nif_iva", "--nif", "ESB12345678"],
        )
        assert result.exit_code == 0, result.output
        assert "nif\tESB12345678" in result.output
        assert "verdict\tvalid" in result.output

    def test_verify_latest_renders_dash_when_no_observation(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(
            verify_app, ["latest", "--surface", "tgvi", "--nif", "B99999999"],
        )
        assert result.exit_code == 0, result.output
        assert "observation_id\t-" in result.output


class TestBorrador100Subgroup:
    def test_borrador_100_list_is_empty_on_fresh_bucket(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(borrador_100_app, ["list"])
        assert result.exit_code == 0, result.output
        assert "count\t0" in result.output

    def test_borrador_100_latest_is_dash_when_no_snapshot(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(borrador_100_app, ["latest", "--tax-year", "2024"])
        assert result.exit_code == 0, result.output
        assert "snapshot_id\t-" in result.output

    def test_borrador_100_show_refuses_unknown_snapshot(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(borrador_100_app, ["show", "no-such-id"])
        assert result.exit_code != 0

    def test_borrador_100_full_lifecycle_via_service_seed(
        self, cli_runner: CliRunner,
    ) -> None:
        bucket_id = "default"
        BorradorService().capture(
            bucket_id=bucket_id,
            tax_year=2024,
            captured_at=datetime(2025, 3, 15, tzinfo=UTC),
            source_url="https://www2.agenciatributaria.gob.es/wlpl/PRET-R210/SimuladorOpenAjax",
            prefill_entries=(
                BorradorPrefillEntry(
                    casilla_id="0100",
                    value=Decimal("1000.00"),
                    source_label="rendimientos del trabajo",
                ),
            ),
        )

        listed = cli_runner.invoke(borrador_100_app, ["list"])
        assert listed.exit_code == 0, listed.output
        assert "count\t1" in listed.output
        assert "active" in listed.output

        latest = cli_runner.invoke(borrador_100_app, ["latest", "--tax-year", "2024"])
        assert latest.exit_code == 0, latest.output
        assert "tax_year\t2024" in latest.output

        # Pick the snapshot id off the latest row to drive show + discard.
        snapshot_id = next(
            line.split("\t", 1)[1]
            for line in latest.output.splitlines()
            if line.startswith("snapshot_id\t")
        )
        shown = cli_runner.invoke(borrador_100_app, ["show", snapshot_id])
        assert shown.exit_code == 0, shown.output
        assert "entry_count\t1" in shown.output

        discarded = cli_runner.invoke(
            borrador_100_app, ["discard", snapshot_id, "--reason", "profile change"],
        )
        assert discarded.exit_code == 0, discarded.output
        assert "reason\tprofile change" in discarded.output

        # After discard the default list hides the row.
        post = cli_runner.invoke(borrador_100_app, ["list"])
        assert "count\t0" in post.output
        included = cli_runner.invoke(borrador_100_app, ["list", "--include-discarded"])
        assert "count\t1" in included.output


class TestReadOnlyStructuralInvariants:
    """Reject accidental introduction of any write/submit-style verb on the
    new live subgroups. The live-AEAT charter forbids mutation here."""

    @pytest.mark.parametrize("subgroup_app", [expedientes_app, verify_app, borrador_100_app])
    def test_no_submit_send_or_present_verb_exists(self, subgroup_app) -> None:
        registered = {info.name for info in subgroup_app.registered_commands}
        forbidden = {"submit", "send", "present", "sign", "pay", "push", "modify"}
        assert registered.isdisjoint(forbidden), (
            f"forbidden write verb on {subgroup_app.info.name}: {registered & forbidden}"
        )
