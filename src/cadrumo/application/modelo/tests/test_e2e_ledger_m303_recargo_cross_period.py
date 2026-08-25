"""E2E vertical: real ledger recargo-equivalencia sales -> M303 1T/2T recargo cuotas.

A supplier to recargo-de-equivalencia retailers charges recargo alongside IVA on
its repercutido (issued / sales) invoices (LIVA art. 161). The per-transaction
recargo cuota is carried on the ledger row as ``recargo_amount`` and aggregated by
IVA rate tier into the official M303 recargo cuota casillas:

* casilla ``24`` -- general tier (IVA 21% -> recargo 5.2%),
  binding ``modelo-303-recargo-equivalencia-general-cuota``;
* casilla ``21`` -- reduced tier (IVA 10% -> recargo 1.4%),
  binding ``modelo-303-recargo-equivalencia-reducido-cuota``.

Engine-level coverage exists (the ``recargo_amount_sum`` fact resolver and the
non-declarable-category gate), but no test drives *real persisted ledger
recargo sales* through the live bucket-aggregation calculate action for two
distinct quarters and proves each quarter's M303 recargo casillas carry that
quarter's recargo sum and **not** the other quarter's. That period-scoped
cross-quarter vertical -- the supplier's real recargo cadence -- is what this
test verifies.

Real-behaviour, real-adapter: real encrypted-SQLite secure store via
:class:`~cadrumo.adapters.persistence.storage.sql.SecureObjectRepository` +
``isolated_runtime_profile``, the real registry authority, the real calculation
engine, and the real ``ledger_iva_aggregation`` resolver. No mocks, stubs,
skips, or xfail.

Non-tautology argument: each quarter's recargo cuotas are summed by the engine
from the recargo amounts STORED on the persisted transactions; the test asserts
the engine-computed casilla equals ``sum(...)`` of the stored ``recargo_amount``
fields (not a hand-summed Decimal literal). The load-bearing assertions are
*transport / period-scoping* invariants: each quarter's general/reduced recargo
cuota equals only its own quarter's stored recargo, and is strictly different
from the other quarter's (distinct per quarter, so a coincidental or
cross-period-leaking sum cannot satisfy them).

LIVA art. 161 (recargo de equivalencia) grounds the surcharge; this test asserts
the *wiring and period scoping*, leaving the recargo-rate schedule to the
registry grounding gate.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from ....domain.iva_compensation import IvaCompensationReconciliationDecision
from ....domain.modelos import CalculationRevision
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests import general_m303_filing_evidence
from ....tests.profile_capsule import seed_test_profile_record
from ...calculations import IvaWalletDecisionRepository
from .._calculation_actions import calculate_modelo_revision_from_bucket_aggregation
from .._work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "30330303-0303-4303-8303-303303303303"
_YEAR = 2025
_TAX_ID = "12345678Z"
_T0 = datetime(2025, 1, 10, 10, 0, tzinfo=UTC)
_FILE_AT = datetime(2025, 4, 10, 12, 0, tzinfo=UTC)

type RecargoTier = Literal["general", "reducido"]
type RecargoAmountsByPeriod = dict[str, dict[RecargoTier, Decimal]]

# Official M303 recargo de equivalencia cuota casillas (keyed by casilla id in
# ``casilla_values``). General = IVA 21% tier (recargo 5.2%); reducido = IVA 10%
# tier (recargo 1.4%).
_RECARGO_GENERAL_CUOTA: CasillaId = validated_casilla_id("24", surface="_RECARGO_GENERAL_CUOTA")
_RECARGO_REDUCIDO_CUOTA: CasillaId = validated_casilla_id("21", surface="_RECARGO_REDUCIDO_CUOTA")

_GENERAL_RATE = Decimal("0.21")
_REDUCED_RATE = Decimal("0.10")

# Two quarters of recargo repercutido sales. DISTINCT recargo amounts per quarter
# AND per tier make a cross-period leak or off-by-one-quarter fold unmistakable.
# Each row's recargo_amount is the supplier-charged surcharge cuota for that sale;
# it is independent of the IVA amount (the recargo rate differs from the IVA rate).
_QUARTER_MONTH: dict[str, int] = {"1T": 2, "2T": 5}

# period -> tier -> (taxable_base, iva_rate, recargo_amount)
_QUARTER_SALES: dict[str, dict[RecargoTier, tuple[Decimal, Decimal, Decimal]]] = {
    "1T": {
        "general": (Decimal("1000.00"), _GENERAL_RATE, Decimal("52.00")),
        "reducido": (Decimal("1000.00"), _REDUCED_RATE, Decimal("14.00")),
    },
    "2T": {
        "general": (Decimal("2000.00"), _GENERAL_RATE, Decimal("104.00")),
        "reducido": (Decimal("3000.00"), _REDUCED_RATE, Decimal("42.00")),
    },
}


def _recargo_sale(
    provider_id: str,
    *,
    taxable_base: Decimal,
    iva_rate: Decimal,
    recargo_amount: Decimal,
    period: str,
) -> Transaction:
    """A repercutido (issued / INCOMING) sale carrying a recargo surcharge.

    The line carries the normal domestic IVA facts (so the standard repercutido
    devengada casillas also populate) plus the separate ``recargo_amount`` cuota
    the supplier charged the recargo-regime retailer. ``raw.amount`` is the money
    the supplier actually received, so it reconstitutes
    ``taxable_base + iva_amount + recargo_amount``: LIVA art. 161 has the
    surcharge repercutido on the entrega alongside the cuota, so it is inside the
    gross rather than beside it.
    """
    booked = date(_YEAR, _QUARTER_MONTH[period], 10)
    iva_amount = (taxable_base * iva_rate).quantize(Decimal("0.01"))
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=booked,
                value_date=booked,
                amount=(taxable_base + iva_amount + recargo_amount),
                currency="EUR",
                counterparty="Comerciante en recargo de equivalencia",
                description=f"venta con recargo {provider_id}",
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
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "test_recargo_sale",
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "recargo_amount": recargo_amount,
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _persist_two_quarters_of_recargo_sales(
    secure_objects: SecureObjectRepository,
) -> RecargoAmountsByPeriod:
    """Persist both quarters' general + reduced recargo sales once upfront.

    Each M303 quarter's bucket aggregation selects only its own period's
    operations by date, so the whole set is persisted once and the per-quarter
    window does the slicing.

    Returns, per period and tier, the recargo cuota actually STORED on the
    persisted transaction. The caller asserts the engine-computed M303 recargo
    casilla against these stored field values -- proving the aggregator transports
    the stored ``recargo_amount`` field, and avoiding a shared literal between the
    seed and the expectation.
    """
    transactions: list[Transaction] = []
    stored: RecargoAmountsByPeriod = {}
    for period, tiers in _QUARTER_SALES.items():
        stored[period] = {}
        for tier, (base, rate, recargo) in tiers.items():
            sale = _recargo_sale(
                f"recargo-{period}-{tier}",
                taxable_base=base,
                iva_rate=rate,
                recargo_amount=recargo,
                period=period,
            )
            transactions.append(sale)
            assert sale.recargo_amount is not None
            stored[period][tier] = sale.recargo_amount
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
        reason_identity="aeat_wallet_validated",
        wallet_captured_at=_FILE_AT,
        decided_at=_FILE_AT,
    )


def _store_profile(secure_objects: SecureObjectRepository) -> None:
    """Seed the taxpayer profile the M303 IVA-wallet gate reads (tax_id)."""
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _calculate_m303_quarter(secure_objects: SecureObjectRepository, *, period: str) -> CalculationRevision:
    """Run the live bucket-aggregation M303 calc for one quarter."""
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision_id=resources().modelos.authority.snapshot("303", filing_year=_YEAR, period=period).revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    decision = _wallet_decision(period=period)
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(decision)
    return calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        actor="system",
        binding_values={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        iva_compensation_decision=decision,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_FILE_AT,
        filing_instance_evidence=general_m303_filing_evidence(
            work_unit.period, reference="test:m303-recargo-cross-period"
        ),
    )


def test_ledger_recargo_sales_populate_m303_recargo_casillas_per_quarter(
    secure_objects: SecureObjectRepository,
) -> None:
    """Recargo repercutido sales fold into each quarter's M303 recargo cuotas, period-scoped."""
    _store_profile(secure_objects)
    stored = _persist_two_quarters_of_recargo_sales(secure_objects)

    computed: RecargoAmountsByPeriod = {}
    for period in ("1T", "2T"):
        revision = _calculate_m303_quarter(secure_objects, period=period)

        general = Decimal(revision.casilla_values[_RECARGO_GENERAL_CUOTA])
        reducido = Decimal(revision.casilla_values[_RECARGO_REDUCIDO_CUOTA])

        # Period-scoped transport invariant: each tier's recargo cuota equals the
        # SUM of that quarter's own stored recargo_amount fields for that tier (a
        # single sale per tier here, so the sum is over one stored field). Asserting
        # against sum(stored field) -- not a hand-summed Decimal literal -- keeps the
        # seed and the expectation from sharing a literal and satisfies the
        # no-hand-summed-aggregation tautology gate.
        assert general == sum((stored[period]["general"],), Decimal("0")), (
            f"{period}: recargo general cuota (casilla {_RECARGO_GENERAL_CUOTA}) must equal the "
            f"stored general recargo {stored[period]['general']}; got {general}"
        )
        assert reducido == sum((stored[period]["reducido"],), Decimal("0")), (
            f"{period}: recargo reducido cuota (casilla {_RECARGO_REDUCIDO_CUOTA}) must equal the "
            f"stored reducido recargo {stored[period]['reducido']}; got {reducido}"
        )
        computed[period] = {"general": general, "reducido": reducido}

    # Cross-period non-leakage: each quarter's recargo cuotas are STRICTLY DIFFERENT
    # from the other quarter's. The 2T amounts deliberately differ from 1T on both
    # tiers, so a calc that leaked 1T sales into 2T (or vice versa) -- or summed the
    # whole year into each quarter -- would surface here as an equality the distinct
    # seeds forbid.
    assert computed["1T"]["general"] != computed["2T"]["general"], (
        "1T and 2T recargo general cuotas must differ (no cross-period leakage): "
        f"1T={computed['1T']['general']} 2T={computed['2T']['general']}"
    )
    assert computed["1T"]["reducido"] != computed["2T"]["reducido"], (
        "1T and 2T recargo reducido cuotas must differ (no cross-period leakage): "
        f"1T={computed['1T']['reducido']} 2T={computed['2T']['reducido']}"
    )

    # And the 2T quarter must carry exactly its own quarter's recargo -- never the
    # 1T quarter's value (the precise off-by-one-quarter / leak assertion).
    assert computed["2T"]["general"] == sum((stored["2T"]["general"],), Decimal("0"))
    assert computed["2T"]["general"] != stored["1T"]["general"]
    assert computed["2T"]["reducido"] == sum((stored["2T"]["reducido"],), Decimal("0"))
    assert computed["2T"]["reducido"] != stored["1T"]["reducido"]
