"""Isolated installed IVA annual profile admission and process reopen."""

from __future__ import annotations

import secrets
from contextlib import AbstractContextManager, ExitStack
from pathlib import Path

from dev.acceptance.installed_cli import InstalledCli, InstalledCliError

from .cli_journey import (
    IvaCliJourneyError,
    SanitizedCommandReceipt,
)
from .filing_year import IvaJourneyYear
from .multirate_cli_journey import (
    _create_profile,
)


def _start(
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    artifact_root: Path,
    journey_year: IvaJourneyYear,
    *,
    resources: ExitStack,
    runtime_scope: AbstractContextManager[object] | None = None,
) -> tuple[InstalledCli, list[SanitizedCommandReceipt], Path]:
    if storage_root.exists() and any(storage_root.iterdir()):
        raise IvaCliJourneyError(f"storage root must be fresh and empty: {storage_root}")
    storage_root.mkdir(parents=True, exist_ok=True)
    if runtime_scope is not None:
        resources.enter_context(runtime_scope)
    artifact_root.mkdir(parents=True, exist_ok=True)
    artifact = artifact_root / "synthetic-annual-foundation-purchase.pdf"
    artifact.write_bytes(b"%PDF-1.4\n% synthetic annual IVA purchase evidence\n")
    cli = InstalledCli(
        executable, storage_root=storage_root, authority_root=authority_root, passphrase=secrets.token_urlsafe(32)
    )
    receipts: list[SanitizedCommandReceipt] = []
    try:
        _create_profile(cli=cli, receipts=receipts, artifact=artifact, journey_year=journey_year)
    except InstalledCliError as exc:
        raise IvaCliJourneyError("config profile create refused") from exc
    return cli, receipts, artifact


def _reopen(cli: InstalledCli, authority_root: Path, storage_root: Path) -> InstalledCli:
    return InstalledCli(
        cli.executable, storage_root=storage_root, authority_root=authority_root, passphrase=cli.passphrase
    )
