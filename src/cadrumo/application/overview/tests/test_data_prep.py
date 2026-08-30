"""Real-behavior tests for ``build_data_prep_walkthrough``.

Exercises the ordered data-prep checklist directly against real
:class:`~cadrumo.domain.transactions.TransactionCatalogueRepository` storage (an
isolated encrypted profile bucket, no mocks), real
:class:`~cadrumo.domain.invoices.InvoiceCatalogue` / :class:`~cadrumo.domain.invoices.Invoice`
records, and a real :func:`~cadrumo.application.ledger.preflight.preflight_ledger_tax_readiness`
report. This module never touches the modelo calculation registry authority, so it
stays independent of any registry-authoring state elsewhere in the tree.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.tests.runtime_profile_fixture import (
    bucket_scoped_transaction_catalogue_fixture,
)
from ....application.ledger.evidence import MediaKind, PurchaseInvoiceEvidence
from ....application.ledger.preflight import preflight_ledger_tax_readiness
from ....core.period import Period
from ....core.aggregation import BindingSourceKind
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..data_prep import (
    DataPrepStepId,
    DataPrepStepState,
    build_data_prep_walkthrough,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "44444444-4444-4444-8444-444444444444"
_PERIOD_1T_2026 = Period.from_year_and_code(2026, "1T")


_tx_repository = bucket_scoped_transaction_catalogue_fixture(_BUCKET_ID, name="_tx_repository")


def _raw(provider_id: str, *, booked_date: date, amount: Decimal = Decimal("100.00")) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Proveedor SL",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path("statement.csv"),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 1, 1, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": BindingSourceKind.LEDGER_TRANSACTION.value},
    )


def _transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 2, 10),
    business_classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
    category_id: str | None = None,
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    iva_amount: Decimal | None = None,
    purchase_invoice_evidence_id: str | None = None,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
) -> Transaction:
    # The gross ``raw.amount`` must equal ``taxable_base + iva_amount`` to the
    # cent when both are populated; derive it rather than hardcoding a value
    # that could silently drift from the base/IVA pair under test.
    gross = (taxable_base or Decimal("0")) + (iva_amount or Decimal("0")) if taxable_base is not None else None
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, booked_date=booked_date, amount=gross or Decimal("100.00")),
            "direction": direction,
            "group_label": None,
            "business_classification": business_classification,
            "source_jurisdiction": "ES",
            "category_id": category_id,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "purchase_invoice_evidence_id": purchase_invoice_evidence_id,
            "classified_at": datetime(2026, 2, 11, tzinfo=UTC)
            if business_classification != BusinessClassification.NOT_YET_PROCESSED
            else None,
            "classified_by": "manual",
        },
    )


def _invoice(*, issued_at: date = date(2026, 2, 5)) -> Invoice:
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-001",
            "issued_at": issued_at,
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "payment_status": PaymentStatus.PAID,
            "lines": (
                InvoiceLine.model_validate(
                    {
                        "description": "Servicios",
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100.00"),
                        "subtotal": Decimal("100.00"),
                        "iva_rate": IvaRate.RATE_21,
                        "iva_amount": Decimal("21.00"),
                    },
                ),
            ),
        },
    )


def _evidence(*, evidence_id: str = "ev-001") -> PurchaseInvoiceEvidence:
    return PurchaseInvoiceEvidence.model_validate(
        {
            "evidence_id": evidence_id,
            "bucket_id": _BUCKET_ID,
            "source_path": "factura.pdf",
            "source_sha256": "a" * 64,
            # The bytes' in-store home; equals source_sha256 for a real `evidence add`.
            "attachment_id": "a" * 64,
            "media_kind": MediaKind.PDF,
            "created_at": datetime(2026, 2, 5, tzinfo=UTC),
            "updated_at": datetime(2026, 2, 5, tzinfo=UTC),
        },
    )


def _work_unit(*, modelo: str = "130", period: Period = _PERIOD_1T_2026, name: str = "130-2026-1T") -> WorkUnit:
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        revision_id="2019-y-siguientes",
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=period.filing_year,
        period=period,
        revision_id="2019-y-siguientes",
        name=name,
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
        updated_at=datetime(2026, 2, 1, tzinfo=UTC),
    )


def _walkthrough(
    tx_repository: TransactionCatalogueRepository,
    *,
    invoice_catalogue: InvoiceCatalogue | None = None,
    evidence_records: tuple[PurchaseInvoiceEvidence, ...] = (),
    work_units: tuple[WorkUnit, ...] = (),
):
    preflight_report = preflight_ledger_tax_readiness(
        bucket_id=_BUCKET_ID,
        period=_PERIOD_1T_2026,
        transaction_repository=tx_repository,
    )
    return build_data_prep_walkthrough(
        bucket_id=_BUCKET_ID,
        modelo="130",
        period=_PERIOD_1T_2026,
        transaction_repository=tx_repository,
        invoice_catalogue=invoice_catalogue or InvoiceCatalogue.model_validate({}),
        evidence_records=evidence_records,
        preflight_report=preflight_report,
        work_unit_catalogue=WorkUnitCatalogue.from_work_units(work_units),
    )


def test_fresh_bucket_declares_no_import_action_and_a_concrete_work_create_action(
    _tx_repository: TransactionCatalogueRepository,
) -> None:
    """A brand-new profile with no ledger data: step 1 is pending and every
    later step is pending too, none marked done."""

    walkthrough = _walkthrough(_tx_repository)

    steps_by_id = {step.step_id: step for step in walkthrough.steps}
    import_step = steps_by_id[DataPrepStepId.IMPORT_TRANSACTIONS]
    assert import_step.state is DataPrepStepState.PENDING
    assert "0 transaction" in import_step.summary
    # Importing needs a statement file and a provider the walkthrough cannot
    # know, so the row declares no executable action rather than a
    # placeholder command.
    assert import_step.next_action is None
    assert walkthrough.ready_for_calculation is False

    # The final step correctly reflects "no work unit yet" and names the
    # exact create command for THIS modelo/period.
    work_step = steps_by_id[DataPrepStepId.START_MODELO_WORK]
    assert work_step.state is DataPrepStepState.PENDING
    assert work_step.next_action is not None
    assert work_step.next_action.action.action_id == "operator.modelo.work.create"
    assert {binding.argument_name: binding.value for binding in work_step.next_action.argument_bindings} == {
        "modelo": "130",
        "year": 2026,
        "period": "1T",
    }


def test_import_step_advances_once_a_transaction_is_recorded(
    _tx_repository: TransactionCatalogueRepository,
) -> None:
    """M19-style progression check: after a transaction lands in the
    requested period, step 1 flips from pending to done - it must not keep
    telling the operator to import when data already exists."""

    _tx_repository.save(TransactionCatalogue.from_transactions((_transaction("row-1"),)))

    walkthrough = _walkthrough(_tx_repository)
    steps_by_id = {step.step_id: step for step in walkthrough.steps}

    import_step = steps_by_id[DataPrepStepId.IMPORT_TRANSACTIONS]
    assert import_step.state is DataPrepStepState.DONE
    assert "1 transaction" in import_step.summary

    # Classification has not happened yet, so the next step is not done.
    classify_step = steps_by_id[DataPrepStepId.CLASSIFY_TRANSACTIONS]
    assert classify_step.state is DataPrepStepState.PENDING
    assert classify_step.next_action is not None
    assert classify_step.next_action.action.action_id == "operator.ledger.classify"


def test_out_of_period_transaction_does_not_satisfy_import_step(
    _tx_repository: TransactionCatalogueRepository,
) -> None:
    """A transaction dated outside the requested 1T 2026 window must not
    falsely mark the import step done for that scope."""

    _tx_repository.save(
        TransactionCatalogue.from_transactions((_transaction("row-q3", booked_date=date(2026, 8, 1)),)),
    )

    walkthrough = _walkthrough(_tx_repository)
    import_step = next(s for s in walkthrough.steps if s.step_id is DataPrepStepId.IMPORT_TRANSACTIONS)
    assert import_step.state is DataPrepStepState.PENDING


def test_classify_step_done_once_all_period_transactions_classified(
    _tx_repository: TransactionCatalogueRepository,
) -> None:
    classified = _transaction(
        "row-classified",
        business_classification=BusinessClassification.BUSINESS,
        category_id="material_oficina",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        purchase_invoice_evidence_id="ev-001",
    )
    _tx_repository.save(TransactionCatalogue.from_transactions((classified,)))

    walkthrough = _walkthrough(_tx_repository, evidence_records=(_evidence(),))
    steps_by_id = {step.step_id: step for step in walkthrough.steps}

    assert steps_by_id[DataPrepStepId.CLASSIFY_TRANSACTIONS].state is DataPrepStepState.DONE
    assert steps_by_id[DataPrepStepId.ATTACH_EVIDENCE].state is DataPrepStepState.DONE
    assert steps_by_id[DataPrepStepId.RESOLVE_READINESS].state is DataPrepStepState.DONE


def test_evidence_step_flags_business_expense_with_no_attached_evidence(
    _tx_repository: TransactionCatalogueRepository,
) -> None:
    expense_without_evidence = _transaction(
        "row-expense",
        business_classification=BusinessClassification.BUSINESS,
        category_id="material_oficina",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        purchase_invoice_evidence_id=None,
    )
    _tx_repository.save(TransactionCatalogue.from_transactions((expense_without_evidence,)))

    walkthrough = _walkthrough(_tx_repository)
    evidence_step = next(s for s in walkthrough.steps if s.step_id is DataPrepStepId.ATTACH_EVIDENCE)
    assert evidence_step.state is DataPrepStepState.PENDING
    assert "1 of 1" in evidence_step.summary
    # Attaching evidence needs a document path only the operator has.
    assert evidence_step.next_action is None


def test_evidence_step_does_not_count_incoming_business_income_as_expense(
    _tx_repository: TransactionCatalogueRepository,
) -> None:
    """An incoming BUSINESS row belongs to income, not purchase evidence."""
    income = _transaction(
        "row-income",
        business_classification=BusinessClassification.BUSINESS,
        direction=TransactionDirection.INCOMING,
    )
    _tx_repository.save(TransactionCatalogue.from_transactions((income,)))

    walkthrough = _walkthrough(_tx_repository)
    evidence_step = next(s for s in walkthrough.steps if s.step_id is DataPrepStepId.ATTACH_EVIDENCE)

    assert evidence_step.state is DataPrepStepState.DONE
    assert "no classified business/mixed expenses require evidence" in evidence_step.summary


def test_invoices_step_reflects_period_scoped_invoice_catalogue(
    _tx_repository: TransactionCatalogueRepository,
) -> None:
    catalogue = InvoiceCatalogue.from_invoices((_invoice(),))

    walkthrough = _walkthrough(_tx_repository, invoice_catalogue=catalogue)
    invoices_step = next(s for s in walkthrough.steps if s.step_id is DataPrepStepId.REGISTER_INVOICES)
    assert invoices_step.state is DataPrepStepState.DONE
    assert "1 business invoice" in invoices_step.summary


def test_work_unit_step_resolves_matching_unit_and_names_calculate_command(
    _tx_repository: TransactionCatalogueRepository,
) -> None:
    unit = _work_unit()
    walkthrough = _walkthrough(_tx_repository, work_units=(unit,))
    work_step = next(s for s in walkthrough.steps if s.step_id is DataPrepStepId.START_MODELO_WORK)

    assert work_step.state is DataPrepStepState.DONE
    assert work_step.next_action is not None
    assert work_step.next_action.action.action_id == "operator.modelo.work.calculate"
    assert {binding.argument_name: binding.value for binding in work_step.next_action.argument_bindings} == {
        "work_unit_id": unit.work_unit_id
    }


def test_ready_for_calculation_true_only_when_every_step_is_done(
    _tx_repository: TransactionCatalogueRepository,
) -> None:
    fully_ready_row = _transaction(
        "row-ready",
        business_classification=BusinessClassification.BUSINESS,
        category_id="material_oficina",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        purchase_invoice_evidence_id="ev-001",
    )
    _tx_repository.save(TransactionCatalogue.from_transactions((fully_ready_row,)))
    catalogue = InvoiceCatalogue.from_invoices((_invoice(),))

    not_ready = _walkthrough(_tx_repository, invoice_catalogue=catalogue, evidence_records=(_evidence(),))
    assert not_ready.ready_for_calculation is False  # no matching work unit yet

    fully_ready = _walkthrough(
        _tx_repository,
        invoice_catalogue=catalogue,
        evidence_records=(_evidence(),),
        work_units=(_work_unit(),),
    )
    assert fully_ready.ready_for_calculation is True
    assert all(step.state is DataPrepStepState.DONE for step in fully_ready.steps)
