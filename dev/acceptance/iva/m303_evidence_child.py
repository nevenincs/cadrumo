"""Admitted installed M303 child workflow over caller-held outcome observations."""

from __future__ import annotations

import argparse
import asyncio
from typing import TYPE_CHECKING, Any, cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    admit_installed_session,
    installed_product_evidence,
)

from .m303_evidence_contracts import (
    COORDINATE_MISMATCH_REFUSAL_KEY,
    EVIDENCE_SUBMIT_ID,
    MALFORMED_IDENTITY_REFUSAL_KEY,
    MISMATCHED_ATTACHMENT_ID,
    MISMATCHED_SHA256,
    PERIOD,
    SCHEMA_VERSION,
    ChildMode,
    ChildReceipt,
    ReopenReadback,
    TuiOutcome,
)
from .m303_evidence_form import calculate_and_verify, fill_evidence_form, form_refusals, open_evidence_form
from .m303_evidence_navigation import listed_revision
from .m303_evidence_projection import year_end_observed_at
from .m303_evidence_refusals import settle_expected_refusal
from .m303_evidence_workbench import attempt_export, verify, workbench_resultado

if TYPE_CHECKING:
    pass


async def _admit_session(pilot: Any, *, passphrase: str, seconds: float = 300.0) -> bool:
    """Drive runtime admission within the existing slow-composition bound."""
    return await admit_installed_session(
        pilot=pilot, passphrase=passphrase, deadline=asyncio.get_running_loop().time() + seconds
    )


def run_child(args: argparse.Namespace, *, passphrase: str) -> ChildReceipt:
    """Run the modelo 303 evidence child process in its mode and return its receipt."""
    product = installed_product_evidence(workspace_root=args.workspace_root)
    mode = cast(ChildMode, args.child)
    work_unit_id = cast(str, args.work_unit_id)
    observed_at = year_end_observed_at(cast(int, args.year))
    outcomes: list[TuiOutcome] = []
    reopen: list[ReopenReadback] = []
    failure: list[InstalledTuiChildError] = []

    from cadrumo_runtime.host.frontend.tui.launcher import main as launch

    async def drive(pilot: Any) -> None:
        try:
            if mode == "tui-led-calculate":
                outcomes.extend(await form_refusals(pilot, work_unit_id=work_unit_id, observed_at=observed_at))
                coordinate = {"period": PERIOD, "filing_year": cast(int, args.year)}
                for step, attachment_id, sha256, refusal_key, refusal_context in (
                    (
                        "mismatched_pair",
                        MISMATCHED_ATTACHMENT_ID,
                        MISMATCHED_SHA256,
                        MALFORMED_IDENTITY_REFUSAL_KEY,
                        {},
                    ),
                    (
                        "wrong_filing_context",
                        args.wrong_attachment_id,
                        args.wrong_sha256,
                        COORDINATE_MISMATCH_REFUSAL_KEY,
                        coordinate,
                    ),
                ):
                    await open_evidence_form(pilot, work_unit_id=work_unit_id)
                    fill_evidence_form(pilot, attachment_id=attachment_id, sha256=sha256)
                    outcomes.append(
                        await settle_expected_refusal(
                            pilot,
                            activation_id=EVIDENCE_SUBMIT_ID,
                            step=step,
                            refusal_key=refusal_key,
                            refusal_context=refusal_context,
                        )
                    )
                outcomes.extend(
                    await calculate_and_verify(pilot, work_unit_id=work_unit_id, form={"observed_at": observed_at})
                )
                outcomes.append(await verify(pilot, work_unit_id=work_unit_id))
            elif mode == "tui-joint-only-calculate":
                outcomes.extend(
                    await calculate_and_verify(pilot, work_unit_id=work_unit_id, form={}, asks_modelo_390=False)
                )
                outcomes.append(await verify(pilot, work_unit_id=work_unit_id))
            elif mode == "tui-continue-calculate":
                outcomes.extend(
                    await calculate_and_verify(
                        pilot,
                        work_unit_id=work_unit_id,
                        form={"attachment_id": args.existing_attachment_id, "sha256": args.existing_sha256},
                    )
                )
            else:
                listed_current, state = await listed_revision(
                    pilot, calculation_revision_id=cast(str, args.calculation_revision_id)
                )
                origin, matches_oracle = await workbench_resultado(pilot, work_unit_id=work_unit_id)
                reopen.append(
                    ReopenReadback(
                        revision_listed_current=listed_current,
                        revision_state=state,
                        resultado_origin=origin,
                        resultado_matches_oracle=matches_oracle,
                    )
                )
                if args.export_path:
                    outcomes.append(
                        await attempt_export(pilot, work_unit_id=work_unit_id, output_path=args.export_path)
                    )
        except InstalledTuiChildError as error:
            failure.append(error)
        finally:
            pilot.app.exit()

    async def autopilot(pilot: Any) -> None:
        try:
            if not await _admit_session(pilot, passphrase=passphrase):
                return
        except InstalledTuiChildError as error:
            failure.append(error)
            pilot.app.exit()
            return
        await drive(pilot)

    exit_code = launch(headless=True, auto_pilot=autopilot)
    if failure:
        raise failure[0]
    if exit_code != 0:
        raise InstalledTuiChildError(f"installed TUI {mode} child exited {exit_code}")
    return ChildReceipt(
        schema_version=SCHEMA_VERSION,
        status="proven",
        mode=mode,
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        outcomes=tuple(outcomes),
        reopen=reopen[0] if reopen else None,
    )
