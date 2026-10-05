"""Canonical state stage for installed export-parity seeding."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from dev.acceptance.installed_cli import InstalledCli

from .seed_contracts import (
    SeedError,
    SeedReceipt,
    SeedRefusalError,
)


class SeedState:
    """Own the installed seed state behavior."""

    def __init__(
        self, cli: InstalledCli, *, receipt: SeedReceipt, receipt_path: Path, artifact_dir: Path, first_year: int
    ) -> None:
        """Bind resumable public command stages to one caller-owned receipt and store."""
        self.cli = cli
        self.receipt = receipt
        self.receipt_path = receipt_path
        self.artifact_dir = artifact_dir
        #: The earliest seeded year; assets in service before it enter with their known opening history.
        self.first_year = first_year

    def _result(self, args: Sequence[str], *, stage: str) -> dict[str, Any]:
        document = self.cli.run(tuple(args), allow_error=True)
        if document.get("status") == "error":
            error = document.get("error") or {}
            code = str(error.get("code")) if isinstance(error, dict) else "unknown"
            message = str(error.get("message", ""))[:300] if isinstance(error, dict) else ""
            self.receipt.blocked[stage] = f"{code}: {message}"
            self.receipt.save(self.receipt_path)
            raise SeedRefusalError(f"{stage}: {' '.join(args[:5])} refused {code}: {message}")
        result = document.get("result")
        if not isinstance(result, dict):
            raise SeedError(f"{stage}: {' '.join(args[:5])} returned no result object")
        if self.receipt.blocked.pop(stage, None) is not None:
            self.receipt.save(self.receipt_path)
        return result

    def _attempt(self, run: Callable[[], None]) -> bool:
        """Run one independent seed item, leaving a refusal on the receipt instead of stopping."""
        try:
            run()
        except SeedRefusalError:
            return False
        return True

    def _stored_transaction(self, description: str) -> str | None:
        """Find a transaction an interrupted run already added, so a resume never replays the add."""
        listed = self._result(("app", "ledger", "list"), stage="lookup.transactions")
        rows = listed.get("rows")
        matches = [
            str(row["transaction_id"])
            for row in (rows if isinstance(rows, list) else ())
            if isinstance(row, dict) and row.get("description") == description
        ]
        if len(matches) > 1:
            raise SeedError(f"{len(matches)} stored transactions carry the description {description!r}")
        return matches[0] if matches else None

    def _stored_invoice(self, kind: str, number: str) -> str | None:
        """Find an invoice an interrupted run already recorded under its deterministic number."""
        listed = self._result(("app", "ledger", "invoice", "list", "--kind", kind), stage="lookup.invoices")
        rows = listed.get("rows")
        matches = [
            str(row["invoice_id"])
            for row in (rows if isinstance(rows, list) else ())
            if isinstance(row, dict) and row.get("invoice_number") == number
        ]
        if len(matches) > 1:
            raise SeedError(f"{len(matches)} stored {kind} invoices carry the number {number!r}")
        return matches[0] if matches else None

    def _remember(self, key: str, value: object) -> str:
        text = str(value)
        self.receipt.identifiers[key] = text
        return text

    def _pending(self, key: str) -> bool:
        """Whether ``key`` still needs seeding; a resumed run skips every completed item and sub-step."""
        return f"done:{key}" not in self.receipt.identifiers

    def _complete(self, key: str) -> None:
        self.receipt.identifiers[f"done:{key}"] = "1"
        # A refusal an interrupted run left for this item is resolved once the item completes.
        for stage in [stage for stage in self.receipt.blocked if stage.rsplit(".", 1)[-1] == key]:
            self.receipt.blocked.pop(stage)
        self.receipt.save(self.receipt_path)

    def _stage(self, name: str) -> bool:
        return name not in self.receipt.completed_stages

    def _done(self, name: str) -> None:
        self.receipt.completed_stages.append(name)
        self.receipt.save(self.receipt_path)
