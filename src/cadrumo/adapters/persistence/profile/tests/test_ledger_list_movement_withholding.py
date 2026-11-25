"""A listed movement carries the retención its paid invoice leaves on it, as the declarations read it.

The quarter is APP-QA's: a natural-person professional bills 300.00 plus 21 per
cent IVA and withholds 15 per cent, 45.00, paid net by one bank movement of
318.00. The expected figures are worked by hand from the invoice, not read back
from the code under test: 15 per cent of 300.00 is 45.00, and half the net
payment settles half of it.

Decimal text is served normalised, as every ledger amount is: 45.00 is "45".

The rows are read through the encrypted repositories and the list operation's own
projection, then compared with what the Modelo 111 source resolver reads from the
same stores.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.aggregation.tests.received_invoice_withholding_support import (
    NATURAL_PERSON_PROFESSIONAL_NIF,
    PROFESSIONAL_COMPANY_NIF,
    paying_movement,
    professional_fee_quarter,
    received_invoice,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from .....application.aggregation.received_invoice_withholding import (
    ReceivedInvoiceWithholdingFindingKind,
    received_invoice_withholding,
)
from .....application.ledger.list_operation import ledger_list_row, listed_movement_withholding
from .....application.ledger.list_query import LedgerTransactionListQuery, query_ledger_transaction_list
from .....application.ledger.read_ports import LedgerReadPorts
from .....application.ledger.transaction_projection import LedgerTransactionReviewProjection
from .....application.review.filter import LedgerReviewFilterSpec
from .....core.period import Period
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.invoices.catalogue import InvoiceCatalogue
from .....domain.transactions.models import Transaction, TransactionCatalogue
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..buckets import BucketEventHistoryRepository
from ..invoices import InvoiceCatalogueRepository
from ..transactions import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "52525252-5252-4525-8525-525252525252"
_ACTIVITY = "actividad_economica"


def _listed(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    invoices: InvoiceCatalogue,
    movements: TransactionCatalogue,
) -> dict[str, LedgerTransactionReviewProjection]:
    """List every movement the way the ledger list operation does, from encrypted stores."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository).save(movements)
        InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository).save(invoices)
        ports = LedgerReadPorts(
            operation=authority_operation,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository),
            bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
            invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository),
        )
        page = query_ledger_transaction_list(
            LedgerTransactionListQuery(spec=LedgerReviewFilterSpec.from_strings(())),
            bucket_id=_BUCKET_ID,
            ports=ports,
        )
        listed: tuple[Transaction, ...] = tuple(item.transaction for item in page.results)
        withholding = listed_movement_withholding(listed, bucket_id=_BUCKET_ID, ports=ports)
    return {
        transaction.transaction_id: ledger_list_row(
            transaction, withholding=withholding.get(transaction.transaction_id, ())
        )
        for transaction in listed
    }


def test_the_paying_movement_lists_the_retencion_in_every_supported_year(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    for year in filing_year_envelope().years:
        invoices, movements = professional_fee_quarter(
            year, tax_id=NATURAL_PERSON_PROFESSIONAL_NIF, irpf_category=_ACTIVITY, bucket_id=_BUCKET_ID
        )
        (fee,) = movements.values()

        (tmp_path / str(year)).mkdir()
        row = _listed(tmp_path / str(year), authority_operation, invoices, movements)[fee.transaction_id]

        assert row.transaction.amount == "318", year
        (withholding,) = row.withholding
        assert withholding.retencion == "45", year
        assert withholding.held_back is None, year
        assert withholding.modelo == "111", year
        assert withholding.scheme == "actividades_profesionales", year
        assert withholding.recognised_on == date(year, 2, 28).isoformat(), year
        assert withholding.invoice_number == f"GES-{year}-001", year


def test_the_listed_retencion_is_the_one_modelo_111_reads(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    year = filing_year_envelope().years[-1]
    invoices, movements = professional_fee_quarter(
        year, tax_id=NATURAL_PERSON_PROFESSIONAL_NIF, irpf_category=_ACTIVITY, bucket_id=_BUCKET_ID
    )
    (fee,) = movements.values()

    row = _listed(tmp_path, authority_operation, invoices, movements)[fee.transaction_id]
    declared = received_invoice_withholding(
        invoices,
        movements,
        bucket_id=_BUCKET_ID,
        modelo="111",
        period=Period.from_year_and_code(year, "1T"),
    )

    assert sum(Decimal(item.retencion_amount) for item in declared.observations) == Decimal("45.00")
    assert tuple(item.retencion for item in row.withholding) == ("45",)


def test_a_movement_paying_no_invoice_with_a_retencion_has_none_and_not_zero(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    year = filing_year_envelope().years[-1]
    invoices, movements = professional_fee_quarter(
        year, tax_id=NATURAL_PERSON_PROFESSIONAL_NIF, irpf_category=_ACTIVITY, bucket_id=_BUCKET_ID
    )
    unrelated = paying_movement("LUZ-0301", date(year, 3, 1), cash=Decimal("60.50"), irpf_category=None)
    movements = TransactionCatalogue.from_transactions((*movements.values(), unrelated))

    rows = _listed(tmp_path, authority_operation, invoices, movements)

    assert rows[unrelated.transaction_id].withholding == ()
    assert len(rows) == 2


def test_a_payment_the_declaration_waits_on_is_held_back_and_not_shown_as_no_retencion(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    year = filing_year_envelope().years[-1]
    invoices, movements = professional_fee_quarter(
        year, tax_id=NATURAL_PERSON_PROFESSIONAL_NIF, irpf_category=None, bucket_id=_BUCKET_ID
    )
    (fee,) = movements.values()

    row = _listed(tmp_path, authority_operation, invoices, movements)[fee.transaction_id]

    (withholding,) = row.withholding
    assert withholding.retencion is None
    assert withholding.held_back == ReceivedInvoiceWithholdingFindingKind.INCOME_KIND_UNDECLARED.value
    assert withholding.modelo is None


def test_a_professional_company_fee_is_held_back_as_an_entity_fee(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    year = filing_year_envelope().years[-1]
    invoices, movements = professional_fee_quarter(
        year, tax_id=PROFESSIONAL_COMPANY_NIF, irpf_category=_ACTIVITY, bucket_id=_BUCKET_ID
    )
    (fee,) = movements.values()

    row = _listed(tmp_path, authority_operation, invoices, movements)[fee.transaction_id]

    (withholding,) = row.withholding
    assert withholding.retencion is None
    assert withholding.held_back == ReceivedInvoiceWithholdingFindingKind.ENTITY_PROFESSIONAL_FEE.value
    assert withholding.modelo == "111"


def test_each_part_payment_carries_its_share_and_the_shares_add_up_to_the_invoice(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    year = filing_year_envelope().years[-1]
    first = paying_movement("GES-PAGO-A", date(year, 2, 20), cash=Decimal("159.00"), irpf_category=_ACTIVITY)
    second = paying_movement("GES-PAGO-B", date(year, 3, 10), cash=Decimal("159.00"), irpf_category=_ACTIVITY)
    invoice = received_invoice(
        f"GES-{year}-002",
        date(year, 2, 18),
        supplier="Pedro Gestor Ejemplo",
        tax_id=NATURAL_PERSON_PROFESSIONAL_NIF,
        base=Decimal("300.00"),
        retencion=Decimal("45.00"),
        rate=Decimal("0.15"),
        linked=(first.transaction_id, second.transaction_id),
        bucket_id=_BUCKET_ID,
    )

    rows = _listed(
        tmp_path,
        authority_operation,
        build_invoice_catalogue((invoice,)),
        TransactionCatalogue.from_transactions((first, second)),
    )

    assert tuple(item.retencion for item in rows[first.transaction_id].withholding) == ("22.5",)
    assert tuple(item.retencion for item in rows[second.transaction_id].withholding) == ("22.5",)
