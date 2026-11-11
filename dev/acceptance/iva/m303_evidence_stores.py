"""Independent installed M303 evidence scenarios in isolated secure stores."""

from __future__ import annotations

import argparse
import json
from typing import TYPE_CHECKING

from .filing_year import IvaJourneyYear
from .m303_evidence_child_process import child
from .m303_evidence_cli import (
    attest,
    calculate_args,
    read_revision,
    require_development_developer_header,
    revision_ids,
    setup_store,
)
from .m303_evidence_contracts import (
    COORDINATE_MISMATCH_REFUSAL_KEY,
    FIRST_QUARTER,
    FIRST_QUARTER_DAYS,
    MALFORMED_IDENTITY_REFUSAL_KEY,
    MISMATCHED_ATTACHMENT_ID,
    MISMATCHED_SHA256,
    MONTH,
    OUTSIDE_LAST_PERIOD,
    PERIOD,
    PRIOR_MONTH,
    WRONG_PERIOD,
    IvaInstalledM303Error,
    StoreEvidence,
)
from .m303_evidence_projection import require_outcomes, require_reopen, text, year_end_observed_at

if TYPE_CHECKING:
    pass


def tui_led_store(
    args: argparse.Namespace, journey_year: IvaJourneyYear, export_positions: tuple[str, str, str]
) -> StoreEvidence:
    """Build the store evidence for the TUI-led M303 scenario."""
    store, passphrase, cli, work_unit_id = setup_store(args, journey_year, "tui-led")
    wrong_id, wrong_sha = attest(
        cli, year=journey_year.year, period=WRONG_PERIOD, observed_at=year_end_observed_at(journey_year.year)
    )
    cli.run(("app", "modelo", "work", "calculate", work_unit_id), expect_refusal=True)
    cli.run(calculate_args(work_unit_id, attestation=None), expect_refusal=True)
    cli.run(
        calculate_args(work_unit_id, attestation=(MISMATCHED_ATTACHMENT_ID, MISMATCHED_SHA256)),
        expect_refusal=True,
    )
    cli.run(calculate_args(work_unit_id, attestation=(wrong_id, wrong_sha)), expect_refusal=True)
    if revision_ids(cli, work_unit_id):
        raise IvaInstalledM303Error("an installed CLI refusal persisted a calculation revision")

    calculate_handle, calculate_outcomes, _ = child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-led-calculate",
        work_unit_id=work_unit_id,
        extra=("--wrong-attachment-id", wrong_id, "--wrong-sha256", wrong_sha),
    )
    require_outcomes(
        calculate_outcomes,
        {
            "missing_booleans": ("form_refused", "tui.modelo.m303_evidence.required"),
            "cancelled": ("cancelled_without_request", "tui.modelo.m303_evidence.cancelled"),
            "mismatched_pair": ("refused", MALFORMED_IDENTITY_REFUSAL_KEY),
            "wrong_filing_context": ("refused", COORDINATE_MISMATCH_REFUSAL_KEY),
            "calculate": ("succeeded", None),
            "verify": ("succeeded", None),
        },
    )

    revisions = revision_ids(cli, work_unit_id)
    if len(revisions) != 1:
        raise IvaInstalledM303Error(f"TUI refusals or calculation left {len(revisions)} revisions, expected one")
    tui_export_path = args.output_root / "tui-led-tui-export.boe"
    reopen_handle, reopen_outcomes, readback = child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-reopen",
        work_unit_id=work_unit_id,
        extra=("--calculation-revision-id", revisions[0], "--export-path", str(tui_export_path)),
    )
    tui_reopen = require_reopen(readback, scenario="tui_led")
    require_outcomes(reopen_outcomes, {"export": ("succeeded", None)})
    matches, verified = read_revision(cli, revisions[0])
    if not (matches and verified):
        raise IvaInstalledM303Error("installed CLI readback of the TUI revision failed the oracle or verification")
    cli_export_path = args.output_root / "tui-led-cli-export.boe"
    cli.run(("app", "modelo", "export", work_unit_id, "--output", str(cli_export_path)))
    tui_bytes = tui_export_path.read_bytes()
    if cli_export_path.read_bytes() != tui_bytes:
        raise IvaInstalledM303Error("installed CLI and TUI exports of one revision wrote different bytes")
    require_development_developer_header(tui_bytes, export_positions)
    return StoreEvidence(
        scenario="tui_led",
        work_unit_id=work_unit_id,
        calculation_revision_id=revisions[0],
        revision_count=len(revisions),
        cli_resultado_matches_oracle=matches,
        cli_revision_verified=verified,
        cli_recalculated_same_revision=None,
        changed_evidence_produced_distinct_revision=None,
        tui_reopen=tui_reopen,
        commands=tuple(cli.outcomes),
        children=(calculate_handle, reopen_handle),
        child_outcomes=(*calculate_outcomes, *reopen_outcomes),
    )


def continuation_store(args: argparse.Namespace, journey_year: IvaJourneyYear) -> StoreEvidence:
    """Build the store evidence for the continuation scenario."""
    store, passphrase, cli, work_unit_id = setup_store(args, journey_year, "continuation")
    attachment_id, sha256 = attest(
        cli, year=journey_year.year, period=PERIOD, observed_at=year_end_observed_at(journey_year.year)
    )
    calculate_handle, calculate_outcomes, _ = child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-continue-calculate",
        work_unit_id=work_unit_id,
        extra=("--existing-attachment-id", attachment_id, "--existing-sha256", sha256),
    )
    require_outcomes(calculate_outcomes, {"calculate": ("succeeded", None)})
    tui_revisions = revision_ids(cli, work_unit_id)
    if len(tui_revisions) != 1:
        raise IvaInstalledM303Error("TUI continuation did not persist exactly one revision")
    recalculated = cli.run(calculate_args(work_unit_id, attestation=(attachment_id, sha256)))
    same_revision = recalculated.get("calculation_revision_id") == tui_revisions[0]
    if not same_revision or revision_ids(cli, work_unit_id) != tui_revisions:
        raise IvaInstalledM303Error("installed CLI recalculation with the same evidence produced another revision")
    verification = cli.run(("app", "modelo", "work", "verify", tui_revisions[0]))
    if verification.get("granted_verificado_completo") is not True:
        raise IvaInstalledM303Error("installed CLI verification of the TUI revision was not granted")
    reopen_handle, reopen_outcomes, readback = child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-reopen",
        work_unit_id=work_unit_id,
        extra=("--calculation-revision-id", tui_revisions[0]),
    )
    tui_reopen = require_reopen(readback, scenario="continuation")
    matches, verified = read_revision(cli, tui_revisions[0])
    changed = cli.run(calculate_args(work_unit_id, attestation=(attachment_id, sha256), joint_return_elected=True))
    distinct = changed.get("calculation_revision_id") not in {None, tui_revisions[0]}
    if not (matches and verified and distinct):
        raise IvaInstalledM303Error("continuation readback, verification or evidence-identity control failed")
    return StoreEvidence(
        scenario="continuation",
        work_unit_id=work_unit_id,
        calculation_revision_id=tui_revisions[0],
        revision_count=len(revision_ids(cli, work_unit_id)),
        cli_resultado_matches_oracle=matches,
        cli_revision_verified=verified,
        cli_recalculated_same_revision=same_revision,
        changed_evidence_produced_distinct_revision=distinct,
        tui_reopen=tui_reopen,
        commands=tuple(cli.outcomes),
        children=(calculate_handle, reopen_handle),
        child_outcomes=(*calculate_outcomes, *reopen_outcomes),
    )


def monthly_store(args: argparse.Namespace, journey_year: IvaJourneyYear) -> StoreEvidence:
    """A REDEME-registered filer settles monthly and answers the Modelo 390 exemption in 12, as others do in 4T."""
    store, passphrase, cli, work_unit_id = setup_store(
        args, journey_year, "monthly", period=MONTH, wallet_period=PRIOR_MONTH, monthly_filer=True
    )
    attestation = attest(cli, year=journey_year.year, period=MONTH, observed_at=year_end_observed_at(journey_year.year))
    calculated = cli.run(calculate_args(work_unit_id, attestation=attestation))
    revision_id = text(calculated.get("calculation_revision_id"), label="monthly calculate")
    verification = cli.run(("app", "modelo", "work", "verify", revision_id))
    if verification.get("granted_verificado_completo") is not True:
        raise IvaInstalledM303Error("installed CLI verification of the monthly revision was not granted")
    reopen_handle, reopen_outcomes, readback = child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-reopen",
        work_unit_id=work_unit_id,
        extra=("--calculation-revision-id", revision_id),
    )
    tui_reopen = require_reopen(readback, scenario="monthly")
    matches, verified = read_revision(cli, revision_id)
    if not (matches and verified):
        raise IvaInstalledM303Error("installed CLI readback of the monthly revision failed the oracle or verification")
    return StoreEvidence(
        scenario="monthly",
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        revision_count=len(revision_ids(cli, work_unit_id)),
        cli_resultado_matches_oracle=matches,
        cli_revision_verified=verified,
        cli_recalculated_same_revision=None,
        changed_evidence_produced_distinct_revision=None,
        tui_reopen=tui_reopen,
        commands=tuple(cli.outcomes),
        children=(reopen_handle,),
        child_outcomes=tuple(reopen_outcomes),
    )


def first_quarter_store(args: argparse.Namespace, journey_year: IvaJourneyYear) -> StoreEvidence:
    """1T asks only the joint-return election: attestation flags are refused and the TUI form asks one question."""
    store, passphrase, cli, work_unit_id = setup_store(
        args,
        journey_year,
        "first-quarter",
        period=FIRST_QUARTER,
        wallet_period=FIRST_QUARTER,
        days=FIRST_QUARTER_DAYS,
    )
    refused = cli.run(
        calculate_args(work_unit_id, attestation=(MISMATCHED_ATTACHMENT_ID, MISMATCHED_ATTACHMENT_ID)),
        expect_refusal=True,
    )
    if OUTSIDE_LAST_PERIOD not in json.dumps(refused, sort_keys=True):
        raise IvaInstalledM303Error("installed CLI did not refuse an attestation the 1T return does not ask for")
    if revision_ids(cli, work_unit_id):
        raise IvaInstalledM303Error("an installed CLI refusal persisted a calculation revision")
    calculate_handle, calculate_outcomes, _ = child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-joint-only-calculate",
        work_unit_id=work_unit_id,
    )
    require_outcomes(calculate_outcomes, {"calculate": ("succeeded", None), "verify": ("succeeded", None)})
    revisions = revision_ids(cli, work_unit_id)
    if len(revisions) != 1:
        raise IvaInstalledM303Error("the 1T TUI calculation did not persist exactly one revision")
    recalculated = cli.run(calculate_args(work_unit_id, attestation=None))
    same_revision = recalculated.get("calculation_revision_id") == revisions[0]
    reopen_handle, reopen_outcomes, readback = child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-reopen",
        work_unit_id=work_unit_id,
        extra=("--calculation-revision-id", revisions[0]),
    )
    tui_reopen = require_reopen(readback, scenario="first_quarter")
    matches, verified = read_revision(cli, revisions[0])
    if not (matches and verified and same_revision):
        raise IvaInstalledM303Error("1T readback, verification or CLI recalculation identity failed")
    return StoreEvidence(
        scenario="first_quarter",
        work_unit_id=work_unit_id,
        calculation_revision_id=revisions[0],
        revision_count=len(revision_ids(cli, work_unit_id)),
        cli_resultado_matches_oracle=matches,
        cli_revision_verified=verified,
        cli_recalculated_same_revision=same_revision,
        changed_evidence_produced_distinct_revision=None,
        tui_reopen=tui_reopen,
        commands=tuple(cli.outcomes),
        children=(calculate_handle, reopen_handle),
        child_outcomes=(*calculate_outcomes, *reopen_outcomes),
    )
