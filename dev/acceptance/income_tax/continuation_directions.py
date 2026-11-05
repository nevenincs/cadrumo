"""Independent secure-store orchestration for both installed continuation directions."""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from dev.acceptance.installed_cli import InstalledCli, authority_generation

from .cli_journey import (
    calculate_m130_work,
    create_m130_work,
    ingest_income_fixture,
    verify_and_file_m130,
)
from .continuation_child_process import run_child
from .continuation_cli import assert_cli_q1_public_artifact, cli_complete, cli_public_readback
from .continuation_contracts import SCHEMA_VERSION, ContinuationPathReceipt, Direction, InstalledContinuationEvidence
from .continuation_state import continuation_state, oracle_fingerprint, parse_child_state
from .continuation_storage import require_empty
from .scenario import build_scenario
from .tui_continuation_evidence import (
    create_continuation_checkpoint,
    prove_continuation,
)


def run_installed_tui_continuations(
    *,
    cli_executable: Path,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    year: int,
    only_direction: Direction | None = None,
) -> InstalledContinuationEvidence:
    """Prove CLI→TUI and TUI→CLI continuations in two separate secure stores."""
    root = require_empty(output_root, label="continuation output root")
    generation = authority_generation(authority_root)
    paths: list[ContinuationPathReceipt] = []

    if only_direction == "tui_to_cli":
        paths.append(
            _run_tui_to_cli_direction(
                root=root,
                generation=generation,
                year=year,
                cli_executable=cli_executable,
                python_executable=python_executable,
                workspace_root=workspace_root,
                authority_root=authority_root,
            )
        )
        return InstalledContinuationEvidence(schema_version=SCHEMA_VERSION, status="proven", paths=tuple(paths))

    cli_store = require_empty(root / "cli-to-tui-store", label="CLI-to-TUI store")
    cli_scratch = require_empty(root / "cli-to-tui-artifacts", label="CLI-to-TUI artifacts")
    cli_passphrase = secrets.token_urlsafe(32)
    cli = InstalledCli(cli_executable, storage_root=cli_store, authority_root=authority_root, passphrase=cli_passphrase)
    cli.create_profile(year=year)
    ingest_income_fixture(cli, year=year)
    work_ids = {period: create_m130_work(cli, year=year, period=period) for period in ("1T", "2T", "3T", "4T")}
    q1 = build_scenario(year).quarter_oracle[0]
    q1_work = work_ids["1T"]
    _actual, q1_revision = calculate_m130_work(cli, work_id=q1_work, oracle=q1)
    verify_and_file_m130(cli, revision_id=q1_revision, period="1T")
    cli_handoff = continuation_state(
        generation=generation,
        year=year,
        periods=("1T", "2T", "3T", "4T"),
        filed=("1T",),
        annual_exported=False,
    )
    cli_checkpoint = create_continuation_checkpoint(frontend_path="cli_to_tui", state=cli_handoff)
    child = run_child(
        direction="cli_to_tui",
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=cli_store,
        scratch=cli_scratch,
        passphrase=cli_passphrase,
        year=year,
    )
    tui_handoff = parse_child_state(child, "handoff_state")
    tui_completion = parse_child_state(child, "completion_state")
    proven = prove_continuation(
        checkpoint=cli_checkpoint, frontend="tui", resumed_state=tui_handoff, completion_state=tui_completion
    )
    validation = child.get("annual_xsd_validation", {})
    paths.append(
        ContinuationPathReceipt(
            "cli_to_tui",
            "proven",
            year,
            str(child["product_origin"]),
            str(child["product_init_sha256"]),
            cli_handoff.state_sha256(),
            proven.resumed_state_sha256,
            tui_completion.state_sha256(),
            8,
            8,
            8,
            tui_completion.locally_filed_periods,
            bool(isinstance(validation, dict) and validation.get("xsd_valid")),
            len(validation.get("error_identities", ())) if isinstance(validation, dict) else 0,
            oracle_fingerprint(year),
            ("cross_frontend_public_value_fingerprint",),
        )
    )

    if only_direction == "cli_to_tui":
        return InstalledContinuationEvidence(schema_version=SCHEMA_VERSION, status="proven", paths=tuple(paths))

    paths.append(
        _run_tui_to_cli_direction(
            root=root,
            generation=generation,
            year=year,
            cli_executable=cli_executable,
            python_executable=python_executable,
            workspace_root=workspace_root,
            authority_root=authority_root,
        )
    )
    return InstalledContinuationEvidence(schema_version=SCHEMA_VERSION, status="proven", paths=tuple(paths))


def _run_tui_to_cli_direction(
    *,
    root: Path,
    generation: str,
    year: int,
    cli_executable: Path,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
) -> ContinuationPathReceipt:
    """Run the independently owned TUI-to-CLI scenario in its own secure store."""
    tui_store = require_empty(root / "tui-to-cli-store", label="TUI-to-CLI store")
    tui_scratch = require_empty(root / "tui-to-cli-artifacts", label="TUI-to-CLI artifacts")
    tui_passphrase = secrets.token_urlsafe(32)
    child = run_child(
        direction="tui_to_cli",
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=tui_store,
        scratch=tui_scratch,
        passphrase=tui_passphrase,
        year=year,
    )
    tui_handoff = parse_child_state(child, "handoff_state")
    tui_checkpoint = create_continuation_checkpoint(frontend_path="tui_to_cli", state=tui_handoff)
    readback_cli = InstalledCli(
        cli_executable, storage_root=tui_store, authority_root=authority_root, passphrase=tui_passphrase
    )
    resumed = cli_public_readback(
        readback_cli,
        generation=generation,
        year=year,
    )
    completing_cli = InstalledCli(
        cli_executable, storage_root=tui_store, authority_root=authority_root, passphrase=tui_passphrase
    )
    assert_cli_q1_public_artifact(cli=completing_cli, output_dir=tui_scratch, year=year)
    completion, validation = cli_complete(
        cli=completing_cli, workspace_root=workspace_root, output_dir=tui_scratch, generation=generation, year=year
    )
    proven = prove_continuation(
        checkpoint=tui_checkpoint, frontend="cli", resumed_state=resumed, completion_state=completion
    )
    return ContinuationPathReceipt(
        "tui_to_cli",
        "proven",
        year,
        str(child["product_origin"]),
        str(child["product_init_sha256"]),
        tui_handoff.state_sha256(),
        proven.resumed_state_sha256,
        completion.state_sha256(),
        8,
        8,
        8,
        completion.locally_filed_periods,
        bool(validation.get("xsd_valid")),
        len(cast("Sequence[object]", validation.get("error_identities", ()))),
        oracle_fingerprint(year),
        ("cross_frontend_public_value_fingerprint",),
    )
