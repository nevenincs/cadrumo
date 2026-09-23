"""Installed proof of one non-linear activity asset through CLI and TUI.

Runs against an installed wheel only: the CLI executable and the installed
Python that hosts the TUI child.  Three isolated encrypted stores prove, in
order, the CLI-only filing chain (claim, Modelo 130, Modelo 100 and the pinned
official XSD), a TUI-created asset continued by the CLI, and a CLI-created asset
read back by the TUI.  The receipt carries the installed identities and the
synthetic oracle comparisons, never a credential or a raw command transcript.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from dev.acceptance.assets.export_journey import run_asset_export_journey
from dev.acceptance.assets.installed_journey import run_installed_tui_probe
from dev.acceptance.assets.installed_profile_setup import run_installed_cli_profile_setup
from dev.acceptance.assets.installed_tui_child import (
    METHOD_ASSET_ID,
    METHOD_CORRECTED_FORECAST_AMOUNT,
    METHOD_REVISION_JSON,
)
from dev.acceptance.income_tax.cli_journey import command_result
from dev.acceptance.installed_cli import InstalledCli
from dev.packaging.command_execution import run_command

_SCHEMA_VERSION = "assets-01-installed-method-proof-v1"
_TUI_TIMEOUT_SECONDS = 300.0
# InstalledCli sends the profile passphrase through --profile-secrets-stdin on
# every command and never resumes a keychain session.
_CLI_CREDENTIAL_CHANNEL = "profile_secrets_stdin"


class InstalledMethodProofError(RuntimeError):
    """One installed proof stage did not reach its expected public outcome."""


@dataclass(frozen=True, slots=True)
class InstalledIdentity:
    """Identities that bind the proof to one installed build."""

    source_commit: str
    wheel_sha256: str
    installed_init_sha256: str
    installed_origin_is_site_packages: bool
    authority_logical_generation: str
    authority_database_sha256: str


@dataclass(frozen=True, slots=True)
class InstalledMethodProofReceipt:
    """Sanitized outcome of the three installed scenarios."""

    schema_version: str
    status: str
    identity: InstalledIdentity
    stages: dict[str, dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe receipt."""
        return cast("dict[str, object]", asdict(self))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _installed_package(python: Path) -> tuple[Path, str]:
    """Locate the installed package and hash its ``__init__`` in a fresh interpreter."""
    completed = run_command(
        (str(python), "-I", "-c", "import cadrumo, pathlib; print(pathlib.Path(cadrumo.__file__).resolve())"),
        cwd=python.parent,
        timeout_seconds=120,
    )
    if completed.returncode != 0:
        raise InstalledMethodProofError("the installed interpreter could not import the product")
    init_path = Path(completed.stdout.strip())
    return init_path.parent, _sha256(init_path)


def installed_identity(*, python: Path, wheel: Path, source_commit: str) -> tuple[InstalledIdentity, Path]:
    """Read the installed build's identities and its embedded authority root."""
    package_root, init_sha256 = _installed_package(python)
    authority_root = package_root / "_data" / "registry" / "authority"
    descriptor: object = json.loads((authority_root / "authority.current.json").read_text(encoding="utf-8"))
    if not isinstance(descriptor, dict):
        raise InstalledMethodProofError("embedded authority descriptor is not a JSON object")
    document = cast("dict[str, object]", descriptor)
    return (
        InstalledIdentity(
            source_commit=source_commit,
            wheel_sha256=_sha256(wheel),
            installed_init_sha256=init_sha256,
            installed_origin_is_site_packages="site-packages" in package_root.parts,
            authority_logical_generation=str(document.get("logical_generation")),
            authority_database_sha256=str(document.get("database_sha256")),
        ),
        authority_root,
    )


def _money(value: object) -> str:
    return f"{Decimal(str(value)):.2f}"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InstalledMethodProofError(message)


def _tui_first(
    *,
    aeat: Path,
    python: Path,
    workspace_root: Path,
    authority_root: Path,
    run_root: Path,
) -> dict[str, object]:
    """TUI creates, corrects, forecasts, claims and hands off; a fresh TUI and the CLI continue."""
    storage_root = run_root / "tui-first-store"
    passphrase = secrets.token_urlsafe(32)
    label = "assets-tui-first"
    run_installed_cli_profile_setup(
        aeat_executable=aeat,
        workspace_root=workspace_root,
        storage_root=storage_root,
        receipt_path=run_root / "tui-first-profile.json",
        profile_label=label,
        passphrase=passphrase,
    )
    lifecycle = run_installed_tui_probe(
        python_executable=python,
        workspace_root=workspace_root,
        storage_root=storage_root,
        receipt_path=run_root / "tui-first-lifecycle" / "receipt.json",
        profile_label=label,
        passphrase=passphrase,
        journey="asset_method_lifecycle",
        profile_bootstrap="existing",
        timeout_seconds=_TUI_TIMEOUT_SECONDS,
    )
    readback = run_installed_tui_probe(
        python_executable=python,
        workspace_root=workspace_root,
        storage_root=storage_root,
        receipt_path=run_root / "tui-first-readback" / "receipt.json",
        profile_label=label,
        passphrase=passphrase,
        journey="asset_readback",
        profile_bootstrap="existing",
        timeout_seconds=_TUI_TIMEOUT_SECONDS,
    )
    cli = InstalledCli(aeat, storage_root=storage_root, authority_root=authority_root, passphrase=passphrase)
    inspected = command_result(cli.run(("app", "ledger", "actividad-asset", "inspect", METHOD_ASSET_ID)))
    revisions = inspected.get("revisions")
    _require(
        isinstance(revisions, list) and len(cast("list[object]", revisions)) == 2, "CLI did not read both TUI revisions"
    )
    handoff = command_result(
        cli.run(("app", "ledger", "actividad-asset", "filing-handoff", "--tax-year", "2025", "--m130-period", "4T"))
    )
    material_m100 = cast("dict[str, object]", handoff["material_m100"])
    material_m130 = cast("dict[str, object]", handoff["material_m130"])
    _require(
        _money(material_m100["amount"]) == METHOD_CORRECTED_FORECAST_AMOUNT
        and _money(material_m130["amount"]) == METHOD_CORRECTED_FORECAST_AMOUNT,
        "CLI continuation did not see the TUI's constant-percentage claim",
    )
    return {
        "tui_lifecycle_status": lifecycle.status,
        "tui_fresh_readback_status": readback.status,
        "cli_revisions_read": 2,
        "cli_material_m100": _money(material_m100["amount"]),
        "cli_material_m130": _money(material_m130["amount"]),
        "cli_credential_channel": _CLI_CREDENTIAL_CHANNEL,
    }


def _cli_first(
    *,
    aeat: Path,
    python: Path,
    workspace_root: Path,
    authority_root: Path,
    run_root: Path,
    expected_generation: str,
) -> dict[str, object]:
    """The CLI creates, forecasts and claims; a fresh TUI process reads the asset back."""
    storage_root = run_root / "cli-first-store"
    passphrase = secrets.token_urlsafe(32)
    label = "assets-cli-first"
    run_installed_cli_profile_setup(
        aeat_executable=aeat,
        workspace_root=workspace_root,
        storage_root=storage_root,
        receipt_path=run_root / "cli-first-profile.json",
        profile_label=label,
        passphrase=passphrase,
    )
    cli = InstalledCli(aeat, storage_root=storage_root, authority_root=authority_root, passphrase=passphrase)
    command_result(cli.run(("app", "ledger", "actividad-asset", "create", METHOD_REVISION_JSON)))
    forecast = command_result(
        cli.run(
            (
                "app",
                "ledger",
                "actividad-asset",
                "forecast",
                METHOD_ASSET_ID,
                "--covered-from",
                "2025-01-01",
                "--covered-until",
                "2026-01-01",
            )
        )
    )
    # The first revision's EUR 2,000 basis: 2,000 x 30% = 600.00.
    _require(_money(forecast["amount"]) == "600.00", "CLI constant-percentage forecast differs from the oracle")
    _require(
        forecast.get("authority_generation") == expected_generation,
        "the CLI forecast was served by a different authority generation than the installed descriptor names",
    )
    claim = command_result(
        cli.run(
            (
                "app",
                "ledger",
                "actividad-asset",
                "claim",
                json.dumps(forecast, separators=(",", ":")),
                "--creating-operation",
                "assets-acceptance.cli-first-claim",
            )
        )
    )
    readback = run_installed_tui_probe(
        python_executable=python,
        workspace_root=workspace_root,
        storage_root=storage_root,
        receipt_path=run_root / "cli-first-tui-readback" / "receipt.json",
        profile_label=label,
        passphrase=passphrase,
        journey="asset_cli_readback",
        profile_bootstrap="existing",
        timeout_seconds=_TUI_TIMEOUT_SECONDS,
    )
    return {
        "cli_forecast": _money(forecast["amount"]),
        "cli_claim_recorded": bool(cast("dict[str, object]", claim["claim"]).get("claim_id")),
        "tui_readback_status": readback.status,
        "cli_forecast_authority_generation": str(forecast.get("authority_generation")),
        "cli_credential_channel": _CLI_CREDENTIAL_CHANNEL,
    }


def run_installed_method_proof(
    *,
    aeat: Path,
    python: Path,
    wheel: Path,
    source_commit: str,
    workspace_root: Path,
    run_root: Path,
    xsd: Path,
    report: Callable[[str], None] = lambda _stage: None,
) -> InstalledMethodProofReceipt:
    """Run the three installed scenarios and return a sanitized receipt."""
    identity, authority_root = installed_identity(python=python, wheel=wheel, source_commit=source_commit)
    _require(identity.installed_origin_is_site_packages, "the product did not import from site-packages")
    stages: dict[str, dict[str, object]] = {}
    report("cli_export")
    export = run_asset_export_journey(
        executable=aeat,
        authority_root=authority_root,
        storage_root=run_root / "cli-export-store",
        output_dir=run_root / "cli-export-output",
        xsd_path=xsd,
    )
    stages["cli_export"] = {
        "forecast_amount": export.forecast_amount,
        "m130_q4_expenses": export.m130_q4_expenses,
        "m100_material_amortization": export.m100_material_amortization,
        "m100_intangible_amortization": export.m100_intangible_amortization,
        "xsd_valid": export.xsd_validation.xsd_valid,
        "xml_sha256": _sha256(Path(export.export_path)),
    }
    report("tui_first")
    stages["tui_first"] = _tui_first(
        aeat=aeat, python=python, workspace_root=workspace_root, authority_root=authority_root, run_root=run_root
    )
    report("cli_first")
    stages["cli_first"] = _cli_first(
        aeat=aeat,
        python=python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        run_root=run_root,
        expected_generation=identity.authority_logical_generation,
    )
    return InstalledMethodProofReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        identity=identity,
        stages=stages,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aeat", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--xsd", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the proof and write the receipt; a failed stage exits non-zero."""
    args = _parser().parse_args(argv)
    args.run_root.mkdir(parents=True, exist_ok=True)
    stage_file = args.run_root / "stage.txt"
    receipt = run_installed_method_proof(
        aeat=args.aeat,
        python=args.python,
        wheel=args.wheel,
        source_commit=args.source_commit,
        workspace_root=args.workspace_root,
        run_root=args.run_root,
        xsd=args.xsd,
        report=lambda stage: stage_file.write_text(stage + "\n", encoding="utf-8"),
    )
    rendered = json.dumps(receipt.to_dict(), indent=2, sort_keys=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(rendered + "\n", encoding="utf-8", newline="\n")
    print(rendered)
    return 0


if __name__ == "__main__":  # pragma: no cover - module execution wrapper
    raise SystemExit(main())


__all__ = [
    "InstalledIdentity",
    "InstalledMethodProofError",
    "InstalledMethodProofReceipt",
    "installed_identity",
    "main",
    "run_installed_method_proof",
]
