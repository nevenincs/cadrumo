"""Repository-backed Renta IVA-regime and prorrata-register contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....domain.categories.spending_category import SpendingCategory
from ....domain.prorrata_register.register import ProrrataRegisterEntry
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_two_bucket_runtime
from .. import RentaLedgerExpenseAggregation, aggregate_renta_ledger_expenses_from_repositories
from ._secure_objects_fixtures import SECURE_OBJECTS_BUCKET_ID
from .renta_income_aggregation_support import _period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = SECURE_OBJECTS_BUCKET_ID
_ANNUAL_2025 = _period(2025, "0A")
_M100_ASESORIA_CASILLA = "0199"


def _raw_transaction(
    provider_id: str,
    *,
    amount: Decimal,
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2025, 4, 5),
        value_date=date(2025, 4, 5),
        amount=amount,
        currency="EUR",
        counterparty="Proveedor SL",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2025, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _transaction(
    provider_id: str,
    *,
    amount: Decimal,
    category: SpendingCategory,
    taxable_base: Decimal | None = None,
    iva_amount: Decimal | None = None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, amount=amount),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": category.value,
            "taxable_base": taxable_base,
            "iva_amount": iva_amount,
            "classified_at": datetime(2025, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _profile_with_iva_regime(*iva_facts: UserProfileFact) -> UserProfileRecord:
    """Build a user-profile record from explicitly supplied IVA facts."""
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="33333333-3333-4333-8333-333333333333",
        facts=(UserProfileFact(path="identity.tax_id", value="X1234567L"), *iva_facts),
    )


def test_repository_wrapper_exento_iva_regime_joins_the_full_iva_to_deductible_cost(
    secure_objects: SecureObjectRepository,
) -> None:
    """A wholly ``EXENTO`` taxpayer's non-deductible input IVA joins the IRPF cost, end to end.

    Same medico radiologo figures the domain-level unit test
    (``domain.renta.tests.test_ledger_expenses.test_wholly_exempt_activity_joins_the_full_iva_amount_to_the_deductible_cost``)
    grounds against the AEAT Manual practico de Renta 2024, Parte 1, Capitulo 7:
    base 8.000,00 EUR, IVA soportado 1.600,00 EUR, gross 9.600,00 EUR. LIVA
    art. 20.Uno.3.º gives the activity NO right to deduct any of its input IVA
    (art. 94.Uno a contrario), so the whole cuota becomes IRPF-deductible cost.
    Drives the real repository path -- a transaction carrying its own
    taxable_base/iva_amount and a profile declaring ``iva.regime = EXENTO`` --
    never a hand-built :class:`RentaDeductibilityContext`.
    """
    row = _transaction(
        "row-exento",
        amount=Decimal("9600.00"),
        category=SpendingCategory.MATERIAL_OFICINA,
        taxable_base=Decimal("8000.00"),
        iva_amount=Decimal("1600.00"),
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )

    def _run(profile_record: UserProfileRecord | None) -> RentaLedgerExpenseAggregation:
        return aggregate_renta_ledger_expenses_from_repositories(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            period=_ANNUAL_2025,
            transaction_repository=TransactionCatalogueRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
            invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
            profile_year=2025,
            profile_record=profile_record,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
        )

    exento = _run(
        _profile_with_iva_regime(
            UserProfileFact(path="iva.regime", value="EXENTO"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        ),
    )
    assert exento.issues == ()
    assert exento.observations[0].deductible_amount == Decimal("9600.00")
    assert exento.observations[0].non_deductible_amount == Decimal("0.00")
    assert exento.casilla_values[_M100_ASESORIA_CASILLA] == Decimal("9600.00")

    general = _run(_profile_with_iva_regime())
    assert general.issues == ()
    assert general.observations[0].deductible_amount == Decimal("8000.00")


def test_repository_wrapper_general_prorrata_register_joins_the_non_deductible_share(
    secure_objects: SecureObjectRepository,
) -> None:
    """A GENERAL-prorrata register entry joins the non-recoverable IVA share, end to end."""
    row = _transaction(
        "row-prorrata",
        amount=Decimal("1210.00"),
        category=SpendingCategory.MATERIAL_OFICINA,
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )
    ProrrataRegisterRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).upsert_entry(
        ProrrataRegisterEntry(
            ejercicio=2025,
            regime=ProrrataRegisterRegime.GENERAL,
            especial_transition=None,
            provisional_percentage=Decimal("70"),
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        ),
    )

    result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
        profile_year=2025,
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    assert result.issues == ()
    assert result.observations[0].deductible_amount == Decimal("1063.00")
    assert result.observations[0].non_deductible_amount == Decimal("147.00")


def test_repository_wrapper_ninguna_prorrata_regime_is_byte_identical_to_absent_entry(
    secure_objects: SecureObjectRepository,
) -> None:
    """A ``NINGUNA`` regime entry (full deduction rights) changes nothing."""
    row = _transaction(
        "row-ninguna",
        amount=Decimal("1210.00"),
        category=SpendingCategory.MATERIAL_OFICINA,
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )
    ProrrataRegisterRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).upsert_entry(
        ProrrataRegisterEntry(ejercicio=2025, regime=ProrrataRegisterRegime.NINGUNA, especial_transition=None),
    )

    result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
        profile_year=2025,
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    assert result.issues == ()
    assert result.observations[0].deductible_amount == Decimal("1000.00")
    assert result.observations[0].non_deductible_amount == Decimal("210.00")


def test_repository_wrapper_uses_the_explicit_secondary_prorrata_store_while_primary_is_active(
    tmp_path: Path,
) -> None:
    """The M100 IVA ratio follows the injected secondary register, never the active primary bucket."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        row = _transaction(
            "secondary-prorrata",
            amount=Decimal("1210.00"),
            category=SpendingCategory.MATERIAL_OFICINA,
            taxable_base=Decimal("1000.00"),
            iva_amount=Decimal("210.00"),
        )
        primary_prorrata_repository = ProrrataRegisterRepository(
            bucket_id=runtime.primary.bucket_id,
            objects=runtime.primary.repository,
        )
        with runtime.switch_to_secondary():
            transaction_repository = TransactionCatalogueRepository(
                bucket_id=runtime.secondary.bucket_id,
                objects=runtime.secondary.repository,
            )
            invoice_repository = InvoiceCatalogueRepository(
                bucket_id=runtime.secondary.bucket_id,
                objects=runtime.secondary.repository,
            )
            secondary_prorrata_repository = ProrrataRegisterRepository(
                bucket_id=runtime.secondary.bucket_id,
                objects=runtime.secondary.repository,
            )
            transaction_repository.save(TransactionCatalogue.from_transactions((row,)))
            secondary_prorrata_repository.upsert_entry(
                ProrrataRegisterEntry(
                    ejercicio=2025,
                    regime=ProrrataRegisterRegime.GENERAL,
                    especial_transition=None,
                    provisional_percentage=Decimal("80"),
                    provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                )
            )

            result = aggregate_renta_ledger_expenses_from_repositories(
                bucket_id=runtime.secondary.bucket_id,
                period=_ANNUAL_2025,
                transaction_repository=transaction_repository,
                invoice_repository=invoice_repository,
                profile_year=2025,
                profile_record=_profile_with_iva_regime(),
                prorrata_register_repository=secondary_prorrata_repository,
            )

        assert primary_prorrata_repository.load().entries == ()

    assert result.issues == ()
    assert result.observations[0].deductible_amount == Decimal("1042.00")
    assert result.observations[0].non_deductible_amount == Decimal("168.00")


def test_repository_wrapper_refuses_an_implicit_prorrata_repository() -> None:
    """No public Renta repository path can silently recreate a register store."""
    with pytest.raises(TypeError, match="prorrata_register_repository"):
        cast(Any, aggregate_renta_ledger_expenses_from_repositories)(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            period=_ANNUAL_2025,
            transaction_repository=None,
            invoice_repository=None,
        )
