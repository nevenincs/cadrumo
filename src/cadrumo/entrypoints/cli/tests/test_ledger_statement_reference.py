"""``ledger list`` and ``ledger view`` serve the reference the bank statement printed.

Rows are stored through the real encrypted repository, read back through the
canonical list query and rendered by the CLI projection and text renderer.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.ledger.list_operation import LedgerListProjection as LedgerListSnapshot
from ....application.ledger.list_operation import ledger_list_row
from ....application.ledger.list_query import LedgerTransactionListQuery, query_ledger_transaction_list
from ....application.ledger.manual_read import ledger_transaction_payload
from ....application.review.filter import LedgerReviewFilterSpec
from ....core.i18n.render import tr
from ....core.ledger_sort import LedgerSortField, LedgerSortOrder
from ....core.output_rendering import render_command_output
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...ledger_action_composition import compose_ledger_action_ports
from ..ledger_list import LedgerListProjection, project_ledger_list
from ..ledger_results import TransactionPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "7c1d2e3f-4a5b-4c6d-8e7f-8091a2b3c4d5"
_REFERENCE = "0049-7731-REF-000184"


def _transaction(*, provider_id: str, amount: Decimal, statement_reference: str | None) -> Transaction:
    booked = date(filing_year_envelope().horizon, 4, 10)
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked,
        amount=amount,
        currency="EUR",
        description="RECIBO LUZ",
        provenance=RawProvenance(
            source_path=Path("extracto.csv"),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(booked.year, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "RECIBO LUZ"},
        statement_reference=statement_reference,
    )
    created = datetime(booked.year, 4, 14, 9, 30, tzinfo=UTC)
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": created,
            "modified_at": created,
        }
    )


def _listed(tmp_path: Path, operation: PinnedAuthorityOperation, rows: list[Transaction]) -> LedgerListProjection:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(TransactionCatalogue.from_transactions(rows))
        page = query_ledger_transaction_list(
            LedgerTransactionListQuery(
                spec=LedgerReviewFilterSpec.from_strings([]),
                sort_by=LedgerSortField.AMOUNT,
                sort_order=LedgerSortOrder.ASC,
            ),
            bucket_id=profile.bucket_id,
            ports=compose_ledger_action_ports(bucket_id=profile.bucket_id, operation=operation),
        )
        return project_ledger_list(
            LedgerListSnapshot(
                profile_id=UUID(profile.bucket_id),
                rows=tuple(ledger_list_row(item.transaction) for item in page.results),
                total=page.total,
                truncated=page.truncated,
                offset=0,
                limit=None,
                by_group=False,
            ),
        )


def test_ledger_list_serves_the_printed_reference_in_json_and_its_own_text_column(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    projection = _listed(
        tmp_path,
        authority_operation,
        [
            _transaction(provider_id="printed", amount=Decimal("10.00"), statement_reference=_REFERENCE),
            _transaction(provider_id="unprinted", amount=Decimal("20.00"), statement_reference=None),
        ],
    )

    assert [row.statement_reference for row in projection.rows] == [_REFERENCE, None]
    header = projection.lines[1].split("\t")
    column = header.index(tr("cli.ledger.labels.statement_reference"))
    assert [line.split("\t")[column] for line in projection.lines[2:]] == [_REFERENCE, ""]
    assert all(len(line.split("\t")) == len(header) for line in projection.lines[2:])


def test_an_imported_reference_with_line_breaks_cannot_forge_a_list_row(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    hostile = "REF-1\nforged\trow"
    projection = _listed(
        tmp_path,
        authority_operation,
        [_transaction(provider_id="hostile", amount=Decimal("10.00"), statement_reference=hostile)],
    )

    rendered = render_command_output(format_name="text", payload=None, lines=projection.lines).text.split("\n")
    assert len(rendered) == 3
    assert len(rendered[-1].split("\t")) == len(rendered[1].split("\t"))
    assert projection.rows[0].statement_reference == hostile


def test_the_view_payload_carries_the_reference_and_none_when_the_statement_printed_none() -> None:
    printed = TransactionPayload.model_validate(
        ledger_transaction_payload(
            _transaction(provider_id="printed", amount=Decimal("10.00"), statement_reference=_REFERENCE)
        ).model_dump(mode="json")
    )
    unprinted = TransactionPayload.model_validate(
        ledger_transaction_payload(
            _transaction(provider_id="unprinted", amount=Decimal("10.00"), statement_reference=None)
        ).model_dump(mode="json")
    )

    assert printed.statement_reference == _REFERENCE
    assert unprinted.statement_reference is None
