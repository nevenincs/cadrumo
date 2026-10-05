"""Independent installed M303 evidence scenarios in isolated secure stores."""

from __future__ import annotations

import argparse
import json
from typing import TYPE_CHECKING

from .filing_year import IvaJourneyYear
from .m303_evidence_child_process import _child
from .m303_evidence_cli import (
    _attest,
    _calculate_args,
    _read_revision,
    _require_development_developer_header,
    _revision_ids,
    _setup_store,
)
from .m303_evidence_contracts import (
    _ATTESTATION_REFUSAL_KEY,
    _FIRST_QUARTER,
    _FIRST_QUARTER_DAYS,
    _MISMATCHED_ATTACHMENT_ID,
    _MISMATCHED_SHA256,
    _MONTH,
    _OUTSIDE_LAST_PERIOD,
    _PERIOD,
    _PRIOR_MONTH,
    _WRONG_PERIOD,
    IvaInstalledM303Error,
    StoreEvidence,
)
from .m303_evidence_projection import _text, _year_end_observed_at, require_outcomes, require_reopen

if TYPE_CHECKING:
    pass


def _tui_led_store(
    args: argparse.Namespace, journey_year: IvaJourneyYear, export_positions: tuple[str, str, str]
) -> StoreEvidence:
    store, passphrase, cli, work_unit_id = _setup_store(args, journey_year, "tui-led")
    wrong_id, wrong_sha = _attest(
        cli, year=journey_year.year, period=_WRONG_PERIOD, observed_at=_year_end_observed_at(journey_year.year)
    )
    cli.run(("app", "modelo", "work", "calculate", work_unit_id), expect_refusal=True)
    cli.run(_calculate_args(work_unit_id, attestation=None), expect_refusal=True)
    cli.run(
        _calculate_args(work_unit_id, attestation=(_MISMATCHED_ATTACHMENT_ID, _MISMATCHED_SHA256)),
        expect_refusal=True,
    )
    cli.run(_calculate_args(work_unit_id, attestation=(wrong_id, wrong_sha)), expect_refusal=True)
    if _revision_ids(cli, work_unit_id):
        raise IvaInstalledM303Error("an installed CLI refusal persisted a calculation revision")

    calculate_handle, calculate_outcomes, _ = _child(
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
            "mismatched_pair": ("refused", _ATTESTATION_REFUSAL_KEY),
            "wrong_filing_context": ("refused", _ATTESTATION_REFUSAL_KEY),
            "calculate": ("succeeded", None),
            "verify": ("succeeded", None),
        },
    )

    revisions = _revision_ids(cli, work_unit_id)
    if len(revisions) != 1:
        raise IvaInstalledM303Error(f"TUI refusals or calculation left {len(revisions)} revisions, expected one")
    tui_export_path = args.output_root / "tui-led-tui-export.boe"
    reopen_handle, reopen_outcomes, readback = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-reopen",
        work_unit_id=work_unit_id,
        extra=("--calculation-revision-id", revisions[0], "--export-path", str(tui_export_path)),
    )
    tui_reopen = require_reopen(readback, scenario="tui_led")
    require_outcomes(reopen_outcomes, {"export": ("succeeded", None)})
    matches, verified = _read_revision(cli, revisions[0])
    if not (matches and verified):
        raise IvaInstalledM303Error("installed CLI readback of the TUI revision failed the oracle or verification")
    cli_export_path = args.output_root / "tui-led-cli-export.boe"
    cli.run(("app", "modelo", "export", work_unit_id, "--output", str(cli_export_path)))
    tui_bytes = tui_export_path.read_bytes()
    if cli_export_path.read_bytes() != tui_bytes:
        raise IvaInstalledM303Error("installed CLI and TUI exports of one revision wrote different bytes")
    _require_development_developer_header(tui_bytes, export_positions)
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


def _continuation_store(args: argparse.Namespace, journey_year: IvaJourneyYear) -> StoreEvidence:
    store, passphrase, cli, work_unit_id = _setup_store(args, journey_year, "continuation")
    attachment_id, sha256 = _attest(
        cli, year=journey_year.year, period=_PERIOD, observed_at=_year_end_observed_at(journey_year.year)
    )
    calculate_handle, calculate_outcomes, _ = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-continue-calculate",
        work_unit_id=work_unit_id,
        extra=("--existing-attachment-id", attachment_id, "--existing-sha256", sha256),
    )
    require_outcomes(calculate_outcomes, {"calculate": ("succeeded", None)})
    tui_revisions = _revision_ids(cli, work_unit_id)
    if len(tui_revisions) != 1:
        raise IvaInstalledM303Error("TUI continuation did not persist exactly one revision")
    recalculated = cli.run(_calculate_args(work_unit_id, attestation=(attachment_id, sha256)))
    same_revision = recalculated.get("calculation_revision_id") == tui_revisions[0]
    if not same_revision or _revision_ids(cli, work_unit_id) != tui_revisions:
        raise IvaInstalledM303Error("installed CLI recalculation with the same evidence produced another revision")
    verification = cli.run(("app", "modelo", "work", "verify", tui_revisions[0]))
    if verification.get("granted_verificado_completo") is not True:
        raise IvaInstalledM303Error("installed CLI verification of the TUI revision was not granted")
    reopen_handle, reopen_outcomes, readback = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-reopen",
        work_unit_id=work_unit_id,
        extra=("--calculation-revision-id", tui_revisions[0]),
    )
    tui_reopen = require_reopen(readback, scenario="continuation")
    matches, verified = _read_revision(cli, tui_revisions[0])
    changed = cli.run(_calculate_args(work_unit_id, attestation=(attachment_id, sha256), joint_return_elected=True))
    distinct = changed.get("calculation_revision_id") not in {None, tui_revisions[0]}
    if not (matches and verified and distinct):
        raise IvaInstalledM303Error("continuation readback, verification or evidence-identity control failed")
    return StoreEvidence(
        scenario="continuation",
        work_unit_id=work_unit_id,
        calculation_revision_id=tui_revisions[0],
        revision_count=len(_revision_ids(cli, work_unit_id)),
        cli_resultado_matches_oracle=matches,
        cli_revision_verified=verified,
        cli_recalculated_same_revision=same_revision,
        changed_evidence_produced_distinct_revision=distinct,
        tui_reopen=tui_reopen,
        commands=tuple(cli.outcomes),
        children=(calculate_handle, reopen_handle),
        child_outcomes=(*calculate_outcomes, *reopen_outcomes),
    )


def _monthly_store(args: argparse.Namespace, journey_year: IvaJourneyYear) -> StoreEvidence:
    """A REDEME-registered filer settles monthly and answers the Modelo 390 exemption in 12, as others do in 4T."""
    store, passphrase, cli, work_unit_id = _setup_store(
        args, journey_year, "monthly", period=_MONTH, wallet_period=_PRIOR_MONTH, monthly_filer=True
    )
    attestation = _attest(
        cli, year=journey_year.year, period=_MONTH, observed_at=_year_end_observed_at(journey_year.year)
    )
    calculated = cli.run(_calculate_args(work_unit_id, attestation=attestation))
    revision_id = _text(calculated.get("calculation_revision_id"), label="monthly calculate")
    verification = cli.run(("app", "modelo", "work", "verify", revision_id))
    if verification.get("granted_verificado_completo") is not True:
        raise IvaInstalledM303Error("installed CLI verification of the monthly revision was not granted")
    reopen_handle, reopen_outcomes, readback = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-reopen",
        work_unit_id=work_unit_id,
        extra=("--calculation-revision-id", revision_id),
    )
    tui_reopen = require_reopen(readback, scenario="monthly")
    matches, verified = _read_revision(cli, revision_id)
    if not (matches and verified):
        raise IvaInstalledM303Error("installed CLI readback of the monthly revision failed the oracle or verification")
    return StoreEvidence(
        scenario="monthly",
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        revision_count=len(_revision_ids(cli, work_unit_id)),
        cli_resultado_matches_oracle=matches,
        cli_revision_verified=verified,
        cli_recalculated_same_revision=None,
        changed_evidence_produced_distinct_revision=None,
        tui_reopen=tui_reopen,
        commands=tuple(cli.outcomes),
        children=(reopen_handle,),
        child_outcomes=tuple(reopen_outcomes),
    )


def _first_quarter_store(args: argparse.Namespace, journey_year: IvaJourneyYear) -> StoreEvidence:
    """1T asks only the joint-return election: attestation flags are refused and the TUI form asks one question."""
    store, passphrase, cli, work_unit_id = _setup_store(
        args,
        journey_year,
        "first-quarter",
        period=_FIRST_QUARTER,
        wallet_period=_FIRST_QUARTER,
        days=_FIRST_QUARTER_DAYS,
    )
    refused = cli.run(
        _calculate_args(work_unit_id, attestation=(_MISMATCHED_ATTACHMENT_ID, _MISMATCHED_ATTACHMENT_ID)),
        expect_refusal=True,
    )
    if _OUTSIDE_LAST_PERIOD not in json.dumps(refused, sort_keys=True):
        raise IvaInstalledM303Error("installed CLI did not refuse an attestation the 1T return does not ask for")
    if _revision_ids(cli, work_unit_id):
        raise IvaInstalledM303Error("an installed CLI refusal persisted a calculation revision")
    calculate_handle, calculate_outcomes, _ = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-joint-only-calculate",
        work_unit_id=work_unit_id,
    )
    require_outcomes(calculate_outcomes, {"calculate": ("succeeded", None), "verify": ("succeeded", None)})
    revisions = _revision_ids(cli, work_unit_id)
    if len(revisions) != 1:
        raise IvaInstalledM303Error("the 1T TUI calculation did not persist exactly one revision")
    recalculated = cli.run(_calculate_args(work_unit_id, attestation=None))
    same_revision = recalculated.get("calculation_revision_id") == revisions[0]
    reopen_handle, reopen_outcomes, readback = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-reopen",
        work_unit_id=work_unit_id,
        extra=("--calculation-revision-id", revisions[0]),
    )
    tui_reopen = require_reopen(readback, scenario="first_quarter")
    matches, verified = _read_revision(cli, revisions[0])
    if not (matches and verified and same_revision):
        raise IvaInstalledM303Error("1T readback, verification or CLI recalculation identity failed")
    return StoreEvidence(
        scenario="first_quarter",
        work_unit_id=work_unit_id,
        calculation_revision_id=revisions[0],
        revision_count=len(_revision_ids(cli, work_unit_id)),
        cli_resultado_matches_oracle=matches,
        cli_revision_verified=verified,
        cli_recalculated_same_revision=same_revision,
        changed_evidence_produced_distinct_revision=None,
        tui_reopen=tui_reopen,
        commands=tuple(cli.outcomes),
        children=(calculate_handle, reopen_handle),
        child_outcomes=(*calculate_outcomes, *reopen_outcomes),
    )
