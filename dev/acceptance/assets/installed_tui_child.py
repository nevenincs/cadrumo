"""Drive and supervise the public installed activity-asset TUI acceptance stages."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Literal, cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    admit_installed_session,
    installed_product_evidence,
)

from .installed_tui_contracts import InstalledAssetTuiError, InstalledAssetTuiJourney, InstalledAssetTuiReceipt
from .installed_tui_controls import (
    _open_activity_asset_screen,
    _open_ledger_destination,
    _public_surface_diagnostic,
    _wait_for_public_selector,
    _wait_for_public_selector_absent,
)
from .installed_tui_lifecycle import (
    _exercise_cli_created_asset_readback,
    _exercise_method_asset_lifecycle,
    _exercise_method_asset_readback,
)

_SCHEMA_VERSION = "activity-asset-installed-tui-child-v3"


_RECEIPT_REPLACE_SECONDS = 2.0


_RECEIPT_REPLACE_RETRY_SECONDS = 0.02


def _installed_product_identity(*, workspace_root: Path) -> tuple[str, str]:
    """Require that this child imported the product from site-packages."""
    try:
        evidence = installed_product_evidence(workspace_root=workspace_root)
    except InstalledTuiChildError as exc:
        raise InstalledAssetTuiError(str(exc), stage="installed_origin") from exc
    return evidence.product_origin, evidence.product_init_sha256


def _sanitized_widget_ids(widget_ids: object) -> list[str] | None:
    candidate_widget_ids = cast("list[object]", widget_ids) if isinstance(widget_ids, list) else []
    if candidate_widget_ids and all(isinstance(value, str) for value in candidate_widget_ids):
        validated_widget_ids = [value for value in candidate_widget_ids if isinstance(value, str)]
        return sorted(set(validated_widget_ids))
    return None


def _sanitized_diagnostic(diagnostic: dict[str, object] | None) -> dict[str, object] | None:
    """Discard everything except public visual identity before persisting it."""
    if diagnostic is None:
        return None
    sanitized: dict[str, object] = {}
    for key in ("current_screen_class", "current_screen_id"):
        value = diagnostic.get(key)
        if isinstance(value, str) or value is None:
            sanitized[key] = value
    widget_ids = _sanitized_widget_ids(diagnostic.get("mounted_widget_ids"))
    if widget_ids is not None:
        sanitized["mounted_widget_ids"] = widget_ids
    return sanitized


def write_receipt_atomically(*, path: Path, receipt: InstalledAssetTuiReceipt) -> None:
    """Atomically publish the current stage for the supervising process.

    The supervisor polls this receipt, and Windows refuses to replace a file
    that another process holds open.  A poll holds it only for one short read,
    so the replacement is retried briefly before the refusal is surfaced.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    deadline = monotonic() + _RECEIPT_REPLACE_SECONDS
    while True:
        try:
            temporary.replace(path)
        except PermissionError:
            if monotonic() >= deadline:
                raise
            sleep(_RECEIPT_REPLACE_RETRY_SECONDS)
        else:
            return


def _completed_stages_from_receipt(path: Path) -> tuple[str, ...]:
    """Recover only stage names from the last safe in-progress receipt."""
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return ()
    payload = cast("dict[str, object]", raw) if isinstance(raw, dict) else None
    stages = payload.get("completed_stages") if payload is not None else None
    if not isinstance(stages, list):
        return ()
    validated: list[str] = []
    for stage in cast("list[object]", stages):
        if not isinstance(stage, str):
            return ()
        validated.append(stage)
    return tuple(validated)


def _read_passphrase_from_stdin() -> str:
    """Read one synthetic passphrase from stdin without echoing it."""
    try:
        raw: object = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise InstalledAssetTuiError("credential stdin is not one JSON object", stage="credential_input") from exc
    if not isinstance(raw, dict):
        raise InstalledAssetTuiError("credential stdin is not one JSON object", stage="credential_input")
    payload = cast("dict[str, object]", raw)
    passphrase = payload.get("profile_passphrase")
    if not isinstance(passphrase, str) or not passphrase:
        raise InstalledAssetTuiError("credential stdin has no profile_passphrase", stage="credential_input")
    return passphrase


async def _register_profile(*, profile_label: str, passphrase: str) -> None:
    """Register through the shipped TUI screen, not a persistence back door."""
    from textual.widgets import Input

    from cadrumo.core.credentials import assess_profile_password
    from cadrumo.entrypoints.tui.components.host import ScreenHostApp
    from cadrumo.entrypoints.tui.secret.registration import (
        RegistrationScreen,
        build_profile_recovery_enrollment_attempt,
        build_profile_registration_attempt,
    )

    screen = RegistrationScreen(
        assess=assess_profile_password,
        register=build_profile_registration_attempt,
        enroll_recovery=build_profile_recovery_enrollment_attempt,
    )
    app = ScreenHostApp(screen)
    async with app.run_test(size=(160, 60)) as pilot:
        await pilot.pause()
        screen.query_one("#field-username", Input).value = profile_label
        screen.query_one("#field-password", Input).value = passphrase
        screen.query_one("#field-confirm", Input).value = passphrase
        await pilot.click("#btn-create")
        await pilot.app.workers.wait_for_complete()  # type: ignore[reportUnknownMemberType]
        await _wait_for_public_selector(pilot, "#btn-skip-recovery", stage="registration_recovery")
        await pilot.click("#btn-skip-recovery")
        await pilot.pause()
    if screen.outcome is None:
        raise InstalledAssetTuiError("registration completed without an admitted profile", stage="registration")


async def _drive_profile_path(
    pilot: Any,
    journey: InstalledAssetTuiJourney,
    completed: list[str],
    observed: list[dict[str, object]],
    publish: Callable[..., None],
) -> None:
    if journey in {
        "home",
        "profile",
        "profile_ready",
        "ledger",
        "asset_screen",
        "asset_method_lifecycle",
        "asset_readback",
        "asset_cli_readback",
    }:
        await _wait_for_public_selector(pilot, "#home-agenda", stage="home_ready", timeout_seconds=45.0)
        observed.append(_public_surface_diagnostic(pilot))
        completed.append("home_ready")
        publish("home_ready", diagnostic=observed[-1])
    if journey in {"profile", "profile_ready"}:
        # F4 is the public account-profile route.  It is deliberately
        # distinct from F2, which opens the account language editor.
        await pilot.press("f4")
        await _wait_for_public_selector(pilot, "#manager-context", stage="profile_ready", timeout_seconds=45.0)
        observed.append(_public_surface_diagnostic(pilot))
        completed.append("profile_ready")
        publish("profile_ready", diagnostic=observed[-1])
    if journey == "profile_ready":
        # Setup completion is a public, explicit profile operation.  The
        # disappearance of its visible control proves a terminal state;
        # a timeout remains a failed stage instead of a guessed success.
        await pilot.press("f8")
        await _wait_for_public_selector_absent(
            pilot,
            "#manager-complete-setup",
            stage="profile_completion",
            timeout_seconds=20.0,
        )
        observed.append(_public_surface_diagnostic(pilot))
        completed.append("profile_completed")
        publish("profile_completed", diagnostic=observed[-1])


async def _drive_asset_path(
    pilot: Any,
    journey: InstalledAssetTuiJourney,
    completed: list[str],
    observed: list[dict[str, object]],
    publish: Callable[..., None],
    assertions: dict[str, object],
) -> None:
    if journey in {"ledger", "asset_screen", "asset_method_lifecycle", "asset_readback", "asset_cli_readback"}:
        await _open_ledger_destination(pilot=pilot)
        observed.append(_public_surface_diagnostic(pilot))
        completed.append("ledger_ready")
        publish("ledger_ready", diagnostic=observed[-1])
    if journey in {"asset_screen", "asset_method_lifecycle", "asset_readback", "asset_cli_readback"}:
        await _open_activity_asset_screen(pilot=pilot)
        observed.append(_public_surface_diagnostic(pilot))
        completed.append("asset_screen_ready")
        publish("asset_screen_ready", diagnostic=observed[-1])

    def record_asset_stage(stage: str) -> None:
        completed.append(stage)
        publish(stage, diagnostic=_public_surface_diagnostic(pilot), receipt_assertions=assertions or None)

    if journey == "asset_method_lifecycle":
        assertions.update(await _exercise_method_asset_lifecycle(pilot=pilot, progress=record_asset_stage))
        publish("asset_claim_replay", diagnostic=_public_surface_diagnostic(pilot), receipt_assertions=assertions)
    if journey == "asset_readback":
        assertions.update(await _exercise_method_asset_readback(pilot=pilot, progress=record_asset_stage))
        publish("asset_readback", diagnostic=_public_surface_diagnostic(pilot), receipt_assertions=assertions)
    if journey == "asset_cli_readback":
        assertions.update(await _exercise_cli_created_asset_readback(pilot=pilot, progress=record_asset_stage))
        publish("asset_cli_readback", diagnostic=_public_surface_diagnostic(pilot), receipt_assertions=assertions)


def _run_probe(
    *,
    workspace_root: Path,
    profile_label: str,
    passphrase: str,
    receipt_path: Path,
    journey: InstalledAssetTuiJourney,
    profile_bootstrap: Literal["register", "existing"],
) -> InstalledAssetTuiReceipt:
    """Prove the production launcher invokes its autopilot and exits cleanly."""
    origin, init_sha = _installed_product_identity(workspace_root=workspace_root)
    completed: list[str] = ["installed_origin"]
    assertions: dict[str, object] = {}

    def publish(
        stage: str,
        *,
        status: Literal["running", "proven", "failed"] = "running",
        diagnostic: dict[str, object] | None = None,
        receipt_assertions: dict[str, object] | None = None,
    ) -> None:
        write_receipt_atomically(
            path=receipt_path,
            receipt=InstalledAssetTuiReceipt(
                schema_version=_SCHEMA_VERSION,
                status=status,
                stage=stage,
                product_origin=origin,
                product_init_sha256=init_sha,
                completed_stages=tuple(completed),
                diagnostic=_sanitized_diagnostic(diagnostic),
                assertions=receipt_assertions,
            ),
        )

    if profile_bootstrap == "register":
        publish("registration")
        # Registration is an installed product operation and therefore needs
        # the same adapter/exchange composition as the production launcher.
        # The driver still interacts only with the public Registration screen.
        from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
        from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

        with live_exchange_rate_composition(), profile_adapter_composition():
            asyncio.run(
                asyncio.wait_for(
                    _register_profile(profile_label=profile_label, passphrase=passphrase),
                    timeout=45.0,
                )
            )
        completed.append("registration")
    else:
        completed.append("existing_profile")
        publish("existing_profile")
    observed: list[dict[str, object]] = []

    async def drive(pilot: Any) -> None:
        try:
            root_ready = await admit_installed_session(
                pilot=pilot,
                passphrase=passphrase,
                deadline=asyncio.get_running_loop().time() + 45.0,
            )
        except InstalledTuiChildError as error:
            raise InstalledAssetTuiError(
                "installed runtime admission did not complete", stage="session_admission", diagnostic=error.diagnostic
            ) from error
        if not root_ready:
            if profile_bootstrap == "existing":
                completed.append("session_admitted")
                publish("session_admitted")
            return
        await pilot.pause()
        observed.append(_public_surface_diagnostic(pilot))
        completed.append("launcher_autopilot")
        publish("launcher_autopilot", diagnostic=observed[-1])
        await _drive_profile_path(pilot, journey, completed, observed, publish)
        await _drive_asset_path(pilot, journey, completed, observed, publish, assertions)
        pilot.app.exit()

    publish("production_launcher")
    from cadrumo.entrypoints.tui.launcher import main

    exit_code = main(headless=True, auto_pilot=drive)
    if exit_code != 0:
        raise InstalledAssetTuiError(f"production launcher returned {exit_code}", stage="launcher_exit")
    from dev.acceptance.assets.installed_journey import required_installed_tui_stages

    # A headless launcher can return the normal completed status before it
    # constructs a workbench (for example when it correctly refuses a missing
    # credential session).  Treat that as failed journey evidence, never as an
    # installed-TUI success merely because its process exit was zero.
    missing_stage = next(
        (
            stage
            for stage in required_installed_tui_stages(
                journey=journey,
                profile_bootstrap=profile_bootstrap,
            )
            if stage != "launcher_exit" and stage not in completed
        ),
        None,
    )
    if missing_stage is not None:
        raise InstalledAssetTuiError(
            "production launcher exited before the installed TUI journey reached its required stage",
            stage=missing_stage,
        )
    completed.append("launcher_exit")
    return InstalledAssetTuiReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        stage="completed",
        product_origin=origin,
        product_init_sha256=init_sha,
        completed_stages=tuple(completed),
        launcher_exit_code=exit_code,
        diagnostic=_sanitized_diagnostic(observed[-1] if observed else None),
        assertions=assertions or None,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a staged activity-asset installed TUI child.")
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--profile-label", default="assets-installed-tui")
    parser.add_argument(
        "--journey",
        choices=(
            "probe",
            "home",
            "profile",
            "profile_ready",
            "ledger",
            "asset_screen",
            "asset_method_lifecycle",
            "asset_readback",
            "asset_cli_readback",
        ),
        default="probe",
    )
    parser.add_argument("--profile-bootstrap", choices=("register", "existing"), default="register")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one bounded child and leave a sanitized terminal receipt."""
    args = _parser().parse_args(argv)
    origin = "unknown"
    init_sha = "unknown"
    try:
        passphrase = _read_passphrase_from_stdin()
        origin, init_sha = _installed_product_identity(workspace_root=args.workspace_root)
        receipt = _run_probe(
            workspace_root=args.workspace_root,
            profile_label=args.profile_label,
            passphrase=passphrase,
            receipt_path=args.receipt,
            journey=args.journey,
            profile_bootstrap=args.profile_bootstrap,
        )
    except (InstalledAssetTuiError, TimeoutError) as exc:
        if isinstance(exc, InstalledAssetTuiError):
            stage = exc.stage
            diagnostic = _sanitized_diagnostic(exc.diagnostic)
            message = str(exc)
        else:
            stage = "timeout"
            diagnostic = None
            message = "installed TUI stage exceeded its bounded timeout"
        write_receipt_atomically(
            path=args.receipt,
            receipt=InstalledAssetTuiReceipt(
                schema_version=_SCHEMA_VERSION,
                status="failed",
                stage=stage,
                product_origin=origin,
                product_init_sha256=init_sha,
                completed_stages=_completed_stages_from_receipt(args.receipt),
                diagnostic=diagnostic,
            ),
        )
        print(json.dumps({"status": "failed", "stage": stage, "error": message}, sort_keys=True))
        return 2
    write_receipt_atomically(path=args.receipt, receipt=receipt)
    print(json.dumps({"status": "proven", "stage": receipt.stage}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - executable module boundary
    raise SystemExit(main())
