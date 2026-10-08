"""Run installed periodic and annual withholding campaigns and write sanitized receipts."""

from __future__ import annotations

import argparse
import json
import secrets
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from dev.acceptance.installed_cli import CommandEvidence, InstalledCli

from .cli_annual import _is_full_annual_campaign, _run_annual_slice, _select_annual_slices
from .cli_contracts import (
    _ANNUAL_SCHEMA_VERSION,
    _SCHEMA_VERSION,
    RetencionesAnnualCliJourneyEvidence,
    RetencionesCliFailureEvidence,
    RetencionesCliJourneyEvidence,
    RetencionesInstalledCliError,
)
from .cli_layout_selection import _selected_annual_layouts, _selected_layouts
from .cli_periodic import _is_full_campaign, _run_periodic_slice, _select_slices
from .cli_preflight import _fresh_directory, _require_nonempty_identity, _sha256_file
from .cli_profile import _create_withholding_profile
from .scenario import (
    BRIEF_ID,
    BRIEF_REVISION,
    INSTALLED_ANNUAL_CLI_SCENARIO_VERSION,
    INSTALLED_CLI_SCENARIO_VERSION,
    PATTERN_ID,
    PATTERN_REVISION,
    SUPPORTED_YEAR,
    build_installed_annual_cli_slices,
    build_installed_periodic_cli_slices,
)


def run_retenciones_cli_journey(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    output_dir: Path,
    year: int,
    as_of: date,
    source_identity: str,
    package_identity: str,
    slice_ids: tuple[str, ...] | None = None,
) -> RetencionesCliJourneyEvidence:
    """Run professional and urban-rent periodic journeys through installed CLI.

    ``source_identity`` and ``package_identity`` are supplied by the wheel-build
    owner.  The driver records them beside the live executable digest; it does
    not infer a source commit from an installed package.
    """
    available_slices = build_installed_periodic_cli_slices(year)
    slices = _select_slices(available_slices, requested_ids=slice_ids)
    _require_nonempty_identity(source_identity, label="source_identity")
    _require_nonempty_identity(package_identity, label="package_identity")
    storage = _fresh_directory(storage_root, label="scenario storage root")
    outputs = _fresh_directory(output_dir, label="scenario output directory")
    authority_generation, layouts = _selected_layouts(authority_root=authority_root, slices=slices, year=year)
    cli = InstalledCli(
        executable,
        storage_root=storage,
        authority_root=authority_root,
        passphrase=secrets.token_urlsafe(32),
    )
    try:
        _create_withholding_profile(cli, year=year)
        evidence = tuple(
            _run_periodic_slice(cli=cli, slice_=slice_, layouts=layouts, year=year, output_dir=outputs)
            for slice_ in slices
        )
    except RetencionesInstalledCliError as exc:
        if not exc.commands:
            exc.commands = tuple(cli.commands)
        raise
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage="driver",
            diagnostic_code=f"unexpected_{type(exc).__name__}",
            commands=tuple(cli.commands),
        ) from exc
    return RetencionesCliJourneyEvidence(
        schema_version=_SCHEMA_VERSION,
        status="proven" if _is_full_campaign(slices, available=available_slices) else "partial",
        campaign_scope="full_campaign" if _is_full_campaign(slices, available=available_slices) else "selected_slices",
        pattern_id=PATTERN_ID,
        pattern_revision=PATTERN_REVISION,
        brief_id=BRIEF_ID,
        brief_revision=BRIEF_REVISION,
        scenario=INSTALLED_CLI_SCENARIO_VERSION,
        year=year,
        as_of=as_of.isoformat(),
        authority_generation=authority_generation,
        source_identity=source_identity,
        package_identity=package_identity,
        executable=str(cli.executable),
        executable_sha256=_sha256_file(cli.executable),
        storage_root=str(storage),
        executed_slice_ids=tuple(slice_.slice_id for slice_ in slices),
        slices=evidence,
        commands=tuple(cli.commands),
        # The caller allocated these roots.  Keeping their encrypted store and
        # selected public artifacts under its explicit retention policy avoids
        # deleting an externally supplied path from inside this driver.
        retention="caller_owned_encrypted_store_and_validated_synthetic_artifacts",
    )


def run_retenciones_annual_cli_journey(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    output_dir: Path,
    year: int,
    as_of: date,
    source_identity: str,
    package_identity: str,
    slice_ids: tuple[str, ...] | None = None,
) -> RetencionesAnnualCliJourneyEvidence:
    """Run public capture through annual Modelo 180/190 export validation.

    The caller receives a distinct receipt from the periodic journey.  This
    prevents a successful annual subset from being relabelled as full
    withholding-campaign completion while preserving a durable vertical-slice
    result for each supported annual return.
    """
    available_slices = build_installed_annual_cli_slices(year)
    slices = _select_annual_slices(available_slices, requested_ids=slice_ids)
    _require_nonempty_identity(source_identity, label="source_identity")
    _require_nonempty_identity(package_identity, label="package_identity")
    storage = _fresh_directory(storage_root, label="annual scenario storage root")
    outputs = _fresh_directory(output_dir, label="annual scenario output directory")
    authority_generation, layouts = _selected_annual_layouts(authority_root=authority_root, slices=slices, year=year)
    cli = InstalledCli(
        executable,
        storage_root=storage,
        authority_root=authority_root,
        passphrase=secrets.token_urlsafe(32),
    )
    try:
        _create_withholding_profile(cli, year=year)
        evidence = tuple(
            _run_annual_slice(cli=cli, slice_=slice_, layouts=layouts, year=year, output_dir=outputs)
            for slice_ in slices
        )
    except RetencionesInstalledCliError as exc:
        if not exc.commands:
            exc.commands = tuple(cli.commands)
        raise
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage="annual_driver",
            diagnostic_code=f"unexpected_{type(exc).__name__}",
            commands=tuple(cli.commands),
        ) from exc
    full_campaign = _is_full_annual_campaign(slices, available=available_slices)
    return RetencionesAnnualCliJourneyEvidence(
        schema_version=_ANNUAL_SCHEMA_VERSION,
        status="proven" if full_campaign else "partial",
        campaign_scope="full_annual_campaign" if full_campaign else "selected_annual_slices",
        pattern_id=PATTERN_ID,
        pattern_revision=PATTERN_REVISION,
        brief_id=BRIEF_ID,
        brief_revision=BRIEF_REVISION,
        scenario=INSTALLED_ANNUAL_CLI_SCENARIO_VERSION,
        year=year,
        as_of=as_of.isoformat(),
        authority_generation=authority_generation,
        source_identity=source_identity,
        package_identity=package_identity,
        executable=str(cli.executable),
        executable_sha256=_sha256_file(cli.executable),
        storage_root=str(storage),
        executed_slice_ids=tuple(slice_.slice_id for slice_ in slices),
        slices=evidence,
        commands=tuple(cli.commands),
        retention="caller_owned_encrypted_store_and_validated_synthetic_annual_artifacts",
    )


def _failure_evidence(
    *,
    error: RetencionesInstalledCliError,
    executable: Path,
    year: int,
    source_identity: str,
    package_identity: str,
    storage_root: Path | None = None,
    output_dir: Path | None = None,
    commands: tuple[CommandEvidence, ...] = (),
    schema_version: str = _SCHEMA_VERSION,
    scenario: str = INSTALLED_CLI_SCENARIO_VERSION,
) -> RetencionesCliFailureEvidence:
    """Render a complete failure receipt without exception or stream contents."""
    return RetencionesCliFailureEvidence(
        schema_version=schema_version,
        status="failed",
        pattern_id=PATTERN_ID,
        pattern_revision=PATTERN_REVISION,
        brief_id=BRIEF_ID,
        brief_revision=BRIEF_REVISION,
        scenario=scenario,
        year=year,
        source_identity=source_identity,
        package_identity=package_identity,
        executable=str(executable),
        executable_sha256=_sha256_file(executable) if executable.is_file() else None,
        storage_root=None if storage_root is None else str(storage_root),
        output_dir=None if output_dir is None else str(output_dir),
        stage=error.stage,
        diagnostic_code=error.diagnostic_code,
        commands=commands,
        retention="caller_owned_failure_artifacts_only; no stdout_or_stderr_retained",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path, help="Absolute installed aeat executable.")
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--year", type=int, default=SUPPORTED_YEAR)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 9, 21))
    parser.add_argument("--source-identity", required=True)
    parser.add_argument("--package-identity", required=True)
    parser.add_argument(
        "--slice",
        action="append",
        dest="slice_ids",
        help="Run one named periodic slice; repeat only for an explicit subset.",
    )
    parser.add_argument(
        "--annual",
        action="store_true",
        help="Run the public capture-to-annual Modelo 180/190 journey.",
    )
    parser.add_argument(
        "--annual-slice",
        action="append",
        dest="annual_slice_ids",
        help="Run one named annual slice; repeat only for an explicit subset.",
    )
    return parser


def _run_requested_journey(
    args: argparse.Namespace, is_annual: bool
) -> RetencionesAnnualCliJourneyEvidence | RetencionesCliJourneyEvidence:
    """Run the selected public acceptance campaign with its own slice vocabulary."""
    if is_annual:
        evidence = run_retenciones_annual_cli_journey(
            executable=args.cli,
            authority_root=args.authority_root,
            storage_root=args.storage_root,
            output_dir=args.output_dir,
            year=args.year,
            as_of=args.as_of,
            source_identity=args.source_identity,
            package_identity=args.package_identity,
            slice_ids=None if args.annual_slice_ids is None else tuple(args.annual_slice_ids),
        )
    else:
        evidence = run_retenciones_cli_journey(
            executable=args.cli,
            authority_root=args.authority_root,
            storage_root=args.storage_root,
            output_dir=args.output_dir,
            year=args.year,
            as_of=args.as_of,
            source_identity=args.source_identity,
            package_identity=args.package_identity,
            slice_ids=None if args.slice_ids is None else tuple(args.slice_ids),
        )
    return evidence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the installed acceptance journey and persist a sanitized receipt."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.annual and args.slice_ids:
        parser.error("--slice is periodic-only; use --annual-slice with --annual")
    if not args.annual and args.annual_slice_ids:
        parser.error("--annual-slice requires --annual")
    is_annual = bool(args.annual)
    failure_schema_version = _ANNUAL_SCHEMA_VERSION if is_annual else _SCHEMA_VERSION
    failure_scenario = INSTALLED_ANNUAL_CLI_SCENARIO_VERSION if is_annual else INSTALLED_CLI_SCENARIO_VERSION
    try:
        evidence = _run_requested_journey(args, is_annual)
    except RetencionesInstalledCliError as exc:
        rendered = _failure_evidence(
            error=exc,
            executable=args.cli,
            year=args.year,
            source_identity=args.source_identity,
            package_identity=args.package_identity,
            storage_root=args.storage_root,
            output_dir=args.output_dir,
            commands=exc.commands,
            schema_version=failure_schema_version,
            scenario=failure_scenario,
        ).to_dict()
        status = 2
    except Exception as exc:
        rendered = _failure_evidence(
            error=RetencionesInstalledCliError(
                stage="driver",
                diagnostic_code=f"unexpected_{type(exc).__name__}",
            ),
            executable=args.cli,
            year=args.year,
            source_identity=args.source_identity,
            package_identity=args.package_identity,
            storage_root=args.storage_root,
            output_dir=args.output_dir,
            schema_version=failure_schema_version,
            scenario=failure_scenario,
        ).to_dict()
        status = 2
    else:
        rendered = evidence.to_dict()
        status = 0
    serialized = json.dumps(rendered, indent=2, sort_keys=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(f"{serialized}\n", encoding="utf-8", newline="\n")
    print(serialized)
    return status


if __name__ == "__main__":  # pragma: no cover - module executable boundary
    raise SystemExit(main())
