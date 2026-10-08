"""Admitted installed TUI continuation child and sanitized completion receipt."""

from __future__ import annotations

import asyncio
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dev.acceptance.installed_cli import authority_generation

from .continuation_contracts import _SCHEMA_VERSION, _Direction
from .continuation_tui_stages import (
    _complete_visible_workflow,
    _prepare_visible_partial_workflow,
    _resume_visible_partial_workflow,
)
from .installed_tui_child import (
    InstalledTuiChildError,
    admit_installed_session,
    installed_product_evidence,
    register_profile_through_installed_tui,
)
from .scenario import build_scenario
from .tui_contracts import ContinuationStateEvidence


def run_tui_continuation_child(
    *, direction: _Direction, workspace_root: Path, profile_label: str, passphrase: str, year: int, scratch: Path
) -> dict[str, object]:
    """Run the TUI side of one continuation through an installed launcher."""
    product = installed_product_evidence(workspace_root=workspace_root)
    scenario = build_scenario(year)
    authority_root = Path(os.environ["CADRUMO_AUTHORITY_ROOT"]).resolve()
    generation = authority_generation(authority_root)
    handoff: ContinuationStateEvidence | None = None
    completion: ContinuationStateEvidence | None = None
    validation: dict[str, object] = {}
    readback_error: str | None = None
    callback_entered = False

    from cadrumo.entrypoints.tui.launcher import main

    if direction == "tui_to_cli":
        from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
        from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

        with live_exchange_rate_composition(), profile_adapter_composition():
            asyncio.run(register_profile_through_installed_tui(profile_label=profile_label, passphrase=passphrase))

    async def drive(pilot: Any) -> None:
        nonlocal handoff, completion, validation, readback_error
        if direction == "cli_to_tui":
            handoff, readback_error = await _resume_visible_partial_workflow(pilot, scenario, scratch, generation, year)
            if readback_error is not None:
                return
        else:
            handoff = await _prepare_visible_partial_workflow(pilot, scenario, scratch, generation, year)
            pilot.app.exit()
            return
        completion, validation = await _complete_visible_workflow(
            pilot, scenario, scratch, generation, year, workspace_root
        )
        pilot.app.exit()

    async def launched(pilot: Any) -> None:
        nonlocal callback_entered, readback_error
        callback_entered = True
        try:
            if not await admit_installed_session(pilot=pilot, passphrase=passphrase):
                return
            await drive(pilot)
        except InstalledTuiChildError as error:
            readback_error = str(error)
            pilot.app.exit()
        except Exception as error:
            readback_error = f"unexpected continuation admission/workflow failure: {type(error).__name__}"
            pilot.app.exit()

    exit_code = main(headless=True, auto_pilot=launched)
    if readback_error is not None:
        raise InstalledTuiChildError(readback_error)
    if exit_code != 0 or handoff is None:
        raise InstalledTuiChildError(
            "installed continuation launcher did not reach its partial workflow boundary "
            f"(exit_code={exit_code}, callback_entered={callback_entered})"
        )
    document: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "status": "proven",
        "direction": direction,
        "product_origin": product.product_origin,
        "product_init_sha256": product.product_init_sha256,
        "handoff_state": asdict(handoff),
        "annual_xsd_validation": validation,
    }
    if completion is not None:
        document["completion_state"] = asdict(completion)
    return document
