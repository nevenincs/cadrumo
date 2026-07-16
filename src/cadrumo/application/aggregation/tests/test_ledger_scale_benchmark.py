"""Scale benchmark: P95 latency at 30k-transaction / 10-year ledger scale.

This module seeds a REAL bucket (encrypted SQLite via
:class:`~cadrumo.adapters.persistence.storage.sql.SecureObjectRepository`, no
mocks) with ~30,000 synthetic ledger transactions spread across 10 filing
years, then measures the P95 wall-clock latency of the ledger-scale
operations the budget contract names:

1. **Ledger read diagnostic** — :meth:`TransactionCatalogueRepository.load`, the full
   per-bucket decrypt-and-parse scan every ledger surface (aggregation,
   filtering, CLI listing) builds on. The latency decision scopes this
   unfiltered read out of the 3-second period-operation budget.
2. **Annual renta aggregation diagnostic** —
   :func:`aggregate_renta_ledger_expenses_from_repositories`, which loads the
   full catalogue and then filters by :meth:`~cadrumo.core.Period.contains` for
   one annual window. The latency decision keeps this path out of the
   date-index optimisation until the invoice-date fallback key is resolved.
3. **Quarterly IVA aggregation budget gate** —
   :func:`aggregate_iva_ledger_observations_from_repositories`, the
   partitioned period-scoped path covered by the latency decision.
4. **Modelo calculate diagnostic** —
   :func:`~cadrumo.application.modelo.calculate_modelo_revision_from_bucket_aggregation`
   for a real M130 quarter, exercising the full registry engine over the
   ledger-backed income resolver.

The 3-second budget applies to concrete period-scoped ledger-touching
operations. Unfiltered full-catalogue reads and the annual renta full-scan
path stay visible as diagnostics but are not budget gates in this file.

Real-behaviour, real-adapter: real encrypted-SQLite secure store via
:class:`SecureObjectRepository` + :func:`isolated_runtime_profile`, the real
transaction repository, the real registry authority, the real calculation
engine. No mocks, stubs, skips, or xfail. Marked ``integration`` (real
cross-layer, deterministic, no external I/O) so it is excluded from the
default ``-m unit`` CI lane per the project's marker taxonomy, and run
explicitly via ``uv run pytest -m integration
src/cadrumo/application/aggregation/tests/test_ledger_scale_benchmark.py``.

The report format follows the honesty mandate: budgeted checks assert their
threshold, while diagnostics label their budget scope and keep structural
assertions on the real outputs they exercise.
"""

from __future__ import annotations

import logging
import statistics
import time
from collections.abc import Iterable, Iterator, Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TX_BUCKET_NAMESPACE, TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....application.calculations import CalculationObservationRepository
from ....application.modelo import (
    calculate_modelo_revision_from_bucket_aggregation,
    create_work_unit,
    persist_filed_revision_observation,
)
from ....core import Period
from ....core.hashing import sha256_hex
from ....domain.calculations.registry import CasillaId, RegistryModeloObservation, validated_casilla_id
from ....domain.invoices import InvoiceCatalogue
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
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    aggregate_iva_ledger_observations,
    aggregate_iva_ledger_observations_from_repositories,
    aggregate_renta_ledger_expenses_from_repositories,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "40404040-4040-4040-8040-404040404040"
_TAX_ID = "40404040T"

#: Period-scoped ledger operations complete under 3 seconds at
#: 30k-transaction scale. Unfiltered full-catalogue reads and the annual renta
#: expense path are reported as diagnostics until their separate levers land.
_P95_BUDGET_SECONDS = 3.0

#: The bundled spending-category profile registry only defines 2024/2025 (see
#: ``src/cadrumo/_data/registry/aeat/categories/profiles/``); the renta-ledger
#: aggregation benchmark pins its category-profile lookup to this registered
#: year regardless of the synthetic filing years it aggregates over.
_CATEGORY_PROFILE_YEAR = 2025

#: Total synthetic transaction volume: 30k transactions over 10 filing years.
#: This is the ledger's own scale axis (read / aggregation-filter benchmarks);
#: it is independent of the registry-window constraint documented below on
#: ``_M130_DIAGNOSTIC_YEARS``, which bounds only the modelo-calculate diagnostic.
_TOTAL_TRANSACTIONS = 30_000
_FILING_YEARS = 10
_TRANSACTIONS_PER_YEAR = _TOTAL_TRANSACTIONS // _FILING_YEARS
_FIRST_YEAR = 2021
_LAST_YEAR = _FIRST_YEAR + _FILING_YEARS - 1  # 2030, inclusive

#: Filing year used by the M130 modelo-calculate diagnostic. The minoracion
#: carry reads a prior-year M100 observation, so the diagnostic uses the latest
#: filing year whose prior year is represented by the bundled M100 registry.
_M130_DIAGNOSTIC_YEAR = 2026
_M130_DIAGNOSTIC_YEARS = (_M130_DIAGNOSTIC_YEAR,)

#: Repeat count for budgeted period-scoped operations; enough samples for a real P95.
_BUDGET_SAMPLE_COUNT = 20

#: Repeat count for out-of-budget diagnostics. These samples still exercise real
#: encrypted persistence but avoid making known out-of-scope full scans dominate
#: the integration runtime.
_DIAGNOSTIC_SAMPLE_COUNT = 3

_M130_REVISION = "2019-y-siguientes"
_M130_MANUAL_INPUTS: dict[CasillaId, Decimal] = {
    validated_casilla_id("06", surface="bench M130 retenciones"): Decimal("0"),
    validated_casilla_id("08", surface="bench M130 agrarian volume"): Decimal("0"),
    validated_casilla_id("10", surface="bench M130 agrarian withheld"): Decimal("0"),
    validated_casilla_id("16", surface="bench M130 home deduction"): Decimal("0"),
    validated_casilla_id("18", surface="bench M130 prior return result"): Decimal("0"),
}
_M100_ANNUAL_PERIOD = "0A"
_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA = validated_casilla_id(
    "0224",
    surface="bench M100 net income",
)
_M100_RENDIMIENTO_SOURCE_1479_CASILLA = validated_casilla_id("1479", surface="bench M100 1479")
_M100_RENDIMIENTO_SOURCE_1553_CASILLA = validated_casilla_id("1553", surface="bench M100 1553")
_M100_RENDIMIENTO_SOURCE_1577_CASILLA = validated_casilla_id("1577", surface="bench M100 1577")
_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA = validated_casilla_id("1391", surface="bench M100 BIN")
_PRIOR_YEAR_NET_INCOME = Decimal("50000")
_TRANSACTION_REPOSITORY_LOGGER = "cadrumo.adapters.persistence.profile.transactions"
_PARTITION_LOG_MARKERS = (
    "partitioned transaction catalogue via date index",
    "partitioned transaction catalogue via full-scan fallback",
)


def _raw(idx: int, *, booked: date) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=f"bench-row-{idx:06d}",
        booked_date=booked,
        value_date=booked,
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor Escala SL",
        description=f"scale benchmark row {idx}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=idx + 1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(booked.year, booked.month, booked.day, 12, 0, tzinfo=UTC),
            provider_name="scale benchmark provider",
        ),
        raw_fields={"Concepto": f"row {idx}"},
    )


def _synthetic_transaction(idx: int, *, booked: date) -> Transaction:
    """Build one classified, deductible business expense row.

    Alternates direction/category deterministically so the generated ledger
    is not degenerate (a single repeated row), while staying cheap to
    construct at 30k-row scale.
    """
    direction = TransactionDirection.OUTGOING if idx % 3 else TransactionDirection.INCOMING
    return Transaction.model_validate(
        {
            "raw": _raw(idx, booked=booked),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": "material_oficina",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(booked.year, booked.month, booked.day, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _dates_across_year(year: int, count: int) -> Iterator[date]:
    """Yield ``count`` distinct booked dates spread evenly across ``year``."""
    start = date(year, 1, 1)
    span_days = (date(year, 12, 31) - start).days
    for i in range(count):
        offset_days = (i * span_days) // max(count - 1, 1)
        yield start + timedelta(days=offset_days)


def _seed_scale_ledger(objects: SecureObjectRepository) -> None:
    """Persist ``_TOTAL_TRANSACTIONS`` synthetic rows across ``_FILING_YEARS`` years.

    The seed is setup cost, not a timed operation. This mirrors a real
    operator's ledger after ten years of quarterly bank-statement imports.
    """
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).save(InvoiceCatalogue())

    idx = 0
    transactions: list[Transaction] = []
    for year in range(_FIRST_YEAR, _FIRST_YEAR + _FILING_YEARS):
        for booked in _dates_across_year(year, _TRANSACTIONS_PER_YEAR):
            transactions.append(_synthetic_transaction(idx, booked=booked))
            idx += 1
    tx_repo.save(TransactionCatalogue.from_transactions(transactions))


def _seed_prior_year_m130_minoracion(objects: SecureObjectRepository) -> None:
    """Observe one M100 net-income row per prior year so each M130 diagnostic year's carry resolves.

    M130 casilla 13 (minoración) reads a ``previous_filing`` binding
    (``filing_year_delta = -1``) summing the IMMEDIATELY PRECEDING year's M100
    net-income casillas -- not just any prior observation -- so one row must
    be seeded for every diagnostic ``year - 1``.
    """
    observation_repo = CalculationObservationRepository(objects=objects)
    for target_year in _M130_DIAGNOSTIC_YEARS:
        prior_year = target_year - 1
        observation_repo.save_observation(
            RegistryModeloObservation(
                modelo="100",
                filing_year=prior_year,
                period=_M100_ANNUAL_PERIOD,
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=prior_year,
                    period=_M100_ANNUAL_PERIOD,
                    casilla_values={
                        _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: _PRIOR_YEAR_NET_INCOME,
                        _M100_RENDIMIENTO_SOURCE_1479_CASILLA: Decimal("0"),
                        _M100_RENDIMIENTO_SOURCE_1553_CASILLA: Decimal("0"),
                        _M100_RENDIMIENTO_SOURCE_1577_CASILLA: Decimal("0"),
                        _M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: Decimal("0"),
                    },
                ),
            ),
            source_kind="app_filing",
            captured_at=datetime(target_year, 4, 6, 12, 0, tzinfo=UTC),
        )


def _seed_taxpayer_profile() -> None:
    """Seed the single-taxpayer profile ``create_work_unit``'s readiness gate requires.

    Mirrors the proven working fixture from
    ``application/modelo/tests/test_e2e_ledger_m130_quarters_to_m100_annual.py``.
    ``activity_start_date`` (2020) predates every benchmarked filing year
    (``_FIRST_YEAR`` 2021 onward).
    """
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Test runtime profile",
        facts=(
            UserProfileFact(path="identity.tax_id", value=_TAX_ID),
            UserProfileFact(path="identity.name", value="Scale"),
            UserProfileFact(path="identity.surnames", value="Bench Tester"),
            UserProfileFact(path="activities.description", value="design services"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
        ),
        created_at=datetime(_FIRST_YEAR, 1, 1, tzinfo=UTC),
        updated_at=datetime(_FIRST_YEAR, 1, 1, tzinfo=UTC),
    )
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID).save(record)


def _p95(samples: list[float]) -> float:
    """Return the 95th percentile of ``samples`` (nearest-rank, no interpolation)."""
    ordered = sorted(samples)
    rank = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return ordered[rank]


def _save_benchmark_update(transaction: Transaction, sample_index: int) -> Transaction:
    """Return a same-id transaction update for write-path timing."""
    payload = transaction.model_dump(mode="python")
    payload["group_label"] = f"write-bench-{sample_index}"
    payload["modified_at"] = datetime(2031, 1, 1, 12, 0, tzinfo=UTC) + timedelta(seconds=sample_index)
    return Transaction.model_validate(payload)


def _partition_log_messages(records: Iterable[logging.LogRecord]) -> tuple[str, ...]:
    """Return real transaction-repository partition log messages captured by pytest."""
    return tuple(
        message
        for record in records
        for message in (record.getMessage(),)
        if any(marker in message for marker in _PARTITION_LOG_MARKERS)
    )


def _partition_in_window_rows(messages: Iterable[str]) -> int:
    """Return the in-window row total reported by real partition log messages."""
    total = 0
    for message in messages:
        marker = "in_window="
        start = message.find(marker)
        if start < 0:
            continue
        start += len(marker)
        end = message.find(" ", start)
        token = message[start:] if end < 0 else message[start:end]
        total += int(token)
    return total


@pytest.fixture(scope="module")
def scale_bucket() -> Iterator[SecureObjectRepository]:
    """Yield a real bucket seeded with the 30k-transaction / 10-year ledger.

    Module-scoped: the seed is expensive real-adapter I/O (30k encrypted
    upserts) and is setup cost shared by every timed operation in this
    module, not itself a measured operation.
    """
    import tempfile

    with (
        tempfile.TemporaryDirectory(prefix="cadrumo-scale-bench-") as tmp_dir,
        isolated_runtime_profile(tmp_path=Path(tmp_dir), bucket_id=_BUCKET_ID) as profile,
    ):
        _seed_scale_ledger(profile.repository)
        _seed_prior_year_m130_minoracion(profile.repository)
        _seed_taxpayer_profile()
        yield profile.repository


def test_scale_fixture_seeds_the_documented_volume(scale_bucket: SecureObjectRepository) -> None:
    """Sanity check: the seeded ledger really holds 30k rows across 10 years."""
    catalogue = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=scale_bucket).load()
    assert len(catalogue) == _TOTAL_TRANSACTIONS, (
        f"expected {_TOTAL_TRANSACTIONS} seeded transactions, found {len(catalogue)}"
    )
    years = {tx.raw.booked_date.year for tx in catalogue.values()}
    assert years == set(range(_FIRST_YEAR, _FIRST_YEAR + _FILING_YEARS)), years


def test_ledger_read_reports_full_catalogue_latency(scale_bucket: SecureObjectRepository) -> None:
    """Report wall-clock latency of a full ledger read at 30k-row scale.

    :meth:`TransactionCatalogueRepository.load` is the operation every other
    ledger-scale surface (aggregation, CLI filtering) is built on top of: it
    scans, decrypts, and pydantic-validates every row in the namespace. This
    unfiltered read is outside the period-scoped 3-second budget, so the test
    keeps an honest diagnostic without turning a separate
    pagination/streaming lever into a failing aggregation gate.
    """
    repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=scale_bucket)
    samples: list[float] = []
    for _ in range(_DIAGNOSTIC_SAMPLE_COUNT):
        started = time.perf_counter()
        catalogue = repo.load()
        samples.append(time.perf_counter() - started)
        assert len(catalogue) == _TOTAL_TRANSACTIONS

    p95 = _p95(samples)
    print(
        f"\n[bench] ledger_read_diagnostic: n={_DIAGNOSTIC_SAMPLE_COUNT} "
        f"p95={p95:.3f}s mean={statistics.mean(samples):.3f}s "
        f"min={min(samples):.3f}s max={max(samples):.3f}s "
        "budget_scope=out_of_scope_full_catalogue_read",
    )


def test_annual_renta_aggregation_reports_full_scan_latency(scale_bucket: SecureObjectRepository) -> None:
    """Report latency of the annual renta full-scan aggregation at 30k-row scale.

    :func:`aggregate_renta_ledger_expenses_from_repositories` loads the full
    catalogue because the annual expense path remains outside date-index
    optimisation until the invoice-issue-date fallback key is resolved. This
    remains a real-behaviour diagnostic, not a period-scoped budget gate.
    """
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=scale_bucket)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=scale_bucket)
    period = Period.from_year_and_code(_LAST_YEAR, "0A")

    samples: list[float] = []
    for _ in range(_DIAGNOSTIC_SAMPLE_COUNT):
        started = time.perf_counter()
        result = aggregate_renta_ledger_expenses_from_repositories(
            bucket_id=_BUCKET_ID,
            period=period,
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            # The bundled spending-category profile registry only covers
            # 2024/2025 (see src/cadrumo/_data/registry/aeat/categories/profiles/);
            # the benchmark's *period* still targets the last synthetic filing
            # year (see module docstring) -- profile_year is intentionally
            # decoupled per the function's own documented contract.
            profile_year=_CATEGORY_PROFILE_YEAR,
        )
        samples.append(time.perf_counter() - started)
        # Real accumulator output, not a mock stand-in: the filtered result carries
        # a real casilla-values mapping for the target period.
        assert isinstance(result.casilla_values, Mapping)

    p95 = _p95(samples)
    print(
        f"\n[bench] annual_renta_aggregation_diagnostic: n={_DIAGNOSTIC_SAMPLE_COUNT} "
        f"p95={p95:.3f}s mean={statistics.mean(samples):.3f}s "
        f"min={min(samples):.3f}s max={max(samples):.3f}s "
        "budget_scope=out_of_scope_pending_invoice_date_key",
    )


def test_single_transaction_save_reports_write_path_latency(scale_bucket: SecureObjectRepository) -> None:
    """Report latency of saving one changed transaction in a 30k-row catalogue.

    The transaction repository no longer rewrites unchanged secure-object rows,
    but `_reconcile` still does O(n) catalogue work before it can discover the
    single changed row: a namespace hash scan plus serialisation and SHA-256 of
    every incoming transaction payload. This benchmark measures those two
    components and the real `repo.save(updated_catalogue)` total against the
    seeded encrypted SQLite bucket.
    """
    repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=scale_bucket)
    original_catalogue = repo.load()
    target_id = min(original_catalogue.transactions)
    target = original_catalogue.transactions[target_id]
    target_filing_date = target.raw.value_date or target.raw.booked_date

    namespace_hash_samples: list[float] = []
    for _ in range(_DIAGNOSTIC_SAMPLE_COUNT):
        started = time.perf_counter()
        namespace_hashes = scale_bucket.namespace_payload_hashes(TX_BUCKET_NAMESPACE)
        namespace_hash_samples.append(time.perf_counter() - started)
        assert len(namespace_hashes) >= _TOTAL_TRANSACTIONS

    serialise_hash_samples: list[float] = []
    for _ in range(_DIAGNOSTIC_SAMPLE_COUNT):
        started = time.perf_counter()
        payload_hashes = tuple(
            sha256_hex(repo._serialise_transaction(transaction))
            for transaction in original_catalogue.transactions.values()
        )
        serialise_hash_samples.append(time.perf_counter() - started)
        assert len(payload_hashes) == _TOTAL_TRANSACTIONS

    save_samples: list[float] = []
    current_catalogue = original_catalogue
    try:
        for sample_index in range(_DIAGNOSTIC_SAMPLE_COUNT):
            current_transaction = current_catalogue.transactions[target_id]
            updated_transaction = _save_benchmark_update(current_transaction, sample_index)
            assert updated_transaction.transaction_id == target_id
            updated_transactions = dict(current_catalogue.transactions)
            updated_transactions[target_id] = updated_transaction
            updated_catalogue = TransactionCatalogue.model_validate({"transactions": updated_transactions})

            started = time.perf_counter()
            repo.save(updated_catalogue)
            save_samples.append(time.perf_counter() - started)
            current_catalogue = updated_catalogue

        loaded_target_window = repo.load_for_date_range(target_filing_date, target_filing_date)
        assert loaded_target_window.transactions[target_id].group_label == f"write-bench-{_DIAGNOSTIC_SAMPLE_COUNT - 1}"
    finally:
        repo.save(original_catalogue)

    namespace_p95 = _p95(namespace_hash_samples)
    serialise_hash_p95 = _p95(serialise_hash_samples)
    save_p95 = _p95(save_samples)
    print(
        f"\n[bench] transaction_save_namespace_hash_scan: n={_DIAGNOSTIC_SAMPLE_COUNT} "
        f"p95={namespace_p95:.3f}s mean={statistics.mean(namespace_hash_samples):.3f}s "
        f"min={min(namespace_hash_samples):.3f}s max={max(namespace_hash_samples):.3f}s "
        f"namespace={TX_BUCKET_NAMESPACE}",
    )
    print(
        f"[bench] transaction_save_serialize_hash_all_rows: n={_DIAGNOSTIC_SAMPLE_COUNT} "
        f"rows={_TOTAL_TRANSACTIONS} p95={serialise_hash_p95:.3f}s "
        f"mean={statistics.mean(serialise_hash_samples):.3f}s "
        f"min={min(serialise_hash_samples):.3f}s max={max(serialise_hash_samples):.3f}s",
    )
    print(
        f"[bench] single_transaction_save: n={_DIAGNOSTIC_SAMPLE_COUNT} rows={_TOTAL_TRANSACTIONS} "
        f"changed_rows=1 p95={save_p95:.3f}s mean={statistics.mean(save_samples):.3f}s "
        f"min={min(save_samples):.3f}s max={max(save_samples):.3f}s "
        f"serialize_hash_p95={serialise_hash_p95:.3f}s namespace_hash_scan_p95={namespace_p95:.3f}s",
    )


@pytest.mark.serial
def test_iva_quarterly_aggregation_partitioned_p95_latency(
    scale_bucket: SecureObjectRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Budgeted P95 latency for the partitioned quarterly IVA path.

    One quarter is roughly 750 of the 30k seeded rows, matching the
    period-scoped ledger operation that must stay below the 3.0s budget.

    A short fresh full-scan diagnostic still calls the pure aggregator
    directly over :meth:`TransactionCatalogueRepository.load` (bypassing the
    partition entirely) so the report preserves the before/after shape without
    spending the whole integration lane on the out-of-scope baseline. The
    budgeted samples measure the real, currently-shipped
    :func:`aggregate_iva_ledger_observations_from_repositories` entry point.
    """
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=scale_bucket)
    period = Period.from_year_and_code(_LAST_YEAR, "4T")

    full_scan_samples: list[float] = []
    partitioned_samples: list[float] = []
    paired_partitioned_samples: list[float] = []
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=_TRANSACTION_REPOSITORY_LOGGER):
        for sample_index in range(_BUDGET_SAMPLE_COUNT):
            if sample_index < _DIAGNOSTIC_SAMPLE_COUNT:
                started = time.perf_counter()
                full_scan_result = aggregate_iva_ledger_observations(tx_repo.load(), period=period)
                full_scan_samples.append(time.perf_counter() - started)
                assert isinstance(full_scan_result.observations, tuple)

            started = time.perf_counter()
            partitioned_result = aggregate_iva_ledger_observations_from_repositories(
                bucket_id=_BUCKET_ID,
                period=period,
                transaction_repository=tx_repo,
            )
            partitioned_duration = time.perf_counter() - started
            partitioned_samples.append(partitioned_duration)
            if sample_index < _DIAGNOSTIC_SAMPLE_COUNT:
                paired_partitioned_samples.append(partitioned_duration)

            # Real accumulator output, not a mock stand-in.
            assert isinstance(partitioned_result.observations, tuple)

    full_scan_p95 = _p95(full_scan_samples)
    partitioned_p95 = _p95(partitioned_samples)
    paired_partitioned_p95 = _p95(paired_partitioned_samples)
    partition_messages = _partition_log_messages(caplog.records)
    partition_read_count = len(partition_messages)
    partition_in_window_rows = _partition_in_window_rows(partition_messages)
    assert partition_read_count == _BUDGET_SAMPLE_COUNT
    print(
        f"\n[bench] iva_quarterly_full_scan_diagnostic: n={_DIAGNOSTIC_SAMPLE_COUNT} "
        f"p95={full_scan_p95:.3f}s mean={statistics.mean(full_scan_samples):.3f}s "
        f"min={min(full_scan_samples):.3f}s max={max(full_scan_samples):.3f}s",
    )
    print(
        f"[bench] iva_quarterly_partitioned: n={_BUDGET_SAMPLE_COUNT} "
        f"p95={partitioned_p95:.3f}s mean={statistics.mean(partitioned_samples):.3f}s "
        f"min={min(partitioned_samples):.3f}s max={max(partitioned_samples):.3f}s "
        f"budget={_P95_BUDGET_SECONDS:.1f}s "
        f"paired_p95_delta_vs_full_scan={(full_scan_p95 - paired_partitioned_p95):.3f}s "
        f"partition_reads={partition_read_count} partition_in_window_rows={partition_in_window_rows}",
    )
    assert partitioned_p95 < _P95_BUDGET_SECONDS, (
        f"IVA quarterly aggregation (partitioned) P95 {partitioned_p95:.3f}s at "
        f"{_TOTAL_TRANSACTIONS}-row ledger scale exceeds the {_P95_BUDGET_SECONDS:.1f}s budget "
        f"(samples={partitioned_samples!r})"
    )


def test_modelo_calculate_reports_latency(
    scale_bucket: SecureObjectRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Report latency of real M130 quarterly calculate at 30k-row ledger scale.

    Exercises :func:`calculate_modelo_revision_from_bucket_aggregation` end to
    end: work-unit creation/lookup, the enrolled ledger income resolver
    reading the 30k-row catalogue, the ``previous_filing`` minoración carry,
    and the full registry formula chain for M130 (RD 439/2007 art. 110).

    M130's casilla-05/15 ``previous_filing`` bindings require the SAME YEAR's
    immediately-preceding quarter to be filed (``source_period_offset_from_target
    = -1, max_year_delta = 0``); each calculated quarter is therefore persisted
    through :func:`persist_filed_revision_observation` before the next quarter
    of that year is calculated, mirroring a real operator's quarterly filing
    cadence. The diagnostic uses the latest filing year whose prior-year M100
    carry is represented by the bundled registry; the ledger itself still
    holds the full 30k-row / 10-year scale this benchmark reads over.
    """
    wu_repo = WorkUnitCatalogueRepository(objects=scale_bucket)
    cr_repo = CalculationRevisionCatalogueRepository(objects=scale_bucket)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=scale_bucket)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=scale_bucket)
    observation_repo = CalculationObservationRepository(objects=scale_bucket)

    quarters = ("1T", "2T", "3T", "4T")
    samples: list[float] = []
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=_TRANSACTION_REPOSITORY_LOGGER):
        for year in _M130_DIAGNOSTIC_YEARS:
            for quarter in quarters:
                filed_at = datetime(year, 4, 6, 12, 0, tzinfo=UTC)
                work_unit = create_work_unit(
                    bucket_id=_BUCKET_ID,
                    modelo="130",
                    filing_year=year,
                    period=Period.from_year_and_code(year, quarter),
                    revision_id=_M130_REVISION,
                    repository=wu_repo,
                    clock=filed_at,
                )
                started = time.perf_counter()
                revision = calculate_modelo_revision_from_bucket_aggregation(
                    work_unit.work_unit_id,
                    casilla_inputs=_M130_MANUAL_INPUTS,
                    work_unit_repository=wu_repo,
                    calculation_repository=cr_repo,
                    transaction_repository=tx_repo,
                    invoice_repository=invoice_repo,
                    clock=filed_at,
                )
                samples.append(time.perf_counter() - started)
                assert revision.casilla_values  # the engine produced real casilla output, not an empty stub
                persist_filed_revision_observation(
                    revision=revision,
                    work_unit=work_unit,
                    repository=observation_repo,
                    captured_at=filed_at,
                )

    reported = samples
    p95 = _p95(reported)
    partition_messages = _partition_log_messages(caplog.records)
    partition_read_count = len(partition_messages)
    partition_in_window_rows = _partition_in_window_rows(partition_messages)
    assert partition_read_count >= len(reported)
    print(
        f"\n[bench] modelo_calculate_diagnostic: n={len(reported)} "
        f"p95={p95:.3f}s mean={statistics.mean(reported):.3f}s "
        f"min={min(reported):.3f}s max={max(reported):.3f}s "
        f"budget={_P95_BUDGET_SECONDS:.1f}s budget_scope=diagnostic_modelo_calculate "
        f"partition_reads={partition_read_count} partition_in_window_rows={partition_in_window_rows}",
    )
