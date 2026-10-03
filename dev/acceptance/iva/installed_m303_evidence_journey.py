"""Orchestrate the installed ordinary Modelo 303 evidence journey and child entrypoint."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo.core.hashing import sha256_hex
from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    read_passphrase_from_stdin,
    write_installed_tui_failure_receipt,
)
from dev.packaging.installed_wheel_binding import environment_interpreter

from .filing_year import require_journey_year, require_m303_developer_header_positions
from .m303_evidence_child import _run_child
from .m303_evidence_contracts import (
    _COORDINATES,
    _FIRST_QUARTER,
    _MONTH,
    _PERIOD,
    _SCHEMA_VERSION,
    IvaInstalledM303Error,
    JourneyReceipt,
)
from .m303_evidence_identity import _authority, _installed_identity
from .m303_evidence_stores import _continuation_store, _first_quarter_store, _monthly_store, _tui_led_store

if TYPE_CHECKING:
    pass


def run_journey(args: argparse.Namespace) -> JourneyReceipt:
    """Run every isolated store for ``args.year`` against one installed wheel and pinned authority.

    Raises:
        IvaFilingYearUnsupportedError: Before the output root is created, when the
            published authority lacks a Modelo 303 revision authored for the year
            in any exercised period, or the year's 4T record design is not one
            whose developer-header positions the journey holds.
    """
    journey_year = require_journey_year(authority_root=args.authority_root, year=args.year, coordinates=_COORDINATES)
    export_positions = require_m303_developer_header_positions(journey_year, period=_PERIOD)
    args.output_root.mkdir(parents=True, exist_ok=True)
    if any(args.output_root.iterdir()):
        raise IvaInstalledM303Error("output root must be empty")
    version, init_path, init_sha256, bundled_generation = _installed_identity(args.python)
    generation, descriptor_sha256 = _authority(args.authority_root)
    if generation != bundled_generation:
        raise IvaInstalledM303Error("supplied authority generation differs from the one the installed wheel bundles")
    stores = (
        _tui_led_store(args, journey_year, export_positions),
        _continuation_store(args, journey_year),
        _monthly_store(args, journey_year),
        _first_quarter_store(args, journey_year),
    )
    return JourneyReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        filing_year=journey_year.year,
        periods=(_PERIOD, _MONTH, _FIRST_QUARTER),
        source_commit=args.source_commit,
        wheel_filename=args.wheel.name,
        wheel_sha256=sha256_hex(args.wheel.read_bytes()),
        package_version=version,
        installed_init_path=init_path,
        installed_init_sha256=init_sha256,
        authority_generation=generation,
        authority_descriptor_sha256=descriptor_sha256,
        bundled_authority_generation=bundled_generation,
        stores=stores,
        unexercised=(
            "official_m303_export_blocked_by_unavailable_eedd_header_identity",
            "tui_invoice_capture_multi_line",
            "aeat_submission",
        ),
        retention=(
            "synthetic encrypted stores and child receipts retained under the output root; "
            "no transient plaintext input remains; removal needs the coordinator's cleanup authorization"
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--child", choices=("tui-led-calculate", "tui-continue-calculate", "tui-joint-only-calculate", "tui-reopen")
    )
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--work-unit-id")
    parser.add_argument("--wrong-attachment-id", default="")
    parser.add_argument("--wrong-sha256", default="")
    parser.add_argument("--existing-attachment-id", default="")
    parser.add_argument("--existing-sha256", default="")
    parser.add_argument("--calculation-revision-id", default="")
    parser.add_argument("--export-path", default="")
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--source-commit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run either the outer installed journey or one credentialed TUI child."""
    args = _parser().parse_args(argv)
    args.workspace_root = args.workspace_root.resolve(strict=True)
    if args.child is not None:
        import faulthandler

        # A native crash writes no Python receipt; this bounded trace is the only evidence it leaves.
        fault_log = args.receipt.with_suffix(".fault.txt").open("w", encoding="utf-8")
        faulthandler.enable(fault_log)
        try:
            receipt = _run_child(args, passphrase=read_passphrase_from_stdin())
        except InstalledTuiChildError as error:
            write_installed_tui_failure_receipt(path=args.receipt, schema_version=_SCHEMA_VERSION, error=error)
            return 2
        except KeyboardInterrupt:
            raise
        except BaseException as error:
            import traceback

            frames = [
                f"{Path(frame.filename).name}:{frame.lineno}" for frame in traceback.extract_tb(error.__traceback__)
            ]
            write_installed_tui_failure_receipt(
                path=args.receipt,
                schema_version=_SCHEMA_VERSION,
                error=InstalledTuiChildError(f"{type(error).__name__}: {error!s:.300} at {frames[-6:]}"),
            )
            return 3
        args.receipt.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0
    for name in ("cli", "python", "wheel", "authority_root", "output_root", "source_commit"):
        if getattr(args, name) is None:
            raise SystemExit(f"--{name.replace('_', '-')} is required for the outer journey")
    args.cli = args.cli.resolve(strict=True)
    args.python = environment_interpreter(args.python)
    args.wheel = args.wheel.resolve(strict=True)
    args.authority_root = args.authority_root.resolve(strict=True)
    args.output_root = args.output_root.resolve()
    receipt = run_journey(args)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt.status, "receipt": str(args.receipt)}))
    return 0


if __name__ == "__main__":  # pragma: no cover - installed execution is integration-owned
    raise SystemExit(main())
