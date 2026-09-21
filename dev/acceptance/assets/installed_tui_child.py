"""Staged installed-TUI child for the ASSETS-01 acceptance journey.

The child stays outside the product package so it can prove that the product
imports from an installed wheel.  Its receipt deliberately contains public
screen identity and stage names only; the synthetic credential and taxpayer
facts never leave the child process.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any, Literal, cast

_SCHEMA_VERSION = "assets-01-installed-tui-child-v1"


class InstalledAssetTuiError(RuntimeError):
    """A public installed-TUI boundary did not reach its expected stage."""

    def __init__(self, message: str, *, stage: str, diagnostic: dict[str, object] | None = None) -> None:
        """Keep one public failed-stage identity and optional safe surface state."""
        super().__init__(message)
        self.stage = stage
        self.diagnostic = diagnostic


@dataclass(frozen=True, slots=True)
class InstalledAssetTuiReceipt:
    """Sanitized stage result from one installed product process."""

    schema_version: str
    status: Literal["running", "proven", "failed"]
    stage: str
    product_origin: str
    product_init_sha256: str
    completed_stages: tuple[str, ...]
    launcher_exit_code: int | None = None
    diagnostic: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe receipt without synthetic taxpayer facts."""
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "stage": self.stage,
            "product_origin": self.product_origin,
            "product_init_sha256": self.product_init_sha256,
            "completed_stages": self.completed_stages,
            "launcher_exit_code": self.launcher_exit_code,
            "diagnostic": self.diagnostic,
        }


def _installed_product_identity(*, workspace_root: Path) -> tuple[str, str]:
    """Require that this child imported the product from site-packages."""
    import cadrumo

    product_init = Path(cadrumo.__file__ or "").resolve()
    source_root = (workspace_root.resolve() / "src" / "cadrumo").resolve()
    if not product_init.exists() or product_init.is_relative_to(source_root):
        raise InstalledAssetTuiError(
            "installed assets TUI child imported product code from the checkout",
            stage="installed_origin",
        )
    if "site-packages" not in {part.casefold() for part in product_init.parts}:
        raise InstalledAssetTuiError(
            "installed assets TUI child product origin is not site-packages",
            stage="installed_origin",
        )
    return "site-packages", hashlib.sha256(product_init.read_bytes()).hexdigest()


def _public_surface_diagnostic(pilot: Any) -> dict[str, object]:
    """Describe only public screen identity and widget IDs for a failed stage."""
    screen = pilot.app.screen
    ids: set[str] = set()
    for scope in (pilot.app, screen):
        for widget in scope.query("*"):
            widget_id: object = getattr(widget, "id", None)
            if isinstance(widget_id, str):
                ids.add(widget_id)
    return {
        "current_screen_class": type(screen).__name__,
        "current_screen_id": screen.id,
        "mounted_widget_ids": sorted(ids),
    }


def _sanitized_diagnostic(diagnostic: dict[str, object] | None) -> dict[str, object] | None:
    """Discard everything except public visual identity before persisting it."""
    if diagnostic is None:
        return None
    sanitized: dict[str, object] = {}
    for key in ("current_screen_class", "current_screen_id"):
        value = diagnostic.get(key)
        if isinstance(value, str) or value is None:
            sanitized[key] = value
    widget_ids = diagnostic.get("mounted_widget_ids")
    candidate_widget_ids = cast("list[object]", widget_ids) if isinstance(widget_ids, list) else []
    if candidate_widget_ids and all(isinstance(value, str) for value in candidate_widget_ids):
        validated_widget_ids = [value for value in candidate_widget_ids if isinstance(value, str)]
        sanitized["mounted_widget_ids"] = sorted(set(validated_widget_ids))
    return sanitized


def _write_receipt(*, path: Path, receipt: InstalledAssetTuiReceipt) -> None:
    """Atomically publish the current stage for the supervising process."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


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


async def _wait_for_public_selector(
    pilot: Any,
    selector: str,
    *,
    stage: str,
    timeout_seconds: float = 15.0,
) -> object:
    """Wait a bounded time for one visible public control."""
    from textual.css.query import NoMatches

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        try:
            return pilot.app.query_one(selector)
        except NoMatches:
            try:
                return pilot.app.screen.query_one(selector)
            except NoMatches:
                await pilot.pause()
    raise InstalledAssetTuiError(
        f"installed TUI did not expose {selector}",
        stage=stage,
        diagnostic=_public_surface_diagnostic(pilot),
    )


def _run_probe(
    *,
    workspace_root: Path,
    profile_label: str,
    passphrase: str,
    receipt_path: Path,
    journey: Literal["probe", "home", "ledger"],
) -> InstalledAssetTuiReceipt:
    """Prove the production launcher invokes its autopilot and exits cleanly."""
    origin, init_sha = _installed_product_identity(workspace_root=workspace_root)
    completed: list[str] = ["installed_origin"]

    def publish(
        stage: str,
        *,
        status: Literal["running", "proven", "failed"] = "running",
        diagnostic: dict[str, object] | None = None,
    ) -> None:
        _write_receipt(
            path=receipt_path,
            receipt=InstalledAssetTuiReceipt(
                schema_version=_SCHEMA_VERSION,
                status=status,
                stage=stage,
                product_origin=origin,
                product_init_sha256=init_sha,
                completed_stages=tuple(completed),
                diagnostic=_sanitized_diagnostic(diagnostic),
            ),
        )

    publish("registration")
    # Registration is an installed product operation and therefore needs the
    # same adapter/exchange composition as the production launcher.  The
    # driver still interacts only with the public Registration screen.
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
    observed: list[dict[str, object]] = []

    async def drive(pilot: Any) -> None:
        await pilot.pause()
        observed.append(_public_surface_diagnostic(pilot))
        completed.append("launcher_autopilot")
        publish("launcher_autopilot", diagnostic=observed[-1])
        if journey in {"home", "ledger"}:
            await _wait_for_public_selector(pilot, "#home-agenda", stage="home_ready", timeout_seconds=45.0)
            observed.append(_public_surface_diagnostic(pilot))
            completed.append("home_ready")
            publish("home_ready", diagnostic=observed[-1])
        if journey == "ledger":
            # F2 is the installed product's declared Ledger navigation.  The
            # Home summary is display-only and is deliberately not used as a
            # hidden driver shortcut.
            await pilot.press("f2")
            await _wait_for_public_selector(pilot, "#ledger-navigation", stage="ledger_ready", timeout_seconds=45.0)
            observed.append(_public_surface_diagnostic(pilot))
            completed.append("ledger_ready")
            publish("ledger_ready", diagnostic=observed[-1])
        pilot.app.exit()

    publish("production_launcher")
    from cadrumo.entrypoints.tui.launcher import main

    exit_code = main(headless=True, auto_pilot=drive)
    if exit_code != 0:
        raise InstalledAssetTuiError(f"production launcher returned {exit_code}", stage="launcher_exit")
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
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a staged ASSETS-01 installed TUI child.")
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--profile-label", default="assets-installed-tui")
    parser.add_argument("--journey", choices=("probe", "home", "ledger"), default="probe")
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
        _write_receipt(
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
    _write_receipt(path=args.receipt, receipt=receipt)
    print(json.dumps({"status": "proven", "stage": receipt.stage}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - executable module boundary
    raise SystemExit(main())


__all__ = [
    "InstalledAssetTuiError",
    "InstalledAssetTuiReceipt",
    "main",
]
