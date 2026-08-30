"""Ledger lifecycle CLI surface tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....core.redaction import CLI_BUCKET_ID_PLACEHOLDER
from ._cli_json_support import _json_object
from ._cli_surface_support import (
    _active_bucket_id,
    _invoke,
    _json,
    create_cli_surface_profile,
)
from ._strict_cli_fixture_support import cli_surface_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

__all__ = ["cli_surface_isolated_backend"]


def _exit_code(result: Result) -> int:
    """Read the captured Click result's exit code at the test boundary."""

    return result.exit_code


def _create_manual_ledger_row(description: str, *, amount: str = "25.00", key: str) -> dict[str, object]:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-03",
            "--amount",
            amount,
            "--direction",
            "OUTGOING",
            "--description",
            description,
            "--idempotency-key",
            key,
        ],
    )
    assert result.exit_code == 0, result.output
    return _json_object(_json(result))


@dataclass(frozen=True, slots=True)
class _LedgerLifecycleOutcome:
    """Bundle returned by _drive_ledger_lifecycle_round_trip."""

    bucket_id: str
    purchase_invoice_evidence_id: str
    attached_payload: dict[str, object]
    archived_payload: dict[str, object]
    stashed_payload: dict[str, object]
    dry_remove_payload: dict[str, object]
    refused_remove_exit_code: int
    removed_payload: dict[str, object]
    export_payload: dict[str, object]
    export_path: Path
    dry_reset_payload: dict[str, object]
    refused_reset_exit_code: int
    reset_payload: dict[str, object]


def _drive_ledger_lifecycle_round_trip(tmp_path: Path) -> _LedgerLifecycleOutcome:
    """Drive the lifecycle round-trip: attach -> archive -> stash -> remove -> export -> reset."""
    create_cli_surface_profile()
    bucket_id = _active_bucket_id()

    purchase_evidence_id = _seed_purchase_invoice_evidence(bucket_id)

    attached = _ledger_lifecycle_attach(purchase_invoice_evidence_id=purchase_evidence_id)
    archived = _ledger_lifecycle_lifecycle_transition("archive", reason="wrong account", key="cli-archive-row")
    stashed = _ledger_lifecycle_lifecycle_transition("stash", reason="needs review", key="cli-stash-row")

    remove_outcome = _ledger_lifecycle_remove()
    export_outcome = _ledger_lifecycle_export(tmp_path)
    reset_outcome = _ledger_lifecycle_reset()

    return _LedgerLifecycleOutcome(
        bucket_id=bucket_id,
        purchase_invoice_evidence_id=purchase_evidence_id,
        attached_payload=attached,
        archived_payload=archived,
        stashed_payload=stashed,
        dry_remove_payload=remove_outcome[0],
        refused_remove_exit_code=remove_outcome[1],
        removed_payload=remove_outcome[2],
        export_payload=export_outcome[0],
        export_path=export_outcome[1],
        dry_reset_payload=reset_outcome[0],
        refused_reset_exit_code=reset_outcome[1],
        reset_payload=reset_outcome[2],
    )


def _seed_purchase_invoice_evidence(bucket_id: str) -> str:
    """Persist one RECEIVED purchase invoice and return its id."""
    from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ....domain.invoices.enums import IvaRate, PaymentStatus
    from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
    from ....domain.iva.classification import InvoiceKind

    purchase_line = InvoiceLine(
        description="Material oficina",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    purchase_evidence = Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": bucket_id,
            "invoice_number": "P-2026-CLI-001",
            "issued_at": date(2026, 5, 3),
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (purchase_line,),
            "payment_status": PaymentStatus.PAID,
        },
    )
    InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    return purchase_evidence.invoice_id


def _ledger_lifecycle_attach(*, purchase_invoice_evidence_id: str) -> dict[str, object]:
    """Create a manual ledger row and attach the purchase-invoice evidence reference."""
    row = _create_manual_ledger_row("attach evidence row", amount="121.00", key="cli-attach-row")
    attached = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "attach",
            str(row["transaction_id"]),
            "--purchase-invoice-evidence-id",
            purchase_invoice_evidence_id,
        ],
    )
    assert attached.exit_code == 0, attached.output
    return _json_object(_json(attached))


def _ledger_lifecycle_lifecycle_transition(verb: str, *, reason: str, key: str) -> dict[str, object]:
    """Drive one ``app ledger <verb> <id> --reason ... --yes`` lifecycle transition."""
    row = _create_manual_ledger_row(f"{verb} row", key=key)
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            verb,
            str(row["transaction_id"]),
            "--reason",
            reason,
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    return _json_object(_json(result))


def _ledger_lifecycle_remove() -> tuple[dict[str, object], int, dict[str, object]]:
    """Drive the three-step remove flow: --dry-run, refused (no --yes), confirmed --yes."""
    remove_row = _create_manual_ledger_row("remove row", key="cli-remove-row")
    dry = _invoke(
        ["--format", "json", "app", "ledger", "remove", str(remove_row["transaction_id"]), "--dry-run"],
    )
    assert dry.exit_code == 0, dry.output
    refused = _invoke(["--format", "json", "app", "ledger", "remove", str(remove_row["transaction_id"])])
    confirmed = _invoke(
        ["--format", "json", "app", "ledger", "remove", str(remove_row["transaction_id"]), "--yes"],
    )
    assert confirmed.exit_code == 0, confirmed.output
    return _json_object(_json(dry)), _exit_code(refused), _json_object(_json(confirmed))


def _ledger_lifecycle_export(tmp_path: Path) -> tuple[dict[str, object], Path]:
    """Drive the ledger export to a JSONL file under ``tmp_path``."""
    export_path = tmp_path / "ledger-export.jsonl"
    exported = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "export",
            "--output",
            str(export_path),
            "--export-format",
            "jsonl",
            "--include-inactive",
        ],
    )
    assert exported.exit_code == 0, exported.output
    return _json_object(_json(exported)), export_path


def _ledger_lifecycle_reset() -> tuple[dict[str, object], int, dict[str, object]]:
    """Drive the three-step reset flow: --dry-run, refused (no --yes), confirmed --yes."""
    dry = _invoke(["--format", "json", "app", "ledger", "reset", "--dry-run"])
    assert dry.exit_code == 0, dry.output
    refused = _invoke(["--format", "json", "app", "ledger", "reset", "--reason", "test cleanup"])
    confirmed = _invoke(["--format", "json", "app", "ledger", "reset", "--reason", "test cleanup", "--yes"])
    assert confirmed.exit_code == 0, confirmed.output
    return _json_object(_json(dry)), _exit_code(refused), _json_object(_json(confirmed))


def test_app_ledger_lifecycle_round_trip_exercises_mutating_surfaces(
    tmp_path: Path,
) -> None:
    outcome = _drive_ledger_lifecycle_round_trip(tmp_path)

    transaction = _json_object(outcome.attached_payload["transaction"])
    assert transaction["purchase_invoice_evidence_id"] == outcome.purchase_invoice_evidence_id
    assert outcome.attached_payload["bucket_event_ids"]

    archived_transaction = _json_object(outcome.archived_payload["transaction"])
    stashed_transaction = _json_object(outcome.stashed_payload["transaction"])
    assert archived_transaction["lifecycle_state"] == "ARCHIVED"
    assert stashed_transaction["lifecycle_state"] == "STASHED"

    assert outcome.dry_remove_payload["dry_run"] is True
    assert outcome.refused_remove_exit_code != 0
    assert outcome.removed_payload["removed"] is True

    assert outcome.bucket_id not in json.dumps(outcome.export_payload, sort_keys=True)
    assert outcome.export_payload["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    assert outcome.export_payload["row_count"] == 3
    assert outcome.export_path.read_text(encoding="utf-8").count("\n") == 3

    assert outcome.dry_reset_payload["dry_run"] is True
    assert outcome.refused_reset_exit_code != 0
    assert outcome.reset_payload["reset"] is True
    removed_transaction_ids = outcome.reset_payload["removed_transaction_ids"]
    assert isinstance(removed_transaction_ids, list)
    assert len(removed_transaction_ids) == 3
