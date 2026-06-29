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
from typing import Literal

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.errors import AeatError
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.iva import EUMemberState, IvaCategory
from ....domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._calculation_revision import CalculationRevision
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._work_unit import WorkUnit
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
    ModeloCrossPeriodCleanStateError,
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
type StoredIvaAxis = Literal["devengada", "deducible", "casilla_59", "resultado"]
type StoredIvaByPeriod = dict[str, dict[StoredIvaAxis, Decimal]]
type ComputedM303CasillasByPeriod = dict[str, dict[CasillaId, Decimal]]


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"ledger M303/M390 E2E fixture casilla key {value!r} is not a CasillaId") from exc

# M303 computed-output casillas the M390 reconciliation relations fold.
_DEVENGADA_TOTAL: CasillaId = _casilla_id("iva.cuota-devengada-total")
_DEDUCIBLE_TOTAL: CasillaId = _casilla_id("iva.cuota-deducible-total")
_RESULTADO: CasillaId = _casilla_id("iva.resultado-regimen-general")
_CASILLA_59: CasillaId = _casilla_id("59")

# M390 annual reconciliation casillas (folded from the four M303 quarters).
_M390_DEVENGADA: CasillaId = _casilla_id("iva.anual.reconciliacion.devengada-303")
_M390_DEDUCIBLE: CasillaId = _casilla_id("iva.anual.reconciliacion.deducible-303")
_M390_RESULTADO: CasillaId = _casilla_id("iva.anual.reconciliacion.resultado-303")

# Laura / Taller Sol annual IVA scenario. Domestic 21% issued and received
# invoice rows drive the normal M303 cuota totals. Q2 additionally carries an
# exempt intra-Community supply base into casilla 59, and Q3 carries a domestic
# reverse-charge operation that books the same self-assessed cuota on both
# devengada and deducible axes.
_LAURA_QUARTER_FACTS: dict[str, dict[str, Decimal]] = {
    "1T": {
        "issued_base": Decimal("10000.00"),
        "issued_iva": Decimal("2100.00"),
        "received_base": Decimal("3000.00"),
        "received_iva": Decimal("630.00"),
        "eu_supply_base": Decimal("0.00"),
        "reverse_charge_base": Decimal("0.00"),
        "reverse_charge_iva": Decimal("0.00"),
    },
    "2T": {
        "issued_base": Decimal("12000.00"),
        "issued_iva": Decimal("2520.00"),
        "received_base": Decimal("2500.00"),
        "received_iva": Decimal("525.00"),
        "eu_supply_base": Decimal("1500.00"),
        "reverse_charge_base": Decimal("0.00"),
        "reverse_charge_iva": Decimal("0.00"),
    },
    "3T": {
        "issued_base": Decimal("9000.00"),
        "issued_iva": Decimal("1890.00"),
        "received_base": Decimal("2200.00"),
        "received_iva": Decimal("462.00"),
        "eu_supply_base": Decimal("0.00"),
        "reverse_charge_base": Decimal("800.00"),
        "reverse_charge_iva": Decimal("168.00"),
    },
    "4T": {
        "issued_base": Decimal("15000.00"),
        "issued_iva": Decimal("3150.00"),
        "received_base": Decimal("1800.00"),
        "received_iva": Decimal("378.00"),
        "eu_supply_base": Decimal("0.00"),
        "reverse_charge_base": Decimal("0.00"),
        "reverse_charge_iva": Decimal("0.00"),
    },
}
_LAURA_ANNUAL_EXPECTED = {
    "devengada": Decimal("9828.00"),
    "deducible": Decimal("2163.00"),
    "resultado": Decimal("7665.00"),
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
    iva_amount: Decimal,
    period: str,
    iva_rate: Decimal = _IVA_RATE,
    amount: Decimal | None = None,
    iva_category: IvaCategory | None = None,
    counterparty_eu_member_state: EUMemberState | None = None,
) -> Transaction:
    booked = date(_YEAR, _QUARTER_MONTH[period], 10)
    payload: dict[str, object] = {
        "raw": RawTransaction(
            transaction_id=provider_id,
            booked_date=booked,
            value_date=booked,
            amount=amount if amount is not None else taxable_base + iva_amount,
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
        "iva_rate": iva_rate,
        "iva_amount": iva_amount,
        "classified_at": _T0,
        "classified_by": "manual",
    }
    if iva_category is not None:
        payload["iva_category"] = iva_category
    if counterparty_eu_member_state is not None:
        payload["counterparty_eu_member_state"] = counterparty_eu_member_state
    return Transaction.model_validate(payload)


def _persist_year_of_invoices(secure_objects: SecureObjectRepository) -> StoredIvaByPeriod:
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
    stored: StoredIvaByPeriod = {}
    for period, facts in _LAURA_QUARTER_FACTS.items():
        issued = _iva_transaction(
            f"sale-{period}",
            direction=TransactionDirection.INCOMING,
            taxable_base=facts["issued_base"],
            iva_amount=facts["issued_iva"],
            period=period,
        )
        received = _iva_transaction(
            f"purchase-{period}",
            direction=TransactionDirection.OUTGOING,
            taxable_base=facts["received_base"],
            iva_amount=facts["received_iva"],
            period=period,
        )
        transactions.extend((issued, received))
        devengada = facts["issued_iva"]
        deducible = facts["received_iva"]
        if facts["eu_supply_base"] > Decimal("0"):
            transactions.append(
                _iva_transaction(
                    f"eu-supply-{period}",
                    direction=TransactionDirection.INCOMING,
                    taxable_base=facts["eu_supply_base"],
                    iva_amount=Decimal("0.00"),
                    iva_rate=Decimal("0.00"),
                    period=period,
                    iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
                    counterparty_eu_member_state=EUMemberState.DE,
                ),
            )
        if facts["reverse_charge_base"] > Decimal("0"):
            transactions.append(
                _iva_transaction(
                    f"reverse-charge-{period}",
                    direction=TransactionDirection.OUTGOING,
                    taxable_base=facts["reverse_charge_base"],
                    iva_amount=facts["reverse_charge_iva"],
                    amount=facts["reverse_charge_base"],
                    period=period,
                    iva_category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
                ),
            )
            devengada += facts["reverse_charge_iva"]
            deducible += facts["reverse_charge_iva"]
        stored[period] = {
            "devengada": devengada,
            "deducible": deducible,
            "casilla_59": facts["eu_supply_base"],
            "resultado": devengada - deducible,
        }
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
    """Seed the ready taxpayer profile the M303 gates read."""
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            display_name="Laura - Taller Sol",
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Laura"),
                UserProfileFact(path="identity.surnames", value="Taller Sol"),
                UserProfileFact(path="activities.description", value="taller"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _calculate_m303_quarter_revision(
    secure_objects: SecureObjectRepository,
    *,
    period: str,
) -> tuple[WorkUnit, CalculationRevision]:
    """Run the live bucket-aggregation M303 calc for one quarter without projecting filed observations."""
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
    return work_unit, revision


def _calculate_and_file_m303_quarter(secure_objects: SecureObjectRepository, *, period: str) -> CalculationRevision:
    """Run the live bucket-aggregation M303 calc for one quarter and project its filed observation."""
    work_unit, revision = _calculate_m303_quarter_revision(secure_objects, period=period)
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

    computed: ComputedM303CasillasByPeriod = {}
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
        assert Decimal(revision.casilla_values[_CASILLA_59]) == stored[period]["casilla_59"], (
            f"{period}: casilla 59 must equal the stored EU supply base {stored[period]['casilla_59']}; "
            f"got {revision.casilla_values.get(_CASILLA_59)}"
        )
        assert Decimal(revision.casilla_values[_RESULTADO]) == stored[period]["resultado"], (
            f"{period}: resultado-regimen-general must match Laura's expected quarterly result "
            f"{stored[period]['resultado']}; got {revision.casilla_values.get(_RESULTADO)}"
        )
        computed[period] = {
            _DEVENGADA_TOTAL: Decimal(revision.casilla_values[_DEVENGADA_TOTAL]),
            _DEDUCIBLE_TOTAL: Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]),
            _RESULTADO: Decimal(revision.casilla_values[_RESULTADO]),
        }

    # Laura's quarterly resultado values are distinct, so a stale or shifted
    # quarterly dependency cannot satisfy the annual result assertion below.
    result_values = [computed[p][_RESULTADO] for p in _QUARTER_ORDER]
    assert len(set(result_values)) == 4, f"quarterly resultado values must be distinct: {result_values}"

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
    assert Decimal(casillas[_M390_DEVENGADA]) == _LAURA_ANNUAL_EXPECTED["devengada"]
    assert Decimal(casillas[_M390_DEDUCIBLE]) == _LAURA_ANNUAL_EXPECTED["deducible"]
    assert Decimal(casillas[_M390_RESULTADO]) == _LAURA_ANNUAL_EXPECTED["resultado"]


def test_m390_refuses_zero_reconciliation_when_m303_calculated_but_observations_missing(
    secure_objects: SecureObjectRepository,
) -> None:
    """Laura regression: calculated nonzero 303 quarters must not become zero M390 reconciliation slots."""
    _store_profile(secure_objects)
    _persist_year_of_invoices(secure_objects)

    computed: ComputedM303CasillasByPeriod = {}
    for period in _QUARTER_ORDER:
        _work_unit, revision = _calculate_m303_quarter_revision(secure_objects, period=period)
        computed[period] = {
            _DEVENGADA_TOTAL: Decimal(revision.casilla_values[_DEVENGADA_TOTAL]),
            _DEDUCIBLE_TOTAL: Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]),
            _RESULTADO: Decimal(revision.casilla_values[_RESULTADO]),
        }

    assert sum((computed[p][_DEVENGADA_TOTAL] for p in _QUARTER_ORDER), Decimal("0")) == Decimal("9828.00")
    assert sum((computed[p][_DEDUCIBLE_TOTAL] for p in _QUARTER_ORDER), Decimal("0")) == Decimal("2163.00")
    assert sum((computed[p][_RESULTADO] for p in _QUARTER_ORDER), Decimal("0")) == Decimal("7665.00")

    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    before_revision_ids = frozenset(cr_repo.load().revisions)
    with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
        _calculate_m390_annual(secure_objects)
    after_revision_ids = frozenset(cr_repo.load().revisions)

    assert after_revision_ids == before_revision_ids
    assert isinstance(exc_info.value, AeatError)
    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"
    context = exc_info.value.context or {}
    assert context["reason"] == "missing_clean_cross_period_303_filings_or_observations"
    assert context["missing_303_periods"] == ("1T", "2T", "3T", "4T")
    assert context["zero_reconciliation_casillas_at_risk"] == (
        _M390_DEVENGADA,
        _M390_DEDUCIBLE,
        _M390_RESULTADO,
    )
