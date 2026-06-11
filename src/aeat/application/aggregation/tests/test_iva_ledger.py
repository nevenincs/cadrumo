"""Tests for bucket-local IVA ledger observation projection."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.resources import resources
from ....domain.calculations.registry import resolve_ledger_iva_aggregation_binding_values
from ....domain.iva import IvaCategory, IvaFlowDirection, IvaRateKind, ProrrataKind, ProrrataRegime
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    AggregationValidationError,
    IvaLedgerAggregationIssueReason,
    IvaLedgerCandidate,
    IvaLedgerInputKind,
    Period,
    aggregate_iva_ledger_candidate_bindings,
    aggregate_iva_ledger_candidates,
    aggregate_iva_ledger_observations,
    aggregate_iva_ledger_observations_from_repositories,
    validate_iva_ledger_observation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_token(year=year, token=code)


_Q2_2023 = _period(2023, "2T")
_Q2_2026 = _period(2026, "2T")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile.repository


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 4, 5),
    value_date: date | None = date(2026, 4, 5),
    amount: Decimal = Decimal("121.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
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
) -> Transaction:
    # Keep the gross consistent with base + iva (the Transaction
    # gross == taxable_base + iva_amount invariant). When the caller does not
    # pin an explicit amount and both tax fields are present, derive the
    # IVA-inclusive gross magnitude from them; flow is carried by ``direction``.
    if amount is None:
        amount = taxable_base + iva_amount if taxable_base is not None and iva_amount is not None else Decimal("121.00")
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
            "business_classification": business_classification,
            "business_pct": business_pct,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "prorrata_reference": prorrata_reference,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


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
    assert observation.category is IvaCategory.DOMESTIC_GENERAL_21
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
    assert observation.category is IvaCategory.DOMESTIC_REDUCED_10
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


def test_iva_aggregation_buckets_on_value_date_caja_basis_only() -> None:
    """Document the confirmed CAJA-only aggregation basis (no devengo selector).

    The ledger keys a transaction into a filing period on a single
    ``value_date or booked_date`` axis — a CASH (caja) basis. There is no
    accrual/devengo basis selector anywhere in the aggregation surface.

    This is a *documentation* test: it pins the current, intentionally
    single-basis behaviour so the future devengo follow-on (#58) has a
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


def test_no_devengo_basis_selector_exists_on_iva_aggregation_surface() -> None:
    """Assert the absence of any accrual/devengo basis selector (caja-only).

    Confirms (against the live module/signature, re-read at runtime) that
    neither the public IVA-aggregation entry points nor their parameters
    expose a ``basis``/``devengo``/``accrual`` axis. Caja is the only basis.
    The future devengo design (#58) will add such a selector; until then this
    test fails RED the moment a basis selector is introduced without the
    accompanying behaviour and tests.
    """
    import inspect

    from .. import _iva_ledger

    forbidden_tokens = ("devengo", "accrual", "basis")
    for entry_point in (
        _iva_ledger.aggregate_iva_ledger_observations,
        _iva_ledger.aggregate_iva_ledger_observations_from_repositories,
        _iva_ledger.aggregate_iva_ledger_candidates,
    ):
        params = inspect.signature(entry_point).parameters
        assert not any(token in name.lower() for name in params for token in forbidden_tokens), (
            f"{entry_point.__name__} unexpectedly grew a basis selector parameter: {tuple(params)}"
        )

    # No basis-selector symbol is exported from the aggregation package surface.
    assert not any(token in symbol.lower() for symbol in _iva_ledger.__all__ for token in forbidden_tokens), (
        _iva_ledger.__all__
    )


def test_repository_backed_projection_rejects_bucket_mismatch_before_loading(
    secure_objects: SecureObjectRepository,
) -> None:
    with pytest.raises(AggregationValidationError, match="bucket_mismatch"):
        aggregate_iva_ledger_observations_from_repositories(
            bucket_id="bucket-a",
            period=_Q2_2026,
            transaction_repository=TransactionCatalogueRepository(
                bucket_id="bucket-b",
                objects=secure_objects,
            ),
        )


def test_repository_backed_projection_loads_persisted_bucket_catalogue(secure_objects: SecureObjectRepository) -> None:
    transaction = _transaction("row-repository")
    repository = TransactionCatalogueRepository(
        bucket_id="bucket-a",
        objects=secure_objects,
    )
    repository.save(TransactionCatalogue.from_transactions((transaction,)))

    result = aggregate_iva_ledger_observations_from_repositories(
        bucket_id="bucket-a",
        period=_Q2_2026,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id="bucket-a",
            objects=secure_objects,
        ),
    )

    assert result.issues == ()
    assert result.observations[0].ledger_id == transaction.transaction_id


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


def test_dated_iva_registry_gap_is_reported_as_unsupported_rate() -> None:
    transaction = _transaction(
        "row-pre-registry",
        booked_date=date(2023, 4, 5),
        value_date=date(2023, 4, 5),
        iva_rate=Decimal("0.21"),
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period=_Q2_2023,
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
        IvaCategory.DOMESTIC_SUPER_REDUCED_4,
    ]


def test_preclassified_candidates_cover_non_domestic_exempt_recargo_and_adjustments() -> None:
    candidates = (
        IvaLedgerCandidate(
            ledger_id="exempt-consulting",
            transaction_date=date(2026, 4, 10),
            category=IvaCategory.DOMESTIC_EXEMPT,
            rate_kind=IvaRateKind.EXEMPT,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("400.00"),
            iva_amount=Decimal("0.00"),
        ),
        IvaLedgerCandidate(
            ledger_id="eu-acquisition",
            transaction_date=date(2026, 4, 11),
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            base_amount=Decimal("200.00"),
            iva_amount=Decimal("42.00"),
        ),
        IvaLedgerCandidate(
            ledger_id="retail-recargo",
            transaction_date=date(2026, 4, 12),
            category=IvaCategory.RECARGO_EQUIVALENCIA,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("5.20"),
        ),
        IvaLedgerCandidate(
            ledger_id="prior-period-adjustment",
            transaction_date=date(2026, 4, 13),
            category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
            rate_kind=IvaRateKind.ZERO,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("-50.00"),
            iva_amount=Decimal("0.00"),
            input_kind=IvaLedgerInputKind.ADJUSTMENT,
        ),
    )

    result = aggregate_iva_ledger_candidates(candidates, period=_Q2_2026)

    assert result.issues == ()
    assert [observation.category for observation in result.observations] == [
        IvaCategory.DOMESTIC_EXEMPT,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        IvaCategory.RECARGO_EQUIVALENCIA,
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
    ]
    assert result.observations[-1].base_amount == Decimal("-50.00")


def test_preclassified_candidates_feed_modelo_309_recargo_and_reverse_charge_bindings() -> None:
    revision = next(item for item in resources().modelos.all() if item.id == "309").revisions["2004-y-siguientes"]
    candidates = (
        IvaLedgerCandidate(
            ledger_id="eu-acquisition",
            transaction_date=date(2026, 4, 11),
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            base_amount=Decimal("200.00"),
            iva_amount=Decimal("42.00"),
        ),
        IvaLedgerCandidate(
            ledger_id="retail-recargo",
            transaction_date=date(2026, 4, 12),
            category=IvaCategory.RECARGO_EQUIVALENCIA,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("5.20"),
        ),
    )

    binding_values = aggregate_iva_ledger_candidate_bindings(revision, candidates, period=_Q2_2026)

    assert binding_values["modelo-309-iva-autorepercutido-intracomunitaria-cuota"] == Decimal("42.00")
    assert binding_values["modelo-309-iva-soportado-recargo-equivalencia-cuota"] == Decimal("5.20")


def test_preclassified_candidate_blocks_unsupported_modelo_390_regime() -> None:
    revision = next(item for item in resources().modelos.all() if item.id == "390").revisions["2010-y-siguientes"]
    candidate = IvaLedgerCandidate(
        ledger_id="retail-recargo",
        transaction_date=date(2026, 4, 12),
        category=IvaCategory.RECARGO_EQUIVALENCIA,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.SOPORTADO,
        base_amount=Decimal("100.00"),
        iva_amount=Decimal("5.20"),
    )

    with pytest.raises(AggregationValidationError, match="unsupported_iva_category") as exc_info:
        aggregate_iva_ledger_candidate_bindings(revision, (candidate,), period=_Q2_2026)

    assert exc_info.value.context is not None
    assert exc_info.value.context["ledger_id"] == "retail-recargo"
    assert exc_info.value.context["category"] == IvaCategory.RECARGO_EQUIVALENCIA.value
    assert exc_info.value.context["revision_id"] == "2010-y-siguientes"


def test_preclassified_candidate_rejects_non_declarable_sentinel_category() -> None:
    candidate = IvaLedgerCandidate(
        ledger_id="unknown-row",
        transaction_date=date(2026, 4, 10),
        category=IvaCategory.UNKNOWN,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        base_amount=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )

    with pytest.raises(AggregationValidationError, match="unsupported_iva_category"):
        validate_iva_ledger_observation(candidate)


def test_preclassified_candidate_outside_period_blocks_binding_resolution() -> None:
    revision = next(item for item in resources().modelos.all() if item.id == "309").revisions["2004-y-siguientes"]
    candidate = IvaLedgerCandidate(
        ledger_id="late-row",
        transaction_date=date(2026, 7, 1),
        category=IvaCategory.RECARGO_EQUIVALENCIA,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.SOPORTADO,
        base_amount=Decimal("100.00"),
        iva_amount=Decimal("5.20"),
    )

    with pytest.raises(AggregationValidationError, match="candidate_outside_period"):
        aggregate_iva_ledger_candidate_bindings(revision, (candidate,), period=_Q2_2026)


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
    modelos = resources().modelos.all()
    revision = next(item for item in modelos if item.id == "303").revisions["2009-y-siguientes"]

    binding_values = resolve_ledger_iva_aggregation_binding_values(revision, projection.observations)

    assert binding_values["modelo-303-iva-repercutido-general-cuota"] == incoming.iva_amount
    assert binding_values["modelo-303-iva-soportado-interiores-cuota"] == outgoing.iva_amount
