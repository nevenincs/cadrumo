"""Real-path tests for the IVA operation date, the V5 fingerprint and sealed invoices.

Worked by hand: a sale of 1,000.00 at 21 % carries a cuota of 210.00, and LIVA
art. 75.Uno places it in the quarter the operation took place. On 30 March that
is 1T, whatever date the money reached the bank. An advance of 500.00 collected
on 20 March carries 105.00 in 1T under art. 75.Dos, while its 500.00 balance
delivered on 10 April stays out of 1T; an advance collected in December stays out
of the following year's 1T, whose balance carries its own 105.00. A purchase of 200.00 at 21 %
carries a deductible cuota of 42.00.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.catalogue_creation import build_catalogue_lifecycle_ports
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from ....adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.aggregation.errors import AggregationValidationError
from ....application.aggregation.ledger_filing_snapshot import row_fingerprint
from ....application.invoices.catalogue_lifecycle import (
    CatalogueInvoicePatch,
    remove_catalogue_invoice,
    update_catalogue_invoice,
)
from ....application.ledger.manual_update import update_manual_transaction_fields
from ....application.ledger.models import ManualLedgerTransactionPatch
from ....application.modelo.export import export_modelo_revision
from ....application.modelo.export_contracts import ModeloExportCommand
from ....application.modelo.filing_actions import file_modelo_revision
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.hierarchy import CadrumoError
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.deadlines.models import M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile
from ....domain.invoices.enums import IvaRate, PaymentStatus, operation_performed_role
from ....domain.invoices.models import Invoice, InvoiceLine, derive_invoice_id
from ....domain.invoices.tests.catalogue_support import build_invoice_catalogue
from ....domain.iva.schema import InvoiceKind
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ....domain.modelos.verification_report import VerificationReport
from ....domain.modelos.work_unit import WorkUnit
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction
from ....tests.env_scope import ready_clave_settings
from ...adapter_composition_work_ports import (
    build_filing_action_ports,
    build_ledger_membership_ports,
    build_verification_repository_bundle,
)
from .ledger_drift_support import (
    BUCKET_ID,
    TAX_ID,
    calculate_irene,
    calculate_irene_revision,
    iva_transaction,
    workflow_profile,
)
from .m303_annual_ledger_support import product_software_identity
from .verification_repository_support import build_test_certificate_secret_backend_factory

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_DEVENGADA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_DEDUCIBLE: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_AT = datetime(2026, 4, 6, 10, 0, tzinfo=UTC)
_MOVEMENT_DATED = "iva_row_placed_on_movement_date"
_AFTER_MOVEMENT = "iva_operation_date_after_movement"
_INVOICE_SHORTFALL = "invoice_domestic_iva_not_in_transaction_ledger"
_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()
_SALE_ON_THE_BOUNDARY = "boundary-sale"


def _general_iva_profile() -> ModeloIVAProfile:
    return ModeloIVAProfile(
        tax_territory=M303TaxTerritory.from_registry("common_regime"),
        regime_composition=M303RegimeComposition.from_registry("general"),
        redeme_enrolled=False,
        cash_accounting_regime_enrolled=False,
        voluntary_sii_enrolled=False,
        hydrocarbon_deposit_advance_payment_deduction_entitled=False,
    )


def _sale(
    provider_id: str = _SALE_ON_THE_BOUNDARY,
    *,
    base: Decimal = Decimal("1000.00"),
    booked: date = date(2026, 4, 2),
    operation_date: date | None = None,
) -> Transaction:
    return iva_transaction(
        provider_id,
        direction=TransactionDirection.INCOMING,
        taxable_base=base,
        booked_date=booked,
        operation_date=operation_date,
    )


def _reasons(work_unit: WorkUnit) -> set[str]:
    return {str(item.reason) for item in calculate_irene(work_unit).source_diagnostics}


def _work_unit_of(objects: SecureObjectRepository, revision: CalculationRevision) -> WorkUnit:
    from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository

    work_unit = WorkUnitCatalogueRepository(objects=objects).load().get(revision.work_unit_id)
    assert work_unit is not None
    return work_unit


def _set_operation_date(objects: SecureObjectRepository, transaction: Transaction, operation_date: date) -> Transaction:
    with ledger_ports_for_test(bucket_id=BUCKET_ID, objects=objects) as ports:
        updated = update_manual_transaction_fields(
            bucket_id=BUCKET_ID,
            transaction_id=transaction.transaction_id,
            patch=ManualLedgerTransactionPatch(operation_date=operation_date),
            actor="operator",
            source_command="ledger.update",
            ports=ports,
            occurred_at=_AT,
        )
    return updated.transaction


def _verify(objects: SecureObjectRepository, revision_id: str) -> VerificationReport:
    with bundled_indexed_authority().operation() as operation:
        return verify_modelo_revision_with_preconditions(
            revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            actor="operator",
            workflow_profile=workflow_profile(),
            settings=ready_clave_settings(TAX_ID),
            verification_repositories=replace(
                build_verification_repository_bundle(BUCKET_ID, operation=operation),
                ledger_membership_ports=build_ledger_membership_ports(
                    bucket_id=BUCKET_ID,
                    transaction_repository=TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=objects),
                ),
            ),
            clock=_AT,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).report


def _export(revision_id: str, output: Path) -> bytes:
    with bundled_indexed_authority().operation() as operation:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=revision_id,
                output_path=output,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            ),
            workflow_profile=workflow_profile().model_copy(update={"iva": _general_iva_profile()}),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=product_software_identity(),
                bucket_id=BUCKET_ID,
                taxpayer_tax_id=TAX_ID,
            ),
            clock=_AT,
            operation=operation,
        )
    return output.read_bytes()


def _file(revision_id: str, report: VerificationReport) -> None:
    with bundled_indexed_authority().operation() as operation:
        file_modelo_revision(
            revision_id,
            approved_verification_report_id=report.verification_report_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            actor="operator",
            workflow_profile=workflow_profile(),
            ports=build_filing_action_ports(bucket_id=BUCKET_ID, operation=operation),
            clock=_AT,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )


def _issued_invoice(*, issued_at: date = date(2026, 3, 30)) -> Invoice:
    base, iva = Decimal("1000.00"), Decimal("210.00")
    grand_total = base + iva
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=InvoiceKind.ISSUED,
            invoice_number="V-075",
            issued_at=issued_at,
            counterparty_tax_id="B00015016",
            currency="EUR",
            grand_total=grand_total,
        ),
        bucket_id=BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        invoice_number="V-075",
        issued_at=issued_at,
        operation_date=issued_at,
        operation_date_role=operation_performed_role(),
        counterparty_name="CLIENTE EJEMPLO SL",
        counterparty_tax_id="B00015016",
        counterparty_country="ES",
        base_total=base,
        iva_total=iva,
        grand_total=grand_total,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Operacion interior",
                quantity=Decimal("1"),
                unit_price=base,
                subtotal=base,
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=iva,
            ),
        ),
        payment_status=PaymentStatus.PENDING,
    )


def test_a_sale_on_30_march_collected_on_2_april_moves_to_the_first_quarter(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        objects = profile.repository
        sale = _sale()
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(objects, operation=operation, rows=(sale,))
        assert sale.transaction_id not in revision.source_transaction_ids

        _set_operation_date(objects, sale, date(2026, 3, 30))
        result = calculate_irene(_work_unit_of(objects, revision))

        assert result.revision.casilla_values[_DEVENGADA] == Decimal("210.00")
        assert sale.transaction_id in result.revision.source_transaction_ids
        assert _MOVEMENT_DATED not in {str(item.reason) for item in result.source_diagnostics}


def test_the_fallback_to_the_bank_date_raises_its_advisory_in_the_receiving_quarter(tmp_path: Path) -> None:
    """Sold on 30 December, banked on 2 January: the first quarter wrongly receives it."""
    sale = _sale(booked=date(2026, 1, 2))
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        objects = profile.repository
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(objects, operation=operation, rows=(sale,))
        result = calculate_irene(_work_unit_of(objects, revision))

        assert result.revision.casilla_values[_DEVENGADA] == Decimal("210.00")
        advisory = next(item for item in result.source_diagnostics if str(item.reason) == _MOVEMENT_DATED)
        assert "ley-37-1992:art-75" in advisory.asserted_legal_refs
        assert sale.transaction_id[:12] in advisory.message

        _set_operation_date(objects, sale, date(2025, 12, 30))
        moved = calculate_irene(_work_unit_of(objects, revision))
        assert sale.transaction_id not in moved.revision.source_transaction_ids


def test_a_linked_invoice_of_march_refuses_in_the_first_quarter_until_the_row_is_dated(tmp_path: Path) -> None:
    """The dead end this field removes: the shortfall had no write path to clear it."""
    invoice = _issued_invoice()
    undated = _sale().model_copy(update={"invoice_id": invoice.invoice_id})
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=profile.repository).save(
            build_invoice_catalogue((invoice,))
        )
        with bundled_indexed_authority().operation() as operation, pytest.raises(AggregationValidationError) as refused:
            calculate_irene_revision(profile.repository, operation=operation, rows=(undated,))
        assert (refused.value.context or {})["reason"] == _INVOICE_SHORTFALL

    dated = _sale(operation_date=date(2026, 3, 30)).model_copy(update={"invoice_id": invoice.invoice_id})
    with isolated_runtime_profile(tmp_path=tmp_path / "dated", bucket_id=BUCKET_ID) as profile:
        InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=profile.repository).save(
            build_invoice_catalogue((invoice,))
        )
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(profile.repository, operation=operation, rows=(dated,))
        assert revision.casilla_values[_DEVENGADA] == Decimal("210.00")


def test_the_one_sided_invoice_screen_stays_silent_in_the_receiving_quarter_and_the_advisory_speaks(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        objects = profile.repository
        invoice = _issued_invoice(issued_at=date(2025, 12, 30))
        InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=objects).save(build_invoice_catalogue((invoice,)))
        sale = _sale(booked=date(2026, 1, 2)).model_copy(update={"invoice_id": invoice.invoice_id})
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(objects, operation=operation, rows=(sale,))
        reasons = _reasons(_work_unit_of(objects, revision))

        assert revision.casilla_values[_DEVENGADA] == Decimal("210.00")
        assert _INVOICE_SHORTFALL not in reasons
        assert _MOVEMENT_DATED in reasons


def test_an_advance_keeps_its_collection_date_and_its_balance_stays_out_of_the_quarter(tmp_path: Path) -> None:
    """LIVA art. 75.Dos: each row states its own devengo; the field computes neither."""
    advance = _sale("advance", base=Decimal("500.00"), booked=date(2026, 3, 20), operation_date=date(2026, 3, 20))
    balance = _sale("balance", base=Decimal("500.00"), booked=date(2026, 4, 15), operation_date=date(2026, 4, 10))
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(profile.repository, operation=operation, rows=(advance, balance))
        assert revision.casilla_values[_DEVENGADA] == Decimal("105.00")
        assert revision.source_transaction_ids == (advance.transaction_id,)


def test_the_balance_of_a_december_advance_carries_only_its_own_cuota(tmp_path: Path) -> None:
    advance = _sale("advance", base=Decimal("500.00"), booked=date(2025, 12, 20), operation_date=date(2025, 12, 20))
    balance = _sale("balance", base=Decimal("500.00"), booked=date(2026, 1, 15), operation_date=date(2026, 1, 10))
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(profile.repository, operation=operation, rows=(advance, balance))
        assert revision.casilla_values[_DEVENGADA] == Decimal("105.00")
        assert revision.source_transaction_ids == (balance.transaction_id,)


def test_money_collected_before_a_later_stated_date_is_flagged_as_a_possible_advance(tmp_path: Path) -> None:
    collected_early = _sale(booked=date(2026, 3, 20), operation_date=date(2026, 3, 28))
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(profile.repository, operation=operation, rows=(collected_early,))
        assert _AFTER_MOVEMENT in _reasons(_work_unit_of(profile.repository, revision))


def test_a_row_dated_in_the_quarter_verifies_and_exports_with_its_worked_cuota(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        objects = profile.repository
        sale = _sale(operation_date=date(2026, 3, 30))
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(objects, operation=operation, rows=(sale,))

        report = _verify(objects, revision.calculation_revision_id)
        assert report.granted_verificado_completo is True
        stored = CalculationRevisionCatalogueRepository(objects=objects).load().get(revision.calculation_revision_id)
        assert stored is not None
        assert stored.ledger_filing_evidence is not None
        (row,) = stored.ledger_filing_evidence.rows
        assert row.operation_date == "2026-03-30"
        exported = _export(revision.calculation_revision_id, tmp_path / "m303.txt")
        assert exported.startswith(b"<T3030")
        assert b"00000000000021000" in exported


def test_changing_the_operation_date_of_a_draft_row_is_drift(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        objects = profile.repository
        sale = _sale(booked=date(2026, 3, 30), operation_date=date(2026, 3, 30))
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(objects, operation=operation, rows=(sale,))
        _set_operation_date(objects, sale, date(2026, 3, 29))

        report = _verify(objects, revision.calculation_revision_id)

        assert report.granted_verificado_completo is False
        assert any("ledger_snapshot_drift" in finding.message_locale_key for finding in report.findings)


def test_detaching_evidence_drifts_where_the_field_set_before_it_stayed_quiet(tmp_path: Path) -> None:
    """Identical under V3, so a stored 42.00 cuota used to pass over zero observations."""
    purchase = iva_transaction(
        "detached",
        direction=TransactionDirection.OUTGOING,
        taxable_base=Decimal("200.00"),
        booked_date=date(2026, 2, 1),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        objects = profile.repository
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(objects, operation=operation, rows=(purchase,))
        assert revision.casilla_values[_DEDUCIBLE] == Decimal("42.00")

        with ledger_ports_for_test(bucket_id=BUCKET_ID, objects=objects) as ports:
            detached = update_manual_transaction_fields(
                bucket_id=BUCKET_ID,
                transaction_id=purchase.transaction_id,
                patch=ManualLedgerTransactionPatch(notes="nota"),
                actor="operator",
                source_command="ledger.update",
                ports=ports,
                occurred_at=_AT,
            ).transaction
        assert detached.deduction_provenance is None

        report = _verify(objects, revision.calculation_revision_id)
        assert report.granted_verificado_completo is False
        assert any("ledger_snapshot_drift" in finding.message_locale_key for finding in report.findings)
        assert row_fingerprint(detached, field_set_version=3) == row_fingerprint(purchase, field_set_version=3)


def _anchor_under_field_set(
    objects: SecureObjectRepository, revision: CalculationRevision, sale: Transaction, version: int
) -> None:
    """Re-seal the stored revision's ledger snapshot as an older fingerprint field-set version would have."""
    repository = CalculationRevisionCatalogueRepository(objects=objects)
    current = repository.load().get(revision.calculation_revision_id)
    assert current is not None
    assert current.ledger_filing_snapshot is not None
    older = current.ledger_filing_snapshot.model_copy(
        update={
            "fingerprint_field_set_version": version,
            "rows": tuple(
                row.model_copy(update={"fingerprint": row_fingerprint(sale, field_set_version=version)})
                for row in current.ledger_filing_snapshot.rows
            ),
        }
    )
    repository.save(
        upsert_calculation_revision(repository.load(), current.model_copy(update={"ledger_filing_snapshot": older}))
    )


@pytest.mark.parametrize("version", [1, 2, 3])
def test_a_revision_anchored_under_an_older_field_set_does_not_drift_spuriously(tmp_path: Path, version: int) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        objects = profile.repository
        sale = _sale(booked=date(2026, 2, 15))
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(objects, operation=operation, rows=(sale,))
        _anchor_under_field_set(objects, revision, sale, version)

        report = _verify(objects, revision.calculation_revision_id)

        assert not any("ledger_snapshot_drift" in finding.message_locale_key for finding in report.findings)


def test_an_operation_date_written_after_an_older_anchor_is_still_seen(tmp_path: Path) -> None:
    """A V3 hash cannot see the date, yet it can move the row out of the quarter."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        objects = profile.repository
        sale = _sale(booked=date(2026, 2, 15))
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(objects, operation=operation, rows=(sale,))
        _anchor_under_field_set(objects, revision, sale, 3)
        _set_operation_date(objects, sale, date(2026, 4, 2))

        report = _verify(objects, revision.calculation_revision_id)

        assert report.granted_verificado_completo is False
        assert any("ledger_snapshot_drift" in finding.message_locale_key for finding in report.findings)


def _sealed_with_invoice(objects: SecureObjectRepository) -> tuple[CalculationRevision, Invoice, VerificationReport]:
    invoice = _issued_invoice(issued_at=date(2026, 2, 15))
    InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=objects).save(build_invoice_catalogue((invoice,)))
    sale = _sale(booked=date(2026, 2, 15)).model_copy(update={"invoice_id": invoice.invoice_id})
    with bundled_indexed_authority().operation() as operation:
        revision, *_ = calculate_irene_revision(objects, operation=operation, rows=(sale,))
    report = _verify(objects, revision.calculation_revision_id)
    assert report.granted_verificado_completo is True
    return revision, invoice, report


def _refused_edit(invoice: Invoice, patch: CatalogueInvoicePatch) -> None:
    with pytest.raises(CadrumoError) as refused:
        update_catalogue_invoice(
            bucket_id=BUCKET_ID,
            invoice_id=invoice.invoice_id,
            patch=patch,
            ports=build_catalogue_lifecycle_ports(bucket_id=BUCKET_ID),
            occurred_at=_AT,
        )
    assert "sealed_invoice_refused" in str(refused.value.translated_message)


def test_a_verified_revision_refuses_the_invoice_edit_and_exports_its_figures(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        revision, invoice, _report = _sealed_with_invoice(profile.repository)
        first = _export(revision.calculation_revision_id, tmp_path / "before.txt")

        _refused_edit(invoice, CatalogueInvoicePatch(operation_date=date(2026, 4, 2)))

        stored = InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=profile.repository).load()
        assert stored.get(invoice.invoice_id) == invoice
        assert _export(revision.calculation_revision_id, tmp_path / "after.txt") == first


def test_a_filed_revision_keeps_its_history_and_refuses_edit_and_removal(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        objects = profile.repository
        revision, invoice, report = _sealed_with_invoice(objects)
        _file(revision.calculation_revision_id, report)
        repository = CalculationRevisionCatalogueRepository(objects=objects)
        filed = repository.load().get(revision.calculation_revision_id)
        assert filed is not None
        assert filed.state is CalculationRevisionState.PRESENTADO

        _refused_edit(invoice, CatalogueInvoicePatch(operation_date=date(2026, 4, 2)))
        with pytest.raises(CadrumoError) as removal:
            remove_catalogue_invoice(
                bucket_id=BUCKET_ID,
                invoice_id=invoice.invoice_id,
                ports=build_catalogue_lifecycle_ports(bucket_id=BUCKET_ID),
            )
        assert "sealed_invoice_refused" in str(removal.value.translated_message)
        assert repository.load().get(revision.calculation_revision_id) == filed


def test_a_sealed_revision_passes_an_edit_that_moves_nothing_it_read_and_a_later_collection(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        _revision, invoice, _report = _sealed_with_invoice(profile.repository)
        updated = update_catalogue_invoice(
            bucket_id=BUCKET_ID,
            invoice_id=invoice.invoice_id,
            patch=CatalogueInvoicePatch(notes="revisada", payment_status=PaymentStatus.PAID),
            ports=build_catalogue_lifecycle_ports(bucket_id=BUCKET_ID),
            occurred_at=_AT,
        )
        assert updated.invoice.payment_status is PaymentStatus.PAID
