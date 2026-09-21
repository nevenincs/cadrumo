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
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any, Literal, cast

_SCHEMA_VERSION = "assets-01-installed-tui-child-v2"
type InstalledAssetTuiJourney = Literal[
    "probe",
    "home",
    "profile",
    "profile_ready",
    "ledger",
    "asset_screen",
    "asset_linear_lifecycle",
    "asset_readback",
    "asset_cli_readback",
]

_LINEAR_ASSET_ID = "assets-tui-linear-material-2025"
_LINEAR_CORRECTED_FORECAST_AMOUNT = "180.00"
_LINEAR_REVISION_JSON = json.dumps(
    {
        "asset_id": _LINEAR_ASSET_ID,
        "revision_number": 1,
        "acquisition": {
            "observed_transaction_id": "a" * 64,
            "invoice_evidence_id": "synthetic-installed-tui-material-invoice",
            "evidence_fingerprint": "b" * 64,
        },
        "acquisition_shape": "primary_purchase",
        "asset_kind": "material",
        "basis": {
            "stage": "business_allocated",
            "basis_amount": "2000.00",
            "prior_allocation_provenance": "synthetic installed TUI allocation",
        },
        "in_service_date": "2025-01-01",
        "opening_history": {"status": "known", "accumulated_amount": "0.00"},
    },
    separators=(",", ":"),
)
_LINEAR_SELECTION_JSON = json.dumps(
    {
        "regime": "simplified",
        "asset_kind": "material",
        "authority_class_key": "instalacion-mobiliario-enseres-resto-material",
    },
    separators=(",", ":"),
)


def _linear_correction_json(*, supersedes_revision_id: str) -> str:
    """Build a synthetic correction only after public inspection supplied its ID."""
    raw_document: object = json.loads(_LINEAR_REVISION_JSON)
    if not isinstance(raw_document, dict):  # pragma: no cover - static fixture invariant
        raise RuntimeError("linear installed-TUI fixture is not a JSON object")
    document = cast("dict[str, object]", raw_document)
    document["revision_number"] = 2
    document["supersedes_revision_id"] = supersedes_revision_id
    document["basis"] = {
        "stage": "business_allocated",
        "basis_amount": "1800.00",
        "prior_allocation_provenance": "synthetic corrected TUI allocation",
    }
    return json.dumps(document, separators=(",", ":"))


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
    assertions: dict[str, object] | None = None

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
            "assertions": self.assertions,
        }


@dataclass(frozen=True, slots=True)
class _PublicAssetActionTransition:
    """Safe public state observed around one keyboard asset action."""

    button_id: str
    result_before: str
    result_after_activation: str
    button_disabled_before: bool


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


async def _wait_for_public_selector_absent(
    pilot: Any,
    selector: str,
    *,
    stage: str,
    timeout_seconds: float = 15.0,
) -> None:
    """Wait for a public control to disappear after its supported operation."""
    from textual.css.query import NoMatches

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        try:
            pilot.app.query_one(selector)
        except NoMatches:
            try:
                pilot.app.screen.query_one(selector)
            except NoMatches:
                return
        await pilot.pause()
    raise InstalledAssetTuiError(
        f"installed TUI did not complete the public operation for {selector}",
        stage=stage,
        diagnostic=_public_surface_diagnostic(pilot),
    )


async def _open_ledger_destination(*, pilot: Any) -> None:
    """Open Ledger through the public command palette, never a private route."""
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    await pilot.press("ctrl+p")
    await pilot.pause()
    try:
        query = pilot.app.screen.query_one(Input)
        results = pilot.app.screen.query_one(OptionList)
    except NoMatches as exc:
        raise InstalledAssetTuiError(
            "installed TUI did not expose its public command palette controls",
            stage="ledger_navigation",
            diagnostic=_public_surface_diagnostic(pilot),
        ) from exc
    query.value = "Ledger"
    deadline = monotonic() + 45.0
    while monotonic() < deadline:
        if results.option_count > 0:
            results.highlighted = 0
            await pilot.press("enter")
            await _wait_for_public_selector(pilot, "#ledger-navigation", stage="ledger_ready", timeout_seconds=45.0)
            return
        await pilot.pause()
    raise InstalledAssetTuiError(
        "installed TUI command palette did not offer Ledger",
        stage="ledger_navigation",
        diagnostic=_public_surface_diagnostic(pilot),
    )


def _safe_asset_result_state(rendered: str) -> str:
    """Classify a public result without retaining taxpayer-facing values or IDs."""
    parts = rendered.split("\t")
    if not rendered:
        return "empty"
    if parts[0] == "pending" and len(parts) == 2:
        return "pending"
    if parts[0] == "refused":
        return "refused"
    if parts[0] == "claim" and len(parts) == 3 and parts[2] in {"reused=false", "reused=true"}:
        return f"claim:{parts[2]}"
    if parts[0] in {"created", "corrected", "asset", "forecast", "filing_handoff"}:
        return parts[0]
    return "other"


def _asset_transition_diagnostic(
    *,
    pilot: Any,
    transition: _PublicAssetActionTransition,
    rendered: str,
) -> dict[str, object]:
    """Add only safe public action state to the existing surface diagnostic."""
    diagnostic = _public_surface_diagnostic(pilot)
    diagnostic.update(
        {
            "asset_action": transition.button_id,
            "asset_button_disabled_before": transition.button_disabled_before,
            "asset_result_before": _safe_asset_result_state(transition.result_before),
            "asset_result_after_activation": _safe_asset_result_state(transition.result_after_activation),
            "asset_result_last": _safe_asset_result_state(rendered),
        }
    )
    return diagnostic


async def _activate_public_button(
    *,
    pilot: Any,
    selector: str,
    stage: str,
    capture_asset_result: bool = True,
) -> _PublicAssetActionTransition:
    """Activate one visible button and retain a safe before/after state receipt."""
    from textual.widgets import Button, Static

    button = await _wait_for_public_selector(pilot, selector, stage=stage)
    if not isinstance(button, Button):
        raise InstalledAssetTuiError(
            "installed TUI control has an unexpected type",
            stage=stage,
            diagnostic=_public_surface_diagnostic(pilot),
        )
    result = (
        await _wait_for_public_selector(pilot, "#asset-result", stage=stage) if capture_asset_result else None
    )
    if result is not None and not isinstance(result, Static):
        raise InstalledAssetTuiError(
            "installed TUI asset result control has an unexpected type",
            stage=stage,
            diagnostic=_public_surface_diagnostic(pilot),
        )
    result_before = str(result.render()).strip() if result is not None else ""
    button_disabled_before = button.disabled
    if button_disabled_before:
        raise InstalledAssetTuiError(
            "installed TUI asset action is disabled before public keyboard activation",
            stage=stage,
            diagnostic=_public_surface_diagnostic(pilot),
        )
    button.focus()
    await pilot.press("enter")
    await pilot.pause()
    return _PublicAssetActionTransition(
        button_id=button.id or selector.removeprefix("#"),
        result_before=result_before,
        result_after_activation=str(result.render()).strip() if result is not None else "",
        button_disabled_before=button_disabled_before,
    )


async def _set_public_input(*, pilot: Any, selector: str, value: str, stage: str) -> None:
    """Enter a synthetic value through one visible Textual Input control."""
    from textual.widgets import Input

    field = await _wait_for_public_selector(pilot, selector, stage=stage)
    if not isinstance(field, Input):
        raise InstalledAssetTuiError(
            "installed TUI control has an unexpected type",
            stage=stage,
            diagnostic=_public_surface_diagnostic(pilot),
        )
    field.value = value
    await pilot.pause()


async def _wait_for_asset_result(
    *,
    pilot: Any,
    expected_prefix: str,
    expected_suffix: str | None = None,
    stage: str,
    transition: _PublicAssetActionTransition | None = None,
    timeout_seconds: float = 45.0,
) -> str:
    """Wait for one public asset action result without preserving raw errors."""
    from textual.widgets import Static

    result = await _wait_for_public_selector(pilot, "#asset-result", stage=stage)
    if not isinstance(result, Static):
        raise InstalledAssetTuiError(
            "installed TUI asset result control has an unexpected type",
            stage=stage,
            diagnostic=_public_surface_diagnostic(pilot),
        )
    deadline = monotonic() + timeout_seconds
    changed_from_prior_result = transition is None
    rendered = ""
    while monotonic() < deadline:
        rendered = str(result.render()).strip()
        if transition is not None and rendered != transition.result_before:
            changed_from_prior_result = True
        if rendered.startswith("refused\t"):
            raise InstalledAssetTuiError(
                "installed TUI asset action displayed a refusal",
                stage=stage,
                diagnostic=(
                    _asset_transition_diagnostic(pilot=pilot, transition=transition, rendered=rendered)
                    if transition is not None
                    else _public_surface_diagnostic(pilot)
                ),
            )
        if (
            changed_from_prior_result
            and rendered.startswith(expected_prefix)
            and (expected_suffix is None or rendered.endswith(expected_suffix))
        ):
            # Let the message handler that published the visible result return
            # before the next keyboard action is sent.  This matters for a
            # replay against an encrypted history, whose thread can complete
            # immediately before the Textual handler unwinds.
            await pilot.pause()
            return rendered
        await pilot.pause()
    raise InstalledAssetTuiError(
        "installed TUI asset action did not publish its expected public result",
        stage=stage,
        diagnostic=(
            _asset_transition_diagnostic(pilot=pilot, transition=transition, rendered=rendered)
            if transition is not None
            else _public_surface_diagnostic(pilot)
        ),
    )


async def _wait_for_current_revision_id(*, pilot: Any, stage: str, timeout_seconds: float = 45.0) -> str:
    """Read a canonical immutable revision ID from the public screen projection."""
    from textual.widgets import Static

    current = await _wait_for_public_selector(pilot, "#asset-current-revision-id", stage=stage)
    if not isinstance(current, Static):
        raise InstalledAssetTuiError(
            "installed TUI current-revision control has an unexpected type",
            stage=stage,
            diagnostic=_public_surface_diagnostic(pilot),
        )
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        rendered = str(current.render()).strip()
        match = re.fullmatch(r"current_revision_id\t([0-9a-f]{64})", rendered)
        if match is not None:
            return str(match.group(1))
        await pilot.pause()
    raise InstalledAssetTuiError(
        "installed TUI did not expose the current immutable revision identity",
        stage=stage,
        diagnostic=_public_surface_diagnostic(pilot),
    )


async def _open_activity_asset_screen(*, pilot: Any) -> None:
    """Reach the public asset screen with the visible Ledger action button."""
    await _activate_public_button(
        pilot=pilot,
        selector="#ledger-activity-assets",
        stage="asset_screen_ready",
        capture_asset_result=False,
    )
    await _wait_for_public_selector(pilot, "#asset-id", stage="asset_screen_ready", timeout_seconds=45.0)


def _claim_result_reused(*, rendered: str, expected: bool, stage: str) -> None:
    """Validate only the public idempotency indicator, never persist the claim ID."""
    parts = rendered.split("\t")
    if len(parts) != 3 or parts[0] != "claim" or not parts[1] or parts[2] != f"reused={str(expected).lower()}":
        raise InstalledAssetTuiError(
            "installed TUI claim response did not satisfy its public idempotency contract",
            stage=stage,
        )


async def _exercise_linear_asset_lifecycle(*, pilot: Any, progress: Callable[[str], None]) -> dict[str, object]:
    """Create, correct, forecast, claim, and hand off one public asset lifecycle."""
    await _set_public_input(
        pilot=pilot,
        selector="#asset-id",
        value=_LINEAR_ASSET_ID,
        stage="asset_creation",
    )
    await _set_public_input(
        pilot=pilot,
        selector="#asset-revision-json",
        value=_LINEAR_REVISION_JSON,
        stage="asset_creation",
    )
    creation_action = await _activate_public_button(pilot=pilot, selector="#asset-create", stage="asset_creation")
    created = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix=f"created\t{_LINEAR_ASSET_ID}\trevisions=1",
        stage="asset_creation",
        transition=creation_action,
    )
    if created != f"created\t{_LINEAR_ASSET_ID}\trevisions=1":
        raise InstalledAssetTuiError(
            "installed TUI asset creation returned an unexpected public result",
            stage="asset_creation",
        )
    progress("asset_created")
    first_revision_id = await _wait_for_current_revision_id(pilot=pilot, stage="asset_inspection")

    inspection_action = await _activate_public_button(pilot=pilot, selector="#asset-inspect", stage="asset_inspection")
    inspected = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix=f"asset\t{_LINEAR_ASSET_ID}\trevisions=1",
        stage="asset_inspection",
        transition=inspection_action,
    )
    if inspected != f"asset\t{_LINEAR_ASSET_ID}\trevisions=1":
        raise InstalledAssetTuiError(
            "installed TUI asset inspection returned an unexpected public result",
            stage="asset_inspection",
        )
    progress("asset_inspected")
    if await _wait_for_current_revision_id(pilot=pilot, stage="asset_inspection") != first_revision_id:
        raise InstalledAssetTuiError(
            "installed TUI inspection did not retain its public current revision identity",
            stage="asset_inspection",
        )

    await _set_public_input(
        pilot=pilot,
        selector="#asset-revision-json",
        value=_linear_correction_json(supersedes_revision_id=first_revision_id),
        stage="asset_correction",
    )
    correction_action = await _activate_public_button(pilot=pilot, selector="#asset-correct", stage="asset_correction")
    corrected = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix=f"corrected\t{_LINEAR_ASSET_ID}\trevisions=2",
        stage="asset_correction",
        transition=correction_action,
    )
    if corrected != f"corrected\t{_LINEAR_ASSET_ID}\trevisions=2":
        raise InstalledAssetTuiError(
            "installed TUI asset correction returned an unexpected public result",
            stage="asset_correction",
        )
    corrected_revision_id = await _wait_for_current_revision_id(pilot=pilot, stage="asset_correction")
    if corrected_revision_id == first_revision_id:
        raise InstalledAssetTuiError(
            "installed TUI correction did not advance the public immutable revision identity",
            stage="asset_correction",
        )
    progress("asset_corrected")

    await _set_public_input(
        pilot=pilot,
        selector="#asset-selection-json",
        value=_LINEAR_SELECTION_JSON,
        stage="asset_forecast",
    )
    await _set_public_input(
        pilot=pilot,
        selector="#asset-covered-from",
        value="2025-01-01",
        stage="asset_forecast",
    )
    await _set_public_input(
        pilot=pilot,
        selector="#asset-covered-until",
        value="2026-01-01",
        stage="asset_forecast",
    )
    forecast_action = await _activate_public_button(pilot=pilot, selector="#asset-forecast", stage="asset_forecast")
    forecast = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix="forecast\t",
        stage="asset_forecast",
        transition=forecast_action,
    )
    forecast_parts = forecast.split("\t", maxsplit=2)
    if (
        len(forecast_parts) != 3
        or forecast_parts[1] != _LINEAR_CORRECTED_FORECAST_AMOUNT
        or not forecast_parts[2]
    ):
        raise InstalledAssetTuiError(
            "installed TUI forecast did not match the independently grounded linear amount",
            stage="asset_forecast",
        )
    progress("asset_forecast")

    first_claim_action = await _activate_public_button(pilot=pilot, selector="#asset-claim", stage="asset_claim")
    first_claim = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix="claim\t",
        expected_suffix="reused=false",
        stage="asset_claim",
        transition=first_claim_action,
    )
    _claim_result_reused(rendered=first_claim, expected=False, stage="asset_claim")
    progress("asset_claim")

    replay_claim_action = await _activate_public_button(
        pilot=pilot,
        selector="#asset-claim",
        stage="asset_claim_replay",
    )
    replayed_claim = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix="claim\t",
        expected_suffix="reused=true",
        stage="asset_claim_replay",
        transition=replay_claim_action,
    )
    _claim_result_reused(rendered=replayed_claim, expected=True, stage="asset_claim_replay")
    progress("asset_claim_replay")

    await _set_public_input(
        pilot=pilot,
        selector="#asset-filing-tax-year",
        value="2025",
        stage="asset_filing_handoff",
    )
    await _set_public_input(
        pilot=pilot,
        selector="#asset-filing-m130-period",
        value="4T",
        stage="asset_filing_handoff",
    )
    filing_handoff_action = await _activate_public_button(
        pilot=pilot,
        selector="#asset-filing-handoff",
        stage="asset_filing_handoff",
    )
    handoff = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix="filing_handoff\t",
        stage="asset_filing_handoff",
        transition=filing_handoff_action,
    )
    expected_handoff = (
        "filing_handoff"
        f"\tm100_material={_LINEAR_CORRECTED_FORECAST_AMOUNT}"
        "\tm100_intangible=0.00"
        f"\tm130_material={_LINEAR_CORRECTED_FORECAST_AMOUNT}"
        "\tm130_intangible=0.00"
    )
    if handoff != expected_handoff:
        raise InstalledAssetTuiError(
            "installed TUI filing handoff did not preserve the single effective claim",
            stage="asset_filing_handoff",
        )
    progress("asset_filing_handoff")
    return {
        "asset_created": True,
        "asset_inspected": True,
        "correction_uses_public_revision_identity": True,
        "forecast_amount": _LINEAR_CORRECTED_FORECAST_AMOUNT,
        "forecast_provenance_present": True,
        "claim_replay_reused": True,
        "filing_handoff_material_m100": _LINEAR_CORRECTED_FORECAST_AMOUNT,
        "filing_handoff_material_m130": _LINEAR_CORRECTED_FORECAST_AMOUNT,
        "inspection_revision_identity_exposed": True,
        "filing_handoff_control_exposed": True,
    }


async def _exercise_linear_asset_readback(*, pilot: Any, progress: Callable[[str], None]) -> dict[str, object]:
    """Read an asset created by a prior installed TUI process through its public screen."""
    await _set_public_input(
        pilot=pilot,
        selector="#asset-id",
        value=_LINEAR_ASSET_ID,
        stage="asset_readback",
    )
    readback_action = await _activate_public_button(pilot=pilot, selector="#asset-inspect", stage="asset_readback")
    inspected = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix=f"asset\t{_LINEAR_ASSET_ID}\trevisions=2",
        stage="asset_readback",
        transition=readback_action,
    )
    if inspected != f"asset\t{_LINEAR_ASSET_ID}\trevisions=2":
        raise InstalledAssetTuiError(
            "installed TUI fresh readback returned an unexpected public result",
            stage="asset_readback",
        )
    await _wait_for_current_revision_id(pilot=pilot, stage="asset_readback")
    progress("asset_readback")
    return {"fresh_process_asset_readback": True, "inspection_revision_identity_exposed": True}


async def _exercise_cli_created_asset_readback(*, pilot: Any, progress: Callable[[str], None]) -> dict[str, object]:
    """Read an asset created by the installed CLI through the public TUI screen."""
    await _set_public_input(
        pilot=pilot,
        selector="#asset-id",
        value=_LINEAR_ASSET_ID,
        stage="asset_cli_readback",
    )
    cli_readback_action = await _activate_public_button(
        pilot=pilot,
        selector="#asset-inspect",
        stage="asset_cli_readback",
    )
    inspected = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix=f"asset\t{_LINEAR_ASSET_ID}\trevisions=1",
        stage="asset_cli_readback",
        transition=cli_readback_action,
    )
    if inspected != f"asset\t{_LINEAR_ASSET_ID}\trevisions=1":
        raise InstalledAssetTuiError(
            "installed TUI CLI-created-asset readback returned an unexpected public result",
            stage="asset_cli_readback",
        )
    await _wait_for_current_revision_id(pilot=pilot, stage="asset_cli_readback")
    progress("asset_cli_readback")
    return {"cli_to_tui_asset_readback": True, "inspection_revision_identity_exposed": True}


async def _admit_existing_profile_session(*, passphrase: str) -> None:
    """Unlock a CLI-created profile through the shipped visible Login screen.

    This runs before the headless workbench launcher on purpose.  The normal
    launcher has no credential-autopilot hook: it may reuse a canonical live
    session in this process, but correctly refuses to prompt a headless child.
    The acceptance child therefore performs the same standalone public screen
    interaction an operator would, then lets the unmodified launcher prove its
    ordinary already-admitted branch.
    """
    from textual.widgets import Input

    from cadrumo.application.user_profile.login_interaction import (
        ProfileLoginInventoryState,
        attempt_profile_login,
        observe_profile_login_inventory,
    )
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.entrypoints.tui.components.host import ScreenHostApp
    from cadrumo.entrypoints.tui.secret.login import LoginScreen

    inventory = observe_profile_login_inventory()
    if inventory.state is not ProfileLoginInventoryState.RECOGNIZED:
        raise InstalledAssetTuiError(
            "installed TUI could not truthfully offer the existing profile for login",
            stage="session_admission",
        )
    diagnostic: dict[str, object] | None = None
    with bundled_indexed_authority().operation() as operation:
        screen = LoginScreen(
            choices=inventory.choices,
            authenticate=lambda candidate_profile_id, candidate_passphrase: attempt_profile_login(
                candidate_profile_id,
                candidate_passphrase,
                profile_decode_context=operation.profile_decode_context(),
            ),
            preselected=inventory.preselected_profile_id,
        )
        app = ScreenHostApp(screen)
        async with app.run_test(size=(160, 60)) as pilot:
            field = await _wait_for_public_selector(pilot, "#field-passphrase", stage="session_admission")
            if not isinstance(field, Input):
                raise InstalledAssetTuiError(
                    "installed TUI passphrase control has an unexpected type",
                    stage="session_admission",
                )
            field.value = passphrase
            await pilot.click("#btn-unlock")
            await pilot.app.workers.wait_for_complete()  # type: ignore[reportUnknownMemberType]
            await pilot.pause()
            diagnostic = _public_surface_diagnostic(pilot)
    if screen.outcome is None:
        raise InstalledAssetTuiError(
            "installed TUI Login screen did not establish a profile session",
            stage="session_admission",
            diagnostic=diagnostic,
        )


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
        # A CLI-created encrypted profile has no live session in this new
        # child process.  Establish it only through the shipped LoginScreen;
        # the subsequent headless launcher keeps its guard and reuses the
        # session through the canonical admission door.
        from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
        from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

        with live_exchange_rate_composition(), profile_adapter_composition():
            asyncio.run(
                asyncio.wait_for(
                    _admit_existing_profile_session(passphrase=passphrase),
                    timeout=45.0,
                )
            )
        completed.append("session_admitted")
        publish("session_admitted")
    observed: list[dict[str, object]] = []

    async def drive(pilot: Any) -> None:
        await pilot.pause()
        observed.append(_public_surface_diagnostic(pilot))
        completed.append("launcher_autopilot")
        publish("launcher_autopilot", diagnostic=observed[-1])
        if journey in {
            "home",
            "profile",
            "profile_ready",
            "ledger",
            "asset_screen",
            "asset_linear_lifecycle",
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
        if journey in {"ledger", "asset_screen", "asset_linear_lifecycle", "asset_readback", "asset_cli_readback"}:
            await _open_ledger_destination(pilot=pilot)
            observed.append(_public_surface_diagnostic(pilot))
            completed.append("ledger_ready")
            publish("ledger_ready", diagnostic=observed[-1])
        if journey in {"asset_screen", "asset_linear_lifecycle", "asset_readback", "asset_cli_readback"}:
            await _open_activity_asset_screen(pilot=pilot)
            observed.append(_public_surface_diagnostic(pilot))
            completed.append("asset_screen_ready")
            publish("asset_screen_ready", diagnostic=observed[-1])

        def record_asset_stage(stage: str) -> None:
            completed.append(stage)
            publish(stage, diagnostic=_public_surface_diagnostic(pilot), receipt_assertions=assertions or None)

        if journey == "asset_linear_lifecycle":
            assertions.update(await _exercise_linear_asset_lifecycle(pilot=pilot, progress=record_asset_stage))
            publish("asset_claim_replay", diagnostic=_public_surface_diagnostic(pilot), receipt_assertions=assertions)
        if journey == "asset_readback":
            assertions.update(await _exercise_linear_asset_readback(pilot=pilot, progress=record_asset_stage))
            publish("asset_readback", diagnostic=_public_surface_diagnostic(pilot), receipt_assertions=assertions)
        if journey == "asset_cli_readback":
            assertions.update(await _exercise_cli_created_asset_readback(pilot=pilot, progress=record_asset_stage))
            publish("asset_cli_readback", diagnostic=_public_surface_diagnostic(pilot), receipt_assertions=assertions)
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
    parser = argparse.ArgumentParser(description="Run a staged ASSETS-01 installed TUI child.")
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
            "asset_linear_lifecycle",
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
