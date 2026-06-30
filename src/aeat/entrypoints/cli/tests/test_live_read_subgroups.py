"""CLI surface tests for `aeat app live {expedientes, verify, borrador} ...`."""

from __future__ import annotations

import asyncio
import json
import platform
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import sleep
from typing import cast

import pytest

from ....application.auth import LiveAuthPreflightReport
from ....application.live import (
    Borrador100SnapshotService,
    IvaRemoteStateAcquisitionReport,
    LiveIvaAcquisitionFailureMode,
    LiveIvaAuthOutcome,
    LiveIvaReadOutcome,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
    LiveIvaSurfaceTimeoutError,
)
from ....application.live._verify import VerifyService, VerifySurface
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import Period
from ....core.config import override_settings
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .._app_live import (
    _iva_remote_state_capture_lines,
    _live_iva_evidence_pull_command_timeout_ms,
    _live_iva_outcome_label,
    _playwright_profile_tokens,
    _process_command_inventory,
    _reap_new_playwright_profile_processes,
    _run_live_iva_evidence_pull_command,
    borrador_100_app,
    expedientes_app,
    iva_wallet_app,
    verify_app,
)
from .._app_live_auth_preflight import _live_auth_preflight_lines

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(aeat_audit_dir=tmp_path / "audit"),
        profile_create_storage_span("00000000-0000-4000-8000-000000000000"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="00000000-0000-4000-8000-000000000000"),
        )
        yield


def _invoke_expedientes(*args: str):
    return invoke_cached_cli(["app", "live", "expedientes", *args])


def _invoke_verify(*args: str):
    return invoke_cached_cli(["app", "live", "verify", *args])


def _invoke_borrador_100(*args: str):
    return invoke_cached_cli(["app", "live", "borrador", "100", *args])


def test_live_auth_preflight_lines_redact_active_profile_identifier() -> None:
    report = LiveAuthPreflightReport(
        provider="clave_movil",
        configured=True,
        available=True,
        active_profile="operator-private-profile-id",
        active_profile_status="ready",
        persisted_session_present=True,
        persisted_session_expired=False,
        persisted_session_state="live",
    )

    lines = _live_auth_preflight_lines(report)

    assert "auth_active_profile=<profile-id>" in lines
    assert "auth_persisted_session_state=live" in lines
    assert all("operator-private-profile-id" not in line for line in lines)


class TestExpedientesSubgroup:
    def test_expedientes_list_is_empty_on_fresh_bucket(self) -> None:
        result = _invoke_expedientes("list")
        assert result.exit_code == 0, result.output
        assert "count\t0" in result.output

    def test_expedientes_show_refuses_unknown_snapshot(self) -> None:
        result = _invoke_expedientes("view", "no-such-id")
        assert result.exit_code != 0

    def test_expedientes_latest_is_dash_on_fresh_bucket(self) -> None:
        result = _invoke_expedientes("latest")
        assert result.exit_code == 0, result.output
        assert "snapshot_id\t-" in result.output


class TestVerifySubgroup:
    def test_verify_list_is_empty_on_fresh_bucket(self) -> None:
        result = _invoke_verify("list")
        assert result.exit_code == 0, result.output
        assert "count\t0" in result.output

    def test_verify_list_refuses_unknown_surface(self) -> None:
        result = _invoke_verify("list", "--surface", "not-a-surface")
        assert result.exit_code != 0

    def test_verify_list_accepts_known_surface(self) -> None:
        result = _invoke_verify("list", "--surface", "nif_iva")
        assert result.exit_code == 0, result.output

    def test_verify_show_refuses_unknown_observation(self) -> None:
        result = _invoke_verify("view", "no-such-observation")
        assert result.exit_code != 0

    def test_verify_latest_renders_persisted_observation(self) -> None:
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
        result = _invoke_verify("latest", "--surface", "nif_iva", "--nif", "ESB12345678")
        assert result.exit_code == 0, result.output
        assert "nif\tESB12345678" in result.output
        assert "verdict\tvalid" in result.output

    def test_verify_latest_renders_dash_when_no_observation(self) -> None:
        result = _invoke_verify("latest", "--surface", "tgvi", "--nif", "B99999999")
        assert result.exit_code == 0, result.output
        assert "observation_id\t-" in result.output


class TestBorrador100Subgroup:
    def test_borrador_100_list_is_empty_on_fresh_bucket(self) -> None:
        result = _invoke_borrador_100("list")
        assert result.exit_code == 0, result.output
        assert "count\t0" in result.output

    def test_borrador_100_latest_is_dash_when_no_snapshot(self) -> None:
        result = _invoke_borrador_100("latest", "--filing-year", "2024")
        assert result.exit_code == 0, result.output
        assert "snapshot_id\t-" in result.output

    def test_borrador_100_show_refuses_unknown_snapshot(self) -> None:
        result = _invoke_borrador_100("view", "no-such-id")
        assert result.exit_code != 0

    def test_borrador_100_full_lifecycle_via_service_seed(self) -> None:
        bucket_id = "default"
        Borrador100SnapshotService(bucket_id=bucket_id).capture(
            filing_year=2024,
            period=Period.from_year_and_code(2024, "0A"),
            captured_at=datetime(2025, 3, 15, tzinfo=UTC),
            source_url=aeat_url("www2", configured_path("sede_paths", "r210_simulator_open_ajax")),
            binding_values={"renta-2025-modelo-111-retenciones-periodicas": Decimal("1000.00")},
        )

        listed = _invoke_borrador_100("list")
        assert listed.exit_code == 0, listed.output
        assert "count\t1" in listed.output
        assert "active" in listed.output

        latest = _invoke_borrador_100("latest", "--filing-year", "2024")
        assert latest.exit_code == 0, latest.output
        assert "filing_year\t2024" in latest.output

        # Pick the snapshot id off the latest row to drive show.
        snapshot_id = next(
            line.split("\t", 1)[1] for line in latest.output.splitlines() if line.startswith("snapshot_id\t")
        )
        shown = _invoke_borrador_100("view", snapshot_id)
        assert shown.exit_code == 0, shown.output
        assert "binding_count\t1" in shown.output
        assert "state\tactive" in shown.output

        shown_json = invoke_cached_cli(["--format", "json", "app", "live", "borrador", "100", "view", snapshot_id])
        assert shown_json.exit_code == 0, shown_json.output
        payload = json.loads(shown_json.output)
        assert payload["command"] == "app.live.borrador.100.view"
        assert payload["result"]["binding_values"] == {
            "renta-2025-modelo-111-retenciones-periodicas": "1000.00",
        }

    def test_borrador_100_list_rejects_unknown_state(self) -> None:
        result = _invoke_borrador_100("list", "--state", "old")
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
    def test_evidence_pull_command_watchdog_budget_scales_with_year_span(self) -> None:
        with override_settings(
            aeat_clave_movil_timeout_ms=120_000,
            aeat_live_iva_surface_timeout_ms=180_000,
            aeat_live_iva_cli_watchdog_timeout_ms=240_000,
        ):
            one_year = _live_iva_evidence_pull_command_timeout_ms(year_from=2026, year_to=2026)
            five_years = _live_iva_evidence_pull_command_timeout_ms(year_from=2022, year_to=2026)

        assert one_year == 720_000
        assert five_years == 1_440_000
        assert five_years > one_year

    def test_evidence_pull_command_watchdog_reports_typed_timeout(self) -> None:
        async def slow_read() -> str:
            await asyncio.sleep(0.05)
            return "unreachable"

        async def run() -> None:
            with pytest.raises(LiveIvaSurfaceTimeoutError) as raised:
                await _run_live_iva_evidence_pull_command(slow_read(), timeout_ms=1)

            assert raised.value.surface == "iva_evidence_command"
            assert raised.value.timeout_ms == 1
            context = raised.value.context
            assert context is not None
            assert context["surface"] == "iva_evidence_command"
            assert context["timeout_ms"] == 1
            progress_node = context["progress"]
            assert isinstance(progress_node, dict)
            # The watchdog progress payload is a JSON object (str keys, object values).
            progress = cast(dict[str, object], progress_node)
            assert progress["stage"] == "cli_watchdog"
            assert progress["surface"] == LiveIvaReadSurface.FILED_HISTORY.value
            assert "watchdog_reaped_process_count" in progress
            assert (
                "auth_watchdog_before_persisted_session" in progress
                or progress.get("auth_watchdog_before_probe") == "unavailable"
            )
            assert (
                "auth_watchdog_after_persisted_session" in progress
                or progress.get("auth_watchdog_after_probe") == "unavailable"
            )

        asyncio.run(run())

    def test_remote_state_watchdog_subprocess_leaves_no_canary_process(self) -> None:
        canary = "aeat-s92-watchdog-timeout-canary"
        code = """
            import asyncio
            import sys

            from aeat.application.live import LiveIvaSurfaceTimeoutError
            from aeat.entrypoints.cli._app_live import _run_live_iva_evidence_pull_command

            async def slow_read():
                await asyncio.sleep(30)

            try:
                asyncio.run(_run_live_iva_evidence_pull_command(slow_read(), timeout_ms=1))
            except LiveIvaSurfaceTimeoutError:
                sys.exit(0)
            sys.exit(2)
            """
        completed = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(code), canary],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr
        assert canary not in _live_process_command_lines()

    def test_watchdog_reaps_new_playwright_temp_profile_process(self) -> None:
        preexisting = _playwright_profile_tokens(_process_command_inventory())
        profile_canary = "playwright_chromiumdev_profile-aeatS92Canary"
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import time; time.sleep(60)",
                f"--user-data-dir={profile_canary}",
            ],
        )
        try:
            deadline = datetime.now(UTC).timestamp() + 10
            while datetime.now(UTC).timestamp() < deadline:
                if profile_canary in _live_process_command_lines():
                    break
                sleep(0.1)
            else:
                raise AssertionError("canary process command line was not visible to process inventory")

            killed = _reap_new_playwright_profile_processes(preexisting_profiles=preexisting)
            assert killed >= 1
            proc.wait(timeout=10)
            assert proc.returncode is not None
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)

    def test_every_live_iva_outcome_has_operator_label(self) -> None:
        for mode in LiveIvaAcquisitionFailureMode:
            label = _live_iva_outcome_label(mode)

            assert label
            assert "cli.app.live.iva_wallet.acquisition.outcome" not in label
            if mode is not LiveIvaAcquisitionFailureMode.UNKNOWN:
                assert label != _live_iva_outcome_label(LiveIvaAcquisitionFailureMode.UNKNOWN)

    def test_iva_wallet_combined_evidence_command_is_registered_as_read_capture(self) -> None:
        registered = {info.name for info in iva_wallet_app.registered_commands}

        assert "pull-evidence" in registered
        assert "pull-remote-state" not in registered
        assert registered.isdisjoint({"submit", "send", "present", "sign", "pay", "modify"})

    def test_remote_state_lines_render_auth_and_surface_outcomes_with_labels(self) -> None:
        report = IvaRemoteStateAcquisitionReport(
            output_root="var/aeat/live/iva-read-evidence",
            year_from=2022,
            year_to=2024,
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
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
                    failure_context={
                        "progress": {
                            "stage": "walk_declarations_register",
                            "modelo": "303",
                            "ejercicio": 2026,
                        },
                    },
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
        assert "auth_outcome_label=no Cl@ve prompt" in lines
        assert "filed_history_succeeded=False" in lines
        assert "wallet_succeeded=False" in lines
        assert any(
            line.startswith("surface_outcome=filed_history\tstatus=failed\toutcome=no_clave_prompt") for line in lines
        )
        assert any(
            "failure_context=progress={ejercicio:2026,modelo:303,stage:walk_declarations_register}" in line
            for line in lines
        )
        assert any(
            line.startswith("surface_outcome=wallet_cartera\tstatus=failed\toutcome=no_clave_prompt") for line in lines
        )


def _live_process_command_lines() -> str:
    """Return process command lines for local stale-process assertions."""
    if platform.system() == "Windows":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell is None:
            raise RuntimeError(
                "PowerShell (powershell or pwsh) is required for Windows process inventory but was not found on PATH",
            )
        script = "Get-CimInstance Win32_Process | Select-Object -ExpandProperty CommandLine | ConvertTo-Json -Compress"
        completed = subprocess.run(
            [powershell, "-NoProfile", "-Command", script],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = completed.stdout.strip()
        if not payload:
            return ""
        decoded = json.loads(payload)
        if isinstance(decoded, str):
            return decoded
        return "\n".join(str(item or "") for item in decoded)

    ps = shutil.which("ps")
    if ps is None:
        raise RuntimeError("ps is required for Unix process inventory but was not found on PATH")
    completed = subprocess.run(
        [ps, "-axo", "args="],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout
