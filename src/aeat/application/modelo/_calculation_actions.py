"""Calculation revision actions for modelo filings.

Resolves the law-determined :class:`RegistrySnapshot` for each work unit and
asserts its revision at calc time before computing. Uses
:class:`BucketEventHistoryRepository` and :class:`ModeloRevision` for compliance.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core import BindingSourceKind
from ...core.time import now as _utc_now
from ...domain._identifiers import canonical_decimal_string as _canonical_decimal_str
from ...domain.buckets import BucketEventHistoryRepository
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry import (
    BindingId,
    CasillaId,
    InputKind,
    ModeloRevision,
    RelationId,
    calculate_registry_snapshot,
    casillas_by_id,
    validated_casilla_id,
)
from ...domain.deadlines import IVARegime
from ...domain.invoices import InvoiceCatalogueRepository
from ...domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.modelos._row_models import ModeloDetailRow
from ...domain.modelos._work_unit import WorkUnit, WorkUnitState
from ...domain.period import period_end_date
from ...domain.transactions import TransactionCatalogueRepository
from ..aggregation._source_mesh import DEFERRED_SOURCE_KINDS as _DEFERRED_SOURCE_KINDS
from ..calculations import cross_period_dependency_requirements as _cross_period_dependency_requirements
from ..live import Borrador100SnapshotRepository
from . import _iva_wallet_gate
from ._action_errors import (
    CalculationRegistryUnavailableError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloAggregationBindingError,
    ModeloCrossPeriodCleanStateError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    WorkUnitRevisionDivergenceError,
)
from ._binding_resolution import (
    resolve_available_bound_inputs_by_casilla_id,
    resolve_calculation_binding_inputs,
)
from ._calculation_helpers import (
    build_typed_observations as _build_typed_observations,
)
from ._calculation_helpers import (
    load_work_unit_for_calculation as _load_work_unit_for_calculation,
)
from ._calculation_helpers import (
    resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit,
)
from ._official_box_advisory import collect_official_box_unpopulated_diagnostics
from ._prior_payment_advisory import (
    collect_prior_payment_minoracion_not_captured_diagnostics,
    collect_prior_payment_not_deducted_diagnostics,
)
from ._registry_helpers import validate_casilla_input_ids as _validate_casilla_input_ids
from ._registry_resources import authority_via_resources as _authority_via_resources
from ._registry_resources import registry_root as _registry_root
from ._revision_persistence import persist_calculation_revision

if TYPE_CHECKING:
    from ...domain.calculations.registry import RegistrySnapshot
    from ...domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
    from ..aggregation import CalculationSourceDiagnostic, CalculationSourceResolution
    from ..calculations._observations_repository import IvaWalletDecisionRepository


@dataclass(frozen=True, slots=True)
class BucketAggregationCalculationResult:
    """Calculation revision plus the non-blocking source diagnostics raised while resolving it.

    ``source_diagnostics`` carries the :class:`CalculationSourceDiagnostic`
    rows the source mesh emitted during resolution — notably the
    unconsumed-declarable-IVA advisories (a declarable IVA observation no
    ``ledger_iva_aggregation`` binding selects). They are NON-blocking: the
    revision in ``revision`` was computed and persisted regardless. Surfacing
    them keeps an unrouted declarable observation from being silently
    under-declared (no-silent-under-declaration).
    """

    revision: CalculationRevision
    source_diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()


_apply_iva_compensation_decision_binding = _iva_wallet_gate.apply_iva_compensation_decision_binding
_taxpayer_nif_for_bucket = _iva_wallet_gate.taxpayer_nif_for_bucket
iva_wallet_blocked_message = _iva_wallet_gate.iva_wallet_blocked_message
resolve_iva_compensation_decision_for_calculation = _iva_wallet_gate.resolve_iva_compensation_decision_for_calculation


# S26 boundary gate — the COMPLETE set of source kinds that the live calculate
# path handles, either through an enrolled resolver (ENROLLED) or through an
# explicitly-deferred advisory (DEFERRED, per W02.P06.S10).  A registry binding
# whose source is not in this set would compile and silently blank; instead the
# gate rejects it at calculation time so the novel source never reaches the
# engine undetected.
#
# ENROLLED — covered by an active ModeloSourceResolver in the live mesh:
#   ledger_iva_aggregation        — LedgerIvaAggregationSourceResolver
#   ledger_renta_expense_aggregation — LedgerRentaExpenseAggregationSourceResolver
#   ledger_renta_income_aggregation  — LedgerRentaIncomeAggregationSourceResolver (S09)
#   ledger_renta_gasto_aggregation   — LedgerRentaGastoAggregationSourceResolver
#                                      (M130 casilla 02 deductible expenses; OUTGOING
#                                      sibling of the income resolver)
#   ledger_oss_aggregation           — OssIossLedgerSourceResolver (S09)
#   retenciones_aggregation          — RetencionesAggregationSourceResolver (RET-1):
#                                      materialises the M180/190/193 distinct
#                                      perceptor-NIF count from the dedicated
#                                      per-perceptor retención store
#   collectible_invoice              — InvoiceCatalogueSourceResolver (S09)
#   payable_invoice                  — InvoiceCatalogueSourceResolver (S09, declared no
#                                      registry binding yet — live capacity headroom)
#   previous_filing                  — PreviousFilingSourceResolver
#   relation_prefill                 — RelationPrefillSourceResolver (S13) — folds
#                                      prior observations through registry relations
#                                      and materialises target_binding slots
#   profile                          — ProfileSourceResolver (pre-mesh gate)
#   borrador                         — Borrador100 source (pre-mesh gate)
#   iva_wallet_decision              — IvaWalletDecisionSourceResolver (pre-mesh gate)
#   manual_input                     — operator-supplied, never enrolled in resolver
#
# DEFERRED — no resolver yet; emit advisory instead of silently blanking (S10):
#   withholding, atribucion_member, related_party_operation, foreign_asset, refund_operation
_BUCKET_AGGREGATION_OWNED_SOURCES: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.LEDGER_IVA_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_EXPENSE_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_GASTO_AGGREGATION,
        BindingSourceKind.LEDGER_OSS_AGGREGATION,
        BindingSourceKind.RETENCIONES_AGGREGATION,
        BindingSourceKind.COLLECTIBLE_INVOICE,
        BindingSourceKind.PAYABLE_INVOICE,
        BindingSourceKind.PREVIOUS_FILING,
        BindingSourceKind.RELATION_PREFILL,
        BindingSourceKind.PROFILE,
        BindingSourceKind.BORRADOR,
        BindingSourceKind.IVA_WALLET_DECISION,
        BindingSourceKind.MANUAL_INPUT,
    },
)

# Caller-override lock set — the subset of OWNED sources whose resolvers are
# deterministic and always return values from the bucket (so callers MUST NOT
# override their bindings / casillas on the aggregation path).  This is a strict
# subset of _BUCKET_AGGREGATION_OWNED_SOURCES; optional-return resolvers like
# previous_filing, profile, and the OSS/invoice resolvers are intentionally absent
# so test fixtures and carry-forward overrides remain valid.
_BUCKET_AGGREGATION_LOCK_SOURCES: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.LEDGER_IVA_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_EXPENSE_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_GASTO_AGGREGATION,
        BindingSourceKind.LEDGER_OSS_AGGREGATION,
        BindingSourceKind.COLLECTIBLE_INVOICE,
        BindingSourceKind.PAYABLE_INVOICE,
    },
)

# Explicitly-deferred source kinds (S10): advisory fires on source_diagnostics,
# never enrolled as manual_sources (which would silence the advisory).
# Canonical definition: DEFERRED_SOURCE_KINDS in aggregation._source_mesh.

# ---------------------------------------------------------------------------
# Declared precedence ladder (W03.P09.S15 — codifies D2/D3 out of inline notes).
#
# For the decimal binding channel, lowest -> highest precedence:
#
#   1. profile resolver           (pre-mesh taxpayer facts)
#   2. mesh backend resolvers     (ledger aggregations, previous_filing,
#                                  relation_prefill) — EXCLUSIVE intra-mesh
#                                  ownership: a duplicate claim is a hard
#                                  AggregationValidationError via _claim_binding,
#                                  never a quiet override
#   3. borrador                   (M100 prefill)
#   4. caller overrides           (--binding / --casilla) — permitted ONLY for
#                                  the auto-CARRIED sources below; REFUSED with a
#                                  hard error for ledger-owned sources (the
#                                  persisted revision must reflect the sources it
#                                  claims to aggregate)
#
# iva_wallet_decision sits OUTSIDE this ladder as an exclusive owner with
# refusal-on-conflict semantics: the M303 compensación binding is stripped from
# the previous-filing resolution pre-mesh (D3) and any conflicting caller/backend
# value raises ModeloIvaWalletReconciliationBlocked rather than being out-ranked.
#
# Caller-overridable carried sources (the D2 carve-out, extended to relation
# carries by the same logic): an operator override of an auto-carried PRIOR value
# is legitimate — the engine's consistency check adjudicates divergence. A caller
# --binding for one of these reaches the engine; for every other mesh-owned
# (ledger) source it is refused.
_CALLER_OVERRIDABLE_CARRY_SOURCES: frozenset[BindingSourceKind] = frozenset(
    {BindingSourceKind.PREVIOUS_FILING, BindingSourceKind.RELATION_PREFILL},
)


def calculate_modelo_revision(
    work_unit_id: str,
    *,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    backend_binding_values: Mapping[BindingId, Decimal] | None = None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    iva_compensation_decision: object | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    ledger_preflight_transaction_repository: TransactionCatalogueRepository | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    unresolved_relation_ids: tuple[RelationId, ...] = (),
    source_transaction_ids: tuple[str, ...] = (),
    filing_period_date: date | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    clock: datetime | None = None,
) -> CalculationRevision:
    """Run the registry formula engine, persist a draft revision, and return a :class:`CalculationRevision`.

    ``ledger_preflight_transaction_repository`` is a :class:`TransactionCatalogueRepository`
    used for the ledger preflight check before calculation.

    Pipeline:

    1. Load the work unit; refuse on DISCARDED.
    2. Resolve the registry snapshot for ``(modelo, filing_year,
       period)``. Failure to resolve raises
       :exc:`CalculationRegistryUnavailableError` — the calculate
       path runs the engine, so a missing snapshot is a hard refusal.
    3. Run :func:`calculate_registry_snapshot` over the snapshot
       with the operator-supplied manual casilla inputs, binding
       values, enum-binding values, and relation values. The
       engine evaluates every declared formula in dependency order
       and returns the full ``casilla_values`` map (inputs plus
       formula outputs).
    4. Build canonical-string ``input_values_by_casilla_id``, ``binding_overrides``,
       and ``relation_overrides`` from the engine inputs (so the
       content-addressed revision id is stable across structurally
       identical re-runs).
    5. Persist the revision in ``DRAFT`` state; advance the work
       unit's ``current_calculation_revision_id`` pointer; emit
       ``modelo.calculation.created``.

    The revision starts in DRAFT state; callers must run
    ``verify_modelo_revision`` and ``file_modelo_revision``
    explicitly to advance through the lifecycle.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    work_units = wu_repo.load()
    work_unit = _load_work_unit_for_calculation(work_units, work_unit_id=work_unit_id)
    snapshot = _resolve_registry_snapshot_for_work_unit(work_unit)
    # Casilla inputs are accepted only as canonical casilla.id values.
    # Printed registry numbers and BOE form numbers must fail before the
    # engine consumes or persists them.
    casilla_inputs = _validate_casilla_input_ids(snapshot.revision, casilla_inputs)
    if backend_casilla_inputs is not None:
        backend_casilla_inputs = _validate_casilla_input_ids(snapshot.revision, backend_casilla_inputs)
    _raise_if_ledger_preflight_blocks_calculation(
        work_unit=work_unit,
        revision=snapshot.revision,
        transaction_repository=ledger_preflight_transaction_repository,
    )
    iva_compensation_decision = resolve_iva_compensation_decision_for_calculation(
        work_unit,
        snapshot=snapshot,
        supplied_decision=iva_compensation_decision,
        repository=iva_compensation_decision_repository,
        binding_values=binding_values,
        backend_binding_values=backend_binding_values,
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
    )

    period_date = filing_period_date or period_end_date(
        filing_year=work_unit.filing_year,
        registry_period=work_unit.period.registry_token,
    )
    caller_binding_values = dict(binding_values or {})
    caller_enum_binding_values = dict(enum_binding_values or {})
    lower_precedence_binding_values = dict(backend_binding_values or {})
    _apply_iva_compensation_decision_binding(
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        bucket_id=work_unit.bucket_id,
        revision=snapshot.revision,
        taxpayer_nif=_taxpayer_nif_for_bucket(work_unit.bucket_id),
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        caller_binding_values=caller_binding_values,
        backend_binding_values=lower_precedence_binding_values,
        decision=iva_compensation_decision,
    )
    binding_resolution = resolve_calculation_binding_inputs(
        bucket_id=work_unit.bucket_id,
        snapshot=snapshot,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        casilla_inputs=casilla_inputs,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        backend_binding_values=lower_precedence_binding_values,
        backend_casilla_inputs=backend_casilla_inputs,
        borrador_snapshot_id=borrador_snapshot_id,
        borrador_snapshot_repository=borrador_snapshot_repository,
        relation_values=relation_values,
    )
    borrador_result = binding_resolution.borrador_result
    resolved_bindings = dict(binding_resolution.resolved_bindings)
    resolved_enum_bindings = dict(binding_resolution.resolved_enum_bindings)
    resolved_date_bindings = dict(binding_resolution.resolved_date_bindings)
    resolved_relations = dict(binding_resolution.resolved_relations)
    resolved_inputs = dict(binding_resolution.resolved_inputs)

    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=resolved_inputs,
        date_context={"filing_period": period_date},
        binding_values=resolved_bindings,
        enum_binding_values=resolved_enum_bindings,
        relation_values=resolved_relations,
        unresolved_relation_ids=unresolved_relation_ids,
        date_binding_values=resolved_date_bindings or None,
    )

    input_values_by_casilla_id: dict[CasillaId, str] = dict(
        sorted(
            (
                validated_casilla_id(k, surface="calculate_modelo_revision.input_values_by_casilla_id"),
                _canonical_decimal_str(v),
            )
            for k, v in resolved_inputs.items()
        ),
    )
    binding_overrides: dict[BindingId, str] = dict(
        sorted(
            [(k.strip(), _canonical_decimal_str(v)) for k, v in resolved_bindings.items()]
            + [(k.strip(), v.strip()) for k, v in resolved_enum_bindings.items()]
            # Persist date-binding inputs with the other BindingId-keyed replay
            # values. Relations ride the separate relation_overrides channel
            # below so a BindingId map never carries RelationId keys.
            + [(k.strip(), v.isoformat()) for k, v in resolved_date_bindings.items()],
        ),
    )
    relation_overrides: dict[RelationId, str] = dict(
        sorted((k.strip(), _canonical_decimal_str(v)) for k, v in resolved_relations.items()),
    )
    casilla_values = dict(engine_result.values)
    typed_observations = _build_typed_observations(engine_result=engine_result, snapshot=snapshot)

    now = clock or _utc_now()
    return persist_calculation_revision(
        work_unit_id=work_unit_id,
        work_unit=work_unit,
        work_units=work_units,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        relation_overrides=relation_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        borrador_snapshot_id=borrador_result.borrador_snapshot_id,
        bindings_sourced_from_borrador=borrador_result.bindings_sourced_from_borrador,
        observations=typed_observations,
        detail_rows=detail_rows,
        formula_count=len(engine_result.entries),
        actor=actor,
        now=now,
        calculation_repository=cr_repo,
        work_unit_repository=wu_repo,
        bucket_event_repository=bv_repo,
    )


# ANY-RETURN-RATIONALE-ACTIONS-IVA-WALLET-DECISION:
# Wrapper preserves the legacy _actions.py private surface and drift token
# while the extracted IVA wallet gate owns message rendering.
def _iva_wallet_blocked_message(decision: IvaCompensationReconciliationDecision) -> str:
    return iva_wallet_blocked_message(decision)


def _iva_regime_for_bucket(bucket_id: str) -> str | None:
    """Return the profile's ``iva.regime`` value, or ``None`` if unset or profile absent."""
    from ...domain.user_profile import ProfileNotFoundError
    from ..user_profile._profile_repository import ProfileRepository
    from ..user_profile._projections import record_to_path_values

    try:
        profile = ProfileRepository().load(bucket_id)
        record = profile.record
    except ProfileNotFoundError:
        return None
    value = record_to_path_values(record).get("iva.regime")
    if value is None or not str(value).strip():
        return None
    return str(value).strip()


_LEDGER_PREFLIGHT_BINDING_SOURCES = frozenset(
    {
        "ledger_iva_aggregation",
        "ledger_renta_expense_aggregation",
    },
)
# IVA regimes that do not use ledger aggregation for IVA repercutido; these
# clients supply régimen-simplificado casillas (47-58) directly as manual
# inputs rather than deriving them from the transaction ledger.
_IVA_LEDGER_EXEMPT_REGIMES = frozenset({IVARegime.SIMPLIFICADO})


def _raise_if_ledger_preflight_blocks_calculation(
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    transaction_repository: TransactionCatalogueRepository | None = None,
) -> None:
    if not any(binding.source in _LEDGER_PREFLIGHT_BINDING_SOURCES for binding in revision.bindings):
        return
    # Régimen simplificado clients supply casillas 47-58 as manual inputs;
    # they have no transaction ledger to satisfy the IVA aggregation preflight.
    iva_regime = _iva_regime_for_bucket(work_unit.bucket_id)
    if iva_regime in _IVA_LEDGER_EXEMPT_REGIMES:
        return
    from ..ledger import preflight_ledger_tax_readiness

    report = preflight_ledger_tax_readiness(
        bucket_id=work_unit.bucket_id,
        period=work_unit.period,
        transaction_repository=transaction_repository,
    )
    if report.ready:
        return
    first_issue = report.issues[0]
    raise ModeloAggregationBindingError(
        translated_message="application.modelo.errors.ledger_preflight_blocked",
        context={
            "transaction_id": first_issue.transaction_id,
            "reason": first_issue.reason.value,
            "period": str(report.period),
        },
        suggestion=f"aeat app ledger preflight --period {report.period.registry_token} --year {report.period.year}",
    )


def calculate_modelo_revision_from_bucket_aggregation(
    work_unit_id: str,
    *,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
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
    borrador_snapshot_repository: Borrador100SnapshotRepository | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    clock: datetime | None = None,
) -> CalculationRevision:
    """Calculate a modelo revision using bucket-local ledger aggregation.

    ``transaction_repository`` is a :class:`TransactionCatalogueRepository` used to
    load the bucket-local ledger transactions for aggregation.
    ``invoice_repository`` is an :class:`InvoiceCatalogueRepository` used to load
    invoice data for the aggregation resolvers that require it.

    Returns a :class:`CalculationRevision`. Use
    :func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`
    when the caller also needs the non-blocking source diagnostics (e.g. the
    operator-facing CLI calculate surface, which surfaces unconsumed-declarable
    -IVA advisories).
    """
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_id,
        actor=actor,
        casilla_inputs=casilla_inputs,
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
        borrador_snapshot_repository=borrador_snapshot_repository,
        detail_rows=detail_rows,
        clock=clock,
    ).revision


def _resolve_bucket_source_mesh(
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    *,
    transaction_repository: TransactionCatalogueRepository | None,
    invoice_repository: InvoiceCatalogueRepository | None,
) -> CalculationSourceResolution:
    """Resolve the live source mesh for a bucket-aggregation calculation.

    Builds the :class:`CalculationSourceContext`, runs every enrolled ledger /
    invoice / carry resolver through :func:`merge_source_resolutions`, and
    augments the result with the unhandled-binding-source advisories for any
    declared source with no enrolled resolver. Returns the merged resolution.
    """
    from ..aggregation import (
        CalculationSourceContext,
        LedgerIvaAggregationSourceResolver,
        LedgerRentaExpenseAggregationSourceResolver,
        LedgerRentaGastoAggregationSourceResolver,
        LedgerRentaIncomeAggregationSourceResolver,
        OssIossLedgerSourceResolver,
        RetencionesAggregationSourceResolver,
        collect_unhandled_source_diagnostics,
        merge_source_resolutions,
    )
    from ..calculations import PreviousFilingSourceResolver, RelationPrefillSourceResolver
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
            LedgerIvaAggregationSourceResolver(transaction_repository=transaction_repository).resolve(context),
            LedgerRentaExpenseAggregationSourceResolver(
                transaction_repository=transaction_repository,
                invoice_repository=invoice_repository,
            ).resolve(context),
            # M130 actividad-económica income (ledger_renta_income_aggregation).
            LedgerRentaIncomeAggregationSourceResolver(
                transaction_repository=transaction_repository,
            ).resolve(context),
            # M130 deductible-expense / gasto into casilla 02
            # (ledger_renta_gasto_aggregation) — the OUTGOING sibling of the
            # income resolver, same cumulative quarterly window.
            LedgerRentaGastoAggregationSourceResolver(
                transaction_repository=transaction_repository,
            ).resolve(context),
            # M369 OSS/IOSS (ledger_oss_aggregation).  The live path projects
            # OSS/IOSS-tagged issued invoices into validated ledger candidates;
            # pre-classified callers can still pass candidates directly through
            # the resolver constructor.
            OssIossLedgerSourceResolver(invoice_repository=invoice_repository).resolve(context),
            # M180/190/193 distinct perceptor-NIF count (retenciones_aggregation):
            # reads the dedicated per-perceptor retención store and materialises the
            # "número total de perceptores" box via the validated distinct-count
            # primitive — replacing the wrong sum-of-quarterly-M115-counts relation
            # (RET-1). Empty store on a declaring revision surfaces a no-silent advisory.
            RetencionesAggregationSourceResolver().resolve(context),
            # M349 collectible / payable invoices (collectible_invoice,
            # payable_invoice).  Loads the encrypted invoice catalogue and resolves
            # binding values for intra-community transactions in scope.
            InvoiceCatalogueSourceResolver(
                invoice_repository=invoice_repository,
            ).resolve(context),
            # Cross-period carry: prior-filing observations flow through the
            # backend-binding channel so an automatically-carried previous_filing
            # value fills the binding gap, while a caller --binding still
            # overrides it (it is deliberately NOT added to the owned-source
            # rejection set below — ruling D2). The 303 IVA-compensation
            # binding is excluded here because the iva-wallet compensación
            # decision owns it (ruling D3).
            _previous_filing_resolution_excluding_iva_compensation(
                PreviousFilingSourceResolver(registry_snapshot=snapshot).resolve(context),
            ),
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
        ),
    )
    # Safety net: collect non-blocking advisories for every binding whose declared
    # source has no enrolled resolver and is not explicitly deferred.
    # handled_sources covers all enrolled-resolver owned_sources plus the three
    # pre-mesh-handled source kinds (profile, borrador, iva_wallet_decision).
    # DEFERRED_SOURCE_KINDS are NOT on the manual_sources allowlist so they still
    # emit an advisory.
    _pre_mesh_handled: frozenset[str] = frozenset({"profile", "borrador", "iva_wallet_decision"})
    _handled = frozenset(source_resolution.owned_sources) | _pre_mesh_handled
    _unhandled_diagnostics = collect_unhandled_source_diagnostics(
        snapshot.revision,
        handled_sources=_handled,
        manual_sources=frozenset({"manual_input"}),
    )
    if _unhandled_diagnostics:
        source_resolution = source_resolution.model_copy(
            update={"diagnostics": source_resolution.diagnostics + _unhandled_diagnostics},
        )
    return source_resolution


def calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
    work_unit_id: str,
    *,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
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
    borrador_snapshot_repository: Borrador100SnapshotRepository | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    clock: datetime | None = None,
) -> BucketAggregationCalculationResult:
    """Calculate a modelo revision and return it alongside the source diagnostics.

    Identical orchestration to
    :func:`calculate_modelo_revision_from_bucket_aggregation`, but returns a
    :class:`BucketAggregationCalculationResult` carrying both the persisted
    :class:`CalculationRevision` and the NON-blocking
    :class:`CalculationSourceDiagnostic` rows the source mesh raised while
    resolving the bucket ledger (the unconsumed-declarable-IVA advisories the
    operator-facing CLI surfaces so an unrouted observation is never silently
    under-declared).

    The ledger evidence is read from the injected
    :class:`TransactionCatalogueRepository` and
    :class:`InvoiceCatalogueRepository`; the source mesh projects their
    contributing rows into the bucket aggregation that feeds the revision.
    """
    from ...domain.calculations.registry import RegistrySnapshotError

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    work_units = wu_repo.load()
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    if work_unit.state is WorkUnitState.DESCARTADO:
        raise WorkUnitMutationRefusedError(
            translated_message="application.modelo.errors.work_unit_discarded_cannot_calculate",
            context={"work_unit_id": work_unit_id},
        )

    try:
        authority = _authority_via_resources()
        snapshot = authority.snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except FileNotFoundError as exc:
        raise CalculationRegistryUnavailableError(
            translated_message="application.modelo.errors.calculation_registry_root_missing",
            context={"registry_root": _registry_root()},
        ) from exc
    except RegistrySnapshotError as exc:
        raise CalculationRegistryUnavailableError(
            translated_message="application.modelo.errors.calculation_registry_snapshot_unresolved",
            context={
                "modelo": work_unit.modelo,
                "filing_year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
            },
        ) from exc
    # D1 calc-time assertion: the law-determined revision must equal the
    # revision the work unit was created against.  The work unit's revision_id
    # is an identity claim, not a resolution input (per the period-revision-
    # resolution ADR ruling 2).
    if snapshot.revision.id != work_unit.revision_id:
        raise WorkUnitRevisionDivergenceError(
            f"work unit {work_unit.work_unit_id!r} was created against registry revision "
            f"{work_unit.revision_id!r}, but the law-determined revision for "
            f"modelo {work_unit.modelo!r} {work_unit.filing_year} {work_unit.period.registry_token!r} "
            f"is now {snapshot.revision.id!r}. "
            f"The registry's law-mapping was corrected after this work unit was created. "
            f"Re-create the work unit (discard this one and run `aeat app modelo work create`) "
            f"to bind it to the current law-determined revision.",
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
    # test fixtures remain valid.  See _BUCKET_AGGREGATION_LOCK_SOURCES.
    _reject_caller_overrides_of_source_bindings(
        revision=snapshot.revision,
        owned_sources=_BUCKET_AGGREGATION_LOCK_SOURCES,
        caller_binding_values=binding_values or {},
        caller_casilla_inputs=casilla_inputs or {},
    )
    source_resolution = _resolve_bucket_source_mesh(
        snapshot,
        work_unit,
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
    )
    # Precedence ladder step 4 (ADR ruling D2, extended): re-run the guard against
    # the merged owned-sources, but EXCLUDE the caller-overridable CARRY sources
    # (previous_filing + relation_prefill). A caller --binding override of an
    # automatically-CARRIED prior value (a previous-filing carry or a relation
    # fold-in) is legitimate and must reach the engine, where the casilla-lift
    # no-ops on the already-resolved binding and the engine's consistency check
    # adjudicates any divergence. Every other dynamically-discovered mesh source
    # (the ledger aggregations) stays guarded so the persisted revision reflects
    # the sources it claims to aggregate.
    _reject_caller_overrides_of_source_bindings(
        revision=snapshot.revision,
        owned_sources=frozenset(source_resolution.owned_sources) - _CALLER_OVERRIDABLE_CARRY_SOURCES,
        caller_binding_values=binding_values or {},
        caller_casilla_inputs=casilla_inputs or {},
    )
    backend_inputs = _merge_bucket_bound_inputs(
        revision=snapshot.revision,
        casilla_inputs=casilla_inputs or {},
        bound_inputs=resolve_available_bound_inputs_by_casilla_id(
            snapshot.revision,
            source_resolution.binding_values,
        ),
    )
    # Feed the relation-resolver's resolved relation_values onto the engine's
    # first-class relation channel so computed casillas that reference
    # ``{ relation = ... }`` operands fire. A caller --relation override still
    # wins (precedence ladder step 4, D2 carve-out for relation carries): an
    # operator override of an auto-carried relation value is legitimate.
    merged_relation_values = {**source_resolution.relation_values, **dict(relation_values or {})}
    caller_relation_ids = frozenset((relation_values or {}).keys())
    unresolved_relation_ids = tuple(
        relation_id
        for relation_id in source_resolution.unresolved_relation_ids
        if relation_id not in caller_relation_ids
    )
    source_diagnostics = tuple(
        diagnostic
        for diagnostic in source_resolution.diagnostics
        if diagnostic.relation_id is None or diagnostic.relation_id not in caller_relation_ids
    )
    revision = calculate_modelo_revision(
        work_unit_id,
        actor=actor,
        casilla_inputs=casilla_inputs or {},
        binding_values=binding_values or {},
        backend_binding_values=source_resolution.binding_values,
        backend_casilla_inputs=backend_inputs,
        iva_compensation_decision=iva_compensation_decision,
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        ledger_preflight_transaction_repository=transaction_repository,
        enum_binding_values=enum_binding_values,
        borrador_snapshot_id=borrador_snapshot_id,
        relation_values=merged_relation_values,
        unresolved_relation_ids=unresolved_relation_ids,
        source_transaction_ids=tuple(source_resolution.source_transaction_ids),
        filing_period_date=filing_period_date,
        work_unit_repository=wu_repo,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        borrador_snapshot_repository=borrador_snapshot_repository,
        detail_rows=detail_rows,
        clock=clock,
    )
    # Stage 1 advisory (no-silent-under-declaration): a ledger-driven calculate
    # folds cuota into the semantic aggregate layer while the official
    # Diseño-de-Registros numbered boxes (manual, the cells the human transcribes
    # to the AEAT sede) stay zero. Surface that contradiction as a non-blocking
    # advisory, reusing the revision's ADVISORY implies_any_nonzero predicates as
    # the single total→constituent mapping so it cannot drift from the verify gate.
    official_box_diagnostics = collect_official_box_unpopulated_diagnostics(
        snapshot.revision,
        revision.casilla_values,
    )
    source_diagnostics = source_diagnostics + official_box_diagnostics
    # Stage 1 advisory (no-silent-under-declaration): Modelo 130 is cumulative
    # from the start of the ejercicio, but casilla 05 ("Pagos fraccionados
    # anteriores") is a manual cell with no binding — a cumulative 2T/3T/4T
    # calculate never auto-deducts the prior trimestre's pago fraccionado, so the
    # operator over-pays (RD 439/2007 art. 110; casilla 07 = 04 - 05 - 06). The
    # advisory fires only when a prior-trimestre M130 filing for the same
    # ejercicio actually exists in the catalogue, so a true first-obligation
    # filer (whose casilla 05 is legitimately null) stays silent.
    from ..calculations import CalculationObservationRepository

    prior_payment_observation_repository = CalculationObservationRepository()
    prior_payment_diagnostics = collect_prior_payment_not_deducted_diagnostics(
        revision.casilla_values,
        modelo=work_unit.modelo,
        period_token=work_unit.period.registry_token,
        filing_year=work_unit.filing_year,
        observation_repository=prior_payment_observation_repository,
    )
    source_diagnostics = source_diagnostics + prior_payment_diagnostics
    # Stage-2 honesty (no-silent-under-declaration): once casilla 05 is a bound
    # carry, a prior filing that carries casilla 07 but no casilla-16 entry is
    # "not captured" - the carry treats the absent minoración as zero, so surface
    # the gap rather than silently dropping it (ADR
    # 2026-06-13-modelo-130-pagos-fraccionados-carry, casilla-16
    # filed-zero-vs-not-captured).
    minoracion_diagnostics = collect_prior_payment_minoracion_not_captured_diagnostics(
        modelo=work_unit.modelo,
        period_token=work_unit.period.registry_token,
        filing_year=work_unit.filing_year,
        observation_repository=prior_payment_observation_repository,
    )
    source_diagnostics = source_diagnostics + minoracion_diagnostics
    return BucketAggregationCalculationResult(
        revision=revision,
        source_diagnostics=source_diagnostics,
    )


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


def _previous_filing_resolution_excluding_iva_compensation(
    resolution: CalculationSourceResolution,
) -> CalculationSourceResolution:
    """Strip the M303 IVA-compensation binding from a previous_filing resolution.

    ADR ruling D3: the iva-wallet compensación decision owns the
    ``modelo-303-compensacion-pendiente-anteriores`` binding. The cross-period
    carry resolver must NOT also emit it, or the two write paths would
    double-count the prior carry-forward balance. This drops both the binding
    value and any matching provenance row before the resolution enters the
    source mesh.

    Uses :class:`CalculationSourceResolution` (immutable); returns a copy with
    the 303 compensation binding removed.
    """
    from ..calculations._binding_prefill import _MODELO_303_IVA_COMPENSATION_BINDING_ID

    excluded = _MODELO_303_IVA_COMPENSATION_BINDING_ID
    if excluded not in resolution.binding_values:
        return resolution
    return resolution.model_copy(
        update={
            "binding_values": {k: v for k, v in resolution.binding_values.items() if k != excluded},
            "provenance": tuple(item for item in resolution.provenance if not item.source_ref.endswith(f":{excluded}")),
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

    * ``_BUCKET_AGGREGATION_OWNED_SOURCES`` — enrolled resolvers + pre-mesh
      gates + ``manual_input``.
    * ``_DEFERRED_SOURCE_KINDS`` — explicitly deferred, emit advisory.

    Args:
        revision: The :class:`ModeloRevision` whose bindings are checked.

    Raises:
        ModeloAggregationBindingError: When a binding carries a source kind
            absent from both the enrolled and the deferred sets.
    """
    _accepted = _BUCKET_AGGREGATION_OWNED_SOURCES | _DEFERRED_SOURCE_KINDS
    novel = sorted({str(binding.source) for binding in revision.bindings if str(binding.source) not in _accepted})
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
        if casilla.input_kind == InputKind.BOUND and casilla.binding in source_owned_binding_ids
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

    The revision must currently be in ``DRAFT`` state. After the
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
            currently in ``DRAFT`` state.
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
    _refuse_direct_cross_period_verification(existing, work_unit_repository=work_unit_repository)
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
