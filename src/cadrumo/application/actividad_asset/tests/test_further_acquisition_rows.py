"""An element owns further acquisition rows: the basis check sees them and their sum, and the forms withhold them."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetValidationError
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetRevision,
    FurtherAcquisitionRow,
)
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import Transaction

from ...aggregation.tests.test_modelo_source_mesh_ledger import (
    _machine_acquisition_transaction,
    _reasons,
    register_asset,
    resolve_m100,
    resolve_m130,
)
from ..acquisition_ledger import require_acquisition_in_ledger
from ..history import ActivityAssetHistory
from ..operation_dtos import ActivityAssetRevisionSnapshot
from .ledger_support import MemoryLedger, acquisition_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_UNREGISTERED = "ledger_amortization_row_unregistered"
_WITHHELD = "register_owned_capital_acquisition"


def _further(row: Transaction, shape: AcquisitionShape = AcquisitionShape.SPLIT_PAYMENT) -> FurtherAcquisitionRow:
    return FurtherAcquisitionRow(
        shape=shape,
        lineage=AcquisitionLineageReference(
            observed_transaction_id=row.transaction_id,
            invoice_evidence_id=f"invoice-{row.transaction_id[:8]}",
            evidence_fingerprint="d" * 64,
        ),
    )


def _split_element(first: Transaction, second: Transaction, *, basis: Decimal) -> ActivityAssetRevision:
    asset = register_asset("press", transaction_id=first.transaction_id, basis=basis)
    return asset.model_copy(update={"further_acquisitions": (_further(second),)})


def _instalment(provider_id: str, *, amount: str, base: str | None, iva: str | None) -> Transaction:
    return acquisition_transaction(
        provider_id=provider_id,
        amount=Decimal(amount),
        taxable_base=None if base is None else Decimal(base),
        iva_amount=None if iva is None else Decimal(iva),
    )


def test_the_basis_check_adds_the_instalments_together() -> None:
    # 1,210 + 1,210 paid, of which 1,000 + 1,000 base; a 2,000 price fits only the two together.
    first = _instalment("first", amount="1210.00", base="1000.00", iva="210.00")
    second = _instalment("second", amount="1210.00", base="1000.00", iva="210.00")
    asset = _split_element(first, second, basis=Decimal("2000.00"))

    assert require_acquisition_in_ledger(asset, MemoryLedger(first, second)) == first


def test_a_basis_above_all_the_rows_is_refused() -> None:
    first = _instalment("first", amount="1210.00", base="1000.00", iva="210.00")
    second = _instalment("second", amount="1210.00", base="1000.00", iva="210.00")
    asset = _split_element(first, second, basis=Decimal("2420.01"))

    with pytest.raises(ActividadAssetValidationError, match="acquisition_cost_exceeds_payment"):
        require_acquisition_in_ledger(asset, MemoryLedger(first, second))


def test_a_price_above_the_declared_bases_is_refused() -> None:
    first = _instalment("first", amount="1210.00", base="1000.00", iva="210.00")
    second = _instalment("second", amount="1210.00", base="1000.00", iva="210.00")
    asset = _split_element(first, second, basis=Decimal("2000.01"))

    with pytest.raises(ActividadAssetValidationError, match="acquisition_price_exceeds_base"):
        require_acquisition_in_ledger(asset, MemoryLedger(first, second))


def test_a_row_that_states_no_base_leaves_the_base_unbounded_but_not_the_payment() -> None:
    first = _instalment("first", amount="1210.00", base="1000.00", iva="210.00")
    second = _instalment("second", amount="1210.00", base=None, iva=None)
    asset = _split_element(first, second, basis=Decimal("2000.01"))

    assert require_acquisition_in_ledger(asset, MemoryLedger(first, second)) == first


@pytest.mark.parametrize("kind", ["missing", "not_payment"])
def test_a_further_row_the_ledger_does_not_bear_out_is_refused(kind: str) -> None:
    first = _instalment("first", amount="1210.00", base="1000.00", iva="210.00")
    second = acquisition_transaction(
        provider_id="second",
        amount=Decimal("1210.00"),
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
        direction=TransactionDirection.INCOMING if kind == "not_payment" else TransactionDirection.OUTGOING,
    )
    asset = _split_element(first, second, basis=Decimal("1000.00"))
    ledger = MemoryLedger(first) if kind == "missing" else MemoryLedger(first, second)

    with pytest.raises(ActividadAssetValidationError, match="acquisition_transaction"):
        require_acquisition_in_ledger(asset, ledger)


def test_a_further_row_cannot_repeat_an_owned_row() -> None:
    row = acquisition_transaction()
    asset = register_asset("press", transaction_id=row.transaction_id)
    facts = {name: getattr(asset, name) for name in type(asset).model_fields}
    facts["further_acquisitions"] = (_further(row),)

    with pytest.raises(ValueError, match="acquisition_row_named_twice"):
        ActivityAssetRevision(**facts)


def test_a_further_row_is_only_an_instalment_or_a_cost() -> None:
    row = acquisition_transaction()

    with pytest.raises(ValueError, match="split payment or an ancillary cost"):
        _further(row, AcquisitionShape.PRIMARY_PURCHASE)


def test_an_element_with_no_further_row_keeps_its_identity_and_one_with_a_row_gains_one() -> None:
    first = acquisition_transaction(provider_id="first")
    second = acquisition_transaction(provider_id="second")
    plain = register_asset("press", transaction_id=first.transaction_id)

    assert plain.model_copy(update={"further_acquisitions": ()}).revision_id == plain.revision_id
    assert _split_element(first, second, basis=Decimal("12000.00")).revision_id != plain.revision_id


def test_further_rows_cross_the_operation_boundary_unchanged() -> None:
    first = acquisition_transaction(provider_id="first")
    second = acquisition_transaction(provider_id="second")
    asset = _split_element(first, second, basis=Decimal("12000.00"))

    restored = ActivityAssetRevisionSnapshot.from_domain(asset).to_domain()

    assert restored.further_acquisitions == asset.further_acquisitions
    assert restored.revision_id == asset.revision_id


def test_a_second_instalment_in_an_amortizable_category_is_withheld_and_blocks_neither_return() -> None:
    first = _machine_acquisition_transaction("hardware_amortizable", provider_id="first-instalment")
    second = _machine_acquisition_transaction("hardware_amortizable", provider_id="second-instalment")
    asset = register_asset("press", transaction_id=first.transaction_id, basis=Decimal("1000.00"))
    history = ActivityAssetHistory(
        revisions=(asset.model_copy(update={"further_acquisitions": (_further(second),)}),),
    )

    for resolution in (resolve_m100(history, rows=(first, second)), resolve_m130(history, "2T", rows=(first, second))):
        assert _UNREGISTERED not in _reasons(resolution)
        assert _reasons(resolution).count(_WITHHELD) == 2


def test_the_same_instalment_with_no_owner_is_still_named() -> None:
    first = _machine_acquisition_transaction("hardware_amortizable", provider_id="first-instalment")
    second = _machine_acquisition_transaction("hardware_amortizable", provider_id="second-instalment")
    asset = register_asset("press", transaction_id=first.transaction_id, basis=Decimal("1000.00"))

    resolution = resolve_m100(ActivityAssetHistory(revisions=(asset,)), rows=(first, second))

    assert _reasons(resolution).count(_UNREGISTERED) == 1
