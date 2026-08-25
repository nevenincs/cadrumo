"""Renta income source-jurisdiction and M100 annual aggregation tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ._secure_objects_fixtures import SECURE_OBJECTS_BUCKET_ID, secure_objects

__all__ = ["secure_objects"]

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.resources import resources
from ....domain.calculations.registry import resolve_ledger_renta_income_aggregation_binding_values
from ....domain.transactions import TransactionCatalogue
from .._renta_income_ledger import (
    RentaIncomeLedgerAggregationIssueReason,
    aggregate_renta_income_ledger,
    aggregate_renta_m100_income_ledger,
    aggregate_renta_m100_income_ledger_from_repositories,
)
from ._renta_income_aggregation_support import (
    _ANNUAL_2024,
    _M100_ACTIVIDAD_ECONOMICA_INGRESOS_CASILLA,
    _M130_INGRESOS_CASILLA,
    _Q1_2024,
    _actividad_transaction_with_source,
    _income_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# Source-jurisdiction provenance pass-through.
#
# LIRPF Art. 8 establishes the universal-base presumption for Spanish-
# resident taxpayers: M100 / M130 actividad-económica income aggregates
# ALL source jurisdictions into the same base, with foreign-source rows
# carrying their declared jurisdiction through for audit. The IRNR /
# Beckham per-row gating concerns (Art. 25 TRLIRNR, Art. 93.5 LIRPF)
# belong on the IRNR / M151 engines, not this one; on the
# resident-IRPF surface the source_jurisdiction is provenance only.
# ---------------------------------------------------------------------------


def test_renta_income_observation_preserves_es_source_jurisdiction() -> None:
    """A Spanish-source actividad row carries source_jurisdiction="ES" on the observation.

    Provenance witness for the M100 / M130 income pipeline. The
    aggregation does NOT filter on source_jurisdiction (Art. 8 universal-
    base presumption); it propagates the declared value from the ledger
    row onto the typed observation so downstream auditors and the future
    IRNR / Beckham engines can read the jurisdiction without retrofitting
    the read-side.
    """
    tx = _actividad_transaction_with_source(
        "ae-es-001",
        value_date=date(2024, 2, 1),
        amount=Decimal("3000.00"),
        source_jurisdiction="ES",
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    assert len(result.observations) == 1
    assert result.observations[0].source_jurisdiction == "ES"


def test_renta_income_aggregation_mixes_es_and_foreign_source() -> None:
    """LIRPF Art. 8: ES and foreign-source rows BOTH enter the M130 base; jurisdictions distinct.

    The universal-base presumption (LIRPF Art. 8.1) taxes Spanish residents
    on worldwide income, so a foreign-source row from an FR client must
    aggregate into casilla 01 alongside ES rows. This test guards against
    a future "clean-up" refactor that filters foreign-source out of the
    resident-IRPF surface — that would silently under-state the base for
    every resident with cross-border income (Pedro intracom, Olivia UK
    landlord pre-IRNR move, etc.).

    Distinct-preservation: both observations must carry their declared
    jurisdiction; collapsing both to "ES" or to None would lose the audit
    trail and break the future IRNR / Beckham read-side.
    """
    es_amount = Decimal("1000.00")
    fr_amount = Decimal("500.00")
    es_row = _actividad_transaction_with_source(
        "ae-es-002",
        value_date=date(2024, 1, 15),
        amount=es_amount,
        source_jurisdiction="ES",
    )
    fr_row = _actividad_transaction_with_source(
        "ae-fr-001",
        value_date=date(2024, 2, 10),
        amount=fr_amount,
        source_jurisdiction="FR",
    )
    catalogue = TransactionCatalogue.from_transactions((es_row, fr_row))

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    # Art. 8 universal-base: both rows enter the casilla aggregation.
    assert len(result.observations) == 2
    assert result.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == es_amount + fr_amount
    # Distinct-preservation witness: each observation carries its own
    # jurisdiction unchanged.
    by_id = {obs.transaction_id: obs for obs in result.observations}
    assert by_id[es_row.transaction_id].source_jurisdiction == "ES"
    assert by_id[fr_row.transaction_id].source_jurisdiction == "FR"


# ---------------------------------------------------------------------------
# Modelo 100 annual actividad-económica income aggregation (casilla 0171)
# ---------------------------------------------------------------------------


def test_m100_annual_income_sums_full_ejercicio_into_casilla_0171() -> None:
    """The annual M100 path sums actividad income over the full year into 0171.

    Unlike the M130 cumulative-quarter window, the annual window spans Jan 1 to
    Dec 31, so a December receipt is included and the target is the M100 income
    leaf 0171, not the M130 casilla 01.
    """
    jan_amount, dec_amount = Decimal("3000.00"), Decimal("5000.00")
    jan = _income_transaction("m100-jan", value_date=date(2024, 1, 20), amount=jan_amount)
    dec = _income_transaction("m100-dec", value_date=date(2024, 12, 28), amount=dec_amount)
    prior = _income_transaction("m100-prior", value_date=date(2023, 12, 31), amount=Decimal("999.00"))
    catalogue = TransactionCatalogue.from_transactions((jan, dec, prior))

    result = aggregate_renta_m100_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_ANNUAL_2024)

    assert all(o.target_casilla_id == _M100_ACTIVIDAD_ECONOMICA_INGRESOS_CASILLA for o in result.observations)
    assert result.casilla_aggregation.modelo == "100"
    # Prior-year row excluded; in-year receipts summed into 0171.
    assert {o.transaction_id for o in result.observations} == {jan.transaction_id, dec.transaction_id}
    assert result.casilla_aggregation.casilla_values[_M100_ACTIVIDAD_ECONOMICA_INGRESOS_CASILLA] == sum(
        (jan_amount, dec_amount),
        Decimal("0"),
    )
    # Regression: the excluded prior-year row must surface as a
    # visible OUTSIDE_PERIOD issue, not silently vanish.
    assert len(result.issues) == 1
    assert result.issues[0].reason is RentaIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD
    assert result.issues[0].transaction_id == prior.transaction_id


def test_repository_backed_m100_aggregation_reports_out_of_period_catalogue_transactions(
    secure_objects: SecureObjectRepository,
) -> None:
    """A catalogue transaction outside the requested ejercicio must surface as a summary.

    Regression test: the repository-backed M100 entry point must
    not silently drop out-of-window rows. The compact summary keeps the
    visibility signal without allocating one issue per plaintext index entry.
    """
    jan_amount, prior_amount = Decimal("3000.00"), Decimal("999.00")
    jan = _income_transaction("m100-repo-jan", value_date=date(2024, 1, 20), amount=jan_amount)
    prior = _income_transaction("m100-repo-prior", value_date=date(2023, 12, 31), amount=prior_amount)
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((jan, prior)))

    result = aggregate_renta_m100_income_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2024,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
    )

    assert {o.transaction_id for o in result.observations} == {jan.transaction_id}
    assert result.casilla_aggregation.casilla_values[_M100_ACTIVIDAD_ECONOMICA_INGRESOS_CASILLA] == jan_amount
    assert result.issues == ()
    assert result.out_of_window_summary is not None
    assert result.out_of_window_summary.count == 1
    assert result.out_of_window_summary.min_filing_date == date(2023, 12, 31)
    assert result.out_of_window_summary.max_filing_date == date(2023, 12, 31)


def test_repository_backed_m100_aggregation_partition_matches_full_scan(
    secure_objects: SecureObjectRepository,
) -> None:
    """The M100 partitioned result matches the full-scan result for declared values.

    The same multi-year catalogue is aggregated once through the
    repository-backed partition and once through the pure full-scan aggregator.
    In-window observations and casilla totals/provenance must match; only the
    out-of-window issue taxonomy can differ.
    """
    in_year = _income_transaction("m100-parity-in-year", value_date=date(2024, 6, 1), amount=Decimal("4000.00"))
    prior_year = _income_transaction("m100-parity-prior-year", value_date=date(2023, 12, 31), amount=Decimal("999.00"))
    catalogue = TransactionCatalogue.from_transactions((in_year, prior_year))
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(catalogue)

    partitioned = aggregate_renta_m100_income_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2024,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
    )
    full_scan = aggregate_renta_m100_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_ANNUAL_2024)

    assert set(partitioned.observations) == set(full_scan.observations)
    assert partitioned.casilla_aggregation.casilla_values == full_scan.casilla_aggregation.casilla_values
    assert set(partitioned.casilla_aggregation.provenance) == set(full_scan.casilla_aggregation.provenance)
    assert {o.transaction_id for o in partitioned.observations} == {in_year.transaction_id}

    assert partitioned.issues == ()
    assert partitioned.out_of_window_summary is not None
    assert partitioned.out_of_window_summary.count == 1
    assert partitioned.out_of_window_summary.min_filing_date == date(2023, 12, 31)
    assert partitioned.out_of_window_summary.max_filing_date == date(2023, 12, 31)
    assert {i.transaction_id for i in full_scan.issues} == {prior_year.transaction_id}
    assert full_scan.issues[0].reason is RentaIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD


def test_m100_annual_income_rejects_non_annual_period() -> None:
    """The annual M100 income aggregator refuses a quarterly period."""
    from .._errors import AggregationPeriodError

    catalogue = TransactionCatalogue.from_transactions(())
    with pytest.raises(AggregationPeriodError):
        aggregate_renta_m100_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)


def test_m100_revision_binds_0171_to_income_source_and_resolves() -> None:
    """The real M100 2025 revision binds casilla 0171 to the income source and folds it.

    Uses the live registry revision so the binding id, selector, and casilla
    wiring under test are exactly what ships. Expected value derived from the
    input, never copied from engine output.
    """
    modelo_def = resources().modelos.get("100")
    revision = modelo_def.revisions["2025"]
    casilla_0171 = next(c for c in revision.casillas if c.id == _M100_ACTIVIDAD_ECONOMICA_INGRESOS_CASILLA)
    assert str(casilla_0171.input_kind) == "bound"
    binding = next(b for b in revision.bindings if b.id == casilla_0171.binding)
    assert str(binding.source) == "ledger_renta_income_aggregation"

    base = Decimal("4200.00")
    tx = _income_transaction("m100-res", value_date=date(2024, 6, 1), amount=base)
    catalogue = TransactionCatalogue.from_transactions((tx,))
    aggregation = aggregate_renta_m100_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_ANNUAL_2024)

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)
    assert resolved[binding.id] == base
