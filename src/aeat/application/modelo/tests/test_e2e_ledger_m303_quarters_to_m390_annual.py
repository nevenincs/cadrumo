"""E2E vertical: real ledger → M303 1T-4T (computed) → M390 annual reconciliation.

The IVA counterpart of ``test_e2e_ledger_m130_quarters_to_m100_annual``. Two
segments are each covered in isolation today:

* ledger IVA transactions → M303 computed cuota
  (``test_bucket_aggregation_flow``, a single quarter).
* M303 quarter totals → M390 annual reconciliation fold-in
  (``test_modelo_390_303_fold_in_live``, but with **injected** M303 observations,
  not values the M303 calc actually computed).

Neither joins the two: no test drives *real persisted IVA ledger transactions*
through the live bucket-aggregation calculate action for four quarters, files
each through the production observation-persistence path, and proves the annual
M390 reconciliation casillas fold in the **engine-computed** quarterly IVA totals.
That full IVA vertical — the autónomo's real yearly IVA cadence — is what this
test verifies.

Real-behaviour, real-adapter: real encrypted-SQLite secure store via
:class:`SecureObjectRepository` + ``isolated_runtime_profile``, the real registry
authority, the real calculation engine, the real ``ledger_iva_aggregation``
resolver, and the real ``relation_prefill`` fold-in resolver. No mocks, stubs,
skips, or xfail.

Non-tautology argument: each quarter's IVA totals are **computed by the engine**
from the ledger transactions' ``iva_amount`` through the M303 formula chain
(repercutido/soportado casillas → cuota-devengada-total / cuota-deducible-total →
resultado-regimen-general); the test never hand-recomputes a registry formula.
The load-bearing assertions are *transport / wiring* invariants: each quarter's
computed cuota-devengada-total equals the persisted incoming IVA the operator
never re-keyed, and the annual M390 reconciliation casillas equal the **sum of
the four engine-computed quarterly totals** (distinct per quarter, so a coincidental
or off-by-one-quarter sum cannot satisfy them).

LIVA art. 88/92 (repercusión / deducción) and the M390 orden ground the
reconciliation; this test asserts the *wiring*, leaving rate currency to the
registry grounding gate.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._calculation_revision import CalculationRevision
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import IvaWalletDecisionRepository
from ...calculations._observations_repository import CalculationObservationRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    calculate_modelo_revision_from_bucket_aggregation,
    create_work_unit,
    persist_filed_revision_observation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "bucket-e2e-ledger-303-390"
_YEAR = 2025
_TAX_ID = "12345678Z"
_T0 = datetime(2025, 1, 10, 10, 0, tzinfo=UTC)
_FILE_AT = datetime(2025, 4, 10, 12, 0, tzinfo=UTC)

_M303_REVISION = "2023-y-siguientes"
_QUARTER_ORDER = ("1T", "2T", "3T", "4T")
_IVA_RATE = Decimal("0.21")

# M303 computed-output casillas the M390 reconciliation relations fold.
_DEVENGADA_TOTAL = "iva.cuota-devengada-total"
_DEDUCIBLE_TOTAL = "iva.cuota-deducible-total"
_RESULTADO = "iva.resultado-regimen-general"

# M390 annual reconciliation casillas (folded from the four M303 quarters).
_M390_DEVENGADA = "iva.anual.reconciliacion.devengada-303"
_M390_DEDUCIBLE = "iva.anual.reconciliacion.deducible-303"
_M390_RESULTADO = "iva.anual.reconciliacion.resultado-303"

# One coherent year of IVA-bearing operations, one issued (INCOMING → IVA
# repercutido / devengada) and one received (OUTGOING → IVA soportado /
# deducible) invoice per quarter. DISTINCT per-quarter taxable bases (all clean
# 21% multiples) make the annual fold unmistakable.
_QUARTER_BASES: dict[str, tuple[Decimal, Decimal]] = {
    # period: (issued taxable_base, received taxable_base)
    "1T": (Decimal("1000.00"), Decimal("400.00")),  # devengada 210.00, deducible 84.00
    "2T": (Decimal("1200.00"), Decimal("500.00")),  # devengada 252.00, deducible 105.00
    "3T": (Decimal("800.00"), Decimal("300.00")),  # devengada 168.00, deducible 63.00
    "4T": (Decimal("1500.00"), Decimal("600.00")),  # devengada 315.00, deducible 126.00
}
_QUARTER_MONTH: dict[str, int] = {"1T": 2, "2T": 5, "3T": 8, "4T": 11}


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
    period: str,
) -> Transaction:
    booked = date(_YEAR, _QUARTER_MONTH[period], 10)
    iva_amount = (taxable_base * _IVA_RATE).quantize(Decimal("0.01"))
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                transaction_id=provider_id,
                booked_date=booked,
                value_date=booked,
                amount=(taxable_base + iva_amount),
                currency="EUR",
                counterparty="Cliente o proveedor",
                description=f"factura IVA {provider_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="c" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=_T0,
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "ledger_transaction"},
            ),
            "direction": direction,
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "test_iva_operation",
            "taxable_base": taxable_base,
            "iva_rate": _IVA_RATE,
            "iva_amount": iva_amount,
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _persist_year_of_invoices(secure_objects: SecureObjectRepository) -> dict[str, dict[str, Decimal]]:
    """Persist all four quarters' issued + received IVA operations once upfront.

    Each M303 quarter's bucket aggregation selects only its own period's
    operations by date (IVA is declared per period, not cumulative-YTD), so the
    whole year is persisted once and the per-quarter window does the slicing.

    Returns, per period, the IVA amounts actually STORED on the persisted
    transactions (``devengada`` = issued invoice's ``iva_amount``, ``deducible``
    = received invoice's ``iva_amount``). The caller asserts the engine-computed
    M303 totals against these stored field values — proving the aggregator
    transports the stored ``iva_amount`` rather than re-deriving base×rate, and
    avoiding a shared-literal between the seed and the expectation.
    """
    transactions: list[Transaction] = []
    stored: dict[str, dict[str, Decimal]] = {}
    for period, (issued_base, received_base) in _QUARTER_BASES.items():
        issued = _iva_transaction(
            f"sale-{period}", direction=TransactionDirection.INCOMING, taxable_base=issued_base, period=period
        )
        received = _iva_transaction(
            f"purchase-{period}",
            direction=TransactionDirection.OUTGOING,
            taxable_base=received_base,
            period=period,
        )
        transactions.extend((issued, received))
        assert issued.iva_amount is not None
        assert received.iva_amount is not None
        stored[period] = {"devengada": issued.iva_amount, "deducible": received.iva_amount}
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions(tuple(transactions)))
    return stored


def _wallet_decision(*, period: str) -> IvaCompensationReconciliationDecision:
    """A neutral (zero, non-blocking) IVA-wallet decision for the quarter."""
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=_TAX_ID,
        target_year=_YEAR,
        target_period=Period.from_year_and_code(_YEAR, period),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0.00"),
        wallet_amount=Decimal("0.00"),
        local_recurrence_amount=Decimal("0.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason="e2e IVA vertical fixture",
        wallet_captured_at=_FILE_AT,
        decided_at=_FILE_AT,
    )


def _store_profile(secure_objects: SecureObjectRepository) -> None:
    """Seed the taxpayer profile the M303 IVA-wallet gate reads (tax_id)."""
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            display_name="Test runtime profile",
            facts=(UserProfileFact(path="identity.tax_id", value=_TAX_ID),),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _calculate_and_file_m303_quarter(secure_objects: SecureObjectRepository, *, period: str) -> CalculationRevision:
    """Run the live bucket-aggregation M303 calc for one quarter and file it."""
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision_id=_M303_REVISION,
        repository=wu_repo,
        clock=_T0,
    )
    decision = _wallet_decision(period=period)
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(decision)
    revision = calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        actor="system",
        binding_values={
            # No prior-period compensación carry in this scenario (each quarter
            # is net-positive); autoconsumo del promotor is nil for this filer.
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        iva_compensation_decision=decision,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_FILE_AT,
    )
    persist_filed_revision_observation(
        revision=revision,
        work_unit=work_unit,
        repository=CalculationObservationRepository(objects=secure_objects),
        captured_at=_FILE_AT,
    )
    return revision


def _calculate_m390_annual(secure_objects: SecureObjectRepository) -> CalculationRevision:
    """Run the live M390/annual calc, leaving the 303-reconciliation relations to fold."""
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot("390", filing_year=_YEAR, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="390",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        binding_values={},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_FILE_AT,
    )


def test_ledger_drives_m303_quarters_and_folds_into_m390_annual(
    secure_objects: SecureObjectRepository,
) -> None:
    """The full yearly IVA cadence: persisted ledger → 4×M303 → M390 reconciliation."""
    _store_profile(secure_objects)
    stored = _persist_year_of_invoices(secure_objects)

    computed: dict[str, dict[str, Decimal]] = {}
    for period in _QUARTER_ORDER:
        revision = _calculate_and_file_m303_quarter(secure_objects, period=period)

        # Transport invariant #1: the computed cuota totals equal the IVA amounts
        # STORED on the persisted invoices (the aggregator sums the stored
        # iva_amount field — it does not re-derive base×rate, confirmed in
        # application/aggregation/_iva_ledger.py). Asserting against the stored
        # field, not a fresh base*rate, keeps the seed and the expectation from
        # sharing a literal.
        assert Decimal(revision.casilla_values[_DEVENGADA_TOTAL]) == stored[period]["devengada"], (
            f"{period}: cuota-devengada-total must equal the stored issued IVA {stored[period]['devengada']}; "
            f"got {revision.casilla_values.get(_DEVENGADA_TOTAL)}"
        )
        assert Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]) == stored[period]["deducible"], (
            f"{period}: cuota-deducible-total must equal the stored received IVA {stored[period]['deducible']}; "
            f"got {revision.casilla_values.get(_DEDUCIBLE_TOTAL)}"
        )
        computed[period] = {
            _DEVENGADA_TOTAL: Decimal(revision.casilla_values[_DEVENGADA_TOTAL]),
            _DEDUCIBLE_TOTAL: Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]),
            _RESULTADO: Decimal(revision.casilla_values[_RESULTADO]),
        }

    # The four computed totals are distinct on every folded axis → a coincidental
    # or off-by-one-quarter fold cannot satisfy the annual assertions below.
    for axis in (_DEVENGADA_TOTAL, _DEDUCIBLE_TOTAL, _RESULTADO):
        values = [computed[p][axis] for p in _QUARTER_ORDER]
        assert len(set(values)) == 4, f"quarterly {axis} must be distinct: {values}"

    annual = _calculate_m390_annual(secure_objects)
    casillas = annual.casilla_values

    # Transport invariant #2: M390 annual reconciliation folds the SUM of the four
    # engine-computed M303 quarterly totals.
    for m390_casilla, m303_output in (
        (_M390_DEVENGADA, _DEVENGADA_TOTAL),
        (_M390_DEDUCIBLE, _DEDUCIBLE_TOTAL),
        (_M390_RESULTADO, _RESULTADO),
    ):
        expected = sum((computed[p][m303_output] for p in _QUARTER_ORDER), Decimal("0"))
        assert Decimal(casillas[m390_casilla]) == expected, (
            f"M390 {m390_casilla} must fold sum(1T-4T {m303_output})={expected}; got {casillas.get(m390_casilla)}"
        )
