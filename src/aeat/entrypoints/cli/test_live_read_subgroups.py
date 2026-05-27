"""CLI surface tests for `aeat app live {expedientes, verify, borrador} ...`."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.live import (
    Borrador100SnapshotService,
    IvaRemoteStateAcquisitionReport,
    LiveIvaAcquisitionFailureMode,
    LiveIvaAuthOutcome,
    LiveIvaReadOutcome,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
)
from aeat.application.live._verify import VerifyService, VerifySurface
from aeat.application.user_profile._orchestration import profile_create_storage_span
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.core.config import override_settings
from aeat.entrypoints.cli._app_live import (
    _iva_remote_state_capture_lines,
    borrador_100_app,
    expedientes_app,
    iva_wallet_app,
    verify_app,
)
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(aeat_audit_dir=tmp_path / "audit"),
        profile_create_storage_span("default"),
    ):
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
        result = cli_runner.invoke(expedientes_app, ["view", "no-such-id"])
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
        result = cli_runner.invoke(verify_app, ["view", "no-such-observation"])
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
            verify_app,
            ["latest", "--surface", "nif_iva", "--nif", "ESB12345678"],
        )
        assert result.exit_code == 0, result.output
        assert "nif\tESB12345678" in result.output
        assert "verdict\tvalid" in result.output

    def test_verify_latest_renders_dash_when_no_observation(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(
            verify_app,
            ["latest", "--surface", "tgvi", "--nif", "B99999999"],
        )
        assert result.exit_code == 0, result.output
        assert "observation_id\t-" in result.output


class TestBorrador100Subgroup:
    def test_borrador_100_list_is_empty_on_fresh_bucket(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(borrador_100_app, ["list"])
        assert result.exit_code == 0, result.output
        assert "count\t0" in result.output

    def test_borrador_100_latest_is_dash_when_no_snapshot(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(borrador_100_app, ["latest", "--filing-year", "2024"])
        assert result.exit_code == 0, result.output
        assert "snapshot_id\t-" in result.output

    def test_borrador_100_show_refuses_unknown_snapshot(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(borrador_100_app, ["view", "no-such-id"])
        assert result.exit_code != 0

    def test_borrador_100_full_lifecycle_via_service_seed(
        self,
        cli_runner: CliRunner,
    ) -> None:
        bucket_id = "default"
        Borrador100SnapshotService(bucket_id=bucket_id).capture(
            filing_year=2024,
            period="0A",
            captured_at=datetime(2025, 3, 15, tzinfo=UTC),
            source_url="https://www2.agenciatributaria.gob.es/wlpl/PRET-R210/SimuladorOpenAjax",
            binding_values={"renta-2025-modelo-111-retenciones-periodicas": Decimal("1000.00")},
        )

        listed = cli_runner.invoke(borrador_100_app, ["list"])
        assert listed.exit_code == 0, listed.output
        assert "count\t1" in listed.output
        assert "active" in listed.output

        latest = cli_runner.invoke(borrador_100_app, ["latest", "--filing-year", "2024"])
        assert latest.exit_code == 0, latest.output
        assert "filing_year\t2024" in latest.output

        # Pick the snapshot id off the latest row to drive show.
        snapshot_id = next(
            line.split("\t", 1)[1] for line in latest.output.splitlines() if line.startswith("snapshot_id\t")
        )
        shown = cli_runner.invoke(borrador_100_app, ["view", snapshot_id])
        assert shown.exit_code == 0, shown.output
        assert "binding_count\t1" in shown.output
        assert "state\tactive" in shown.output

    def test_borrador_100_list_rejects_unknown_state(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(borrador_100_app, ["list", "--state", "old"])
        assert result.exit_code != 0


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


class TestIvaRemoteStateCliSurface:
    def test_iva_wallet_remote_state_command_is_registered_as_read_capture(self) -> None:
        registered = {info.name for info in iva_wallet_app.registered_commands}

        assert "capture-remote-state" in registered
        assert registered.isdisjoint({"submit", "send", "present", "sign", "pay", "modify"})

    def test_remote_state_lines_render_auth_and_surface_outcomes_with_labels(self) -> None:
        report = IvaRemoteStateAcquisitionReport(
            output_root="var/aeat/live/iva-remote-state",
            year_from=2022,
            year_to=2024,
            target_year=2026,
            target_period="2T",
            auth=LiveIvaAuthOutcome(
                status=LiveIvaReadStatus.FAILED,
                outcome_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                failure_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                failure_type="ClaveMovilApprovalTimeoutError",
            ),
            filed_history=None,
            wallet=None,
            outcomes=(
                LiveIvaReadOutcome(
                    surface=LiveIvaReadSurface.FILED_HISTORY,
                    status=LiveIvaReadStatus.FAILED,
                    outcome_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                    failure_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                    failure_type="ClaveMovilApprovalTimeoutError",
                ),
                LiveIvaReadOutcome(
                    surface=LiveIvaReadSurface.WALLET_CARTERA,
                    status=LiveIvaReadStatus.FAILED,
                    outcome_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                    failure_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                    failure_type="ClaveMovilApprovalTimeoutError",
                ),
            ),
        )

        lines = _iva_remote_state_capture_lines(report)

        assert "auth_status=failed" in lines
        assert "auth_outcome=no_clave_prompt" in lines
        assert "auth_outcome_label=no clave prompt" in lines
        assert "filed_history_succeeded=False" in lines
        assert "wallet_succeeded=False" in lines
        assert any(
            line.startswith("surface_outcome=filed_history\tstatus=failed\toutcome=no_clave_prompt")
            for line in lines
        )
        assert any(
            line.startswith("surface_outcome=wallet_cartera\tstatus=failed\toutcome=no_clave_prompt")
            for line in lines
        )
