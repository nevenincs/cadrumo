"""Tests for bucket-local IVA ledger observation projection."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.operator_action_enums import OperatorActionAxis
from ....core.period import Period
from ....core.prorrata_exclusions import Art104TresExclusion
from ....domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord, BienInversionKind
from ....domain.calculations.registry.ledger_iva_bindings import resolve_ledger_iva_aggregation_binding_values
from ....domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.flow import IvaFlowDirection
from ....domain.iva.prorrata import ProrrataKind, ProrrataRegime
from ....domain.iva.schema import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_two_bucket_runtime
from ...ledger.preflight import OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE
from .. import (
    AggregationValidationError,
    IvaLedgerAggregation,
    IvaLedgerAggregationIssueReason,
    aggregate_iva_ledger_observations_from_repositories,
)
from .. import (
    aggregate_iva_ledger_observations as _aggregate_iva_ledger_observations_with_authority,
)
from .renta_income_aggregation_support import _period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TEST_ASSET_REGISTER = BienesInversionIvaRegister()


def aggregate_iva_ledger_observations(
    transactions: TransactionCatalogue,
    *,
    period: Period,
) -> IvaLedgerAggregation:
    """Exercise the public path with an explicit empty authority owned by this test profile."""
    return _aggregate_iva_ledger_observations_with_authority(
        transactions,
        period=period,
        ledger_profile_id="test-profile",
        investment_asset_register=_TEST_ASSET_REGISTER,
        investment_asset_profile_id="test-profile",
    )


def _iva_binding(
    binding_id: str,
    *,
    categories: tuple[IvaCategory, ...],
    rate_kinds: tuple[IvaRateKind, ...],
    flow_direction: IvaFlowDirection,
) -> DataBindingDefinition:
    return DataBindingDefinition(
        id=binding_id,
        source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        selector={
            "categories": categories,
            "rate_kinds": rate_kinds,
            "flow_direction": flow_direction,
            "observation_roles": (IvaLedgerObservationRole.SETTLEMENT,),
            "cash_accounting_treatments": (
                IvaCashAccountingTreatment.NONE,
                IvaCashAccountingTreatment.TAXPAYER_REGIME,
                IvaCashAccountingTreatment.SUPPLIER_REGIME,
            ),
            "fact": "iva_amount_sum",
        },
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=("ley-37-1992:art-88",),
        source_refs=("test-iva-ledger-binding",),
    )


def _revision_with_iva_bindings(revision_id: str, *bindings: DataBindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id=revision_id,
        localization_key=f"test.schema.revision.{revision_id}.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(year_from=2026, periods=("1T", "2T", "3T", "4T", "0A")),
        legal_refs=("ley-37-1992:art-88",),
        source_refs=("test-iva-ledger-binding",),
        bindings=bindings,
    )


def _modelo_303_iva_revision() -> ModeloRevision:
    return _revision_with_iva_bindings(
        "2022",
        _iva_binding(
            "modelo-303-iva-repercutido-general-cuota",
            categories=(IvaCategory.DOMESTIC_GENERAL,),
            rate_kinds=(IvaRateKind.GENERAL,),
            flow_direction=IvaFlowDirection.REPERCUTIDO,
        ),
        _iva_binding(
            "modelo-303-iva-soportado-interiores-cuota",
            categories=(
                IvaCategory.DOMESTIC_GENERAL,
                IvaCategory.DOMESTIC_REDUCED,
                IvaCategory.DOMESTIC_SUPER_REDUCED,
            ),
            rate_kinds=(IvaRateKind.GENERAL, IvaRateKind.REDUCED, IvaRateKind.SUPER_REDUCED),
            flow_direction=IvaFlowDirection.SOPORTADO,
        ),
    )


_Q2_2023 = _period(2023, "2T")
_Q2_2026 = _period(2026, "2T")
# Before Ley 41/1994 art. 78.Segundo took effect on 1 January 1995, so genuinely
# outside the rate table's coverage: no ES window of any tier reaches back past
# it.
#
# This probe has now moved TWICE, each time because the table gained real
# coverage rather than because the distinction weakened. 2T 2023 served first,
# until the general and reduced windows were corrected back to 2012; 2T 2012
# served next, until the super-reducido window was corrected back to 1995 and
# began covering the date the probe relied on being uncovered.
#
# The lesson is in the pattern, not the dates: a probe anchored to where the
# data currently STOPS will be falsified every time the data is corrected, and
# it fails by reporting the wrong reason rather than by looking wrong. Anchor it
# to the earliest provision the table can ever cite, which is what this is.
_Q2_1994 = _period(1994, "2T")
_BUCKET_ID = "14141414-1414-4414-8414-141414141414"
_OTHER_BUCKET_ID = "15151515-1515-4515-8515-151515151515"


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 4, 5),
    value_date: date | None = date(2026, 4, 5),
    amount: Decimal = Decimal("121.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty="Cliente o proveedor",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(
    provider_id: str,
    *,
    amount: Decimal | None = None,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    booked_date: date = date(2026, 4, 5),
    value_date: date | None = date(2026, 4, 5),
    currency: str = "EUR",
    taxable_base: Decimal | None = Decimal("100.00"),
    iva_rate: Decimal | None = Decimal("0.21"),
    iva_amount: Decimal | None = Decimal("21.00"),
    prorrata_reference: str | None = None,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
    fx_rate: Decimal | None = None,
    value_in_eur: Decimal | None = None,
    iva_category: IvaCategory | None = None,
    exemption_article: IvaExemptionArticle | None = None,
    art_104_tres_exclusion: Art104TresExclusion | None = None,
) -> Transaction:
    # Keep the gross consistent with base + iva (the Transaction
    # gross == taxable_base + iva_amount invariant). When the caller does not
    # pin an explicit amount and both tax fields are present, derive the
    # IVA-inclusive gross magnitude from them; flow is carried by ``direction``.
    if amount is None:
        amount = taxable_base + iva_amount if taxable_base is not None and iva_amount is not None else Decimal("121.00")
    carries_input_iva = (
        direction is TransactionDirection.OUTGOING
        and taxable_base is not None
        and iva_rate is not None
        and iva_amount is not None
    )
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=booked_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": business_classification,
            "business_pct": business_pct,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": iva_category,
            "deduction_fact_kind": (IvaDeductionFactKind.DOMESTIC_CURRENT if carries_input_iva else None),
            "deduction_provenance": (
                IvaDeductionClassificationProvenance(
                    authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                    source_locator=f"test-invoice:{provider_id}",
                    evidence_digest="a" * 64,
                )
                if carries_input_iva
                else None
            ),
            "exemption_article": exemption_article,
            "art_104_tres_exclusion": art_104_tres_exclusion,
            "prorrata_reference": prorrata_reference,
            "lifecycle_state": lifecycle_state,
            "fx_rate": fx_rate,
            "value_in_eur": value_in_eur,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def test_direct_aggregation_cannot_bypass_investment_reciprocity_authority() -> None:
    transaction = _transaction("direct-investment").model_copy(
        update={
            "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_INVESTMENT,
            "investment_asset_id": "asset-direct",
            "prorrata_sector_id": "sector-a",
        }
    )
    catalogue = TransactionCatalogue.from_transactions((transaction,))

    with pytest.raises(TypeError, match="investment_asset_register"):
        cast(Any, _aggregate_iva_ledger_observations_with_authority)(catalogue, period=_Q2_2026)


def test_direct_aggregation_accepts_exact_reciprocal_investment_authority() -> None:
    transaction = _transaction("direct-investment-valid").model_copy(
        update={
            "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_INVESTMENT,
            "investment_asset_id": "asset-direct",
            "prorrata_sector_id": "sector-a",
        }
    )
    register = BienesInversionIvaRegister(
        records=(
            BienInversionIvaRecord(
                identifier="asset-direct",
                description="Direct aggregation asset",
                acquisition_year=2026,
                cuota_soportada=Decimal("21.00"),
                prorrata_inicial_pct=Decimal("100"),
                kind=BienInversionKind.MUEBLE,
                acquisition_ledger_id=transaction.transaction_id,
                prorrata_sector_id="sector-a",
            ),
        )
    )

    result = _aggregate_iva_ledger_observations_with_authority(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
        ledger_profile_id="test-profile",
        investment_asset_register=register,
        investment_asset_profile_id="test-profile",
    )

    assert result.observations[0].investment_asset_id == "asset-direct"


def test_art_104_tres_tagged_transaction_is_recorded_as_excluded_ledger_id() -> None:
    """An operator-tagged art. 104.Tres judgment operation is recorded for prorrata exclusion.

    The tagged sale still projects its IVA cuota observation (it is a real
    taxable supply); only its ledger id is collected so the prorrata annual
    volume rollup can skip it from both terms of the ratio.
    """
    untagged = _transaction("row-taxable-sale", direction=TransactionDirection.INCOMING)
    tagged = _transaction(
        "row-non-habitual-inmueble",
        direction=TransactionDirection.INCOMING,
        art_104_tres_exclusion=Art104TresExclusion.NON_HABITUAL_REAL_ESTATE_OR_FINANCIAL,
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((untagged, tagged)),
        period=_Q2_2026,
    )

    assert len(result.observations) == 2
    assert result.art_104_tres_excluded_ledger_ids == (tagged.transaction_id,)


def test_outgoing_business_transaction_projects_to_soportado_iva_observation() -> None:
    transaction = _transaction("row-expense")

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert result.issues == ()
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.ledger_id == transaction.transaction_id
    assert observation.transaction_date == date(2026, 4, 5)
    assert observation.category is IvaCategory.DOMESTIC_GENERAL
    assert observation.rate_kind is IvaRateKind.GENERAL
    assert observation.flow_direction is IvaFlowDirection.SOPORTADO
    assert observation.base_amount == transaction.taxable_base
    assert observation.iva_amount == transaction.iva_amount


def test_archived_and_stashed_transactions_do_not_feed_iva_projection() -> None:
    active = _transaction("row-active")
    archived = _transaction(
        "row-archived",
        taxable_base=Decimal("900.00"),
        iva_amount=Decimal("189.00"),
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    stashed = _transaction(
        "row-stashed",
        taxable_base=Decimal("700.00"),
        iva_amount=Decimal("147.00"),
        lifecycle_state=TransactionLifecycleState.STASHED,
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((active, archived, stashed)),
        period=_Q2_2026,
    )

    assert result.issues == ()
    assert [observation.ledger_id for observation in result.observations] == [active.transaction_id]
    assert result.observations[0].base_amount == active.taxable_base
    assert result.observations[0].iva_amount == active.iva_amount


def test_reviewed_excluded_transaction_omitted_from_iva_projection_without_issue() -> None:
    """A reviewed-excluded row is silently omitted: no observation and no gate issue.

    The operator reviewed the row and deliberately excluded it from filing (a
    final disposition). It must not feed the aggregation, and — unlike an
    unclassified row — it must not surface an ``UNCLASSIFIED_BUSINESS_STATE``
    "classify me" advisory, since the exclusion is an explicit recorded decision.
    """
    active = _transaction("row-active")
    excluded = _transaction(
        "row-reviewed-excluded",
        taxable_base=Decimal("900.00"),
        iva_amount=Decimal("189.00"),
        business_classification=BusinessClassification.REVIEWED_EXCLUDED,
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((active, excluded)),
        period=_Q2_2026,
    )

    assert result.issues == ()
    assert [observation.ledger_id for observation in result.observations] == [active.transaction_id]


def test_incoming_business_transaction_projects_to_repercutido_iva_observation() -> None:
    transaction = _transaction(
        "row-income",
        amount=Decimal("110.00"),
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.10"),
        iva_amount=Decimal("10.00"),
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert result.issues == ()
    observation = result.observations[0]
    assert observation.category is IvaCategory.DOMESTIC_REDUCED
    assert observation.rate_kind is IvaRateKind.REDUCED
    assert observation.flow_direction is IvaFlowDirection.REPERCUTIDO
    assert observation.iva_amount == Decimal("10.00")


def test_mixed_business_transaction_applies_business_percentage_to_base_and_iva() -> None:
    transaction = _transaction(
        "row-mixed",
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.25"),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert result.issues == ()
    assert result.observations[0].base_amount == Decimal("50.0000")
    assert result.observations[0].iva_amount == Decimal("10.5000")


def test_outgoing_input_row_carries_legal_prorrata_reference_separately_from_observation() -> None:
    transaction = _transaction(
        "row-prorrata",
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        prorrata_reference="prorrata:2026:provisional:general",
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert result.issues == ()
    assert len(result.observations) == 1
    assert len(result.prorrata_references) == 1
    reference = result.prorrata_references[0]
    assert reference.transaction_id == transaction.transaction_id
    assert reference.transaction_date == date(2026, 4, 5)
    assert reference.reference.year == 2026
    assert reference.reference.kind is ProrrataKind.PROVISIONAL
    assert reference.reference.regime is ProrrataRegime.GENERAL
    assert reference.base_amount == Decimal("200.00")
    assert reference.input_iva_amount == Decimal("42.00")
    assert result.observations[0].iva_amount == Decimal("42.00")


def test_mixed_input_row_applies_business_percentage_before_carrying_prorrata_reference() -> None:
    transaction = _transaction(
        "row-mixed-prorrata",
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.25"),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        prorrata_reference="prorrata:2026:provisional:especial:sector-retail",
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert result.issues == ()
    assert result.prorrata_references[0].reference.sector_id == "sector-retail"
    assert result.prorrata_references[0].base_amount == Decimal("50.0000")
    assert result.prorrata_references[0].input_iva_amount == Decimal("10.5000")


def test_invalid_prorrata_reference_is_reported_without_dropping_iva_observation() -> None:
    transaction = _transaction("row-bad-prorrata", prorrata_reference="telefonia_movil")

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert len(result.observations) == 1
    assert result.prorrata_references == ()
    assert result.issues[0].transaction_id == transaction.transaction_id
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE


def test_prorrata_reference_on_output_iva_row_is_reported_but_output_observation_survives() -> None:
    transaction = _transaction(
        "row-output-prorrata",
        amount=Decimal("121.00"),
        direction=TransactionDirection.INCOMING,
        prorrata_reference="prorrata:2026:provisional:general",
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert result.observations[0].flow_direction is IvaFlowDirection.REPERCUTIDO
    assert result.prorrata_references == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE


def test_personal_transaction_is_reported_without_iva_observation() -> None:
    transaction = _transaction("row-personal", business_classification=BusinessClassification.PERSONAL)

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert result.observations == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION


def test_missing_tax_fact_is_reported_before_projection() -> None:
    transaction = _transaction("row-missing-rate", iva_rate=None)

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert result.observations == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.MISSING_IVA_RATE


def test_non_canonical_iva_rate_is_reported() -> None:
    transaction = _transaction("row-bad-rate", iva_rate=Decimal("0.07"), iva_amount=Decimal("7.00"))

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert result.observations == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE


def test_out_of_period_and_foreign_currency_rows_do_not_project() -> None:
    old_row = _transaction("row-old", booked_date=date(2026, 1, 5), value_date=date(2026, 1, 5))
    usd_row = _transaction("row-usd", currency="USD")

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((old_row, usd_row)),
        period=_Q2_2026,
    )

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
        IvaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
    ]


def test_converted_foreign_currency_tax_substrate_does_not_project_as_eur() -> None:
    converted_gbp = _transaction(
        "row-gbp-converted",
        currency="GBP",
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        value_in_eur=Decimal("142.35"),
        fx_rate=Decimal("1.176"),
    )
    eur_row = _transaction("row-eur", taxable_base=Decimal("50.00"), iva_amount=Decimal("10.50"))
    unconverted_usd = _transaction("row-usd-unconverted", currency="USD")

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((converted_gbp, eur_row, unconverted_usd)),
        period=_Q2_2026,
    )

    assert [observation.ledger_id for observation in result.observations] == [eur_row.transaction_id]
    assert result.observations[0].base_amount == Decimal("50.00")
    assert result.observations[0].iva_amount == Decimal("10.50")
    assert [(issue.transaction_id, issue.reason) for issue in result.issues] == [
        (converted_gbp.transaction_id, IvaLedgerAggregationIssueReason.MISSING_EUR_TAX_SUBSTRATE),
        (unconverted_usd.transaction_id, IvaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY),
    ]
    assert "value_in_eur" in result.issues[0].detail
    assert "native-currency facts" in result.issues[0].detail


def test_iva_aggregation_buckets_on_value_date_caja_basis_only() -> None:
    """Document the confirmed CAJA-only aggregation basis (no devengo selector).

    The ledger keys a transaction into a filing period on a single
    ``value_date or booked_date`` axis — a CASH (caja) basis. There is no
    accrual/devengo basis selector anywhere in the aggregation surface.

    This is a *documentation* test: it pins the current, intentionally
    single-basis behaviour so a future devengo addition has a
    regression anchor. If someone silently introduces a devengo branch (e.g.
    bucketing on ``booked_date`` while ``value_date`` says otherwise, or a
    new basis-selector argument), the assertions below turn RED.

    Construction: ``value_date`` (the caja/payment date) lands inside 2026Q2,
    while ``booked_date`` (the would-be devengo/accrual posting date) lands in
    2026Q1. A devengo-basis path would exclude the row from 2026Q2; the
    caja-basis path includes it and stamps the observation date as the
    value_date. The mirror row inverts the two dates and must be excluded.
    """
    # value_date in-period (caja), booked_date out-of-period (devengo would differ).
    caja_in_period = _transaction(
        "row-caja-in-period",
        booked_date=date(2026, 1, 31),
        value_date=date(2026, 4, 2),
    )
    # value_date out-of-period (caja), booked_date in-period (devengo would include).
    caja_out_of_period = _transaction(
        "row-caja-out-of-period",
        booked_date=date(2026, 4, 2),
        value_date=date(2026, 1, 31),
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((caja_in_period, caja_out_of_period)),
        period=_Q2_2026,
    )

    # Caja basis: the row whose VALUE_DATE is in-period is the only one projected,
    # and the observation date is the value_date — never the booked_date.
    assert [observation.ledger_id for observation in result.observations] == [caja_in_period.transaction_id]
    assert result.observations[0].transaction_date == date(2026, 4, 2)
    # The row whose value_date is out-of-period is excluded, keyed on value_date —
    # a devengo basis (booked_date 2026-04-02) would instead have INCLUDED it.
    assert [issue.transaction_id for issue in result.issues] == [caja_out_of_period.transaction_id]
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD
    assert "2026-01-31" in result.issues[0].detail


def test_future_out_of_window_row_is_a_nonblocking_review_advisory() -> None:
    future_row = _transaction(
        "row-future-outside-period",
        booked_date=date(2026, 7, 2),
        value_date=date(2026, 7, 2),
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((future_row,)),
        period=_Q2_2026,
    )

    assert result.observations == ()
    assert len(result.issues) == 1
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD
    assert (
        OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE[result.issues[0].reason] is OperatorActionAxis.REVIEW_ADVISORY
    )


def test_no_devengo_basis_selector_exists_on_iva_aggregation_surface() -> None:
    """Assert the absence of any accrual/devengo basis selector (caja-only).

    Confirms (against the live module/signature, re-read at runtime) that
    neither the public IVA-aggregation entry points nor their parameters
    expose a ``basis``/``devengo``/``accrual`` axis. Caja is the only basis.
    A future devengo design will add such a selector; until then this
    test fails RED the moment a basis selector is introduced without the
    accompanying behaviour and tests.
    """
    import inspect

    from .. import iva_ledger

    forbidden_tokens = ("devengo", "accrual", "basis")
    for entry_point in (
        iva_ledger.aggregate_iva_ledger_observations,
        iva_ledger.aggregate_iva_ledger_observations_from_repositories,
        iva_ledger.aggregate_iva_ledger_candidates,
    ):
        params = inspect.signature(entry_point).parameters
        assert not any(token in name.lower() for name in params for token in forbidden_tokens), (
            f"{entry_point.__name__} unexpectedly grew a basis selector parameter: {tuple(params)}"
        )

    # No basis-selector symbol is exported from the aggregation package surface.
    assert not any(token in symbol.lower() for symbol in iva_ledger.__all__ for token in forbidden_tokens), (
        iva_ledger.__all__
    )


def test_repository_backed_projection_rejects_bucket_mismatch_before_loading(
    secure_objects: SecureObjectRepository,
) -> None:
    with pytest.raises(AggregationValidationError, match="bucket_mismatch"):
        aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_Q2_2026,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=_BUCKET_ID,
                objects=secure_objects,
            ),
            transaction_repository=TransactionCatalogueRepository(
                bucket_id=_OTHER_BUCKET_ID,
                objects=secure_objects,
            ),
            investment_asset_register=_TEST_ASSET_REGISTER,
            investment_asset_profile_id=_BUCKET_ID,
        )


def test_repository_backed_projection_refuses_a_real_foreign_prorrata_repository_before_loading(
    tmp_path: Path,
) -> None:
    """IVA aggregation never combines a primary ledger with another bucket's register."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        TransactionCatalogueRepository(bucket_id=runtime.primary.bucket_id).save(
            TransactionCatalogue.from_transactions((_transaction("primary-ledger-row"),))
        )
        foreign_prorrata_repository = ProrrataRegisterRepository(
            bucket_id=runtime.secondary.bucket_id,
            objects=runtime.secondary.repository,
        )

        assert foreign_prorrata_repository.bucket_id == runtime.secondary.bucket_id
        with pytest.raises(AggregationValidationError, match="bucket_mismatch"):
            aggregate_iva_ledger_observations_from_repositories(
                bucket_id=runtime.primary.bucket_id,
                period=_Q2_2026,
                prorrata_register_repository=foreign_prorrata_repository,
            )


def test_repository_backed_projection_loads_persisted_bucket_catalogue(secure_objects: SecureObjectRepository) -> None:
    transaction = _transaction("row-repository")
    repository = TransactionCatalogueRepository(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
    )
    repository.save(TransactionCatalogue.from_transactions((transaction,)))

    result = aggregate_iva_ledger_observations_from_repositories(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
        ),
        investment_asset_register=_TEST_ASSET_REGISTER,
        investment_asset_profile_id=_BUCKET_ID,
    )

    assert result.issues == ()
    assert result.observations[0].ledger_id == transaction.transaction_id


def test_repository_backed_projection_reports_out_of_period_catalogue_transactions(
    secure_objects: SecureObjectRepository,
) -> None:
    """A catalogue transaction outside the requested quarter must surface as a summary.

    Regression test: the repository-backed entry point must NOT
    silently drop out-of-window rows. The compact summary keeps the operator
    visibility signal without allocating one row-level issue per excluded
    plaintext index entry.
    """
    in_period = _transaction("row-in-period", value_date=date(2026, 4, 5))
    out_of_period = _transaction("row-out-of-period", value_date=date(2026, 7, 10))
    repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    repository.save(TransactionCatalogue.from_transactions((in_period, out_of_period)))

    result = aggregate_iva_ledger_observations_from_repositories(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        investment_asset_register=_TEST_ASSET_REGISTER,
        investment_asset_profile_id=_BUCKET_ID,
    )

    assert {o.ledger_id for o in result.observations} == {in_period.transaction_id}
    assert result.issues == ()
    assert result.out_of_window_summary is not None
    assert result.out_of_window_summary.count == 1
    assert result.out_of_window_summary.min_filing_date == date(2026, 7, 10)
    assert result.out_of_window_summary.max_filing_date == date(2026, 7, 10)


def test_repository_backed_projection_summarizes_previously_silent_out_of_window_rows(
    secure_objects: SecureObjectRepository,
) -> None:
    """Out-of-window rows surface as one compact period-exclusion summary.

    Reviewed-excluded and archived rows are ignored before the in-window IVA
    classifier runs. When those rows fall outside the requested window, the
    repository-backed partition reports their count and date span instead of
    dropping them before aggregation.
    """
    in_period = _transaction("row-in-period", value_date=date(2026, 4, 5))
    excluded_out_of_period = _transaction(
        "row-excluded-out-of-period",
        value_date=date(2026, 7, 1),
        business_classification=BusinessClassification.REVIEWED_EXCLUDED,
    )
    archived_out_of_period = _transaction(
        "row-archived-out-of-period",
        value_date=date(2026, 7, 2),
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    repository.save(
        TransactionCatalogue.from_transactions((in_period, excluded_out_of_period, archived_out_of_period)),
    )

    result = aggregate_iva_ledger_observations_from_repositories(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        investment_asset_register=_TEST_ASSET_REGISTER,
        investment_asset_profile_id=_BUCKET_ID,
    )

    assert {o.ledger_id for o in result.observations} == {in_period.transaction_id}
    assert result.issues == ()
    assert result.out_of_window_summary is not None
    assert result.out_of_window_summary.count == 2
    assert result.out_of_window_summary.min_filing_date == date(2026, 7, 1)
    assert result.out_of_window_summary.max_filing_date == date(2026, 7, 2)


def test_repository_backed_projection_partition_matches_full_scan(
    secure_objects: SecureObjectRepository,
) -> None:
    """The partitioned result matches the full-scan result for declared values.

    The same multi-period catalogue is aggregated once through the
    repository-backed partition and once through the pure full-scan aggregator.
    In-window observations and prorrata references must match; only the
    out-of-window issue taxonomy can differ between the two paths.
    """
    q2_row_a = _transaction("row-q2-a", value_date=date(2026, 4, 5), taxable_base=Decimal("100.00"))
    q2_row_b = _transaction("row-q2-b", value_date=date(2026, 6, 20), taxable_base=Decimal("200.00"))
    q1_row = _transaction("row-q1", value_date=date(2026, 2, 1), taxable_base=Decimal("50.00"))
    q3_row = _transaction("row-q3", value_date=date(2026, 8, 1), taxable_base=Decimal("75.00"))
    excluded_q3_row = _transaction(
        "row-q3-excluded",
        value_date=date(2026, 9, 1),
        business_classification=BusinessClassification.REVIEWED_EXCLUDED,
    )
    catalogue = TransactionCatalogue.from_transactions(
        (q2_row_a, q2_row_b, q1_row, q3_row, excluded_q3_row),
    )
    repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    repository.save(catalogue)

    partitioned = aggregate_iva_ledger_observations_from_repositories(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        investment_asset_register=_TEST_ASSET_REGISTER,
        investment_asset_profile_id=_BUCKET_ID,
    )
    full_scan = aggregate_iva_ledger_observations(catalogue, period=_Q2_2026)

    # Declared-value invariance: observations and prorrata references are
    # identical SETS between the two paths (order may differ: full-scan
    # iterates catalogue insertion order, partitioned iterates sorted ids).
    assert set(partitioned.observations) == set(full_scan.observations)
    assert set(partitioned.prorrata_references) == set(full_scan.prorrata_references)
    assert {o.ledger_id for o in partitioned.observations} == {q2_row_a.transaction_id, q2_row_b.transaction_id}

    # Permitted delta: repository-backed partitioning reports one compact
    # out-of-window summary, while full-scan refines by row after decryption.
    assert partitioned.issues == ()
    assert partitioned.out_of_window_summary is not None
    assert partitioned.out_of_window_summary.count == 3
    assert partitioned.out_of_window_summary.min_filing_date == date(2026, 2, 1)
    assert partitioned.out_of_window_summary.max_filing_date == date(2026, 9, 1)

    full_scan_ids_with_issues = {i.transaction_id for i in full_scan.issues}
    assert full_scan_ids_with_issues == {q1_row.transaction_id, q3_row.transaction_id}
    assert all(i.reason is IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD for i in full_scan.issues)
    # excluded_q3_row is silently skipped by full-scan (no issue) but surfaces
    # under the partitioned path.
    assert excluded_q3_row.transaction_id not in full_scan_ids_with_issues


def test_internal_transfer_is_reported_as_unsupported_direction() -> None:
    transaction = _transaction(
        "row-transfer",
        amount=Decimal("10.00"),
        direction=TransactionDirection.INTERNAL_TRANSFER,
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert result.observations == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION


def test_missing_base_and_amount_are_reported_as_distinct_tax_fact_issues() -> None:
    missing_base = _transaction("row-missing-base", taxable_base=None)
    missing_amount = _transaction("row-missing-amount", iva_amount=None)

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((missing_base, missing_amount)),
        period=_Q2_2026,
    )

    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE,
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT,
    ]


def test_a_date_outside_the_rate_table_blames_the_year_not_the_rate() -> None:
    """21 % before September 2012 is a correct rate; only the date is unsupported.

    A row outside the table's coverage cannot be classified whatever rate it
    carries. This previously reported ``UNSUPPORTED_IVA_RATE``, which told the
    filer that the one figure they had right was wrong and sent them to correct
    it. The two conditions carry separate reasons, and that is what is asserted.

    THE PROBE MOVED FROM 2023 TO 2012, and the docstring's old premise -- "the
    rate table holds CURRENT rates, no member state has a record before 2024" --
    was not a fact about the law but a defect in the table. ``effective_from``
    carried a bulk-refresh boundary, so 2022 and 2023 refused despite sitting
    inside prescripción. Both years now classify correctly, which is the point
    of that correction.

    The distinction under test is untouched and still worth a gate. It has moved
    to where coverage genuinely ends: 21 % was fixed by RDL 20/2012 art. 23.Dos
    with effect from 1 September 2012, and the table carries nothing before it.
    """
    transaction = _transaction(
        "row-pre-registry",
        booked_date=date(1994, 4, 5),
        value_date=date(1994, 4, 5),
        iva_rate=Decimal("0.21"),
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_1994,
    )

    assert result.observations == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.IVA_RATE_DATE_OUTSIDE_TABLE_COVERAGE
    assert "filing year is outside the supported window" in result.issues[0].detail
    # The 21 % is named as NOT the thing to correct -- a filer who reads only
    # the number in the message must not go looking for a rate error.
    assert "not what needs correcting" in result.issues[0].detail
    # The message must not describe the table's extent in terms a data change
    # can falsify. It once said the table "holds current rates only", which was
    # true when written and stopped being true the moment the windows were
    # corrected back to 2012 -- with nothing tying the sentence to the data it
    # described. It now states the condition the branch actually tested.
    assert "current rates only" not in result.issues[0].detail
    assert "no tier bearing a positive rate" in result.issues[0].detail


def test_the_applied_rate_survives_tier_resolution() -> None:
    """Two lines of one tier at different rates stay distinguishable.

    Modelo 390 carries one box per rate per window where Modelo 303 carries one
    per tier, because a tier's rate can change inside a filing year. Resolving to
    the tier and discarding the value made those boxes unpopulatable: two lines
    arrived downstream identical apart from their amounts.
    """
    general = _transaction("row-21", iva_rate=Decimal("0.21"), iva_amount=Decimal("21.00"))
    reduced = _transaction("row-10", iva_rate=Decimal("0.10"), iva_amount=Decimal("10.00"))

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((general, reduced)),
        period=_Q2_2026,
    )

    by_rate = {observation.applied_rate: observation for observation in result.observations}
    assert set(by_rate) == {Decimal("0.21"), Decimal("0.10")}
    # The tier is still carried, unchanged -- the value rides ALONGSIDE it, and a
    # reader must not conclude one replaced the other.
    assert by_rate[Decimal("0.21")].rate_kind is IvaRateKind.GENERAL
    assert by_rate[Decimal("0.10")].rate_kind is IvaRateKind.REDUCED


def test_a_covered_date_with_a_non_canonical_rate_still_blames_the_rate() -> None:
    """The discriminator's other side: inside coverage, the rate is the fault.

    Without this the new reason could swallow both conditions and the split
    would buy nothing -- a genuinely wrong rate must still say so.
    """
    transaction = _transaction(
        "row-bad-rate-covered",
        iva_rate=Decimal("0.13"),
        iva_amount=Decimal("13.00"),
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert result.observations == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE


def test_zero_and_super_reduced_rates_project_to_canonical_iva_categories() -> None:
    zero = _transaction("row-zero", taxable_base=Decimal("100.00"), iva_rate=Decimal("0"), iva_amount=Decimal("0"))
    super_reduced = _transaction(
        "row-super",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.04"),
        iva_amount=Decimal("4.00"),
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((zero, super_reduced)),
        period=_Q2_2026,
    )

    assert [observation.category for observation in result.observations] == [
        IvaCategory.DOMESTIC_ZERO,
        IvaCategory.DOMESTIC_SUPER_REDUCED,
    ]


def test_transaction_exemption_article_projects_to_iva_observation() -> None:
    transaction = _transaction(
        "row-art-20-8",
        amount=Decimal("400.00"),
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("400.00"),
        iva_rate=Decimal("0"),
        iva_amount=Decimal("0"),
        iva_category=IvaCategory.DOMESTIC_EXEMPT,
        exemption_article=IvaExemptionArticle.ART_20_UNO_8,
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2026,
    )

    assert result.issues == ()
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.category is IvaCategory.DOMESTIC_EXEMPT
    assert observation.ledger_id == transaction.transaction_id
    assert observation.exemption_article is IvaExemptionArticle.ART_20_UNO_8


def test_projected_observations_feed_modelo_303_binding_resolver() -> None:
    incoming = _transaction(
        "row-output",
        amount=Decimal("121.00"),
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )
    outgoing = _transaction(
        "row-input",
        taxable_base=Decimal("50.00"),
        iva_rate=Decimal("0.10"),
        iva_amount=Decimal("5.00"),
    )
    projection = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((incoming, outgoing)),
        period=_Q2_2026,
    )
    revision = _modelo_303_iva_revision()

    binding_values = resolve_ledger_iva_aggregation_binding_values(revision, projection.observations)

    assert binding_values["modelo-303-iva-repercutido-general-cuota"] == incoming.iva_amount
    assert binding_values["modelo-303-iva-soportado-interiores-cuota"] == outgoing.iva_amount


def test_a_two_percent_food_sale_reaches_the_super_reducido_cuota() -> None:
    """A rate the engine used to refuse now flows from transaction to binding value.

    The acceptance test for the whole temporary-rate chain, driven from a real
    transaction so every link is exercised: the rate record must exist, the
    classifier must resolve 2 % to super-reducido on that date, and the M390
    binding must aggregate it. Before the records existed this row was rejected
    as an unsupported rate and contributed nothing to any form.

    Started from a transaction rather than a hand-built observation
    deliberately. An observation carries ``rate_kind`` as a field, so
    constructing one directly sets by hand the very thing the rate table is
    supposed to decide -- a test written that way passes with the rate record
    deleted, which is exactly what a first attempt at this did.
    """
    food = _transaction(
        "food-2pct",
        booked_date=date(2024, 11, 15),
        value_date=date(2024, 11, 15),
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("0.02"),
        iva_amount=Decimal("20.00"),
        direction=TransactionDirection.INCOMING,
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((food,)),
        period=_period(2024, "4T"),
    )

    assert result.observations != (), f"the 2 % sale was refused: {[i.reason for i in result.issues]}"
    observation = result.observations[0]
    assert observation.rate_kind is IvaRateKind.SUPER_REDUCED
    assert observation.applied_rate == Decimal("0.02")


def test_the_same_sale_dated_after_the_measure_expired_is_refused() -> None:
    """The window is load-bearing, not decorative.

    Without this the rate records could be open-ended and the test above would
    still pass. A 2 % sale in June 2025 is not a legitimate Spanish rate.
    """
    late = _transaction(
        "food-2pct-expired",
        booked_date=date(2025, 6, 15),
        value_date=date(2025, 6, 15),
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("0.02"),
        iva_amount=Decimal("20.00"),
        direction=TransactionDirection.INCOMING,
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((late,)),
        period=_period(2025, "2T"),
    )

    assert result.observations == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE
