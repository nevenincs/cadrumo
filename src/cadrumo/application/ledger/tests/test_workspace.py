"""Safety and authority tests for the frontend-neutral Ledger workspace."""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from ....core.period import Period
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.ledger_filing_snapshot import LedgerFilingStalenessVerdict
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
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
    assert tuple((row.area, row.sources, row.availability, row.status, row.item_count) for row in first.areas) == (
        (
            LedgerWorkspaceArea.OVERVIEW,
            (LedgerWorkspaceSource.LOCAL_LEDGER, LedgerWorkspaceSource.LOCAL_DECLARATIONS),
            LedgerWorkspaceAvailability.AVAILABLE,
            LedgerWorkspaceStatus.NEEDS_ATTENTION,
            1,
        ),
        (
            LedgerWorkspaceArea.ENTRIES,
            (LedgerWorkspaceSource.LOCAL_LEDGER,),
            LedgerWorkspaceAvailability.AVAILABLE,
            LedgerWorkspaceStatus.READY,
            1,
        ),
        (
            LedgerWorkspaceArea.REVIEW,
            (LedgerWorkspaceSource.LOCAL_LEDGER,),
            LedgerWorkspaceAvailability.AVAILABLE,
            LedgerWorkspaceStatus.NEEDS_ATTENTION,
            1,
        ),
        (
            LedgerWorkspaceArea.IMPORT,
            (LedgerWorkspaceSource.LOCAL_LEDGER,),
            LedgerWorkspaceAvailability.AVAILABLE,
            LedgerWorkspaceStatus.UNMEASURED,
            0,
        ),
        (
            LedgerWorkspaceArea.CLASSIFICATION,
            (LedgerWorkspaceSource.LOCAL_LEDGER,),
            LedgerWorkspaceAvailability.AVAILABLE,
            LedgerWorkspaceStatus.NEEDS_ATTENTION,
            1,
        ),
        (
            LedgerWorkspaceArea.EVIDENCE,
            (LedgerWorkspaceSource.LOCAL_LEDGER, LedgerWorkspaceSource.LOCAL_INVOICES),
            LedgerWorkspaceAvailability.AVAILABLE,
            LedgerWorkspaceStatus.UNMEASURED,
            0,
        ),
        (
            LedgerWorkspaceArea.RECONCILIATION,
            (
                LedgerWorkspaceSource.LOCAL_LEDGER,
                LedgerWorkspaceSource.LOCAL_INVOICES,
                LedgerWorkspaceSource.LOCAL_DECLARATIONS,
            ),
            LedgerWorkspaceAvailability.AVAILABLE,
            LedgerWorkspaceStatus.NEEDS_ATTENTION,
            1,
        ),
    )
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


def test_foreign_invoice_is_refused_before_any_reconciliation_reader() -> None:
    transaction = _transaction()
    foreign = _invoice().model_copy(update={"bucket_id": "41414141-4141-4141-8141-414141414141"})
    calls: list[str] = []

    def reader(*_args: object, **_kwargs: object) -> tuple[()]:
        calls.append("called")
        return ()

    with pytest.raises(LedgerWorkspaceProjectionError, match="foreign Ledger bucket"):
        project_ledger_workspace(
            summary=_summary(),
            preflight=None,
            review=_review(transaction),
            transactions=TransactionCatalogue.from_transactions((transaction,)),
            invoices=InvoiceCatalogue.from_invoices((foreign,)),
            revisions={},
            work_units=WorkUnitCatalogue(),
            invoice_reconciliation_reader=reader,
            link_consistency_reader=reader,
            filing_staleness_reader=reader,
        )
    assert calls == []


@pytest.mark.parametrize(
    ("summary_delta", "review_status", "message"),
    [
        ({"total_count": 2}, "pending", "summary counts"),
        ({}, "reviewed", "review status"),
    ],
)
def test_contradictory_summary_or_review_facts_are_refused(
    summary_delta: dict[str, int],
    review_status: str,
    message: str,
) -> None:
    transaction = _transaction()
    resolved_review = _review(transaction).model_copy(
        update={"rows": (_review(transaction).rows[0].model_copy(update={"status": review_status}),)}
    )
    with pytest.raises(LedgerWorkspaceProjectionError, match=message):
        project_ledger_workspace(
            summary=_summary().model_copy(update=summary_delta),
            preflight=None,
            review=resolved_review,
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


def test_affected_declarations_keep_natural_addresses_counts_and_deterministic_order() -> None:
    periods = (Period.from_year_and_code(2026, "1T"), Period.from_year_and_code(2026, "2T"))
    units: list[WorkUnit] = []
    revisions: list[CalculationRevision] = []
    verdicts: list[LedgerFilingStalenessVerdict] = []
    for index, period in enumerate(periods, start=1):
        work_unit_id = derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=period,
            revision_id=f"revision-{index}",
        )
        units.append(
            WorkUnit(
                work_unit_id=work_unit_id,
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2026,
                period=period,
                revision_id=f"revision-{index}",
                name=f"Synthetic {index}",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        revisions.append(
            cast(
                CalculationRevision,
                SimpleNamespace(work_unit_id=work_unit_id, calculation_revision_id=f"{index}" * 64),
            )
        )
        verdicts.append(
            LedgerFilingStalenessVerdict(
                is_stale=True,
                changed=tuple("c" * 64 for _ in range(index)),
                removed=tuple("d" * 64 for _ in range(3 - index)),
            )
        )

    rows = project_affected_declaration_reconciliations(
        bucket_id=_BUCKET_ID,
        revisions={revision.calculation_revision_id: revision for revision in revisions},
        transactions=TransactionCatalogue(),
        work_units=WorkUnitCatalogue.from_work_units(tuple(units)),
        staleness_reader=lambda **_kwargs: tuple(reversed(tuple(zip(revisions, verdicts, strict=True)))),
    )

    assert tuple((row.modelo, row.filing_year, row.period) for row in rows) == (
        ("303", 2026, periods[0]),
        ("303", 2026, periods[1]),
    )
    assert tuple((row.changed_count, row.removed_count) for row in rows) == ((1, 2), (2, 1))
    assert tuple(row.calculation_revision_id for row in rows) == ("1" * 64, "2" * 64)


def test_workspace_module_has_no_adapter_entrypoint_or_io_imports() -> None:
    source_path = Path(__file__).parents[1] / "workspace.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert not any("adapters" in module or "entrypoints" in module for module in imported)
    assert not any(module in {"os", "pathlib", "socket", "subprocess"} for module in imported)
