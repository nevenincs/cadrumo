"""Safety and authority tests for the frontend-neutral Ledger workspace."""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.ledger_filing_snapshot import LedgerFilingStalenessVerdict
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..models import LedgerReviewQueryResult, LedgerReviewRow, LedgerStatusReport
from ..workspace import (
    LEDGER_WORKSPACE_CONTRACT_VERSION,
    LedgerWorkspaceArea,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceProjectionError,
    LedgerWorkspaceSource,
    LedgerWorkspaceStatus,
    project_affected_declaration_reconciliations,
    project_ledger_workspace,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "31313131-3131-4131-8131-313131313131"
_NOW = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)


def _transaction() -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="synthetic-row",
                booked_date=date(2026, 8, 1),
                amount=Decimal("121.00"),
                currency="EUR",
                counterparty="SENSITIVE-COUNTERPARTY-CANARY",
                description="SENSITIVE-DESCRIPTION-CANARY",
                provenance=RawProvenance(
                    source_path=Path("SENSITIVE-PATH-CANARY.csv"),
                    source_sha256="a" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=_NOW,
                    provider_name="synthetic",
                ),
                raw_fields={"secret": "SENSITIVE-RAW-CANARY"},
            ),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "group_label": None,
        }
    )


def _invoice() -> Invoice:
    line = InvoiceLine(
        description="SENSITIVE-INVOICE-LINE-CANARY",
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        subtotal=Decimal("100"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21"),
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": _BUCKET_ID,
            "invoice_number": "SENSITIVE-INVOICE-NUMBER-CANARY",
            "issued_at": date(2026, 8, 1),
            "counterparty_name": "SENSITIVE-COUNTERPARTY-CANARY",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100"),
            "iva_total": Decimal("21"),
            "grand_total": Decimal("121"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
        }
    )


def _summary(*, bucket_id: str = _BUCKET_ID) -> LedgerStatusReport:
    return LedgerStatusReport(
        bucket_id=bucket_id,
        total_count=1,
        active_count=1,
        archived_count=0,
        stashed_count=0,
        pending_review_count=1,
        reviewed_count=0,
        skipped_count=0,
    )


def _review(transaction: Transaction, *, bucket_id: str = _BUCKET_ID) -> LedgerReviewQueryResult:
    return LedgerReviewQueryResult(
        bucket_id=bucket_id,
        rows=(
            LedgerReviewRow(
                id=transaction.transaction_id,
                date="2026-08-01",
                amount="121.00",
                description="SENSITIVE-REVIEW-CANARY",
                status="pending",
            ),
        ),
    )


def _project(transaction: Transaction):
    return project_ledger_workspace(
        summary=_summary(),
        preflight=None,
        review=_review(transaction),
        transactions=TransactionCatalogue.from_transactions((transaction,)),
        invoices=InvoiceCatalogue.from_invoices((_invoice(),)),
        revisions={},
        work_units=WorkUnitCatalogue(),
        filing_staleness_reader=lambda **_kwargs: (),
    )


def test_projection_is_deterministic_total_local_and_intrinsically_safe() -> None:
    transaction = _transaction()
    first = _project(transaction)
    second = _project(transaction)

    assert first == second
    assert first.contract_version == LEDGER_WORKSPACE_CONTRACT_VERSION
    assert tuple(row.area for row in first.areas) == tuple(LedgerWorkspaceArea)
    assert all(source.value.startswith("local.") for row in first.areas for source in row.sources)
    assert first.areas[2].status is LedgerWorkspaceStatus.NEEDS_ATTENTION
    payload = first.model_dump_json()
    for canary in (
        "SENSITIVE-COUNTERPARTY-CANARY",
        "SENSITIVE-DESCRIPTION-CANARY",
        "SENSITIVE-PATH-CANARY",
        "SENSITIVE-RAW-CANARY",
        "SENSITIVE-INVOICE-LINE-CANARY",
        "SENSITIVE-INVOICE-NUMBER-CANARY",
        "SENSITIVE-REVIEW-CANARY",
        "121.00",
    ):
        assert canary not in payload
        assert canary not in repr(first)


def test_each_injected_reader_runs_once_and_no_hidden_reader_is_needed() -> None:
    transaction = _transaction()
    calls: list[str] = []

    def suggestions(
        _invoices: InvoiceCatalogue,
        _transactions: TransactionCatalogue,
    ) -> tuple[()]:
        calls.append("suggestions")
        return ()

    def consistency(
        _invoices: InvoiceCatalogue,
        _transactions: TransactionCatalogue,
    ) -> tuple[()]:
        calls.append("consistency")
        return ()

    def staleness(**_kwargs: object) -> tuple[()]:
        calls.append("staleness")
        return ()

    projection = project_ledger_workspace(
        summary=_summary(),
        preflight=None,
        review=_review(transaction),
        transactions=TransactionCatalogue.from_transactions((transaction,)),
        invoices=InvoiceCatalogue(),
        revisions={},
        work_units=WorkUnitCatalogue(),
        invoice_reconciliation_reader=suggestions,
        link_consistency_reader=consistency,
        filing_staleness_reader=staleness,
    )

    assert calls == ["suggestions", "consistency", "staleness"]
    assert projection.areas[-1].status is LedgerWorkspaceStatus.EMPTY


def test_availability_is_not_inferred_from_empty_or_unmeasured_status() -> None:
    empty = LedgerWorkspaceAreaStateV1(
        area=LedgerWorkspaceArea.ENTRIES,
        sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
        status=LedgerWorkspaceStatus.EMPTY,
        item_count=0,
    )
    assert empty.availability is LedgerWorkspaceAvailability.AVAILABLE

    with pytest.raises(ValueError, match="requires an availability reason"):
        LedgerWorkspaceAreaStateV1(
            area=LedgerWorkspaceArea.IMPORT,
            sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
            availability=LedgerWorkspaceAvailability.UNAVAILABLE,
            status=LedgerWorkspaceStatus.UNMEASURED,
            item_count=0,
        )


def test_bucket_sources_cannot_be_mixed() -> None:
    transaction = _transaction()
    other_bucket = "41414141-4141-4141-8141-414141414141"
    with pytest.raises(LedgerWorkspaceProjectionError, match="different buckets"):
        project_ledger_workspace(
            summary=_summary(),
            preflight=None,
            review=_review(transaction, bucket_id=other_bucket),
            transactions=TransactionCatalogue.from_transactions((transaction,)),
            invoices=InvoiceCatalogue(),
            revisions={},
            work_units=WorkUnitCatalogue(),
            filing_staleness_reader=lambda **_kwargs: (),
        )


def test_affected_revision_without_declaration_identity_is_never_silently_dropped() -> None:
    revision = cast(
        CalculationRevision,
        SimpleNamespace(work_unit_id="a" * 64, calculation_revision_id="b" * 64),
    )
    verdict = LedgerFilingStalenessVerdict(is_stale=True, changed=("c" * 64,))

    with pytest.raises(LedgerWorkspaceProjectionError, match="no declaration identity"):
        project_affected_declaration_reconciliations(
            bucket_id=_BUCKET_ID,
            revisions={"b" * 64: revision},
            transactions=TransactionCatalogue(),
            work_units=WorkUnitCatalogue(),
            staleness_reader=lambda **_kwargs: ((revision, verdict),),
        )


def test_workspace_module_has_no_adapter_entrypoint_or_io_imports() -> None:
    source_path = Path(__file__).parents[1] / "workspace.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any("adapters" in module or "entrypoints" in module for module in imported)
    assert not any(module in {"os", "pathlib", "socket", "subprocess"} for module in imported)
