"""Modelo 151 impatriado (Ley Beckham) Spanish-source base aggregation tests.

The régimen especial del art. 93 LIRPF (Ley Beckham) taxes a resident
impatriado by the IRNR scope rules: only Spanish-source income enters the base
liquidable general (art. 93.2, art. 25.1.f TRLIRNR segregation). These tests
prove the source-scope classifier consumes the per-row ``source_jurisdiction``
axis the CLI compels an impatriado to declare:

- an ES-source row folds into ``impatriado.base-liquidable-general``;
- a foreign-source row is segregated (BECKHAM_FOREIGN_SOURCE_SEGREGATED) and
  does NOT silently enter the base — an anti-tautology mutation flips the same
  row's jurisdiction and asserts the base drops and the issue fires;
- a ``source_jurisdiction is None`` row fails loud as the same segregation
  issue rather than being silently coerced to ES (no-silent-under-declaration);
- ``trabajo`` income (nómina — the class the M130 pipeline routes OUT) IS
  admitted into the impatriado base, while the same row is still excluded from
  the M130 actividad-económica casilla.

The expected base is derived from the art. 93.2 source-scope rule (which amounts
are in scope), not by re-running the aggregation arithmetic — a scope/structure
assertion, per aeat-quality-gates.

See Also:
    :mod:`~application.aggregation._impatriado_income_ledger`
        Application classifier that consumes ``source_jurisdiction`` for Modelo
        151 Spanish-source income.
    :func:`~application.aggregation._impatriado_income_ledger.aggregate_impatriado_income_ledger`
        Pure aggregation entry point exercised by the source-scope cases.
    :func:`~application.aggregation._impatriado_income_ledger.aggregate_impatriado_income_ledger_from_repositories`
        Repository-backed entry point covered by the bucket roundtrip cases.
    :func:`~domain.calculations.registry.resolve_ledger_impatriado_income_aggregation_binding_values`
        Registry binding resolver that turns source-scoped observations into
        Modelo 151 binding values.
    :class:`~domain.transactions.Transaction`
        Ledger record carrying the per-row ``source_jurisdiction`` axis.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core import Period
from ....domain.calculations.registry import (
    BindingId,
    ModeloRevision,
    RegistryValidationError,
    bundled_authority,
    resolve_ledger_impatriado_income_aggregation_binding_values,
    validate_ledger_impatriado_income_aggregation_binding_definition,
)
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._impatriado_income_ledger import (
    ImpatriadoIncomeLedgerAggregation,
    ImpatriadoIncomeLedgerAggregationIssueReason,
    aggregate_impatriado_income_ledger,
    aggregate_impatriado_income_ledger_from_repositories,
)
from .._renta_income_ledger import (
    RentaIncomeLedgerAggregationIssueReason,
    aggregate_renta_m100_income_ledger,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ANNUAL_2024 = Period.from_year_and_code(2024, "0A")
_BASE_CASILLA = "impatriado.base-liquidable-general"


def _m151_revision_for(period: Period) -> ModeloRevision:
    """Return the revision AEAT binds to modelo 151 for ``period``.

    The revision is resolved from the period rather than pinned by id: the
    open ``2015-y-siguientes`` span was split into ``2015-2022`` and
    ``2025-y-siguientes``, and every id literal naming the old span stopped
    resolving. Resolution survives the next split; an id literal does not.
    """
    return (
        bundled_authority()
        .snapshot(
            "151",
            filing_year=period.filing_year,
            period=period.registry_token,
        )
        .revision
    )


_BUCKET_ID = "16161616-1616-4616-8616-161616161616"


def _impatriado_transaction(
    provider_id: str,
    *,
    amount: Decimal,
    source_jurisdiction: str | None,
    irpf_category: str | None = "trabajo",
    direction: TransactionDirection = TransactionDirection.INCOMING,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    taxable_base: Decimal | None = None,
    iva_amount: Decimal | None = None,
    value_date: date = date(2024, 3, 1),
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Empleador SA",
                description=f"impatriado income {provider_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="a" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2024, 4, 6, 12, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": provider_id},
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": source_jurisdiction,
            "business_classification": business_classification,
            "business_pct": business_pct,
            "taxable_base": taxable_base,
            "iva_amount": iva_amount,
            "irpf_category": irpf_category,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _base_total(aggregation: ImpatriadoIncomeLedgerAggregation) -> Decimal:
    values = aggregation.casilla_aggregation.casilla_values
    return next((v for c, v in values.items() if str(c) == _BASE_CASILLA), Decimal("0"))


def test_es_source_income_folds_into_impatriado_base() -> None:
    """An ES-source trabajo row enters the impatriado base liquidable general."""
    tx = _impatriado_transaction("es-001", amount=Decimal("50000.00"), source_jurisdiction="ES")
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_impatriado_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)

    assert len(result.observations) == 1
    assert result.observations[0].transaction_id == tx.transaction_id
    assert result.observations[0].source_jurisdiction == "ES"
    # Base equals the single ES amount — derived from the art. 93.2 scope rule.
    assert _base_total(result) == Decimal("50000.00")
    assert not result.issues


def test_foreign_source_row_is_segregated_and_excluded() -> None:
    """A foreign-source row is segregated out of the base, never silently admitted.

    Anti-tautology: the SAME row with source_jurisdiction="ES" enters the base;
    mutating only the jurisdiction to a foreign code drops it from the base and
    fires the BECKHAM_FOREIGN_SOURCE_SEGREGATED issue carrying the rejected code.
    """
    es_row = _impatriado_transaction("row-es", amount=Decimal("40000.00"), source_jurisdiction="ES")
    fr_row = _impatriado_transaction("row-fr", amount=Decimal("40000.00"), source_jurisdiction="FR")

    admitted = aggregate_impatriado_income_ledger(
        TransactionCatalogue.from_transactions((es_row,)),
        bucket_id="test",
        period=_ANNUAL_2024,
    )
    segregated = aggregate_impatriado_income_ledger(
        TransactionCatalogue.from_transactions((fr_row,)),
        bucket_id="test",
        period=_ANNUAL_2024,
    )

    # ES admits; the identical foreign row is fully excluded from the base.
    assert _base_total(admitted) == Decimal("40000.00")
    assert _base_total(segregated) == Decimal("0")
    assert not segregated.observations
    assert len(segregated.issues) == 1
    issue = segregated.issues[0]
    assert issue.reason is ImpatriadoIncomeLedgerAggregationIssueReason.BECKHAM_FOREIGN_SOURCE_SEGREGATED
    assert issue.rejected_source_jurisdiction == "FR"
    assert issue.transaction_id == fr_row.transaction_id


def test_none_jurisdiction_fails_loud_never_silently_es() -> None:
    """A None source_jurisdiction fails loud as a segregation issue, not an ES default.

    This is the load-bearing no-silent-under-declaration safeguard: an
    unresolved jurisdiction must NOT be coerced to ES and silently admitted.
    """
    tx = _impatriado_transaction("unresolved-001", amount=Decimal("70000.00"), source_jurisdiction=None)
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_impatriado_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)

    assert not result.observations
    assert _base_total(result) == Decimal("0")
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.reason is ImpatriadoIncomeLedgerAggregationIssueReason.BECKHAM_FOREIGN_SOURCE_SEGREGATED
    # Distinguishable from a foreign-source segregation: no rejected code.
    assert issue.rejected_source_jurisdiction is None
    assert "unresolved" in issue.detail.lower()


def test_trabajo_income_admitted_into_m151_base_but_excluded_from_m130() -> None:
    """A trabajo (nómina) ES-source row feeds the M151 base yet stays out of M130.

    The impatriado base is predominantly rendimientos del trabajo — the exact
    income class the M130 actividad-económica pipeline routes OUT via
    TRABAJO_INCOME. This proves the two pipelines are complementary.
    """
    nomina = _impatriado_transaction(
        "nomina-001",
        amount=Decimal("90000.00"),
        source_jurisdiction="ES",
        irpf_category="trabajo",
    )
    catalogue = TransactionCatalogue.from_transactions((nomina,))

    m151 = aggregate_impatriado_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)
    assert _base_total(m151) == Decimal("90000.00")
    assert len(m151.observations) == 1

    # Same row through the M130 / M100 actividad-económica pipeline is excluded.
    m130 = aggregate_renta_m100_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)
    assert not m130.observations
    assert any(issue.reason is RentaIncomeLedgerAggregationIssueReason.TRABAJO_INCOME for issue in m130.issues)


def test_outgoing_row_is_not_owned_by_the_impatriado_base_pipeline() -> None:
    """An OUTGOING row is out of scope for the base and produces neither obs nor issue."""
    outgoing = _impatriado_transaction(
        "out-001",
        amount=Decimal("500.00"),
        source_jurisdiction="ES",
        direction=TransactionDirection.OUTGOING,
    )
    result = aggregate_impatriado_income_ledger(
        TransactionCatalogue.from_transactions((outgoing,)),
        bucket_id="test",
        period=_ANNUAL_2024,
    )
    assert not result.observations
    assert not result.issues
    assert _base_total(result) == Decimal("0")


def test_registry_binding_resolves_es_source_total_into_base() -> None:
    """The M151 registry binding resolves the ES-source observation total end to end.

    Loads the real M151 revision (with the ledger_impatriado_income_aggregation
    binding), aggregates a mixed ES/foreign catalogue, and asserts the binding
    value equals the ES-source total — segregated foreign income never reaches it.
    """
    revision = _m151_revision_for(_ANNUAL_2024)
    es_row = _impatriado_transaction("bind-es", amount=Decimal("120000.00"), source_jurisdiction="ES")
    foreign_row = _impatriado_transaction("bind-de", amount=Decimal("55000.00"), source_jurisdiction="DE")
    catalogue = TransactionCatalogue.from_transactions((es_row, foreign_row))

    aggregation = aggregate_impatriado_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)
    resolved = resolve_ledger_impatriado_income_aggregation_binding_values(revision, aggregation.observations)

    binding_id: BindingId = "modelo-151-impatriado-base-liquidable-general"
    assert resolved[binding_id] == Decimal("120000.00")


def _mixed_and_business_binding_values() -> tuple[Decimal, Decimal]:
    """Resolve the M151 base binding for one receipt classified BUSINESS, then MIXED.

    One invoice, two classifications, driven end to end from a
    :class:`~domain.transactions.Transaction` through the real aggregation and
    the real registry binding, so nothing under test is hand-built.
    """
    revision = _m151_revision_for(_ANNUAL_2024)
    binding_id: BindingId = "modelo-151-impatriado-base-liquidable-general"
    resolved: list[Decimal] = []
    for classification, pct in (
        (BusinessClassification.BUSINESS, None),
        (BusinessClassification.MIXED, Decimal("0.5")),
    ):
        row = _impatriado_transaction(
            "affectation-row",
            # 2000 base + 420 IVA on one Spanish-source activity receipt.
            amount=Decimal("2420.00"),
            source_jurisdiction="ES",
            irpf_category="actividad_economica",
            business_classification=classification,
            business_pct=pct,
            taxable_base=Decimal("2000.00"),
            iva_amount=Decimal("420.00"),
        )
        aggregation = aggregate_impatriado_income_ledger(
            TransactionCatalogue.from_transactions((row,)),
            bucket_id="test",
            period=_ANNUAL_2024,
        )
        resolved.append(
            resolve_ledger_impatriado_income_aggregation_binding_values(revision, aggregation.observations)[binding_id],
        )
    return resolved[0], resolved[1]


def test_partial_affectation_never_divides_the_impatriado_base() -> None:
    """A MIXED classification must not shrink the impatriado base of one receipt.

    Art. 93.2 LIRPF determines the impatriado's deuda tributaria by the TRLIRNR
    rules for rentas obtained without establecimiento permanente, and TRLIRNR
    art. 24.1 (RDLeg 5/2004) fixes that base as "su importe íntegro ... sin que
    sean de aplicación los porcentajes multiplicadores ni las reducciones". A
    business-usage percentage applied to an ingreso is exactly such a porcentaje
    multiplicador, so the same receipt declares the same base under either
    classification.

    Asserted at the BINDING the M151 filing reads, not at the observation, and
    expressed as an equality between two classifications rather than against a
    figure recomputed from the code under test.
    """
    business_base, mixed_base = _mixed_and_business_binding_values()

    assert mixed_base == business_base
    # Pins the shared figure to the invoice's own IVA-exclusive base imponible,
    # so the equality above cannot be satisfied by both halving.
    assert business_base == Decimal("2000.00")


def test_repository_backed_aggregation_reports_out_of_period_catalogue_transactions(
    tmp_path: Path,
) -> None:
    """A catalogue transaction outside the requested ejercicio must surface as a summary.

    Regression test: the repository-backed entry point must NOT
    silently drop out-of-window rows. The compact summary keeps the operator
    visibility signal without allocating one issue per plaintext index entry.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        in_period = _impatriado_transaction(
            "row-in-period",
            amount=Decimal("30000.00"),
            source_jurisdiction="ES",
            value_date=date(2024, 6, 1),
        )
        out_of_period = _impatriado_transaction(
            "row-out-of-period",
            amount=Decimal("45000.00"),
            source_jurisdiction="ES",
            value_date=date(2025, 1, 15),
        )
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((in_period, out_of_period)))

        result = aggregate_impatriado_income_ledger_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_ANNUAL_2024,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository),
        )

    assert {o.transaction_id for o in result.observations} == {in_period.transaction_id}
    assert _base_total(result) == Decimal("30000.00")
    assert result.issues == ()
    assert result.out_of_window_summary is not None
    assert result.out_of_window_summary.count == 1
    assert result.out_of_window_summary.min_filing_date == date(2025, 1, 15)
    assert result.out_of_window_summary.max_filing_date == date(2025, 1, 15)


def test_repository_backed_aggregation_summarizes_previously_silent_out_of_window_rows(
    tmp_path: Path,
) -> None:
    """Out-of-window rows surface as one compact period-exclusion summary.

    A wrong-direction outgoing row is ignored by the in-window classifier
    because this aggregation owns incoming rows. When that same row falls
    outside the requested ejercicio, the repository-backed partition reports
    its count and date span instead of dropping it before aggregation.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        in_year = _impatriado_transaction(
            "row-in-year",
            amount=Decimal("20000.00"),
            source_jurisdiction="ES",
            value_date=date(2024, 3, 1),
        )
        wrong_direction_out_of_year = _impatriado_transaction(
            "row-wrong-direction-out-of-year",
            amount=Decimal("15000.00"),
            source_jurisdiction="ES",
            value_date=date(2025, 2, 1),
            direction=TransactionDirection.OUTGOING,
        )
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((in_year, wrong_direction_out_of_year)))

        result = aggregate_impatriado_income_ledger_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_ANNUAL_2024,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository),
        )

    assert {o.transaction_id for o in result.observations} == {in_year.transaction_id}
    assert result.issues == ()
    assert result.out_of_window_summary is not None
    assert result.out_of_window_summary.count == 1
    assert result.out_of_window_summary.min_filing_date == date(2025, 2, 1)
    assert result.out_of_window_summary.max_filing_date == date(2025, 2, 1)


def test_repository_backed_aggregation_partition_matches_full_scan(
    tmp_path: Path,
) -> None:
    """The partitioned result matches the full-scan result for declared values.

    The same multi-year catalogue is aggregated once through the
    repository-backed partition and once through the pure full-scan aggregator.
    In-window observations and casilla totals/provenance must match; only the
    out-of-window diagnostic shape can differ. The full-scan path keeps row
    reasons, while the partition reports a compact count and date span.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        in_year = _impatriado_transaction(
            "row-parity-in-year",
            amount=Decimal("20000.00"),
            source_jurisdiction="ES",
            value_date=date(2024, 3, 1),
        )
        out_of_year = _impatriado_transaction(
            "row-parity-out-of-year",
            amount=Decimal("10000.00"),
            source_jurisdiction="ES",
            value_date=date(2025, 1, 15),
        )
        foreign_out_of_year = _impatriado_transaction(
            "row-parity-foreign-out-of-year",
            amount=Decimal("5000.00"),
            source_jurisdiction="FR",
            value_date=date(2023, 6, 1),
        )
        catalogue = TransactionCatalogue.from_transactions((in_year, out_of_year, foreign_out_of_year))
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(catalogue)

        partitioned = aggregate_impatriado_income_ledger_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_ANNUAL_2024,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository),
        )
        full_scan = aggregate_impatriado_income_ledger(catalogue, bucket_id=_BUCKET_ID, period=_ANNUAL_2024)

    assert set(partitioned.observations) == set(full_scan.observations)
    assert partitioned.casilla_aggregation.casilla_values == full_scan.casilla_aggregation.casilla_values
    assert set(partitioned.casilla_aggregation.provenance) == set(full_scan.casilla_aggregation.provenance)
    assert {o.transaction_id for o in partitioned.observations} == {in_year.transaction_id}

    assert partitioned.issues == ()
    assert partitioned.out_of_window_summary is not None
    assert partitioned.out_of_window_summary.count == 2
    assert partitioned.out_of_window_summary.min_filing_date == date(2023, 6, 1)
    assert partitioned.out_of_window_summary.max_filing_date == date(2025, 1, 15)

    full_scan_issue_ids = {i.transaction_id for i in full_scan.issues}
    assert full_scan_issue_ids == {out_of_year.transaction_id, foreign_out_of_year.transaction_id}
    full_scan_by_id = {i.transaction_id: i for i in full_scan.issues}
    assert (
        full_scan_by_id[out_of_year.transaction_id].reason
        is ImpatriadoIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD
    )
    assert (
        full_scan_by_id[foreign_out_of_year.transaction_id].reason
        is ImpatriadoIncomeLedgerAggregationIssueReason.BECKHAM_FOREIGN_SOURCE_SEGREGATED
    )


def test_registry_binding_definition_validates_and_rejects_wrong_casilla() -> None:
    """The build-time validator accepts the shipped binding and rejects an off-target one."""
    revision = _m151_revision_for(_ANNUAL_2024)
    binding = next(b for b in revision.bindings if b.id == "modelo-151-impatriado-base-liquidable-general")
    # Shipped binding validates.
    validate_ledger_impatriado_income_aggregation_binding_definition(binding)

    # A binding targeting a non-base casilla is rejected (anti-tautology: the
    # validator is not vacuously passing).
    off_target = binding.model_copy(
        update={
            "selector": {
                "modelo": "151",
                "target_casilla_id": "impatriado.retenciones",
                "fact": "ingresos_integros_sum",
            },
        },
    )
    with pytest.raises(RegistryValidationError, match="outside the supported"):
        validate_ledger_impatriado_income_aggregation_binding_definition(off_target)
