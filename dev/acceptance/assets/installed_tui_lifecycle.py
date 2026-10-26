"""Exercise the public asset lifecycle and fresh-process readback controls."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .installed_method_fixture import (
    METHOD_ASSET_ID,
    METHOD_CORRECTED_FORECAST_AMOUNT,
    METHOD_REVISION_JSON,
    method_correction_json,
)
from .installed_tui_contracts import InstalledAssetTuiError
from .installed_tui_controls import (
    _activate_public_button,
    _set_public_input,
    _wait_for_asset_result,
    _wait_for_current_revision_id,
)


def _claim_result_reused(*, rendered: str, expected: bool, stage: str) -> None:
    """Validate only the public idempotency indicator, never persist the claim ID."""
    parts = rendered.split("\t")
    if len(parts) != 3 or parts[0] != "claim" or not parts[1] or parts[2] != f"reused={str(expected).lower()}":
        raise InstalledAssetTuiError(
            "installed TUI claim response did not satisfy its public idempotency contract",
            stage=stage,
        )


def _assert_method_forecast_result(forecast: str) -> None:
    forecast_parts = forecast.split("\t", maxsplit=2)
    if len(forecast_parts) != 3 or forecast_parts[1] != METHOD_CORRECTED_FORECAST_AMOUNT or not forecast_parts[2]:
        raise InstalledAssetTuiError(
            "installed TUI forecast did not match the independently grounded constant-percentage amount",
            stage="asset_forecast",
        )


async def _exercise_method_asset_lifecycle(*, pilot: Any, progress: Callable[[str], None]) -> dict[str, object]:
    """Create, correct, forecast, claim, and hand off one public asset lifecycle."""
    await _set_public_input(
        pilot=pilot,
        selector="#asset-id",
        value=METHOD_ASSET_ID,
        stage="asset_creation",
    )
    await _set_public_input(
        pilot=pilot,
        selector="#asset-revision-json",
        value=METHOD_REVISION_JSON,
        stage="asset_creation",
    )
    creation_action = await _activate_public_button(pilot=pilot, selector="#asset-create", stage="asset_creation")
    created = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix=f"created\t{METHOD_ASSET_ID}\trevisions=1",
        stage="asset_creation",
        transition=creation_action,
    )
    if created != f"created\t{METHOD_ASSET_ID}\trevisions=1":
        raise InstalledAssetTuiError(
            "installed TUI asset creation returned an unexpected public result",
            stage="asset_creation",
        )
    progress("asset_created")
    first_revision_id = await _wait_for_current_revision_id(pilot=pilot, stage="asset_inspection")

    inspection_action = await _activate_public_button(pilot=pilot, selector="#asset-inspect", stage="asset_inspection")
    inspected = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix=f"asset\t{METHOD_ASSET_ID}\trevisions=1",
        stage="asset_inspection",
        transition=inspection_action,
    )
    if inspected != f"asset\t{METHOD_ASSET_ID}\trevisions=1":
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
        value=method_correction_json(supersedes_revision_id=first_revision_id),
        stage="asset_correction",
    )
    correction_action = await _activate_public_button(pilot=pilot, selector="#asset-correct", stage="asset_correction")
    corrected = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix=f"corrected\t{METHOD_ASSET_ID}\trevisions=2",
        stage="asset_correction",
        transition=correction_action,
    )
    if corrected != f"corrected\t{METHOD_ASSET_ID}\trevisions=2":
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
    _assert_method_forecast_result(forecast)
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

    # Replace the recorded claim through the public supersession control.  The
    # superseding forecast leaves the replaced claim out, so it reproduces the
    # same amount, and the filing handoff below must still count one claim.
    superseded_claim_id = first_claim.split("\t")[1]
    await _set_public_input(
        pilot=pilot,
        selector="#asset-supersedes-claim-id",
        value=superseded_claim_id,
        stage="asset_superseding_forecast",
    )
    superseding_forecast_action = await _activate_public_button(
        pilot=pilot,
        selector="#asset-forecast",
        stage="asset_superseding_forecast",
    )
    await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix=f"forecast\t{METHOD_CORRECTED_FORECAST_AMOUNT}\t",
        stage="asset_superseding_forecast",
        transition=superseding_forecast_action,
    )
    progress("asset_superseding_forecast")
    superseding_claim_action = await _activate_public_button(
        pilot=pilot,
        selector="#asset-claim",
        stage="asset_superseding_claim",
    )
    superseding_claim = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix="claim\t",
        expected_suffix="reused=false",
        stage="asset_superseding_claim",
        transition=superseding_claim_action,
    )
    _claim_result_reused(rendered=superseding_claim, expected=False, stage="asset_superseding_claim")
    if superseding_claim.split("\t")[1] == superseded_claim_id:
        raise InstalledAssetTuiError(
            "installed TUI superseding claim did not record a new claim identity",
            stage="asset_superseding_claim",
        )
    progress("asset_superseding_claim")

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
        f"\tm100_material={METHOD_CORRECTED_FORECAST_AMOUNT}"
        "\tm100_intangible=0.00"
        f"\tm130_material={METHOD_CORRECTED_FORECAST_AMOUNT}"
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
        "forecast_amount": METHOD_CORRECTED_FORECAST_AMOUNT,
        "forecast_provenance_present": True,
        "claim_replay_reused": True,
        "superseding_claim_replaced_the_first": True,
        "filing_handoff_material_m100": METHOD_CORRECTED_FORECAST_AMOUNT,
        "filing_handoff_material_m130": METHOD_CORRECTED_FORECAST_AMOUNT,
        "inspection_revision_identity_exposed": True,
        "filing_handoff_control_exposed": True,
    }


async def _exercise_method_asset_readback(*, pilot: Any, progress: Callable[[str], None]) -> dict[str, object]:
    """Read an asset created by a prior installed TUI process through its public screen."""
    await _set_public_input(
        pilot=pilot,
        selector="#asset-id",
        value=METHOD_ASSET_ID,
        stage="asset_readback",
    )
    readback_action = await _activate_public_button(pilot=pilot, selector="#asset-inspect", stage="asset_readback")
    inspected = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix=f"asset\t{METHOD_ASSET_ID}\trevisions=2",
        stage="asset_readback",
        transition=readback_action,
    )
    if inspected != f"asset\t{METHOD_ASSET_ID}\trevisions=2":
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
        value=METHOD_ASSET_ID,
        stage="asset_cli_readback",
    )
    cli_readback_action = await _activate_public_button(
        pilot=pilot,
        selector="#asset-inspect",
        stage="asset_cli_readback",
    )
    inspected = await _wait_for_asset_result(
        pilot=pilot,
        expected_prefix=f"asset\t{METHOD_ASSET_ID}\trevisions=1",
        stage="asset_cli_readback",
        transition=cli_readback_action,
    )
    if inspected != f"asset\t{METHOD_ASSET_ID}\trevisions=1":
        raise InstalledAssetTuiError(
            "installed TUI CLI-created-asset readback returned an unexpected public result",
            stage="asset_cli_readback",
        )
    await _wait_for_current_revision_id(pilot=pilot, stage="asset_cli_readback")
    progress("asset_cli_readback")
    return {"cli_to_tui_asset_readback": True, "inspection_revision_identity_exposed": True}
