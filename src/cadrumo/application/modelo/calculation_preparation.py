"""Preparation gates for modelo calculation actions.

This module prepares calculation input channels against the registry
:class:`ModeloRevision` for a :class:`WorkUnit`, resolves the law-determined
:class:`RegistrySnapshot`, applies the Modelo 303 IVA wallet gate, and runs
ledger preflight through the application-facing transaction port before
calculation proceeds.

See Also:
    :func:`~application.modelo.calculation_actions.calculate_modelo_revision_with_trusted_mesh_sources`:
        Consumes the prepared bundle before persisting a draft revision.
    :func:`~application.modelo.calculation_resolution.resolve_calculation_binding_channels`:
        Merges caller, backend, borrador, enum, and date binding channels.
    :mod:`~application.modelo.iva_wallet_gate`:
        Resolves the persisted Modelo 303 IVA-wallet authority during preparation.
    :mod:`~application.modelo.iva_wallet_binding`:
        Applies that authority to the prior-compensation binding.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from dataclasses import replace as _dataclass_replace
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.external_constants import DEFAULT_CURRENCY, OutputLanguage
from ...core.i18n.render import tr
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.iva_regime_vocabulary import (
    iva_regime_simplificado_token,
    require_iva_regime,
)
from ...domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ...domain.calculations.registry.schema import (
    ModeloRevision,
    RegistrySnapshot,
)
from ...domain.deadlines.models import IVARegime
from ...domain.modelos.calculation_revision_sources import CalculationSourceRef
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.period import calculation_filing_date
from ...domain.transactions.enums import BUSINESS_BEARING_STATES, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import Transaction
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    IvaWalletDecisionRepositoryProtocol,
)
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReader
from ..ledger.usage_ratio_repository import UsageRatioProfileLoader
from ..operations.error_detail import served_words_language
from ..operations.next_step import OperationNextStepWording, OperationOpenMovementStepV1
from ..user_profile.projections import record_to_path_values
from .action_errors import ModeloAggregationInputConflictError, ModeloLedgerPreflightBlockedError
from .calculation_helpers import load_work_unit_for_calculation, resolve_registry_snapshot_for_work_unit
from .calculation_resolution import ResolvedCalculationChannels, resolve_calculation_binding_channels
from .iva_wallet_binding import apply_iva_compensation_decision_binding
from .iva_wallet_gate import resolve_iva_compensation_decision_for_calculation
from .iva_wallet_prior_period import CataloguePriorModeloCalculations
from .iva_wallet_refusal import iva_wallet_door
from .iva_wallet_values import taxpayer_nif_from_path_values
from .lifecycle_clock_gate import (
    ModeloLifecycleClockOperation,
    require_lifecycle_clock_not_before,
    work_unit_ordering_instants,
)
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure
from .registry_helpers import validate_casilla_input_ids
from .required_binding_gate import (
    require_modelo_required_bindings_resolved,
    resolved_required_profile_binding_values,
)
from .value_presentation import format_casilla_value
from .work_form_wording import period_words
from .work_profile import ModeloWorkProfile

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..ledger.preflight import LedgerPreflightIssue
    from ..live.borrador_100 import Borrador100SnapshotRepository

_apply_iva_compensation_decision_binding = apply_iva_compensation_decision_binding


@dataclass(frozen=True, slots=True)
class PreparedCalculation:
    """Validated calculation preflight bundle consumed by the action layer.

    ``work_unit`` is the loaded :class:`WorkUnit`;
    ``snapshot`` is the resolved :class:`RegistrySnapshot`; ``channels`` is the
    merged :class:`ResolvedCalculationChannels` set that the registry engine will
    consume. Casilla inputs have already been canonicalised and ledger, profile,
    required-binding, borrador, and IVA-wallet gates have already run.
    """

    work_units: WorkUnitCatalogue
    #: The revision ``work_units`` was read at. Carried because the persistence
    #: this feeds composes that catalogue into a co-commit, which cannot use a
    #: self-committing mutation: without the revision its batch rewrites the
    #: whole singleton row over a unit another caller created in between.
    work_units_revision_id: str
    work_unit: WorkUnit
    snapshot: RegistrySnapshot
    profile: ModeloWorkProfile
    casilla_inputs: Mapping[CasillaId, Decimal]
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None
    period_date: date
    channels: ResolvedCalculationChannels


def _validate_calculation_inputs(
    revision: ModeloRevision,
    casilla_inputs: Mapping[CasillaId, Decimal],
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
) -> tuple[Mapping[CasillaId, Decimal], Mapping[CasillaId, Decimal] | None]:
    casilla_inputs = validate_casilla_input_ids(revision, casilla_inputs)
    if backend_casilla_inputs is not None:
        backend_casilla_inputs = validate_casilla_input_ids(revision, backend_casilla_inputs)
    return casilla_inputs, backend_casilla_inputs


def _with_required_profile_bindings(
    work_unit: WorkUnit, snapshot: RegistrySnapshot, profile: ModeloWorkProfile, channels: ResolvedCalculationChannels
) -> ResolvedCalculationChannels:
    required_profile_bindings = resolved_required_profile_binding_values(
        work_unit=work_unit,
        registry_revision=snapshot.revision,
        profile=profile,
    )
    if required_profile_bindings:
        channels = _dataclass_replace(
            channels,
            bindings=dict(sorted({**required_profile_bindings, **channels.bindings}.items())),
        )
    return channels


def prepare_calculation(
    *,
    work_unit_id: str,
    evaluated_at: datetime,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    casilla_inputs: Mapping[CasillaId, Decimal],
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
    ledger_preflight_transaction_repository: TransactionCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    iva_compensation_decision: object | None,
    observation_repository: CalculationObservationRepositoryProtocol,
    iva_compensation_decision_repository: IvaWalletDecisionRepositoryProtocol,
    iva_compensation_history_repository: IvaCompensationHistoryRepositoryProtocol,
    binding_values: Mapping[BindingId, Decimal] | None,
    enum_binding_values: Mapping[BindingId, str] | None,
    backend_binding_values: Mapping[BindingId, Decimal] | None,
    filing_period_date: date | None,
    borrador_snapshot_id: str | None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None,
    unresolved_relation_ids: tuple[RelationId, ...],
    unresolved_binding_ids: tuple[BindingId, ...],
    profile: ModeloWorkProfile | None,
    backend_source_provenance: Sequence[CalculationSourceRef] = (),
) -> PreparedCalculation:
    """Prepare validated inputs, source channels, and gates for calculation.

    The resolved registry :class:`ModeloRevision` supplies binding and casilla
    requirements. ``ledger_preflight_transaction_repository`` may provide a
    :class:`TransactionCatalogueRepositoryProtocol` for the Modelo 200 accounting-result check;
    the ledger-tax readiness check runs before the source mesh is resolved.
    ``iva_compensation_decision_repository`` may provide the matching
    :class:`~application.calculations.observations_repository.IvaWalletDecisionRepositoryProtocol` for the
    Modelo 303 wallet authority, while
    :class:`~application.live.borrador_100.Borrador100SnapshotRepository` supplies the
    optional Modelo 100 borrador tier.

    Returns:
        A :class:`PreparedCalculation` carrying the :class:`WorkUnit`,
        :class:`RegistrySnapshot`, validated inputs, period date, and
        :class:`ResolvedCalculationChannels`.
    """
    work_units, work_units_revision_id = work_unit_repository.load_revisioned()
    work_unit = load_work_unit_for_calculation(
        work_units,
        work_unit_id=work_unit_id,
        repository_bucket_id=work_unit_repository.bucket_id,
    )
    # Wallet reconciliation can persist a refreshed decision during preparation.
    # Refuse an invalid operation instant before any such write.
    require_lifecycle_clock_not_before(
        evaluated_at,
        operation=ModeloLifecycleClockOperation.CALCULATE,
        instants=work_unit_ordering_instants(work_unit),
    )
    from .profile_readiness_gate import require_profile_ready_for_work_unit

    checked_profile = require_profile_ready_for_work_unit(
        work_unit,
        profile_decode_context=operation.profile_decode_context(),
        operation=operation,
        profile=profile,
    )
    profile_values = record_to_path_values(checked_profile.record)
    # Calculate needs the amount-computing rung, not the filing rung: this
    # prepares an in-memory calculation and renders no fichero or export layout.
    snapshot = resolve_registry_snapshot_for_work_unit(
        work_unit,
        grade=RegistryAuthorityGrade.CALCULATION,
        operation=operation,
    )
    casilla_inputs, backend_casilla_inputs = _validate_calculation_inputs(
        snapshot.revision, casilla_inputs, backend_casilla_inputs
    )
    _raise_if_m200_ledger_requires_accounting_result_input(
        work_unit=work_unit,
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        transaction_repository=ledger_preflight_transaction_repository,
    )
    period_date = filing_period_date or calculation_filing_date(work_unit.period)
    caller_binding_values = dict(binding_values or {})
    caller_enum_binding_values = dict(enum_binding_values or {})
    lower_precedence_binding_values = dict(backend_binding_values or {})
    with iva_wallet_door(work_unit.work_unit_id):
        iva_compensation_decision = resolve_iva_compensation_decision_for_calculation(
            work_unit,
            evaluated_at=evaluated_at,
            snapshot=snapshot,
            supplied_decision=iva_compensation_decision,
            observation_repository=observation_repository,
            repository=iva_compensation_decision_repository,
            history_repository=iva_compensation_history_repository,
            binding_values=binding_values,
            backend_binding_values=backend_binding_values,
            casilla_inputs=casilla_inputs,
            backend_casilla_inputs=backend_casilla_inputs,
            operation=operation,
            profile_values=profile_values,
            prior_calculations=CataloguePriorModeloCalculations(
                work_units=work_units,
                calculation_repository=calculation_repository,
                operation=operation,
            ),
        )
        _apply_iva_compensation_decision_binding(
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            bucket_id=work_unit.bucket_id,
            revision=snapshot.revision,
            taxpayer_nif=taxpayer_nif_from_path_values(profile_values),
            casilla_inputs=casilla_inputs,
            backend_casilla_inputs=backend_casilla_inputs,
            caller_binding_values=caller_binding_values,
            backend_binding_values=lower_precedence_binding_values,
            decision=iva_compensation_decision,
        )
    channels = resolve_calculation_binding_channels(
        work_unit=work_unit,
        snapshot=snapshot,
        casilla_inputs=casilla_inputs,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        backend_binding_values=lower_precedence_binding_values,
        borrador_snapshot_id=borrador_snapshot_id,
        borrador_snapshot_repository=borrador_snapshot_repository,
        operation=operation,
        profile=checked_profile,
        backend_source_provenance=backend_source_provenance,
    )
    channels = _with_required_profile_bindings(work_unit, snapshot, checked_profile, channels)
    _require_calculation_binding_resolution(
        work_unit,
        snapshot,
        channels,
        caller_binding_values,
        unresolved_relation_ids,
        unresolved_binding_ids,
        profile=checked_profile,
        operation=operation,
    )
    return PreparedCalculation(
        work_units=work_units,
        work_units_revision_id=work_units_revision_id,
        work_unit=work_unit,
        snapshot=snapshot,
        profile=checked_profile,
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        period_date=period_date,
        channels=channels,
    )


def _require_calculation_binding_resolution(
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    channels: ResolvedCalculationChannels,
    caller_binding_values: Mapping[BindingId, Decimal],
    unresolved_relation_ids: tuple[RelationId, ...],
    unresolved_binding_ids: tuple[BindingId, ...],
    *,
    profile: ModeloWorkProfile,
    operation: PinnedAuthorityOperation,
) -> None:
    require_modelo_required_bindings_resolved(
        work_unit=work_unit,
        registry_revision=snapshot.revision,
        resolved_binding_ids=_resolved_binding_ids_for_required_binding_gate(
            revision=snapshot.revision,
            channels=channels,
            caller_binding_ids=caller_binding_values,
            unresolved_relation_ids=unresolved_relation_ids,
            unresolved_binding_ids=unresolved_binding_ids,
        ),
        action="calculate",
        profile=profile,
        operation=operation,
    )


def _resolved_binding_ids_for_required_binding_gate(
    *,
    revision: ModeloRevision,
    channels: ResolvedCalculationChannels,
    caller_binding_ids: Mapping[BindingId, Decimal],
    unresolved_relation_ids: tuple[RelationId, ...],
    unresolved_binding_ids: tuple[BindingId, ...],
) -> tuple[BindingId, ...]:
    resolved = set(channels.bindings) | set(channels.enum_bindings) | set(channels.date_bindings)
    caller_ids = set(caller_binding_ids)
    unresolved_relation_targets = {
        binding.id
        for binding, _ in relation_prefill_bindings_for_period(revision)
        if binding.id in unresolved_relation_ids and binding.id not in caller_ids
    }
    unresolved_bindings = set(unresolved_binding_ids).difference(caller_ids)
    return tuple(sorted(resolved.difference(unresolved_relation_targets).difference(unresolved_bindings)))


def _iva_regime_from_path_values(profile_values: Mapping[str, str]) -> IVARegime | None:
    value = profile_values.get("iva.regime")
    if value is None or not value.strip():
        return None
    return require_iva_regime(value.strip())


_LEDGER_PREFLIGHT_BINDING_SOURCES = frozenset(
    {
        "ledger_iva_aggregation",
        "ledger_renta_gastos_estimacion_directa_aggregation",
    },
)
_IVA_LEDGER_PREFLIGHT_SOURCE = "ledger_iva_aggregation"
_IVA_ONLY_PREFLIGHT_REASONS = frozenset(
    {
        "missing_iva_amount",
        "missing_iva_rate",
        "missing_eur_tax_substrate",
        "anomaly_non_declarable_iva_category",
        "anomaly_non_declarable_recargo_equivalencia",
        # The IVA deduction taxonomy is read by no Renta binding: the first-slice
        # expense aggregation consumes the base and the business share, not which
        # input-IVA deduction the row's cuota qualifies as. A wrong deduction kind
        # therefore blocks 303/390 and leaves the annual Renta return computable
        # from the same row.
        "inadmissible_deduction_classification",
        # The invoice side of the period feeds the IVA aggregation alone.
        "invoice_deduction_family_unresolved",
        "invoice_category_contradicted",
        "movement_invoice_double_count",
        "invoice_cash_accounting_regime_unmodelled",
        "linked_movement_contradicts_invoice",
        "invoice_recargo_split_unresolved",
        "invoice_recargo_not_declarable",
    },
)
_M200_ACCOUNTING_RESULT_CASILLA: CasillaId = "DP200012:00501"
_M200_ACCOUNTING_LEDGER_DIRECTIONS = frozenset(
    {
        TransactionDirection.INCOMING,
        TransactionDirection.OUTGOING,
    },
)


_LEDGER_PREFLIGHT_NEED_KEY = "application.modelo.errors.ledger_preflight_need"


def _movement_words(movement: Transaction, language: OutputLanguage) -> dict[str, str]:
    """The date, description and signed amount the person knows the movement by."""
    raw = movement.raw
    magnitude = -raw.amount if movement.direction is TransactionDirection.OUTGOING else raw.amount
    amount = (
        format_casilla_value(magnitude, data_type="money", language=language)
        if raw.currency == DEFAULT_CURRENCY
        else f"{format_casilla_value(magnitude, data_type='decimal', language=language)} {raw.currency}"
    )
    return {
        "movement_date": format_casilla_value(raw.value_date or raw.booked_date, data_type="date", language=language),
        "movement_description": raw.description.strip() or "-",
        "movement_amount": amount,
    }


def open_movement_step(transaction_id: str) -> OperationNextStepWording:
    """Offer opening the movement the refusal names in the Libro."""

    def worded(language: OutputLanguage) -> OperationOpenMovementStepV1:
        return OperationOpenMovementStepV1(
            transaction_id=transaction_id,
            words=tr(_OPEN_MOVEMENT_LOCALE_KEY, locale=language.value),
        )

    return worded


_OPEN_MOVEMENT_LOCALE_KEY = "application.modelo.projection_words.next_step.open_movement"


@dataclass(frozen=True, slots=True)
class LedgerPreflightHold:
    """The first ledger-readiness issue that holds a revision's calculation, with its served words.

    ``movement`` is the movement the issue names, ``None`` for an issue about
    the whole period; ``context`` carries the words the refusal and the to-do
    line are rendered with, in the language they were asked in.
    """

    reason: str
    issue_transaction_id: str
    movement: Transaction | None
    context: Mapping[str, str]


def _first_blocking_issue(
    issues: Sequence[LedgerPreflightIssue], ledger_preflight_sources: frozenset[str]
) -> LedgerPreflightIssue | None:
    return next(
        (
            issue
            for issue in issues
            if _preflight_issue_blocks_revision(
                reason=str(issue.reason.value),
                ledger_preflight_sources=ledger_preflight_sources,
            )
        ),
        None,
    )


def _hold_context(
    reason: str, period: Period, movement: Transaction | None, language: OutputLanguage
) -> dict[str, str]:
    context = {
        "need": tr(f"{_LEDGER_PREFLIGHT_NEED_KEY}.{reason}", locale=language.value),
        "period": period_words(period, language),
    }
    if movement is not None:
        context.update(_movement_words(movement, language))
    return context


def ledger_preflight_hold(
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    invoice_reader: InvoiceCatalogueReader,
    usage_ratio_profile_loader: UsageRatioProfileLoader,
    operation: PinnedAuthorityOperation,
    profile_values: Mapping[str, str],
    language: OutputLanguage,
) -> LedgerPreflightHold | None:
    """The ledger issue that holds this revision's calculation, or ``None`` when its ledger is ready.

    Calculation refuses on it and the workbench's to-do list names it, so the
    person is told before calculating exactly what calculating would refuse.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    ledger_preflight_sources = frozenset(
        str(binding.source) for binding in revision.bindings if binding.source in _LEDGER_PREFLIGHT_BINDING_SOURCES
    )
    if not ledger_preflight_sources:
        return None
    iva_regime = _iva_regime_from_path_values(profile_values)
    if iva_regime is not None and iva_regime == iva_regime_simplificado_token():
        return None
    from ..ledger.preflight import preflight_ledger_tax_readiness

    report = preflight_ledger_tax_readiness(
        bucket_id=work_unit.bucket_id,
        period=work_unit.period,
        transaction_repository=transaction_repository,
        usage_ratio_profile_loader=usage_ratio_profile_loader,
        invoice_reader=invoice_reader,
        operation=operation,
    )
    if report.ready:
        return None
    first_issue = _first_blocking_issue(report.issues, ledger_preflight_sources)
    if first_issue is None:
        return None
    movement = (
        None
        if first_issue.transaction_id == "__period__"
        else transaction_repository.load_by_ids({first_issue.transaction_id}).get(first_issue.transaction_id)
    )
    context = _hold_context(first_issue.reason.value, report.period, movement, language)
    return LedgerPreflightHold(
        reason=first_issue.reason.value,
        issue_transaction_id=first_issue.transaction_id,
        movement=movement,
        context=context,
    )


def ledger_hold_words(hold: LedgerPreflightHold, language: OutputLanguage) -> str:
    """The to-do line for a ledger hold: what to put right before the period can be calculated."""
    key = (
        "application.modelo.projection_words.ledger_hold.period"
        if hold.movement is None
        else "application.modelo.projection_words.ledger_hold.movement"
    )
    return tr(key, locale=language.value, **hold.context)


def raise_if_ledger_preflight_blocks_calculation(
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    invoice_reader: InvoiceCatalogueReader,
    usage_ratio_profile_loader: UsageRatioProfileLoader,
    operation: PinnedAuthorityOperation,
    profile_values: Mapping[str, str],
) -> None:
    """Refuse ledger-backed calculations whose period ledger readiness blocks.

    The refusal names the movement by its date, description and amount, in the
    language of the served words, and offers to open it; an issue about the
    whole period says what the period lacks. Nothing has been written when it
    is raised.

    The bucket calculation runs it before resolving the source mesh, so a row the
    readiness check refuses is named as the row rather than as the aggregate that
    could not be built from it.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    hold = ledger_preflight_hold(
        work_unit=work_unit,
        revision=revision,
        transaction_repository=transaction_repository,
        invoice_reader=invoice_reader,
        usage_ratio_profile_loader=usage_ratio_profile_loader,
        operation=operation,
        profile_values=profile_values,
        language=served_words_language(),
    )
    if hold is None:
        return
    movement = hold.movement
    raise ModeloLedgerPreflightBlockedError(
        translated_message=(
            "application.modelo.errors.ledger_preflight_blocked_movement"
            if movement is not None
            else "application.modelo.errors.ledger_preflight_blocked_period"
        ),
        context={**hold.context, "reason": hold.reason},
        next_step=None if movement is None else open_movement_step(movement.transaction_id),
        precondition_failure=ledger_preflight_precondition(
            work_unit_id=work_unit.work_unit_id,
            modelo=str(work_unit.modelo),
            period=work_unit.period,
            transaction_id=hold.issue_transaction_id,
            reason=hold.reason,
            names_movement=movement is not None,
        ),
    )


def ledger_preflight_precondition(
    *,
    work_unit_id: str,
    modelo: str,
    period: Period,
    transaction_id: str,
    reason: str,
    names_movement: bool,
) -> ModeloPreconditionFailure:
    """The precondition a ledger hold refuses with, and the door it serves.

    A hold that names a movement opens that movement's reclassification with
    the movement named, so the door runs as served; a hold about the whole
    period re-checks the period's ledger readiness instead, because there is
    no movement to name.
    """
    if names_movement:
        scenario_id = "modelo.work.calculate.ledger_preflight.blocked"
        action_id = "operator.ledger.classify.movement"
        action_argument_values: dict[str, str | int] = {"transaction_id": transaction_id}
    else:
        scenario_id = "modelo.work.calculate.ledger_preflight.period_blocked"
        action_id = "operator.ledger.preflight"
        action_argument_values = {"period": period.registry_token, "year": period.filing_year}
    return build_modelo_precondition_failure(
        subject_leaf_key="modelo.work.calculate",
        condition_id="modelo.work.calculate.ledger_preflight.ready",
        scenario_id=scenario_id,
        evidence_id="modelo.work.calculate.ledger_preflight",
        evidence_values={
            "work_unit_id": work_unit_id,
            "modelo": modelo,
            "year": period.filing_year,
            "period": period.registry_token,
            "transaction_id": transaction_id,
            "reason_code": reason,
        },
        provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        action_id=action_id,
        action_argument_values=action_argument_values,
    )


def _preflight_issue_blocks_revision(
    *,
    reason: str,
    ledger_preflight_sources: frozenset[str],
) -> bool:
    """Return whether a generic ledger-preflight issue blocks this revision.

    ``preflight_ledger_tax_readiness`` reports the full IVA readiness surface.
    Modelo 100 Renta expense aggregation consumes category, base, business
    classification, and usage-ratio facts, but it does not consume IVA amount,
    IVA rate, or IVA-only anomaly facts. Keep those IVA-only findings blocking
    for revisions that own ``ledger_iva_aggregation`` bindings, while allowing
    annual Renta calculations to proceed from the same taxable-base-only ledger
    rows that Modelo 130 already consumes.
    """
    if _IVA_LEDGER_PREFLIGHT_SOURCE in ledger_preflight_sources:
        return True
    return reason not in _IVA_ONLY_PREFLIGHT_REASONS


def _raise_if_m200_ledger_requires_accounting_result_input(
    *,
    work_unit: WorkUnit,
    casilla_inputs: Mapping[CasillaId, Decimal],
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
) -> None:
    """Refuse Modelo 200 ledger-backed calculation without accounting-result input."""
    if str(work_unit.modelo) != form_for_role("sociedades.annual"):
        return
    if _M200_ACCOUNTING_RESULT_CASILLA in casilla_inputs or (
        backend_casilla_inputs is not None and _M200_ACCOUNTING_RESULT_CASILLA in backend_casilla_inputs
    ):
        return
    ledger_transaction_count = _m200_accounting_ledger_transaction_count(
        work_unit=work_unit,
        transaction_repository=transaction_repository,
    )
    if ledger_transaction_count == 0:
        return
    raise ModeloAggregationInputConflictError(
        translated_message="application.modelo.errors.m200_accounting_result_required",
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "ledger_transaction_count": ledger_transaction_count,
            "required_casilla_id": _M200_ACCOUNTING_RESULT_CASILLA,
        },
        precondition_failure=build_modelo_precondition_failure(
            subject_leaf_key="modelo.work.calculate",
            condition_id="modelo.work.calculate.m200.accounting_result.present",
            scenario_id="modelo.work.calculate.m200.accounting_result.ledger_rows_without_accounting_result",
            evidence_id="modelo.work.calculate.m200.accounting_result",
            evidence_values={
                "work_unit_id": work_unit.work_unit_id,
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
                "ledger_transaction_count": ledger_transaction_count,
                "required_casilla_id": _M200_ACCOUNTING_RESULT_CASILLA,
            },
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        ),
    )


def _m200_accounting_ledger_transaction_count(
    *,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
) -> int:
    repository = transaction_repository
    period = work_unit.period
    count = 0
    for transaction in repository.load():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        if transaction.direction not in _M200_ACCOUNTING_LEDGER_DIRECTIONS:
            continue
        if transaction.business_classification not in BUSINESS_BEARING_STATES:
            continue
        effective_date = transaction.raw.value_date or transaction.raw.booked_date
        if period.contains(effective_date):
            count += 1
    return count
