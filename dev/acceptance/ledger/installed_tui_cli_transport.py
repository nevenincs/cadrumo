"""Installed ledger command transport and strict public scalar observations."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from dev.acceptance.installed_cli import InstalledCli, InstalledCliError

from .installed_tui_contracts import LedgerInstalledTuiError


def _result(document: dict[str, Any], *, stage: str) -> dict[str, Any]:
    """Return one public CLI result object or name the failed observation stage."""
    result = document.get("result")
    if not isinstance(result, dict):
        raise LedgerInstalledTuiError(f"{stage} did not return a public result object")
    return result


def _cli_command(
    cli: InstalledCli,
    arguments: Sequence[str],
    *,
    stage: str,
    command: str,
    allow_error: bool = False,
) -> dict[str, Any]:
    """Run one public command and retain a value-free failure identity.

    The shared runner deliberately keeps envelopes out of its evidence.  The
    acceptance layer adds the scenario stage plus a static command name and
    its public exit/status so a failed installed journey can be diagnosed
    without retaining identifiers, financial values, or credentials.
    """
    command_count = len(cli.commands)
    try:
        return cli.run(arguments, command=command, allow_error=allow_error)
    except InstalledCliError as error:
        evidence = cli.commands[-1] if len(cli.commands) > command_count else None
        if evidence is None:
            outcome = "no accepted envelope"
        else:
            outcome = f"status={evidence.status}, exit_code={evidence.returncode}"
        raise LedgerInstalledTuiError(f"{stage}: installed CLI {command} failed ({outcome})") from error


def _create_profile(cli: InstalledCli, *, year: int, stage: str) -> None:
    """Create the shared synthetic profile while preserving a safe failure stage."""
    command_count = len(cli.commands)
    try:
        cli.create_profile(year=year)
    except InstalledCliError as error:
        evidence = cli.commands[-1] if len(cli.commands) > command_count else None
        command = evidence.command if evidence is not None else "config.profile"
        outcome = (
            "no accepted envelope" if evidence is None else f"status={evidence.status}, exit_code={evidence.returncode}"
        )
        raise LedgerInstalledTuiError(f"{stage}: installed CLI {command} failed ({outcome})") from error


def _decimal(value: object, *, stage: str) -> Decimal:
    """Parse an observed public monetary value without accepting malformed data."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise LedgerInstalledTuiError(f"{stage} exposed an invalid public monetary value") from error
    if not amount.is_finite():
        raise LedgerInstalledTuiError(f"{stage} exposed a non-finite public monetary value")
    return amount


def _text(value: object, *, stage: str) -> str:
    """Require one non-empty public transport string."""
    if not isinstance(value, str) or not value:
        raise LedgerInstalledTuiError(f"{stage} omitted a required public identifier")
    return value
