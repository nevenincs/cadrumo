"""Calculation revision actions for modelo work units.

The calculate paths resolve a law-determined :class:`~domain.calculations.registry.RegistrySnapshot` from
each :class:`~domain.modelos.WorkUnit`, merge manual inputs with profile,
borrador, IVA-wallet, and bucket aggregation channels, and execute
:func:`~domain.calculations.registry.calculate_registry_snapshot` against
the asserted :class:`~domain.calculations.registry.ModeloRevision`.

Persistence is centralized through :class:`~domain.modelos.CalculationRevision`,
:class:`~adapters.persistence.profile.modelos_calculation.CalculationRevisionCatalogueRepository`,
and :class:`~adapters.persistence.profile.buckets.BucketEventHistoryRepository`, so the work-unit pointer and
``modelo.calculation.created`` event advance with the stored draft revision.

:func:`~application.modelo.calculate_modelo_revision` is the lower-level
calculation service: callers provide already-resolved manual, binding,
enum-binding, relation, borrador, and IVA-wallet inputs.
:func:`~application.modelo.calculate_modelo_revision_from_bucket_aggregation`
first runs the application source mesh over bucket-local ledgers, invoices,
previous filings, relation prefill, retenciones, withholding, and detail rows,
then feeds the resolved backend channels into the same persistence path.
Source-owned bindings and their bound casillas are guarded before the engine
runs so a persisted revision cannot claim bucket-source grounding while carrying
a caller substitute for the same value.

See Also:
    :mod:`~application.aggregation`:
        Public source-mesh contracts and diagnostics consumed by the bucket
        aggregation path.
    :func:`~application.modelo._calculation_resolution.resolve_calculation_binding_channels`:
        Merges caller, backend, borrador, and date binding channels for the
        registry engine.
    :func:`~application.modelo._calculation_helpers.build_typed_observations`:
        Projects engine output into provenance-bearing casilla observations.
    :func:`~application.modelo._revision_persistence.persist_calculation_revision`:
        Stores the content-addressed ``BORRADOR`` revision and emits the bucket
        event.
    :func:`~application.modelo._verification_actions.verify_modelo_revision`:
        Lifecycle gate that promotes a calculated revision after verification.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.aggregation import BindingSourceKind
from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry import (
    IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS,
    BindingId,
    CasillaId,
    InputKind,
    ModeloRevision,
    RelationId,
    bound_casilla_binding_ids,
    calculate_registry_snapshot,
    casillas_by_id,
    validated_text_input_casilla_ids,
)
from ...domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    CalculationSourceRef,
    ModeloDetailRow,
    WorkUnit,
    WorkUnitCatalogueRepositoryProtocol,
    upsert_calculation_revision,
)
from ..calculations import cross_period_dependency_requirements as _cross_period_dependency_requirements
from ..live import Borrador100SnapshotRepository
from ._action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloAggregationBindingError,
    ModeloCrossPeriodCleanStateError,
    WorkUnitNotFoundError,
)
from ._binding_resolution import resolve_available_bound_inputs_by_casilla_id
from ._calculation_aggregation_context import load_bucket_aggregation_context as _load_bucket_aggregation_context
from ._calculation_diagnostics import collect_bucket_aggregation_advisory_diagnostics
from ._calculation_helpers import (
    build_typed_observations as _build_typed_observations,
)
from ._calculation_helpers import (
    resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit,
)
from ._calculation_modelo_adjustments import (
    _calculated_decimal,
    _detail_row_binding_values_for_calculation,
    _m131_objective_estimation_data_base_inputs,
    _raise_if_m390_303_reconciliation_would_save_silent_zero,
    _suppress_m349_row_field_template_outputs,
)
from ._calculation_preparation import (
    _IVA_LEDGER_EXEMPT_REGIMES as _IVA_LEDGER_EXEMPT_REGIMES,
)
from ._calculation_preparation import (
    _raise_if_ledger_preflight_blocks_calculation as _raise_if_ledger_preflight_blocks_calculation,
)
from ._calculation_preparation import (
    prepare_calculation as _prepare_calculation,
)
from ._calculation_resolution import (
    build_calculation_replay_payloads as _build_calculation_replay_payloads,
)
from ._calculation_resolution import (
    resolve_calculation_inputs as _resolve_calculation_inputs,
)
from ._calculation_source_policy import (
    _BINDING_SOURCE_DISPOSITIONS as _BINDING_SOURCE_DISPOSITIONS,
)
from ._calculation_source_policy import (
    _ENROLLED_SOURCE_KINDS as _ENROLLED_SOURCE_KINDS,
)
from ._calculation_source_policy import (
    ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS,
    BUCKET_AGGREGATION_LOCK_SOURCES,
    CALLER_OVERRIDABLE_CARRY_SOURCES,
)
from ._calculation_source_staging import (
    add_expected_missing_binding_diagnostics as _add_expected_missing_binding_diagnostics,
)
from ._calculation_source_staging import (
    add_unhandled_source_diagnostics as _add_unhandled_source_diagnostics,
)
from ._calculation_source_staging import (
    resolve_prorrata_regularizacion_sources as _resolve_prorrata_regularizacion_sources,
)
from ._m349_ledger_guard import (
    raise_if_m349_intracom_ledger_rows_need_operator_rows as _raise_if_m349_intracom_ledger_rows_need_operator_rows,
)
from ._registry_helpers import validate_casilla_input_ids as _validate_casilla_input_ids
from ._revision_persistence import persist_calculation_revision

if TYPE_CHECKING:
    from ...domain.calculations.registry import RegistrySnapshot
    from ...domain.transactions import LedgerDatePartition, TransactionCatalogue, TransactionCatalogueRepositoryProtocol
    from ..aggregation import (
        CalculationSourceDiagnostic,
        CalculationSourceResolution,
        ForeignAssetIngestObservation,
    )
    from ..calculations import IvaWalletDecisionRepository


@dataclass(frozen=True, slots=True)
class BucketAggregationCalculationResult:
    """Calculation revision plus the non-blocking source diagnostics raised while resolving it.

    ``revision`` is the persisted :class:`CalculationRevision`.
    ``source_diagnostics`` carries the
    :class:`~application.aggregation.CalculationSourceDiagnostic` rows the
    source mesh emitted during resolution, notably the unconsumed-declarable-IVA
    advisories (a declarable IVA observation no ``ledger_iva_aggregation``
    binding selects). They are NON-blocking: the revision was computed and
    persisted regardless. Surfacing them keeps an unrouted declarable
    observation from being silently under-declared (no-silent-under-declaration).
    """

    revision: CalculationRevision
    source_diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()


def calculate_modelo_revision(
    work_unit_id: str,
    *,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal],
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    backend_binding_values: Mapping[BindingId, Decimal] | None = None,
    row_binding_values: Mapping[tuple[BindingId, int], Decimal | str] | None = None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    iva_compensation_decision: object | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    ledger_preflight_transaction_repository: TransactionCatalogueRepository | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    unresolved_relation_ids: tuple[RelationId, ...] = (),
    unresolved_binding_ids: tuple[BindingId, ...] = (),
    source_transaction_ids: tuple[str, ...] = (),
    filing_period_date: date | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    source_provenance: tuple[CalculationSourceRef, ...] = (),
    clock: datetime | None = None,
) -> CalculationRevision:
    """Run the registry formula engine, persist a draft revision, and return a :class:`CalculationRevision`.

    ``ledger_preflight_transaction_repository`` is a :class:`TransactionCatalogueRepository`
    used for the ledger preflight check before calculation.

    Pipeline:

    1. Load the work unit; refuse on DISCARDED.
    2. Resolve the :class:`RegistrySnapshot` for the work unit's
       ``(modelo, filing_year, period)`` and assert its
       :class:`ModeloRevision`. Failure to resolve raises
       :exc:`CalculationRegistryUnavailableError` — the calculate
       path runs the engine, so a missing snapshot is a hard refusal.
    3. Run :func:`~domain.calculations.registry.calculate_registry_snapshot`
       over the snapshot
       with the operator-supplied manual casilla inputs, binding
       values, enum-binding values, and relation values. The
       engine evaluates every declared formula in dependency order
       and returns the full ``casilla_values`` map (inputs plus
       formula outputs).
    4. Build canonical replay payloads for inputs, binding overrides,
       enum/date bindings, and relation overrides (so the content-addressed
       revision id is stable across structurally identical re-runs).
    5. Project the engine result to :class:`CasillaObservation` rows and persist
       the revision in ``BORRADOR`` state; advance the work unit's
       ``current_calculation_revision_id`` pointer; emit
       ``modelo.calculation.created``.

    The revision starts in ``BORRADOR`` state; callers must run
    :func:`~application.modelo.verify_modelo_revision` and
    :func:`~application.modelo.file_modelo_revision`
    explicitly to advance through the lifecycle.

    See Also:
        :func:`~application.modelo._calculation_resolution.build_calculation_replay_payloads`:
            Canonicalizes the values that participate in the revision id.
        :func:`~application.modelo._calculation_helpers.build_typed_observations`:
            Carries registry legal/source provenance onto the persisted
            revision.
        :func:`~application.modelo._revision_persistence.persist_calculation_revision`:
            Owns duplicate detection, work-unit pointer advancement, and event
            emission.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    prepared = _prepare_calculation(
        work_unit_id=work_unit_id,
        work_unit_repository=wu_repo,
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        ledger_preflight_transaction_repository=ledger_preflight_transaction_repository,
        iva_compensation_decision=iva_compensation_decision,
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        backend_binding_values=backend_binding_values,
        filing_period_date=filing_period_date,
        borrador_snapshot_id=borrador_snapshot_id,
        borrador_snapshot_repository=borrador_snapshot_repository,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
    )
    work_units = prepared.work_units
    work_unit = prepared.work_unit
    snapshot = prepared.snapshot
    resolved_relations = dict(relation_values or {})
    backend_casilla_inputs = {
        **_m131_objective_estimation_data_base_inputs(
            work_unit=work_unit,
            revision=snapshot.revision,
            binding_values=prepared.channels.bindings,
        ),
        **dict(prepared.backend_casilla_inputs or {}),
    }
    resolved_inputs = _resolve_calculation_inputs(
        revision=snapshot.revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        backend_casilla_inputs=backend_casilla_inputs,
        resolved_bindings=prepared.channels.bindings,
        casilla_inputs=prepared.casilla_inputs,
    )

    resolved_text_inputs = validated_text_input_casilla_ids(text_casilla_inputs or {})

    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=resolved_inputs,
        text_inputs=resolved_text_inputs or None,
        date_context={"filing_period": prepared.period_date},
        binding_values=prepared.channels.bindings,
        enum_binding_values=prepared.channels.enum_bindings,
        relation_values=resolved_relations,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        date_binding_values=prepared.channels.date_bindings or None,
    )

    replay_payloads = _build_calculation_replay_payloads(
        resolved_inputs=resolved_inputs,
        resolved_bindings=prepared.channels.bindings,
        resolved_enum_bindings=prepared.channels.enum_bindings,
        resolved_date_bindings=prepared.channels.date_bindings,
        resolved_relations=resolved_relations,
        resolved_row_bindings=row_binding_values or {},
    )
    casilla_values = dict(engine_result.values)
    _raise_if_m390_303_reconciliation_would_save_silent_zero(
        work_unit=work_unit,
        snapshot=snapshot,
        casilla_values=casilla_values,
        resolved_binding_values=prepared.channels.bindings,
    )
    typed_observations = _build_typed_observations(engine_result=engine_result, snapshot=snapshot)
    casilla_values, typed_observations = _suppress_m349_row_field_template_outputs(
        work_unit=work_unit,
        revision=snapshot.revision,
        casilla_values=casilla_values,
        observations=typed_observations,
    )

    now = clock or _utc_now()
    return persist_calculation_revision(
        work_unit_id=work_unit_id,
        work_unit=work_unit,
        work_units=work_units,
        input_values_by_casilla_id={**replay_payloads.input_values_by_casilla_id, **resolved_text_inputs},
        binding_overrides=replay_payloads.binding_overrides,
        row_binding_values=replay_payloads.row_binding_values,
        relation_overrides=replay_payloads.relation_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        borrador_snapshot_id=prepared.channels.borrador_snapshot_id,
        bindings_sourced_from_borrador=prepared.channels.bindings_sourced_from_borrador,
        observations=typed_observations,
        unresolved_outcomes=engine_result.unresolved_outcomes,
        source_provenance=source_provenance,
        detail_rows=detail_rows,
        formula_count=len(engine_result.entries),
        actor=actor,
        now=now,
        calculation_repository=cr_repo,
        work_unit_repository=wu_repo,
        bucket_event_repository=bv_repo,
    )


def calculate_modelo_revision_from_bucket_aggregation(
    work_unit_id: str,
    *,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    iva_compensation_decision: object | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    filing_period_date: date | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    foreign_asset_observations: tuple[ForeignAssetIngestObservation, ...] = (),
    borrador_snapshot_repository: Borrador100SnapshotRepository | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    clock: datetime | None = None,
) -> CalculationRevision:
    """Calculate a modelo revision through the bucket-local source mesh.

    ``transaction_repository`` is a :class:`TransactionCatalogueRepository` used to
    load bucket-local ledger transactions for aggregation.
    ``invoice_repository`` is an :class:`InvoiceCatalogueRepository` used by
    invoice and OSS/IOSS resolvers. ``foreign_asset_observations`` feeds the
    repository-free M720 foreign-asset resolver when the caller has already
    supplied typed asset observations. The wrapper resolves enrolled source
    families into backend binding, casilla, relation, detail-row, and provenance
    channels, rejects caller collisions with source-owned bindings, and then
    delegates to :func:`~application.modelo.calculate_modelo_revision`.

    Returns a :class:`CalculationRevision`. Use
    :func:`~application.modelo.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`
    when the caller also needs the non-blocking source diagnostics (e.g. the
    operator-facing CLI calculate surface, which surfaces unconsumed-declarable
    IVA advisories).

    See Also:
        :func:`_resolve_bucket_source_mesh`:
            Runs the enrolled resolver set and returns the merged
            :class:`~application.aggregation.CalculationSourceResolution`.
        :func:`_reject_caller_overrides_of_source_bindings`:
            Refuses caller values for source-owned binding and bound-casilla
            slots.
    """
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_id,
        actor=actor,
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        iva_compensation_decision=iva_compensation_decision,
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        borrador_snapshot_id=borrador_snapshot_id,
        relation_values=relation_values,
        filing_period_date=filing_period_date,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
        foreign_asset_observations=foreign_asset_observations,
        borrador_snapshot_repository=borrador_snapshot_repository,
        detail_rows=detail_rows,
        clock=clock,
    ).revision


class _MemoizedTransactionCatalogueRepository:
    """Read-through cache over one :class:`TransactionCatalogueRepositoryProtocol` load.

    The bucket-aggregation source mesh (:func:`_resolve_bucket_source_mesh`)
    constructs up to five independent ledger resolvers
    (``LedgerIvaAggregationSourceResolver``,
    ``LedgerRentaExpenseAggregationSourceResolver``,
    ``LedgerRentaIncomeAggregationSourceResolver``,
    ``LedgerImpatriadoIncomeAggregationSourceResolver``,
    ``LedgerRentaGastoAggregationSourceResolver``) against the SAME
    transaction repository, and every enrolled resolver independently calls
    :meth:`~TransactionCatalogueRepositoryProtocol.load` when its binding
    source is declared on the target revision. At 30k-row ledger scale this
    repeats a full per-row decrypt-and-validate scan (~0.3-0.4s) once per
    enrolled resolver within a SINGLE calculate invocation — a real,
    measured P95 contributor (issue #408) with no behavioural benefit, since
    :class:`~domain.transactions.TransactionCatalogue` is frozen and the
    mesh never writes between resolver calls.

    This wrapper loads the underlying repository at most once per instance
    and returns the identical frozen :class:`TransactionCatalogue` to every
    caller. ``save`` is not memoized (it is never called during source-mesh
    resolution; see the module docstring) and delegates straight through so
    the wrapper stays a strict read-through cache, not a write cache.

    :meth:`load_for_date_range` and :meth:`partition_by_date_range` are ALSO
    memoized, each keyed by the exact ``(start, end)`` window, so two
    resolvers that request the identical window in one calculate invocation
    share one targeted scan instead of each independently re-scanning. A
    resolver requesting a distinct window gets its own cache entry rather
    than colliding with an unrelated one.

    As of issue #408 Path A / O2 (``2026-07-05-ledger-latency-budget-adr``),
    four of the five ledger resolvers (IVA, M130/M100 income, M130 gasto,
    impatriado) call :meth:`partition_by_date_range`, which decrypts only the
    in-window subset and reports the out-of-window remainder as plaintext
    stubs -- the M130 income and gasto resolvers request the IDENTICAL
    cumulative window in one calculate invocation, so
    ``_partition_catalogues`` memoization is load-bearing here, not
    incidental. :class:`LedgerRentaExpenseAggregationSourceResolver` (the
    #599 first-slice path) still calls ``load`` and reads the FULL catalogue,
    because its effective filing date prefers the linked invoice's issue
    date over the transaction's own date, so the transaction-date index is
    the wrong pre-filter key for it (excluded from Path A pending #599).
    ``load_for_date_range`` itself has no current caller; its cache branch is
    retained alongside the method for any future direct caller.
    """

    __slots__ = ("_catalogue", "_date_range_catalogues", "_partition_catalogues", "_repository")

    def __init__(self, repository: TransactionCatalogueRepositoryProtocol) -> None:
        self._repository = repository
        self._catalogue: TransactionCatalogue | None = None
        self._date_range_catalogues: dict[tuple[date, date], TransactionCatalogue] = {}
        self._partition_catalogues: dict[tuple[date, date], LedgerDatePartition] = {}

    @property
    def bucket_id(self) -> str:
        """Return the wrapped repository's bound bucket id."""
        return self._repository.bucket_id

    def exists(self) -> bool:
        """Delegate straight through; not memoized (cheap index-only read)."""
        return self._repository.exists()

    def load(self) -> TransactionCatalogue:
        """Return the cached catalogue, loading it from storage at most once."""
        if self._catalogue is None:
            self._catalogue = self._repository.load()
        return self._catalogue

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        """Return the cached window catalogue, loading it from storage at most once per exact window."""
        key = (start, end)
        cached = self._date_range_catalogues.get(key)
        if cached is None:
            cached = self._repository.load_for_date_range(start, end)
            self._date_range_catalogues[key] = cached
        return cached

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        """Return the cached partition, computing it from storage at most once per exact window."""
        key = (start, end)
        cached = self._partition_catalogues.get(key)
        if cached is None:
            cached = self._repository.partition_by_date_range(start, end)
            self._partition_catalogues[key] = cached
        return cached

    def save(self, catalogue: TransactionCatalogue) -> None:
        """Delegate the :class:`~domain.transactions.TransactionCatalogue` save to the wrapped repository.

        This method is never called during mesh resolution.
        """
        self._repository.save(catalogue)


def _resolve_bucket_source_mesh(
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    *,
    transaction_repository: TransactionCatalogueRepository | None,
    invoice_repository: InvoiceCatalogueRepository | None,
    foreign_asset_observations: tuple[ForeignAssetIngestObservation, ...],
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    date_binding_values: Mapping[BindingId, date] | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    filing_period_date: date | None = None,
) -> CalculationSourceResolution:
    """Resolve the live source mesh for a bucket-aggregation calculation.

    Builds the :class:`~application.aggregation.CalculationSourceContext`,
    runs every enrolled ledger / invoice / carry resolver through
    :func:`~application.aggregation.merge_source_resolutions`, and augments
    the result with the unhandled-binding-source advisories for any declared
    source with no enrolled resolver. Returns the merged
    :class:`~application.aggregation.CalculationSourceResolution`.

    The transaction repository is wrapped in :class:`_MemoizedTransactionCatalogueRepository`
    so every enrolled ledger resolver shares one ``load()`` of the bucket's
    transaction catalogue instead of each resolver independently re-scanning
    and re-decrypting it (see that class's docstring; issue #408).
    """
    resolved_transaction_repository = transaction_repository or TransactionCatalogueRepository(
        bucket_id=work_unit.bucket_id,
    )
    memoized_transaction_repository = _MemoizedTransactionCatalogueRepository(resolved_transaction_repository)
    from ..aggregation import (
        AtribucionMemberSourceResolver,
        CalculationSourceContext,
        ForeignAssetsAggregationSourceResolver,
        LedgerImpatriadoIncomeAggregationSourceResolver,
        LedgerIvaAggregationSourceResolver,
        LedgerRentaExpenseAggregationSourceResolver,
        LedgerRentaGastoAggregationSourceResolver,
        LedgerRentaIncomeAggregationSourceResolver,
        OssIossLedgerSourceResolver,
        RetencionesAggregationSourceResolver,
        WithholdingSourceResolver,
        merge_source_resolutions,
    )
    from ..calculations import (
        IvaCompensationAnnualPartitionSourceResolver,
        PreviousFilingSourceResolver,
        RelationPrefillSourceResolver,
    )
    from ..invoices import InvoiceCatalogueSourceResolver

    context = CalculationSourceContext(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        revision=snapshot.revision,
    )
    source_resolution = merge_source_resolutions(
        (
            LedgerIvaAggregationSourceResolver(
                transaction_repository=memoized_transaction_repository,
            ).resolve(context),
            LedgerRentaExpenseAggregationSourceResolver(
                transaction_repository=memoized_transaction_repository,
                invoice_repository=invoice_repository,
            ).resolve(context),
            # M130 actividad-económica income (ledger_renta_income_aggregation).
            LedgerRentaIncomeAggregationSourceResolver(
                transaction_repository=memoized_transaction_repository,
            ).resolve(context),
            # M130 deductible-expense / gasto into casilla 02
            # (ledger_renta_gasto_aggregation) — the OUTGOING sibling of the
            # income resolver, same cumulative quarterly window.
            LedgerRentaGastoAggregationSourceResolver(
                transaction_repository=memoized_transaction_repository,
            ).resolve(context),
            # M151 impatriado (Ley Beckham) Spanish-source base
            # (ledger_impatriado_income_aggregation): folds only ES-source income
            # into impatriado.base-liquidable-general over the annual ejercicio and
            # segregates every foreign / jurisdiction-unresolved row as a typed
            # BECKHAM_FOREIGN_SOURCE_SEGREGATED source diagnostic (art. 93.2 LIRPF).
            LedgerImpatriadoIncomeAggregationSourceResolver(
                transaction_repository=memoized_transaction_repository,
            ).resolve(context),
            # M369 OSS/IOSS (ledger_oss_aggregation).  The live path projects
            # OSS/IOSS-tagged issued invoices into validated ledger candidates;
            # pre-classified callers can still pass candidates directly through
            # the resolver constructor.
            OssIossLedgerSourceResolver(invoice_repository=invoice_repository).resolve(context),
            # Retenciones family source (retenciones_aggregation): M115 reads the
            # dedicated per-perceptor store for quarterly count/base, while M180/M193
            # read it for distinct perceptor-NIF counts. Empty store on a declaring
            # revision surfaces a no-silent advisory.
            RetencionesAggregationSourceResolver().resolve(context),
            # M190 distinct percepción count (withholding): reads the dedicated
            # per-perceptor-clave withholding store and materialises scalar
            # withholding bindings. Empty store on a declaring revision surfaces
            # a no-silent advisory while still materialising an explicit zero.
            WithholdingSourceResolver().resolve(context),
            # M349 collectible / payable invoices (collectible_invoice,
            # payable_invoice).  Loads the encrypted invoice catalogue and resolves
            # binding values for intra-community transactions in scope.
            InvoiceCatalogueSourceResolver(
                invoice_repository=invoice_repository,
            ).resolve(context),
            # Modelo 720 foreign assets (foreign_asset). This resolver is
            # repository-free: callers pass typed observations explicitly when a
            # calculation should include M720 asset rows.
            ForeignAssetsAggregationSourceResolver(
                observations=foreign_asset_observations,
            ).resolve(context),
            # Modelo 184 attribution members are declared on the attribution-entity
            # profile as repeatable socios with explicit assigned base amounts.
            AtribucionMemberSourceResolver().resolve(context),
            # Cross-period carry: prior-filing observations flow through the
            # backend-binding channel so an automatically-carried previous_filing
            # value fills the binding gap, while a caller --binding still
            # overrides it (it is deliberately NOT added to the owned-source
            # rejection set below — ruling D2). The 303 IVA-compensation
            # binding is excluded here because the iva-wallet compensación
            # decision owns it (ruling D3).
            PreviousFilingSourceResolver(
                registry_snapshot=snapshot,
                excluded_binding_ids=IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS,
            ).resolve(context),
            # Relation canonical for cross-modelo fold-in. The relation resolver
            # folds prior filed observations through each declared relation's
            # aggregation op and MATERIALISES the result into the relation's
            # target_binding slot (now declared source = "relation_prefill"). The
            # materialised binding values ride in this resolution's binding_values
            # so the mesh _claim_binding exclusive-ownership guard adjudicates any
            # collision loudly (aggregation-taxonomy rulings 2+4). This brings the
            # entire relation corpus (M100 pagos-fraccionados + retenciones
            # credits, M180/M190/M193 reconciliations, M200/M202 carries) live on
            # the operator calculate path.
            RelationPrefillSourceResolver(registry_snapshot=snapshot).resolve(context),
            # Modelo 390 annual compensation carry boxes 97 / 662 are one FIFO
            # partition over filed Modelo 303 compensation states, not two
            # independent relation copy/sum folds.
            IvaCompensationAnnualPartitionSourceResolver(registry_snapshot=snapshot).resolve(context),
        ),
    )
    source_resolution = _source_resolution_excluding_iva_compensation(snapshot.revision, source_resolution)
    source_resolution = _resolve_prorrata_regularizacion_sources(
        registry_snapshot=snapshot,
        work_unit=work_unit,
        context=context,
        source_resolution=source_resolution,
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        date_binding_values=date_binding_values,
        relation_values=relation_values,
        filing_period_date=filing_period_date,
    )
    source_resolution = _add_unhandled_source_diagnostics(snapshot.revision, source_resolution)
    return _add_expected_missing_binding_diagnostics(snapshot.revision, source_resolution)


def _source_provenance_refs(
    source_resolution: CalculationSourceResolution,
) -> tuple[CalculationSourceRef, ...]:
    """Project the mesh resolution's application provenance into persisted domain refs.

    Maps each :class:`~application.aggregation.CalculationSourceProvenance`
    row (the resolver→source-object→fingerprint trace) into the domain-side
    :class:`~domain.modelos.CalculationSourceRef` that
    :func:`~application.modelo._revision_persistence.persist_calculation_revision`
    persists on the :class:`~domain.modelos.CalculationRevision`. This is the
    application→domain boundary map: the domain never imports the application
    provenance model, and the compact ref deliberately drops the per-casilla
    ``legal_refs`` / ``source_refs`` (carried by the revision's ``observations``)
    to avoid duplicating that grounding.
    """
    return tuple(
        CalculationSourceRef(
            source_kind=provenance.source_kind,
            binding_source=provenance.binding_source,
            source_ref=provenance.source_ref,
            fingerprint=provenance.fingerprint,
        )
        for provenance in source_resolution.provenance
    )


def calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
    work_unit_id: str,
    *,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    iva_compensation_decision: object | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    filing_period_date: date | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    foreign_asset_observations: tuple[ForeignAssetIngestObservation, ...] = (),
    borrador_snapshot_repository: Borrador100SnapshotRepository | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    clock: datetime | None = None,
) -> BucketAggregationCalculationResult:
    """Calculate a modelo revision and return it alongside the source diagnostics.

    Identical orchestration to
    :func:`~application.modelo.calculate_modelo_revision_from_bucket_aggregation`,
    but returns a
    :class:`BucketAggregationCalculationResult` carrying both the persisted
    :class:`CalculationRevision` and the NON-blocking
    :class:`~application.aggregation.CalculationSourceDiagnostic` rows the
    source mesh raised while resolving the bucket ledger (the
    unconsumed-declarable-IVA advisories the operator-facing CLI surfaces so an
    unrouted observation is never silently under-declared).

    The bucket evidence is read from the injected
    :class:`TransactionCatalogueRepository` and
    :class:`InvoiceCatalogueRepository`; the source mesh projects their
    contributing rows plus explicitly supplied foreign-asset observations,
    previous-filing, relation-prefill, withholding, retenciones, and detail-row
    sources into the backend channels that feed the revision.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    work_unit, snapshot = _load_bucket_aggregation_context(
        work_unit_id,
        work_unit_repository=wu_repo,
    )

    # S26 boundary gate: reject any binding source that is neither enrolled in
    # the live resolver mesh nor explicitly deferred.  This converts a silent
    # blank into a loud error so a novel TOML source cannot slip through.
    assert_no_novel_source_kinds(snapshot.revision)

    # Refuse non-canonical casilla keys before source-collision and
    # bucket-merge checks compare them against registry casilla ids.
    if casilla_inputs is not None:
        casilla_inputs = _validate_casilla_input_ids(snapshot.revision, casilla_inputs)

    # Use the LOCK set (deterministic ledger resolvers only) for the pre-merge
    # caller-override guard.  Optional-return resolvers (previous_filing, profile,
    # OSS, invoices) are absent from the lock so carry-forward overrides and
    # test fixtures remain valid. See BUCKET_AGGREGATION_LOCK_SOURCES.
    _reject_caller_overrides_of_source_bindings(
        revision=snapshot.revision,
        owned_sources=BUCKET_AGGREGATION_LOCK_SOURCES,
        caller_binding_values=binding_values or {},
        caller_casilla_inputs=casilla_inputs or {},
    )
    source_resolution = _resolve_bucket_source_mesh(
        snapshot,
        work_unit,
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
        foreign_asset_observations=foreign_asset_observations,
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
        filing_period_date=filing_period_date,
    )
    # Precedence ladder step 4 (ADR ruling D2, extended): re-run the guard against
    # the merged owned-sources, but EXCLUDE the caller-overridable CARRY sources
    # (previous_filing, relation_prefill, iva_compensation_annual_partition). A
    # caller --binding override of an automatically-carried prior value is
    # legitimate and must reach the engine, where the casilla-lift no-ops on the
    # already-resolved binding and the engine's consistency check adjudicates any
    # divergence. Every other dynamically-discovered mesh source (the ledger
    # aggregations) stays guarded so the persisted revision reflects the sources
    # it claims to aggregate.
    _reject_caller_overrides_of_source_bindings(
        revision=snapshot.revision,
        owned_sources=frozenset(source_resolution.owned_sources) - CALLER_OVERRIDABLE_CARRY_SOURCES,
        caller_binding_values=binding_values or {},
        caller_casilla_inputs=casilla_inputs or {},
    )
    all_detail_rows = (*source_resolution.detail_rows, *detail_rows)
    _raise_if_m349_intracom_ledger_rows_need_operator_rows(
        work_unit=work_unit,
        transaction_repository=transaction_repository,
        detail_rows=all_detail_rows,
    )
    detail_row_binding_values = _detail_row_binding_values_for_calculation(
        work_unit=work_unit,
        detail_rows=detail_rows,
    )
    backend_binding_values = _merge_detail_row_binding_values(
        source_resolution.binding_values,
        detail_row_binding_values,
    )
    backend_source_inputs = {
        **dict(source_resolution.bound_inputs_by_casilla_id),
        **resolve_available_bound_inputs_by_casilla_id(
            snapshot.revision,
            backend_binding_values,
        ),
    }
    backend_inputs = _merge_bucket_bound_inputs(
        revision=snapshot.revision,
        casilla_inputs=casilla_inputs or {},
        bound_inputs=backend_source_inputs,
    )
    caller_binding_values = binding_values or {}
    target_period = work_unit.period.registry_token
    caller_relation_values_from_bindings = {
        relation.id: _calculated_decimal(caller_binding_values[relation.target_binding])
        for relation in snapshot.revision.relations
        if relation.target_binding in caller_binding_values
        and (not relation.target_periods or target_period in relation.target_periods)
    }
    # Feed the relation-resolver's resolved relation_values onto the engine's
    # first-class relation channel so computed casillas that reference
    # ``{ relation = ... }`` operands fire. A caller --binding override of a
    # relation's target binding also resolves that relation for formula operands;
    # this keeps the public binding override contract aligned with relation-only
    # formulas such as M100 0604. A caller --relation override remains the most
    # explicit value and wins last.
    merged_relation_values = {
        **source_resolution.relation_values,
        **caller_relation_values_from_bindings,
        **dict(relation_values or {}),
    }
    caller_relation_ids = frozenset((relation_values or {}).keys())
    caller_resolved_relation_ids = caller_relation_ids | frozenset(caller_relation_values_from_bindings)
    unresolved_relation_ids = tuple(
        relation_id
        for relation_id in source_resolution.unresolved_relation_ids
        if relation_id not in caller_resolved_relation_ids
    )
    # A caller --binding override of an expected-but-missing binding RESOLVES it,
    # so drop it from the unresolved set and its advisory (mirrors the relation
    # caller-override carve-out above).
    caller_binding_ids = frozenset(caller_binding_values)
    unresolved_binding_ids = tuple(
        binding_id
        for binding_id in source_resolution.unresolved_binding_ids
        if binding_id not in caller_binding_ids and binding_id not in detail_row_binding_values
    )
    source_diagnostics = tuple(
        diagnostic
        for diagnostic in source_resolution.diagnostics
        if (diagnostic.relation_id is None or diagnostic.relation_id not in caller_resolved_relation_ids)
        and (
            diagnostic.binding_id is None
            or (
                diagnostic.binding_id not in caller_binding_ids
                and diagnostic.binding_id not in detail_row_binding_values
            )
        )
    )
    revision = calculate_modelo_revision(
        work_unit_id,
        actor=actor,
        casilla_inputs=casilla_inputs or {},
        text_casilla_inputs=text_casilla_inputs,
        binding_values=binding_values or {},
        backend_binding_values=backend_binding_values,
        row_binding_values=source_resolution.row_binding_values,
        backend_casilla_inputs=backend_inputs,
        iva_compensation_decision=iva_compensation_decision,
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        ledger_preflight_transaction_repository=transaction_repository,
        enum_binding_values=enum_binding_values,
        borrador_snapshot_id=borrador_snapshot_id,
        relation_values=merged_relation_values,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        source_transaction_ids=tuple(source_resolution.source_transaction_ids),
        source_provenance=_source_provenance_refs(source_resolution),
        filing_period_date=filing_period_date,
        work_unit_repository=wu_repo,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        borrador_snapshot_repository=borrador_snapshot_repository,
        detail_rows=all_detail_rows,
        clock=clock,
    )
    advisory_diagnostics = collect_bucket_aggregation_advisory_diagnostics(
        snapshot.revision,
        revision.casilla_values,
        modelo=work_unit.modelo,
        period_token=work_unit.period.registry_token,
        filing_year=work_unit.filing_year,
        bucket_id=work_unit.bucket_id,
    )
    source_diagnostics = source_diagnostics + advisory_diagnostics
    return BucketAggregationCalculationResult(
        revision=revision,
        source_diagnostics=source_diagnostics,
    )


def _merge_detail_row_binding_values(
    source_binding_values: Mapping[BindingId, Decimal],
    detail_row_binding_values: Mapping[BindingId, Decimal],
) -> dict[BindingId, Decimal]:
    merged = dict(source_binding_values)
    for binding_id, value in detail_row_binding_values.items():
        merged[binding_id] = merged.get(binding_id, Decimal("0")) + value
    return merged


def _merge_bucket_bound_inputs(
    *,
    revision: ModeloRevision,
    casilla_inputs: Mapping[CasillaId, Decimal],
    bound_inputs: Mapping[CasillaId, Decimal],
) -> dict[CasillaId, Decimal]:
    casillas = casillas_by_id(revision)
    computed = sorted(
        casilla_id
        for casilla_id in bound_inputs
        if casilla_id in casillas and casillas[casilla_id].input_kind == InputKind.COMPUTED
    )
    if computed:
        raise ModeloAggregationBindingError(
            translated_message="application.modelo.errors.computed_casilla_binding_conflict",
            context={"computed": computed},
        )
    return dict(sorted({**bound_inputs, **casilla_inputs}.items()))


def _source_resolution_excluding_iva_compensation(
    revision: ModeloRevision,
    resolution: CalculationSourceResolution,
) -> CalculationSourceResolution:
    """Keep Modelo 303 prior-compensation owned exclusively by the IVA wallet."""
    excluded_bindings = IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS
    relation_ids = frozenset(rel.id for rel in revision.relations if rel.target_binding in excluded_bindings)
    if not excluded_bindings.intersection(resolution.binding_values) and not relation_ids.intersection(
        resolution.relation_values,
    ):
        return resolution
    return resolution.model_copy(
        update={
            "binding_values": {k: v for k, v in resolution.binding_values.items() if k not in excluded_bindings},
            "relation_values": {k: v for k, v in resolution.relation_values.items() if k not in relation_ids},
            "provenance": tuple(
                item
                for item in resolution.provenance
                if not any(item.source_ref.endswith(f":{binding_id}") for binding_id in excluded_bindings)
                and item.source_ref.split(":", 1)[0] not in relation_ids
            ),
        },
    )


def assert_no_novel_source_kinds(revision: ModeloRevision) -> None:
    """Raise if any binding source kind is unknown to the live mesh (S26 boundary gate).

    A binding whose ``source`` is not in the enrolled-resolver union, the
    explicitly-deferred set, or ``manual_input`` would silently blank on every
    calculation.  This gate converts that silent blank into a loud
    :exc:`ModeloAggregationBindingError` at calculation time so a novel TOML
    source cannot compile into a silently-zero revision.

    The accepted set is:

    * ``ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS`` — enrolled resolvers plus
      explicitly deferred advisory sources.

    Args:
        revision: The :class:`ModeloRevision` whose binding source kinds are
            checked against the live source-mesh enrollment.

    Raises:
        ModeloAggregationBindingError: When a binding carries a source kind
            absent from both the enrolled and the deferred sets.
    """
    novel = sorted(
        {
            str(binding.source)
            for binding in revision.bindings
            if str(binding.source) not in ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS
        },
    )
    if novel:
        raise ModeloAggregationBindingError(
            translated_message="application.modelo.errors.novel_source_kind_rejected",
            context={"novel_source_kinds": novel, "revision_id": revision.id},
        )


def _source_owned_binding_ids(
    revision: ModeloRevision, owned_sources: frozenset[BindingSourceKind]
) -> frozenset[BindingId]:
    return frozenset(binding.id for binding in revision.bindings if binding.source in owned_sources)


def _source_owned_bound_casilla_ids(
    revision: ModeloRevision, owned_sources: frozenset[BindingSourceKind]
) -> frozenset[CasillaId]:
    source_owned_binding_ids = _source_owned_binding_ids(revision, owned_sources)
    return frozenset(
        casilla.id
        for casilla in revision.casillas
        if casilla.input_kind == InputKind.BOUND
        and source_owned_binding_ids.intersection(bound_casilla_binding_ids(casilla))
    )


def _reject_caller_overrides_of_source_bindings(
    *,
    revision: ModeloRevision,
    owned_sources: frozenset[BindingSourceKind],
    caller_binding_values: Mapping[BindingId, Decimal],
    caller_casilla_inputs: Mapping[CasillaId, Decimal],
) -> None:
    """Refuse caller-supplied bindings or casilla inputs that collide with values bucket source resolvers own.

    Bucket-aggregation calculation derives source-owned binding values
    (and the casillas bound to them) from bucket substrate. Letting a
    caller override those silently would break calculation grounding:
    the persisted revision would no longer reflect the sources it claims
    to aggregate. Both collisions are rejected before any value reaches
    the engine.
    """
    rejected_bindings = sorted(
        set(caller_binding_values).intersection(_source_owned_binding_ids(revision, owned_sources)),
    )
    if rejected_bindings:
        # For the IVA compensation binding the operator should use the seed verb, not
        # a manual override, to set the prior carry-forward balance.
        seed_suggestion = (
            "aeat app modelo iva-wallet seed"
            if any("compensacion-pendiente-anteriores" in b for b in rejected_bindings)
            else None
        )
        raise ModeloAggregationBindingError(
            translated_message="errors.error.error_modelo_aggregation_binding",
            suggestion=seed_suggestion,
        )
    rejected_casillas = sorted(
        set(caller_casilla_inputs).intersection(_source_owned_bound_casilla_ids(revision, owned_sources)),
    )
    if rejected_casillas:
        raise ModeloAggregationBindingError(
            translated_message="application.modelo.errors.caller_casilla_source_binding_conflict",
            context={"casillas": rejected_casillas},
        )


def list_calculation_revisions(
    *,
    work_unit_id: str | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> tuple[CalculationRevision, ...]:
    """List calculation revisions, optionally filtered to one work unit.

    Results are sorted by ``(work_unit_id, created_at)`` so the
    chronological revision chain for one work unit is contiguous
    and stable across calls.

    Each element is a :class:`CalculationRevision`.
    """
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    revisions = tuple(
        revision for revision in catalogue.values() if work_unit_id is None or revision.work_unit_id == work_unit_id
    )
    return tuple(sorted(revisions, key=lambda r: (r.work_unit_id, r.created_at)))


def get_calculation_revision(
    calculation_revision_id: str,
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> CalculationRevision:
    """Return one calculation revision by id, or raise.

    Returns the :class:`CalculationRevision` matching
    ``calculation_revision_id``.
    """
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    revision = catalogue.get(calculation_revision_id)
    if revision is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    return revision


def mark_revision_verificado_completo(
    calculation_revision_id: str,
    *,
    actor: str,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> CalculationRevision:
    """Transition a draft revision to ``VERIFICADO_COMPLETO``.

    The revision must currently be in ``BORRADOR`` state. After the
    transition the revision is immutable; subsequent calculation
    work on the same work unit must produce a new revision.

    Args:
        calculation_revision_id: The id of the draft revision to promote.
        actor: Operator identifier stamped as ``verified_by``.
        calculation_repository: Optional calculation-revision catalogue
            repository override.
        work_unit_repository: Optional work-unit catalogue repository
            override used to refuse direct promotion for cross-period
            dependency revisions.
        clock: Optional UTC timestamp override for ``verified_at``.

    Returns:
        The updated :class:`CalculationRevision` in ``VERIFICADO_COMPLETO`` state.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is
            absent.
        CalculationRevisionStateError: When the revision is not
            currently in ``BORRADOR`` state.
    """
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    existing = catalogue.get(calculation_revision_id)
    if existing is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    if existing.state is not CalculationRevisionState.BORRADOR:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{existing.state.value!r}; only DRAFT revisions can be marked verified-complete",
        )
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    work_unit = wu_repo.load().get(existing.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": existing.work_unit_id},
        )
    from ._profile_readiness_gate import require_profile_ready_for_work_unit

    require_profile_ready_for_work_unit(work_unit)
    _refuse_direct_cross_period_verification(existing, work_unit_repository=wu_repo)
    now = clock or _utc_now()
    verified = existing.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
        },
    )
    cr_repo.save(upsert_calculation_revision(catalogue, verified))
    return verified


def _refuse_direct_cross_period_verification(
    revision: CalculationRevision,
    *,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
) -> None:
    """Require the full verification pipeline for cross-period dependency revisions."""
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    work_unit = wu_repo.load().get(revision.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": revision.work_unit_id},
        )
    snapshot = _resolve_registry_snapshot_for_work_unit(work_unit)
    if tuple(_cross_period_dependency_requirements(snapshot)):
        raise ModeloCrossPeriodCleanStateError(
            translated_message="application.modelo.errors.cross_period_clean_state_incomplete",
            context={
                "calculation_revision_id": revision.calculation_revision_id,
                "work_unit_id": revision.work_unit_id,
                "modelo": work_unit.modelo,
                "filing_year": str(work_unit.filing_year),
                "period": work_unit.period.registry_token,
            },
            suggestion="aeat app modelo work verify",
        )
