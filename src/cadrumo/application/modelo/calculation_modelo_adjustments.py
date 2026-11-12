"""Modelo-specific adjustment helpers for calculation actions.

These private helpers keep model-specific edge cases out of the generic
calculation action path: M131 fixed-record data-base projections, M390/M303
cross-period reconciliation refusal, and the dropping of row-field template
outputs that a repeated export record fills once per detail row.
They operate on the already resolved registry snapshot and preserve the typed
observation contract that the calculation action persists.

See Also:
    :func:`~application.modelo.calculation_actions.calculate_modelo_revision_with_trusted_mesh_sources`
        Application calculation action that calls these adjustment helpers.
    :func:`~domain.calculations.registry.formula_runtime.calculate_registry_snapshot`
        Registry engine whose output is adjusted before persistence.
    :class:`~domain.calculations.registry.schema.RegistrySnapshot`
        Law-determined snapshot used for relation and period requirements.
    :class:`~domain.calculations.registry.schema.ModeloRevision`
        Revision whose export layouts, bindings, and relations drive the
        model-specific adjustments.
    :class:`~domain.calculations.registry.bindings.CasillaObservation`
        Provenance-bearing observation rows filtered of row-field template casillas.
    :class:`~WorkUnit`
        Modelo, filing year, and period context selecting each adjustment.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.aggregation import BindingAggregationOp, BindingSourceKind
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.decimal.coercion import coerce_decimal_strict
from ...core.decimal.constants import ZERO
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language
from ...core.money.rounding import round_to_cents
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.registry.binding_aggregation import binding_aggregation_op
from ...domain.calculations.registry.binding_selector_utils import manual_input_record_field_selector
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids, casillas_by_binding
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.casilla_membership import row_field_template_records_by_casilla
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.invoice_bindings import M349IntracommunityOperationProvider
from ...domain.calculations.registry.relations import (
    relation_prefill_bindings_for_period,
    relation_source_requirements,
)
from ...domain.calculations.registry.schema import (
    ModeloRevision,
    RegistrySnapshot,
)
from ...domain.calculations.registry.schema_verification import parse_verification_predicate_expression
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.m156_rows import Modelo156AfiliadoRow
from ...domain.modelos.row_models import (
    Modelo184MemberRow,
    Modelo210AgrupacionRentaRow,
    Modelo232VinculadaRow,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
    ModeloDetailRow,
    resolve_detail_bearing_modelos,
    resolve_detail_row_owning_modelos,
)
from ...domain.modelos.work_unit import WorkUnit
from .action_errors import ModeloAggregationInputConflictError, ModeloCrossPeriodCleanStateError
from .preconditions import build_modelo_calculate_refusal_failure, build_modelo_precondition_failure
from .refusal_door_verdicts import operator_choice_verdict
from .work_form_wording import modelo_number

if TYPE_CHECKING:
    from .reconciliation_sources import ReconciliationSourceNeed

type ReconciliationSourceNeedsReader = Callable[[tuple[RelationId, ...]], tuple[ReconciliationSourceNeed, ...]]
"""Read where each source declaration of the given unproven reconciliation relations stands."""


def detail_row_declaration_modelos(*, effective_date: date) -> frozenset[str]:
    """Return registry-declared detail-row declaration modelos.

    Detail-row ownership is authored by the selected registry revision.  This
    calculation helper deliberately does not carry a second, module-level
    owner catalogue; callers that need the declaration surface query the
    revision instead.
    """
    return resolve_detail_bearing_modelos(effective_date=effective_date)


def require_detail_rows_declared_for_their_owning_modelo(
    *,
    work_unit: WorkUnit,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> None:
    """Refuse any detail row whose typed kind belongs to a different modelo.

    Each ``ModeloDetailRow`` subtype is a bespoke per-modelo shape (M184
    member, M232 vinculada, M349 operador/rectificación, M210 agrupación
    renta) that is never legitimately declared against a
    different modelo's work unit. Before this check existed, a mismatched
    row was silently PERSISTED into that revision's ``detail_rows`` while
    contributing to no figure -- a taxpayer-declared row that appeared to
    exist yet affected nothing, with no advisory anywhere. Every kind now
    refuses through one convention rather than five ad hoc call sites.

    This runs at the calculate boundary's single funnel
    (:func:`~.calculation_actions.calculate_modelo_revision_with_trusted_mesh_sources`),
    which the bucket-aggregation calculate entry point feeds.
    """
    if not detail_rows:
        return
    ownership = resolve_detail_row_owning_modelos(
        effective_date=date(work_unit.filing_year, 12, 31),
    )
    work_unit_modelo = str(work_unit.modelo)
    for row in detail_rows:
        owning_modelo = ownership.get(row.row_type)
        if owning_modelo == work_unit_modelo:
            continue
        raise ModeloError(
            translated_message="errors.error.error_modelos",
            precondition_verdict=operator_choice_verdict("detail_rows_owning_modelo"),
            context={
                "row_type": type(row).__name__,
                "owning_modelo": owning_modelo,
                "work_unit_modelo": work_unit_modelo,
            },
        )


#: Each detail-row kind's own natural real-world identity -- the field tuple
#: that names WHICH counterparty/operation/member a row is about, as distinct
#: from the declarable figures (amounts, percentages) that describe it. Two
#: rows sharing this key from different supply paths (a resolver and a
#: caller) name the SAME real-world thing and must union rather than
#: double-count; two rows sharing it that disagree on a declarable figure are
#: a genuine conflict, not a duplicate.
ROW_IDENTITY_FIELDS: Mapping[type[ModeloDetailRow], tuple[str, ...]] = {
    Modelo156AfiliadoRow: ("nif", "numero_afiliacion"),
    Modelo184MemberRow: ("nif", "clave", "subclave"),
    Modelo232VinculadaRow: ("nif", "tipo_operacion"),
    Modelo349OperadorRow: ("nif_comunitario", "clave_operacion"),
    Modelo349RectificacionRow: ("nif_comunitario", "clave_operacion", "ejercicio", "periodo"),
    Modelo210AgrupacionRentaRow: ("source_id",),
}


def _row_identity(row: ModeloDetailRow) -> tuple[object, ...]:
    fields = ROW_IDENTITY_FIELDS.get(type(row))
    if fields is None:
        # An undeclared row kind has no known identity to union by; treat it
        # as identity-unique so it never collides (owning-modelo validation
        # elsewhere refuses genuinely unknown kinds).
        return (id(row),)
    return tuple(getattr(row, field) for field in fields)


def union_detail_rows_by_identity(
    *,
    resolver_rows: tuple[ModeloDetailRow, ...],
    caller_rows: tuple[ModeloDetailRow, ...],
) -> tuple[ModeloDetailRow, ...]:
    """Union resolver-produced and caller-supplied detail rows by identity.

    Naive concatenation double-counts a row two supply paths both name --
    an invoice-derived M349 operador row the operator also enters manually,
    for instance -- inflating every downstream count and sum derived from
    the row set. Rows are grouped by (row type, natural identity); a group
    fed by only one path passes through unchanged. A group fed by BOTH
    paths unions to the resolver's row when every remaining field (the
    declarable figures) agrees, and REFUSES, naming the identity and the
    divergent fields, when they disagree -- an unstated precedence pick
    between two supply paths on a filing-grade value is not this function's
    call to make.

    Two same-path rows sharing an identity (two caller rows, or two
    resolver rows) are left as duplicates for the caller to see: this
    function's contract is cross-path union, not intra-path deduplication,
    which is a different defect with a different owner.
    """
    if not resolver_rows or not caller_rows:
        return (*resolver_rows, *caller_rows)
    resolver_by_identity: dict[tuple[str, tuple[object, ...]], ModeloDetailRow] = {
        (row.row_type, _row_identity(row)): row for row in resolver_rows
    }
    unioned: list[ModeloDetailRow] = list(resolver_rows)
    for caller_row in caller_rows:
        key = (caller_row.row_type, _row_identity(caller_row))
        resolver_row = resolver_by_identity.get(key)
        if resolver_row is None:
            unioned.append(caller_row)
            continue
        if resolver_row == caller_row:
            continue
        divergent_fields = tuple(
            sorted(
                field
                for field in type(resolver_row).model_fields
                if getattr(resolver_row, field) != getattr(caller_row, field)
            ),
        )
        raise ModeloAggregationInputConflictError(
            translated_message="application.modelo.errors.detail_row_identity_conflict",
            context={
                "reason": "detail_row_identity_conflict",
                "row_type": caller_row.row_type,
                "identity": [str(component) for component in _row_identity(caller_row)],
                "divergent_fields": list(divergent_fields),
            },
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="detail_rows.identity_conflict",
                evidence_values={
                    "row_type": caller_row.row_type,
                    "divergent_fields": "|".join(divergent_fields),
                },
            ),
        )
    return tuple(unioned)


@dataclass(frozen=True, slots=True)
class _M131ActivityInputs:
    rendimiento: Decimal | None = None
    porcentaje: Decimal | None = None
    resultado: Decimal | None = None


@dataclass(slots=True)
class _M131ProjectionInputs:
    """Grouped M131 fixed-record inputs before casilla projection.

    The two groups are intentionally kept separate.  Page-1 activity rows
    take precedence for casilla 01, while DPA module rendimientos are only a
    fallback when no page-1 rendimiento is present.  Keeping that distinction
    in a typed intermediate object prevents the collection loop from also
    deciding liquidation precedence.
    """

    page1_rows: dict[str, _M131ActivityInputs] = field(default_factory=dict)
    dpa_rendimientos: list[Decimal] = field(default_factory=list)


def _m131_page1_activity_field(field_name: str) -> tuple[str, str] | None:
    parts = field_name.split("-", 2)
    if len(parts) != 3 or not parts[1].isdigit():
        return None
    attribute = parts[2].split("-", 1)[0]
    if attribute not in _M131ActivityInputs.__dataclass_fields__:
        return None
    return parts[1], attribute


def _m131_update_page1_activity(
    inputs: _M131ProjectionInputs,
    *,
    field_name: str,
    value: Decimal,
) -> None:
    parsed_field = _m131_page1_activity_field(field_name)
    if parsed_field is None:
        return
    index, attribute = parsed_field
    current = inputs.page1_rows.get(index, _M131ActivityInputs())
    inputs.page1_rows[index] = replace(current, **{attribute: value})


def _is_m131_module_yield(record: str, module_parts: list[str]) -> bool:
    """Recognize only the DPA module net-yield fields, retaining field checks."""
    return (
        record == "DPA"
        and len(module_parts) == 3
        and module_parts[0] == "modulo"
        and module_parts[1].isdigit()
        and module_parts[2] == "rendimiento-neto"
    )


def _m131_collect_projection_inputs(
    *,
    revision: ModeloRevision,
    binding_values: Mapping[BindingId, Decimal],
) -> _M131ProjectionInputs:
    """Collect validated M131 record-field bindings into their input groups."""
    inputs = _M131ProjectionInputs()
    for binding in revision.bindings:
        if binding.source is not BindingSourceKind.MANUAL_INPUT or binding.id not in binding_values:
            continue
        # Distinguishes the record-field manual_input shape (what this loop
        # projects) from the casilla shape (a real, different manual_input
        # selector this loop is not asked about) via the typed model, rather
        # than a raw selector.get("record") whose None default cannot tell a
        # legitimately-absent field from a mistyped one. A malformed selector
        # raises here instead of being silently treated as casilla-shape.
        manual_selector = manual_input_record_field_selector(binding)
        if manual_selector is None:
            continue
        record = manual_selector.record
        field = manual_selector.field
        value = binding_values[binding.id]
        if record == "page_1":
            _m131_update_page1_activity(inputs, field_name=field, value=value)
            continue
        # Casilla 01 sums the modules' net yields only; the DPA record carries
        # each module's unit count beside its yield, and a count is not money.
        module_parts = field.split("-", 2)
        if _is_m131_module_yield(record, module_parts):
            inputs.dpa_rendimientos.append(value)

    return inputs


def _m131_activity_result(row: _M131ActivityInputs) -> Decimal | None:
    if row.resultado is not None:
        return row.resultado
    if row.rendimiento is None or row.porcentaje is None:
        return None
    return round_to_cents(row.rendimiento * row.porcentaje / Decimal("100"))


def _m131_page1_results(rows: Mapping[str, _M131ActivityInputs]) -> tuple[Decimal, ...]:
    results: list[Decimal] = []
    for row in rows.values():
        result = _m131_activity_result(row)
        if result is not None:
            results.append(result)
    return tuple(results)


def _m131_project_data_base_inputs(
    inputs: _M131ProjectionInputs,
    *,
    target_casillas: tuple[CasillaId, ...],
) -> dict[CasillaId, Decimal]:
    if len(target_casillas) < 2:
        return {}
    rendimento_casilla, pago_previo_casilla = target_casillas[:2]
    page1_rendimientos = tuple(row.rendimiento for row in inputs.page1_rows.values() if row.rendimiento is not None)

    projected: dict[CasillaId, Decimal] = {}
    if page1_rendimientos:
        projected[rendimento_casilla] = sum(page1_rendimientos, Decimal("0"))
    elif inputs.dpa_rendimientos:
        projected[rendimento_casilla] = sum(inputs.dpa_rendimientos, Decimal("0"))

    page1_results = _m131_page1_results(inputs.page1_rows)
    if page1_results:
        projected[pago_previo_casilla] = sum(page1_results, Decimal("0"))
    return projected


def _m131_objective_estimation_data_base_inputs(
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    binding_values: Mapping[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Project M131 page-1/DPA datos-base fixed-record bindings into liquidation inputs."""
    inputs = _m131_collect_projection_inputs(revision=revision, binding_values=binding_values)
    target_casillas = tuple(
        sorted(
            (
                casilla.id
                for casilla in revision.casillas
                if str(getattr(casilla.input_kind, "value", casilla.input_kind)) == "manual"
            ),
            key=str,
        )[:2]
    )
    del work_unit
    return _m131_project_data_base_inputs(inputs, target_casillas=target_casillas)


def _calculated_decimal(value: object | None) -> Decimal:
    if value is None:
        return ZERO
    return coerce_decimal_strict(value)


def reconciliation_relation_targets(
    snapshot: RegistrySnapshot,
) -> tuple[tuple[RelationId, BindingId, tuple[CasillaId, ...], CasillaId, CasillaId], ...]:
    """Return selected annual-relation targets from the registry revision.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
    """
    target_casillas_by_binding = casillas_by_binding(snapshot.revision)
    annual_by_reconciliation = _annual_casillas_by_reconciliation_slot(snapshot.revision)
    targets: list[tuple[RelationId, BindingId, tuple[CasillaId, ...], CasillaId, CasillaId]] = []
    for binding, provider in relation_prefill_bindings_for_period(snapshot.revision):
        target_casillas = target_casillas_by_binding.get(binding.id, ())
        if not target_casillas:
            continue
        source_casillas = provider.declared_source_casilla_ids
        annual_casilla = annual_by_reconciliation.get(target_casillas[0])
        if len(source_casillas) != 1 or annual_casilla is None:
            continue
        targets.append((binding.id, binding.id, target_casillas, source_casillas[0], annual_casilla))
    return tuple(targets)


def _annual_casillas_by_reconciliation_slot(revision: ModeloRevision) -> dict[CasillaId, CasillaId]:
    """Pair each casilla with the one a registry ``equals`` predicate says it must equal.

    The pairing is read from the revision's own two-casilla ``equals``
    verification predicates, so no annual casilla is named in code.
    """
    pairs: dict[CasillaId, CasillaId] = {}
    for predicate in revision.verification_predicates:
        parsed = parse_verification_predicate_expression(predicate.expression)
        if parsed is None or parsed.operator != "equals" or len(parsed.casilla_ids) != 2:
            continue
        first, second = (validated_casilla_id(token) for token in parsed.casilla_ids)
        pairs[first] = second
        pairs[second] = first
    return pairs


def _required_relation_periods(snapshot: RegistrySnapshot, relation_ids: frozenset[RelationId]) -> tuple[str, ...]:
    periods: set[str] = set()
    for requirement in relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        if relation_ids.intersection(requirement.target_bindings):
            periods.update(requirement.periods)
    return tuple(sorted(periods))


def _general_regime_figure_present(
    targets: tuple[tuple[RelationId, BindingId, tuple[CasillaId, ...], CasillaId, CasillaId], ...],
    *,
    casilla_values: Mapping[CasillaId, Decimal],
    resolved_binding_values: Mapping[BindingId, Decimal],
) -> bool:
    """Whether a reconciled annual box or its resolved 303 fold holds a non-zero figure."""
    for _relation_id, binding_id, _targets, _source_casilla, annual_casilla in targets:
        for value in (casilla_values.get(annual_casilla), resolved_binding_values.get(binding_id)):
            if value is not None and _calculated_decimal(value) != ZERO:
                return True
    return False


def _zero_rests_on_resolved_values(
    casilla_id: CasillaId,
    *,
    observations_by_casilla: Mapping[CasillaId, CasillaObservation],
    bound_binding_ids_by_casilla: Mapping[CasillaId, tuple[BindingId, ...]],
    supplied_casilla_ids: frozenset[CasillaId],
    answered_binding_ids: frozenset[BindingId],
) -> bool:
    """Whether every value a calculated casilla was folded from was actually supplied.

    The engine reads an input nobody supplied as zero, and seeds a relation slot
    with no prior filing to fold as a structural zero, so a calculated zero
    alone does not say the figure is known. Walk the formula lineage to its
    leaves: each must be a supplied input (an operator entry or a resolved
    source's projection) or a bound casilla whose binding the source answered,
    with a value or as settled (inapplicable or row-fed).
    """
    pending = [casilla_id]
    visited: set[CasillaId] = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        observation = observations_by_casilla.get(current)
        if observation is None:
            return False
        if observation.formula_id is not None:
            pending.extend(observation.operand_casilla_refs)
            continue
        if current in supplied_casilla_ids:
            continue
        if not answered_binding_ids.intersection(bound_binding_ids_by_casilla.get(current, ())):
            return False
    return True


def _reconciliation_slot_grounded(
    binding_id: BindingId,
    annual_casilla: CasillaId,
    *,
    casilla_values: Mapping[CasillaId, Decimal],
    resolved_binding_values: Mapping[BindingId, Decimal],
    resolved_annual_casillas: set[CasillaId],
    proven_zero_annual_casillas: frozenset[CasillaId],
    general_regime_not_applicable: bool,
) -> bool:
    """Whether a slot is resolved, proven zero, or not applicable and so needs no refusal."""
    if binding_id in resolved_binding_values or annual_casilla in resolved_annual_casillas:
        return True
    annual_value = casilla_values.get(annual_casilla)
    if annual_value is not None and _calculated_decimal(annual_value) != ZERO:
        return False
    if annual_casilla in proven_zero_annual_casillas:
        return True
    return general_regime_not_applicable


def _grounded_annual_casillas(
    snapshot: RegistrySnapshot,
    targets: Sequence[tuple[RelationId, BindingId, tuple[CasillaId, ...], CasillaId, CasillaId]],
    *,
    casilla_values: Mapping[CasillaId, Decimal],
    resolved_binding_values: Mapping[BindingId, Decimal],
    observations: tuple[CasillaObservation, ...],
    supplied_casilla_ids: frozenset[CasillaId],
    answered_binding_ids: frozenset[BindingId],
) -> tuple[set[CasillaId], frozenset[CasillaId]]:
    """Return the annual boxes a resolved source grounds and those whose calculated zero rests on supplied values."""
    # Several bindings may feed one casilla as alternative sources (M100 0596
    # from Modelo 111, Modelo 190, or a salary certificate); any resolved source
    # already grounds it.
    target_casillas_by_binding = casillas_by_binding(snapshot.revision)
    resolved_annual_casillas = {
        casilla_id
        for binding_id in resolved_binding_values
        for casilla_id in target_casillas_by_binding.get(binding_id, ())
    }
    observations_by_casilla = {observation.casilla_id: observation for observation in observations}
    bound_binding_ids_by_casilla = {
        casilla.id: bound_casilla_binding_ids(casilla) for casilla in snapshot.revision.casillas
    }
    proven_zero_annual_casillas = frozenset(
        annual_casilla
        for *_slot, annual_casilla in targets
        if annual_casilla in casilla_values
        and _zero_rests_on_resolved_values(
            annual_casilla,
            observations_by_casilla=observations_by_casilla,
            bound_binding_ids_by_casilla=bound_binding_ids_by_casilla,
            supplied_casilla_ids=supplied_casilla_ids,
            answered_binding_ids=answered_binding_ids,
        )
    )
    return resolved_annual_casillas, proven_zero_annual_casillas


def _incomplete_reconciliation_error(
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    *,
    missing_relations: Sequence[RelationId],
    missing_bindings: Sequence[BindingId],
    missing_targets: Sequence[CasillaId],
    missing_annuals: Sequence[CasillaId],
    source_needs: tuple[ReconciliationSourceNeed, ...] = (),
) -> ModeloCrossPeriodCleanStateError:
    """Name the 303 periods, bindings and boxes whose missing evidence blocks the M390 reconciliation.

    ``source_needs`` says why each source declaration's filed values are not
    there yet; when it names any, the refusal lists them in the words of the
    refusal's language and serves the first one's step.
    """
    missing_periods = _required_relation_periods(snapshot, frozenset(missing_relations))
    language = OutputLanguage(output_language())
    sourced = (
        {
            "modelo_words": modelo_number(str(work_unit.modelo), language),
            "year": str(work_unit.filing_year),
            "sources": "; ".join(need.words(language) for need in source_needs),
            "missing_303_period_standings": tuple(
                f"{need.period.registry_token}:{need.standing.value}" for need in source_needs
            ),
        }
        if source_needs
        else {}
    )
    return ModeloCrossPeriodCleanStateError(
        translated_message=(
            "application.modelo.errors.cross_period_sources_not_filed"
            if source_needs
            else "application.modelo.errors.cross_period_clean_state_incomplete"
        ),
        next_step=source_needs[0].next_step() if source_needs else None,
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "finding_count": len(missing_bindings),
            "reason": "missing_clean_cross_period_303_filings_or_observations",
            "missing_303_periods": missing_periods,
            **sourced,
            "missing_303_reconciliation_bindings": tuple(missing_bindings),
            "zero_reconciliation_casillas_at_risk": tuple(missing_targets),
            "annual_casillas_not_proven_zero": tuple(missing_annuals),
        },
        precondition_failure=build_modelo_precondition_failure(
            subject_leaf_key="modelo.work.calculate",
            condition_id="modelo.work.calculate.m390.reconciliation.complete",
            scenario_id="modelo.work.calculate.m390.reconciliation.clean_m303_observations_missing",
            evidence_id="modelo.work.calculate.m390.reconciliation",
            evidence_values={
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
                "missing_item_count": len(missing_bindings),
                "missing_periods": "|".join(missing_periods),
                "missing_binding_ids": "|".join(missing_bindings),
                "target_casilla_ids": "|".join(missing_targets),
                "annual_casilla_ids": "|".join(missing_annuals),
            },
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        ),
    )


def _raise_if_m390_303_reconciliation_would_save_silent_zero(
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    casilla_values: Mapping[CasillaId, Decimal],
    resolved_binding_values: Mapping[BindingId, Decimal],
    general_regime_claimed: bool,
    observations: tuple[CasillaObservation, ...],
    supplied_casilla_ids: frozenset[CasillaId],
    answered_binding_ids: frozenset[BindingId],
    source_needs: ReconciliationSourceNeedsReader | None = None,
) -> None:
    """Refuse an M390 draft that would save zero 303 reconciliation slots from missing fold-in evidence.

    ``source_needs`` reads where each source declaration of the unproven
    relations stands, so the refusal names them as the to-do list does.

    A calculated zero proves a slot has nothing to reconcile only when every
    value it was folded from was supplied: an operator entry, a resolved
    source, or a binding its source settled as inapplicable or row-fed
    (``answered_binding_ids``). A zero folded from inputs nobody supplied, and
    an absent annual box, are unknown, so they refuse. The exception is a filer
    claiming no general regime with no figure on any general-regime box: those
    boxes do not apply to them. One non-zero figure contradicts that, and every
    unknown box is unknown again.
    """
    targets = reconciliation_relation_targets(snapshot)
    if not targets:
        return
    general_regime_not_applicable = not general_regime_claimed and not _general_regime_figure_present(
        targets, casilla_values=casilla_values, resolved_binding_values=resolved_binding_values
    )

    resolved_annual_casillas, proven_zero_annual_casillas = _grounded_annual_casillas(
        snapshot,
        targets,
        casilla_values=casilla_values,
        resolved_binding_values=resolved_binding_values,
        observations=observations,
        supplied_casilla_ids=supplied_casilla_ids,
        answered_binding_ids=answered_binding_ids,
    )
    missing_relations: list[RelationId] = []
    missing_bindings: list[BindingId] = []
    missing_targets: list[CasillaId] = []
    missing_annuals: list[CasillaId] = []
    for relation_id, binding_id, target_casillas, _source_casilla, annual_casilla in targets:
        if _reconciliation_slot_grounded(
            binding_id,
            annual_casilla,
            casilla_values=casilla_values,
            resolved_binding_values=resolved_binding_values,
            resolved_annual_casillas=resolved_annual_casillas,
            proven_zero_annual_casillas=proven_zero_annual_casillas,
            general_regime_not_applicable=general_regime_not_applicable,
        ):
            continue
        missing_relations.append(relation_id)
        missing_bindings.append(binding_id)
        missing_targets.extend(target_casillas)
        missing_annuals.append(annual_casilla)

    if not missing_bindings:
        return

    raise _incomplete_reconciliation_error(
        work_unit,
        snapshot,
        missing_relations=missing_relations,
        missing_bindings=missing_bindings,
        missing_targets=missing_targets,
        missing_annuals=missing_annuals,
        source_needs=() if source_needs is None else source_needs(tuple(missing_relations)),
    )


def drop_row_field_template_outputs(
    *,
    revision: ModeloRevision,
    casilla_values: dict[CasillaId, Decimal],
    observations: tuple[CasillaObservation, ...],
) -> tuple[dict[CasillaId, Decimal], tuple[CasillaObservation, ...]]:
    """Drop the scalar values and observations of casillas a repeated export record fills per row.

    The engine evaluates every declared casilla, so a row-field template
    casilla comes out as a scalar with no row behind it; its real values live
    on the detail rows that the export emits one record for each.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation`,
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    row_field_casilla_ids = frozenset(row_field_template_records_by_casilla(revision))
    if not row_field_casilla_ids:
        return casilla_values, observations
    return (
        {casilla_id: value for casilla_id, value in casilla_values.items() if casilla_id not in row_field_casilla_ids},
        tuple(observation for observation in observations if observation.casilla_id not in row_field_casilla_ids),
    )


def _detail_summary_bindings(revision: ModeloRevision) -> dict[tuple[str, str], BindingId]:
    """Select the M349 intra-community summary providers in declaration order."""
    summary_bindings: dict[tuple[str, str], BindingId] = {}
    for binding in revision.bindings:
        provider = binding.provider
        if not isinstance(provider, M349IntracommunityOperationProvider):
            continue
        if provider.record is not None:
            continue
        scope = provider.rectification_scope
        summary_bindings[(binding_aggregation_op(binding).value, scope.value)] = binding.id

    return summary_bindings


def _detail_summary_values(
    summary_bindings: dict[tuple[str, str], BindingId],
    operador_rows: tuple[Modelo349OperadorRow, ...],
    rectification_rows: tuple[Modelo349RectificacionRow, ...],
    importe_operaciones: Decimal,
    importe_rectificaciones: Decimal,
) -> dict[BindingId, Decimal]:
    """Project original per-scope counts or amounts, omitting unsupported scopes."""
    result: dict[BindingId, Decimal] = {}
    for (op, scope), binding_id in summary_bindings.items():
        if scope.startswith("exclude"):
            value = (
                Decimal(len(operador_rows)) if op == BindingAggregationOp.COUNT_DISTINCT.value else importe_operaciones
            )
        elif scope.startswith("only"):
            value = (
                Decimal(len(rectification_rows))
                if op == BindingAggregationOp.COUNT_DISTINCT.value
                else importe_rectificaciones
            )
        else:
            continue
        result[binding_id] = value
    return result


def _detail_row_binding_values_for_calculation(
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> dict[BindingId, Decimal]:
    del work_unit
    summary_bindings = _detail_summary_bindings(revision)

    operador_rows = tuple(row for row in detail_rows if isinstance(row, Modelo349OperadorRow))
    rectification_rows = tuple(row for row in detail_rows if isinstance(row, Modelo349RectificacionRow))
    if not operador_rows and not rectification_rows:
        return {}
    importe_operaciones = sum((row.importe for row in operador_rows), Decimal("0"))
    importe_rectificaciones = sum(
        (abs(row.base_rectificada - row.base_anterior) for row in rectification_rows),
        Decimal("0"),
    )
    return _detail_summary_values(
        summary_bindings, operador_rows, rectification_rows, importe_operaciones, importe_rectificaciones
    )


calculated_decimal = _calculated_decimal
detail_row_binding_values_for_calculation = _detail_row_binding_values_for_calculation
m131_objective_estimation_data_base_inputs = _m131_objective_estimation_data_base_inputs
raise_if_m390_303_reconciliation_would_save_silent_zero = _raise_if_m390_303_reconciliation_would_save_silent_zero
