"""Typed installed ledger receipts and canonical readback assertions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from dev.acceptance.installed_cli import CommandEvidence


class LedgerJourneyError(RuntimeError):
    """A named public CLI acceptance invariant failed."""


@dataclass(frozen=True, slots=True)
class LedgerCliReceipt:
    """Sanitized facts retained after a fresh-process installed CLI journey."""

    brief_revision: str
    pattern_revision: str
    scenario: str
    executable: str
    package_identity: str
    storage_root: str
    authority_root: str
    authority_generation: str
    year: int
    invoice_count: int
    transaction_count: int
    linked_count: int
    imported_count: int
    replay_skipped_count: int
    evidence_count: int
    export_rows: int
    export_sha256: str
    command_count: int
    commands: tuple[CommandEvidence, ...]


def result(document: dict[str, Any], *, stage: str) -> dict[str, Any]:
    """Return the result object of a CLI response, refusing a non-object."""
    value = document.get("result")
    if not isinstance(value, dict):
        raise LedgerJourneyError(f"{stage}: result is not an object")
    return value


def equal_decimal(actual: object, expected: Decimal, *, stage: str) -> None:
    """Require a value to equal the expected Decimal, naming the stage on mismatch."""
    try:
        matches = Decimal(str(actual)) == expected
    except (ValueError, ArithmeticError):
        matches = False
    if not matches:
        raise LedgerJourneyError(f"{stage}: monetary meaning differs")


def expect(condition: bool, *, stage: str) -> None:
    """Require a readback condition to hold, naming the stage when it differs."""
    if not condition:
        raise LedgerJourneyError(f"{stage}: canonical readback differs")


class LedgerRun(Protocol):
    """Installed command callable retaining the explicit refusal switch."""

    def __call__(self, args: Sequence[str], *, allow_error: bool = False) -> dict[str, Any]:
        """Run the CLI with ``args`` and return its decoded JSON envelope."""
