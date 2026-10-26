"""A declared bien de inversión is proven once per filing year, from any period of it.

The bienes-inversión register pairs each good with exactly one acquisition row
through ``acquisition_ledger_id``, and that pairing is a fact of the good's
acquisition year. A quarterly Modelo 303 decrypts only its own quarter's rows,
so the quarters that do not hold the acquisition prove the pairing from the one
row the register names, read by id. These tests persist real rows in the
encrypted transaction catalogue and read them back through the
repository-backed aggregation the calculation uses.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.aggregation.iva_ledger import (
    IvaLedgerAggregation,
    aggregate_iva_ledger_observations_from_repositories,
)
from .....application.aggregation.tests.ledger_transaction_support import iva_transaction
from .....core.iva_deduction_fact import IvaDeductionFactKind
from .....core.period import Period
from .....domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    BienInversionIvaRecord,
    BienInversionValidationError,
    validate_investment_asset_reciprocity,
)
from .....domain.bienes_inversion.vocabulary import BienInversionKind
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from .....domain.transactions.models import Transaction, TransactionCatalogue
from ...storage.sql.secure_objects import SecureObjectRepository
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..prorrata_register import ProrrataRegisterRepository
from ..transactions import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "5e1d0c2a-7b3f-4a9e-8c61-2f4d9b0a7e35"
_YEAR = 2025
_ASSET_ID = "BI-TORNO-CNC"
_QUARTERS = ("1T", "2T", "3T", "4T")


@pytest.fixture
def ledger_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _sale(month: int, *, year: int = _YEAR) -> Transaction:
    return iva_transaction(
        f"venta-{year}-{month:02d}",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("12100.00"),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        booked_date=date(year, month, 14),
    )


def _investment(
    booked: date,
    *,
    asset_id: str = _ASSET_ID,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    purchase = iva_transaction(
        f"torno-{booked.isoformat()}",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("4840.00"),
        taxable_base=Decimal("4000.00"),
        iva_amount=Decimal("840.00"),
        booked_date=booked,
    )
    payload = purchase.model_dump(mode="python")
    payload.update(
        {
            "deduction_fact_kind": IvaDeductionFactKind.from_registry("domestic_investment"),
            "investment_asset_id": asset_id,
            "business_classification": business_classification,
            "lifecycle_state": lifecycle_state,
        }
    )
    return Transaction.model_validate(payload)


def _register(acquisition_ledger_id: str, *, acquisition_year: int = _YEAR) -> BienesInversionIvaRegister:
    return BienesInversionIvaRegister(
        records=(
            BienInversionIvaRecord(
                identifier=_ASSET_ID,
                description="Torno CNC",
                acquisition_year=acquisition_year,
                cuota_soportada=Decimal("840.00"),
                prorrata_inicial_pct=Decimal("100"),
                kind=BienInversionKind.from_registry("mueble"),
                acquisition_ledger_id=acquisition_ledger_id,
            ),
        )
    )


def _persist(objects: SecureObjectRepository, *transactions: Transaction) -> None:
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).save(
        TransactionCatalogue.from_transactions(transactions),
    )


def _aggregate(
    objects: SecureObjectRepository,
    register: BienesInversionIvaRegister,
    *,
    year: int = _YEAR,
    code: str,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregation:
    return aggregate_iva_ledger_observations_from_repositories(
        bucket_id=_BUCKET_ID,
        period=Period.from_year_and_code(year, code),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
        investment_asset_register=register,
        investment_asset_profile_id=_BUCKET_ID,
        operation=operation,
    )


def _investment_ledger_ids(aggregation: IvaLedgerAggregation) -> set[str]:
    return {
        observation.ledger_id for observation in aggregation.observations if observation.investment_asset_id is not None
    }


def test_every_period_of_the_year_proves_the_acquisition_it_does_not_hold(
    ledger_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The 2T good aggregates in 2T and the year, and no other quarter refuses over it."""
    purchase = _investment(date(_YEAR, 5, 20))
    _persist(ledger_objects, _sale(2), _sale(5), purchase, _sale(8), _sale(11))
    register = _register(purchase.transaction_id)

    by_period = {
        code: _aggregate(ledger_objects, register, code=code, operation=operation) for code in (*_QUARTERS, "0A")
    }

    for code, aggregation in by_period.items():
        assert aggregation.issues == (), code
    assert _investment_ledger_ids(by_period["2T"]) == {purchase.transaction_id}
    assert _investment_ledger_ids(by_period["0A"]) == {purchase.transaction_id}
    for code in ("1T", "3T", "4T"):
        assert _investment_ledger_ids(by_period[code]) == set(), code
        assert len(by_period[code].observations) == 1, code


def test_a_quarter_proven_from_its_own_rows_alone_would_refuse_the_good(
    ledger_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Detector: the quarter's own observations are not enough evidence for the year's contract.

    This is the input the reciprocity check used to receive, and it refuses a
    quarter the good has nothing to do with. The same quarter passes above only
    because the row the register names is read in beside it.
    """
    purchase = _investment(date(_YEAR, 5, 20))
    _persist(ledger_objects, _sale(2), purchase)
    register = _register(purchase.transaction_id)
    first_quarter = _aggregate(ledger_objects, register, code="1T", operation=operation)

    with pytest.raises(BienInversionValidationError, match=f"no reciprocal ledger observation: {_ASSET_ID}"):
        validate_investment_asset_reciprocity(
            observations=first_quarter.observations,
            register=register,
            ledger_profile_id=_BUCKET_ID,
            asset_profile_id=_BUCKET_ID,
            filing_year=_YEAR,
        )


@pytest.mark.parametrize("code", ["1T", "2T", "4T", "0A"])
def test_a_record_naming_no_ledger_row_refuses_every_period_of_its_year(
    ledger_objects: SecureObjectRepository,
    code: str,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A register record the ledger never bought is refused wherever its year is filed."""
    _persist(ledger_objects, _sale(2), _sale(5), _sale(11))

    with pytest.raises(BienInversionValidationError, match=f"no reciprocal ledger observation: {_ASSET_ID}"):
        _aggregate(ledger_objects, _register("f" * 64), code=code, operation=operation)


def test_an_investment_row_without_its_record_still_refuses_its_quarter(
    ledger_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The quarter holding an undeclared bien de inversión refuses; the others never read it."""
    _persist(ledger_objects, _sale(2), _investment(date(_YEAR, 5, 20)))

    with pytest.raises(BienInversionValidationError, match="no reciprocal bienes-inversion record"):
        _aggregate(ledger_objects, BienesInversionIvaRegister(), code="2T", operation=operation)
    assert _aggregate(ledger_objects, BienesInversionIvaRegister(), code="1T", operation=operation).issues == ()


def test_a_record_whose_row_is_dated_in_another_year_refuses_its_declared_year(
    ledger_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A row found outside the quarter is still held to the year the record declares."""
    purchase = _investment(date(_YEAR - 1, 11, 20))
    _persist(ledger_objects, _sale(2), purchase)

    with pytest.raises(BienInversionValidationError, match="share the filing year"):
        _aggregate(ledger_objects, _register(purchase.transaction_id), code="1T", operation=operation)


def test_a_record_whose_row_claims_another_asset_refuses(
    ledger_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The out-of-quarter row must name the very good whose record names it."""
    purchase = _investment(date(_YEAR, 5, 20), asset_id="BI-OTRO-BIEN")
    _persist(ledger_objects, _sale(2), purchase)

    with pytest.raises(BienInversionValidationError, match="no reciprocal bienes-inversion record"):
        _aggregate(ledger_objects, _register(purchase.transaction_id), code="1T", operation=operation)


def test_a_record_naming_an_archived_row_refuses(
    ledger_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A row the ledger no longer holds live proves no acquisition, in or out of its quarter."""
    purchase = _investment(date(_YEAR, 5, 20), lifecycle_state=TransactionLifecycleState.ARCHIVED)
    _persist(ledger_objects, _sale(2), purchase)

    with pytest.raises(BienInversionValidationError, match=f"no reciprocal ledger observation: {_ASSET_ID}"):
        _aggregate(ledger_objects, _register(purchase.transaction_id), code="1T", operation=operation)


def test_a_row_inside_the_quarter_is_proven_only_by_that_quarter_classifying_it(
    ledger_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A row its own quarter will not observe cannot be vouched for from the row itself.

    A personal row yields no IVA observation, so the quarter that holds it has
    no reciprocal acquisition and refuses, even though the stored row names the
    good exactly.
    """
    purchase = _investment(date(_YEAR, 5, 20), business_classification=BusinessClassification.PERSONAL)
    _persist(ledger_objects, _sale(5), purchase)

    with pytest.raises(BienInversionValidationError, match=f"no reciprocal ledger observation: {_ASSET_ID}"):
        _aggregate(ledger_objects, _register(purchase.transaction_id), code="2T", operation=operation)


def test_a_good_acquired_in_an_earlier_year_is_not_proven_again_later(
    ledger_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Every period of a later year aggregates without asking for the earlier acquisition."""
    purchase = _investment(date(_YEAR - 1, 5, 20))
    _persist(ledger_objects, purchase, *(_sale(month) for month in (2, 5, 8, 11)))
    register = _register(purchase.transaction_id, acquisition_year=_YEAR - 1)

    for code in (*_QUARTERS, "0A"):
        aggregation = _aggregate(ledger_objects, register, code=code, operation=operation)
        assert aggregation.issues == (), code
        assert _investment_ledger_ids(aggregation) == set(), code
