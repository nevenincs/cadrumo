"""Installed ledger acceptance orchestration and sanitized CLI receipts."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    read_passphrase_from_stdin,
)
from dev.acceptance.installed_cli import InstalledCliError
from dev.packaging.installed_wheel_binding import environment_interpreter

from .installed_tui_child_runs import run_installed_tui_child
from .installed_tui_continuations import _run_cli_to_tui, _run_tui_only, _run_tui_to_cli
from .installed_tui_contracts import (
    _SCHEMA_VERSION,
    _YEAR,
    ChildMode,
    InstalledLedgerTuiReceipt,
    LedgerInstalledTuiError,
    TuiOnlyCliOracleReceipt,
)
from .installed_tui_storage import _require_empty_directory


def run_installed_ledger_tui_journey(
    *,
    cli_executable: Path,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    package_identity: str,
    year: int = _YEAR,
) -> InstalledLedgerTuiReceipt:
    """Run installed TUI-only and both direction continuations against fresh secure stores."""
    workspace = workspace_root.resolve(strict=True)
    authority = authority_root.resolve(strict=True)
    cli = cli_executable.resolve(strict=True)
    python = environment_interpreter(python_executable)
    if cli.parent != python.parent:
        raise LedgerInstalledTuiError("installed CLI and TUI child Python do not belong to one environment")
    if not package_identity.startswith("wheel_sha256:") or len(package_identity.removeprefix("wheel_sha256:")) != 64:
        raise LedgerInstalledTuiError("installed Ledger journey requires the exact built wheel identity")
    root = _require_empty_directory(output_root, label="LEDGER installed-TUI output root")
    tui_only_run = _run_tui_only(
        python_executable=python,
        workspace_root=workspace,
        authority_root=authority,
        output_root=_require_empty_directory(root / "tui-only", label="TUI-only Ledger output root"),
        year=year,
    )
    cli_to_tui, cli_to_tui_child = _run_cli_to_tui(
        cli_executable=cli,
        python_executable=python,
        workspace_root=workspace,
        authority_root=authority,
        output_root=_require_empty_directory(root / "cli-to-tui", label="CLI-to-TUI Ledger output root"),
        year=year,
    )
    tui_to_cli, tui_to_cli_child = _run_tui_to_cli(
        cli_executable=cli,
        python_executable=python,
        workspace_root=workspace,
        authority_root=authority,
        output_root=_require_empty_directory(root / "tui-to-cli", label="TUI-to-CLI Ledger output root"),
        year=year,
    )
    product_hashes = {
        tui_only_run.receipt.product_init_sha256,
        cli_to_tui_child.product_init_sha256,
        tui_to_cli_child.product_init_sha256,
    }
    if len(product_hashes) != 1:
        raise LedgerInstalledTuiError("installed Ledger journeys used different product package identities")
    return InstalledLedgerTuiReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        package_identity=package_identity,
        year=year,
        product_origin="site-packages",
        product_init_sha256=product_hashes.pop(),
        tui_only_observations=tui_only_run.receipt.observations,
        cli_to_tui=cli_to_tui,
        tui_to_cli=tui_to_cli,
    )


def run_installed_tui_only_cli_oracle(
    *,
    cli_executable: Path,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    package_identity: str,
    year: int = _YEAR,
) -> TuiOnlyCliOracleReceipt:
    """Run only the independent TUI path plus read-only installed CLI proof."""
    workspace = workspace_root.resolve(strict=True)
    authority = authority_root.resolve(strict=True)
    cli = cli_executable.resolve(strict=True)
    python = environment_interpreter(python_executable)
    if cli.parent != python.parent:
        raise LedgerInstalledTuiError("installed CLI and TUI child Python do not belong to one environment")
    if not package_identity.startswith("wheel_sha256:") or len(package_identity.removeprefix("wheel_sha256:")) != 64:
        raise LedgerInstalledTuiError("installed Ledger journey requires the exact built wheel identity")
    root = _require_empty_directory(output_root, label="LEDGER supplemental installed-TUI output root")
    tui_only = _run_tui_only(
        python_executable=python,
        workspace_root=workspace,
        authority_root=authority,
        output_root=_require_empty_directory(root / "tui-only", label="supplemental TUI-only Ledger output root"),
        year=year,
        cli_executable=cli,
    )
    if not tui_only.cli_oracle_observations:
        raise LedgerInstalledTuiError("supplemental TUI-only CLI oracle recorded no public observations")
    return TuiOnlyCliOracleReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        journey="tui_only_cli_oracle",
        package_identity=package_identity,
        year=year,
        product_origin="site-packages",
        product_init_sha256=tui_only.receipt.product_init_sha256,
        tui_only_observations=tui_only.receipt.observations,
        cli_oracle_observations=tui_only.cli_oracle_observations,
        cli_command_count=tui_only.cli_command_count,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--package-identity")
    parser.add_argument("--supplemental-tui-only", action="store_true")
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--year", type=int, default=_YEAR)
    parser.add_argument(
        "--mode",
        choices=(
            "tui_only_capture_update",
            "tui_only_reopen",
            "cli_to_tui",
            "linked_refusal_readback",
            "tui_to_cli_reopen",
        ),
    )
    parser.add_argument("--invoice-number")
    parser.add_argument("--initial-notes")
    parser.add_argument("--updated-notes")
    parser.add_argument("--transaction-description")
    parser.add_argument("--updated-description")
    return parser


def _write_receipt(path: Path, document: dict[str, object]) -> None:
    """Write one JSON receipt after its caller has reduced it to safe evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run an installed outer journey or one stdin-credentialed installed TUI child."""
    args = _parser().parse_args(argv)
    try:
        if args.mode is not None:
            if args.supplemental_tui_only or any(
                value is not None for value in (args.output_root, args.cli, args.python, args.authority_root)
            ):
                raise LedgerInstalledTuiError("installed Ledger TUI child received outer-only arguments")
            receipt = run_installed_tui_child(
                workspace_root=args.workspace_root,
                scratch=args.receipt.parent,
                passphrase=read_passphrase_from_stdin(),
                mode=cast("ChildMode", args.mode),
                invoice_number=cast("str", args.invoice_number),
                initial_notes=cast("str", args.initial_notes),
                updated_notes=args.updated_notes,
                transaction_description=args.transaction_description,
                updated_description=args.updated_description,
                year=args.year,
            )
            _write_receipt(args.receipt, receipt.to_dict())
            return 0
        if None in (args.cli, args.python, args.authority_root, args.output_root, args.package_identity):
            raise LedgerInstalledTuiError(
                "installed Ledger outer journey requires CLI, Python, authority, output and wheel identity"
            )
        if args.supplemental_tui_only:
            receipt = run_installed_tui_only_cli_oracle(
                cli_executable=args.cli,
                python_executable=args.python,
                workspace_root=args.workspace_root,
                authority_root=args.authority_root,
                output_root=args.output_root,
                package_identity=args.package_identity,
                year=args.year,
            )
        else:
            receipt = run_installed_ledger_tui_journey(
                cli_executable=args.cli,
                python_executable=args.python,
                workspace_root=args.workspace_root,
                authority_root=args.authority_root,
                output_root=args.output_root,
                package_identity=args.package_identity,
                year=args.year,
            )
        _write_receipt(args.receipt, receipt.to_dict())
        return 0
    except (LedgerInstalledTuiError, InstalledTuiChildError, InstalledCliError) as error:
        _write_receipt(
            args.receipt,
            {
                "schema_version": _SCHEMA_VERSION,
                "status": "failed",
                "error_type": type(error).__name__,
                "diagnostic": (
                    str(error) if isinstance(error, LedgerInstalledTuiError) else "installed frontend or command failed"
                ),
            },
        )
        return 2
    except Exception as error:
        _write_receipt(
            args.receipt,
            {
                "schema_version": _SCHEMA_VERSION,
                "status": "failed",
                "error_type": type(error).__name__,
                "diagnostic": "unexpected installed Ledger journey failure",
            },
        )
        return 2


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
