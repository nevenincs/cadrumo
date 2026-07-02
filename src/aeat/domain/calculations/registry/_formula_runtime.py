"""Registry-backed formula runtime using typed operation graphs.

Evaluates
:class:`~aeat.domain.calculations.registry.FormulaExpression` trees declared on
a :class:`~aeat.domain.calculations.registry.ModeloRevision` against casilla
inputs and binding values drawn from a
:class:`~aeat.domain.calculations.registry.RegistrySnapshot`.
The calculation entry point :func:`calculate_registry_snapshot` is the
primary surface used by
:class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority`-backed
callers to produce
:class:`~aeat.domain.calculations.registry.CasillaObservation` rows with full
provenance.

See Also:
    :mod:`aeat.domain.calculations.registry._runtime_graph`
        Produces formula evaluation order and dependency projections.
    :mod:`aeat.domain.calculations.registry._formula_runtime_ops`
        Arithmetic, rounding, and parameter lookup helpers called by this
        evaluator.
    :mod:`aeat.domain.calculations.registry._formula_initial_values`
        Builds the initial casilla value map and materialised observation
        envelope for this runtime.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, localcontext
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from ....core import STRICT_FROZEN_CONFIG, ConvenioOverrideKind, TipoRentaIrnr
from ...contribuyente import UE_EEA_COUNTRY_CODES
from . import _formula_initial_values as _formula_inputs
from . import _formula_runtime_ops as _ops
from ._bindings import CasillaObservation
from ._casilla_membership import casillas_by_id as _casillas_by_id
from ._convenio import ConvenioAuthority, ConvenioOverride
from ._errors import CasillaConstraintViolationError, RegistrySnapshotError, RegistryValidationError
from ._formula_text_inputs import validate_text_input_targets as _validate_text_input_targets
from ._formula_text_inputs import validated_text_input_casilla_ids as _validated_text_input_casilla_ids
from ._ids import (
    BindingId,
    CasillaId,
    FormulaId,
    LegalRefId,
    ParameterId,
    RelationId,
    SourceRefId,
    validated_casilla_id,
)
from ._runtime_graph import formula_evaluation_order
from ._schema import FormulaExpression, ParameterDefinition, RegistrySnapshot

_ZERO = Decimal("0")
_ONE = Decimal("1")
_M100_IMPUTATION_YEAR_DAYS = Decimal("365")
read_parameter, _resolve_bracket = _ops.read_parameter, _ops.resolve_bracket


class _UnresolvedFormulaDependencyError(RegistrySnapshotError):
    """Raised internally when a non-blocking source gap makes a formula unresolved."""

    def __init__(self, dependency_ids: tuple[str, ...]) -> None:
        super().__init__(", ".join(dependency_ids))
        self.dependency_ids = dependency_ids


class RegistryUnresolvedOutcomeReason(StrEnum):
    """Closed reason catalogue for typed formula outcomes with no Decimal value."""

    M210_BASELINE_TIPO_DEFERRED = "m210-baseline-tipo-deferred"
    M210_CONVENIO_RATE_MISSING = "m210-convenio-rate-missing"


class _UnresolvedFormulaOutcomeError(RegistrySnapshotError):
    """Raised internally when a formula emits a typed unresolved outcome."""

    def __init__(
        self,
        reason: RegistryUnresolvedOutcomeReason,
        *,
        context: Mapping[str, str],
    ) -> None:
        super().__init__(reason.value)
        self.reason = reason
        self.context = dict(context)


@dataclass(frozen=True, slots=True)
class _IrnrResolveTipoGravamenArgs:
    """Resolved registry ids for the M210 IRNR rate dispatcher."""

    tipo_casilla_id: CasillaId
    baseline_parameter: ParameterId
    country_binding: BindingId
    base_casilla_id: CasillaId
    pension_tariff_parameter: ParameterId


@dataclass(frozen=True, slots=True)
class _M210ResolveBaseArgs:
    """Resolved registry ids for the M210 base-imponible dispatcher."""

    tipo_casilla_id: CasillaId
    gross_casilla_id: CasillaId
    deductible_expenses_casilla_id: CasillaId
    country_binding: BindingId
    catastral_value_casilla_id: CasillaId
    imputation_coefficient_casilla_id: CasillaId
    imputation_days_casilla_id: CasillaId
    acquisition_value_casilla_id: CasillaId
    administrative_value_casilla_id: CasillaId
    recent_rate_parameter: ParameterId
    old_rate_parameter: ParameterId
    no_catastral_fraction_parameter: ParameterId


@dataclass(frozen=True, slots=True)
class _M100ResolveImputedRentArgs:
    """Resolved registry ids for the M100 imputed-rent dispatcher."""

    catastral_value_casilla_id: CasillaId
    revised_flag_casilla_id: CasillaId
    disposal_days_casilla_id: CasillaId
    mixed_use_flag_casilla_id: CasillaId
    disposal_percentage_casilla_id: CasillaId
    mixed_use_days_casilla_id: CasillaId
    recent_rate_parameter: ParameterId
    old_rate_parameter: ParameterId


class RegistryCalculationEntry(BaseModel):
    """One trace row emitted by the registry formula runtime.

    Carries the per-formula provenance for a single formula-computed
    :class:`~aeat.domain.calculations.registry.CasillaId`. Entries cover only
    casillas computed by a registry formula; input and bound casillas remain in
    :class:`~aeat.domain.calculations.registry.CasillaObservation` storage and
    must be read through :attr:`RegistryCalculationResult.observations`.
    """

    model_config = STRICT_FROZEN_CONFIG

    formula_id: FormulaId
    target_casilla_id: CasillaId
    op: str
    operand_refs: tuple[str, ...]
    operand_casilla_refs: tuple[CasillaId, ...]
    operand_values: tuple[Decimal, ...]
    value: Decimal
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


class RegistryCalculationUnresolvedOutcome(BaseModel):
    """One formula target that could not produce a Decimal value.

    The outcome rides beside :attr:`RegistryCalculationResult.observations` so
    the engine's value channels remain Decimal-only. Legal/source refs and
    formula lineage mirror :class:`CasillaObservation` for the same target.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    reason: RegistryUnresolvedOutcomeReason
    formula_id: FormulaId
    op: str
    operand_refs: tuple[str, ...] = ()
    operand_casilla_refs: tuple[CasillaId, ...] = ()
    operand_values: tuple[Decimal, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    context: Mapping[str, str] = Field(default_factory=dict)


class RegistryCalculationResult(BaseModel):
    """Calculated outputs for one registry snapshot.

    Canonical storage is :attr:`observations`: a typed tuple of
    :class:`~aeat.domain.calculations.registry.CasillaObservation` covering
    every casilla on the
    :class:`~aeat.domain.calculations.registry.RegistrySnapshot` revision
    (inputs, bound, and formula-computed). Each observation carries
    its final Decimal ``value`` plus the legal / source provenance for
    that casilla pulled from the registry. Formula-computed
    observations additionally carry ``formula_id``, ``op``,
    ``operand_refs``, and ``operand_values`` so the full evaluation
    lineage survives the engine boundary.

    The :attr:`values` and :attr:`entries` views are derived convenience
    properties for readers that need the flat ``{casilla_id: Decimal}``
    map or the formula-only :class:`RegistryCalculationEntry` tuple. The typed
    envelope is the contract; the flat views never grow new fields.

    Coverage asymmetry preserved by the derivation:

    * :attr:`values` covers every observation (inputs, bound, computed), keyed
      by ``casilla_id`` to ``value``.
    * :attr:`entries` covers ONLY observations where ``formula_id`` is
      set. ``len(entries) <= len(observations)`` always; equality holds
      only when every casilla is formula-computed (rare in practice).

    Consumers that need provenance for non-computed casillas must iterate
    :attr:`observations` directly; the entries view drops them by design.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    revision: str
    observations: tuple[CasillaObservation, ...] = Field(default_factory=tuple)
    unresolved_outcomes: tuple[RegistryCalculationUnresolvedOutcome, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _require_observation_provenance(self) -> RegistryCalculationResult:
        for observation in self.observations:
            if not observation.legal_refs or not observation.source_refs:
                raise RegistryValidationError(
                    f"registry calculation result for modelo {self.modelo!r} revision {self.revision!r} "
                    f"contains ungrounded CasillaObservation for casilla {observation.casilla_id!r}; "
                    "legal_refs and source_refs are required",
                    context={
                        "modelo": self.modelo,
                        "revision": self.revision,
                        "casilla_id": observation.casilla_id,
                    },
                )
        for outcome in self.unresolved_outcomes:
            if not outcome.legal_refs or not outcome.source_refs:
                raise RegistryValidationError(
                    f"registry calculation result for modelo {self.modelo!r} revision {self.revision!r} "
                    f"contains ungrounded unresolved outcome for casilla {outcome.casilla_id!r}; "
                    "legal_refs and source_refs are required",
                    context={
                        "modelo": self.modelo,
                        "revision": self.revision,
                        "casilla_id": outcome.casilla_id,
                        "reason": outcome.reason.value,
                    },
                )
        return self

    @property
    def values(self) -> Mapping[CasillaId, Decimal]:
        """Read-only view from registry casilla id to final Decimal value.

        Deliberately a plain ``@property``, not a pydantic
        ``computed_field``: the typed ``observations`` envelope is
        canonical storage; exposing this in JSON would round-trip
        self-incompatibly under ``extra='forbid'`` because the loader
        would refuse the duplicate field on the way back in.
        """
        return {obs.casilla_id: obs.value for obs in self.observations}

    @property
    def entries(self) -> tuple[RegistryCalculationEntry, ...]:
        """Read-only view of formula-computed :class:`RegistryCalculationEntry` rows.

        Preserves the formula-only entry view with ``target_casilla_id`` and
        ``op`` fields for the application-layer indexers that build
        ``{target_casilla_id: entry}`` dictionaries. Insertion order from
        ``observations`` is preserved; the engine emits in formula
        evaluation order, which matches the original ``entries`` shape.
        """
        return tuple(
            RegistryCalculationEntry(
                formula_id=obs.formula_id,
                target_casilla_id=obs.casilla_id,
                op=obs.op or "value",
                operand_refs=obs.operand_refs,
                operand_casilla_refs=obs.operand_casilla_refs,
                operand_values=obs.operand_values,
                value=obs.value,
                legal_refs=obs.legal_refs,
                source_refs=obs.source_refs,
            )
            for obs in self.observations
            if obs.formula_id is not None
        )


def calculate_registry_snapshot[InputKey, InputValue, TextInputKey, TextInputValue](
    snapshot: RegistrySnapshot,
    *,
    inputs: Mapping[InputKey, InputValue],
    date_context: Mapping[str, date],
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    unresolved_relation_ids: tuple[RelationId, ...] = (),
    unresolved_binding_ids: tuple[BindingId, ...] = (),
    date_binding_values: Mapping[BindingId, date] | None = None,
    text_inputs: Mapping[TextInputKey, TextInputValue] | None = None,
) -> RegistryCalculationResult:
    """Evaluate all computed formulas for a registry snapshot.

    ``enum_binding_values`` carries string-valued bindings (typically
    profile-sourced enums like ``CCAA``) that the
    ``lookup_bracket_by_ccaa`` op routes against. They are kept in
    a separate mapping from ``binding_values`` so the Decimal-only
    contract on numeric bindings stays intact.

    ``date_binding_values`` carries date-valued profile facts (e.g.
    birth_date) consumed by the ``age_at_year_end`` op.  Date facts
    cannot flow through the Decimal ``binding_values`` channel; keeping
    them in a dedicated channel preserves the Decimal-only invariant.

    The returned :class:`RegistryCalculationResult` stores
    :class:`~aeat.domain.calculations.registry.CasillaObservation` rows for all
    materialised casillas. Input validation is delegated to
    :mod:`aeat.domain.calculations.registry._formula_runtime_ops` and
    :mod:`aeat.domain.calculations.registry._formula_text_inputs`; initial
    casilla values and absent-by-design markers are delegated to
    :mod:`aeat.domain.calculations.registry._formula_initial_values`.

    Args:
        snapshot: The
            :class:`~aeat.domain.calculations.registry.RegistrySnapshot` that
            supplies the revision, casilla definitions, and formula graph to
            evaluate.
        inputs: Operator-supplied input casilla values; rejected if any value
            is not a :class:`decimal.Decimal`.
        date_context: Date-axis context (e.g. ``filing_period``) consumed by
            date-aware ops; ``filing_period`` defaults to the snapshot's
            year-end when absent.
        binding_values: Optional resolved numeric binding values keyed by
            :class:`~aeat.domain.calculations.registry.DataBindingDefinition`
            id; Decimal-only.
        enum_binding_values: Optional string-valued bindings (e.g. profile
            CCAA) keyed by binding id; consumed by enum-routed ops.
        relation_values: Optional resolved relation values keyed by
            ``relation.id``; Decimal-only.
        unresolved_relation_ids: Relation ids that source resolution proved
            missing/incomplete but non-blocking. Formula targets depending on
            these ids are omitted instead of zero-contributed; relation ids not
            listed here remain hard validation errors when absent.
        unresolved_binding_ids: Binding ids whose enrolled resolver ran for a
            present source but produced no value (expected-but-missing).
            Formula targets depending on these ids are omitted instead of
            raising ``binding_value_missing``; binding ids not listed here
            remain hard validation errors when absent from ``binding_values``.
        date_binding_values: Optional date-valued profile bindings (e.g.
            ``birth_date``) consumed by date-aware ops.
        text_inputs: Optional string-valued operator inputs keyed by casilla
            id; consumed by text-routed ops.
    """
    revision = snapshot.revision
    resolved_inputs = _ops.validated_decimal_input_casilla_ids(
        inputs,
        revision=revision,
    )
    resolved_date_context = dict(date_context)
    default_filing_date = (
        snapshot.filing_period.end_date
        if snapshot.filing_period is not None and snapshot.filing_period.has_date_span()
        else date(snapshot.filing_year, 12, 31)
    )
    resolved_date_context.setdefault("filing_period", default_filing_date)
    supplied_bindings = binding_values or {}
    _ops.reject_non_decimal(supplied_bindings, "binding")
    resolved_bindings = _formula_inputs.binding_values_with_absent_by_design_defaults(
        revision,
        supplied_bindings,
        target_period=snapshot.period,
    )
    _ops.reject_non_decimal(resolved_bindings, "binding")
    resolved_enum_bindings = enum_binding_values or {}
    _ops.reject_non_string(resolved_enum_bindings, "enum_binding")
    resolved_relations = relation_values or {}
    _ops.reject_non_decimal(resolved_relations, "relation")
    resolved_unresolved_relations = frozenset(unresolved_relation_ids).difference(resolved_relations)
    resolved_unresolved_bindings = frozenset(unresolved_binding_ids).difference(resolved_bindings)
    resolved_date_bindings: Mapping[BindingId, date] = date_binding_values or {}
    resolved_text_inputs = _validated_text_input_casilla_ids(text_inputs or {})

    _ops.reject_unknown_external_values(resolved_bindings, {binding.id for binding in revision.bindings}, "binding")
    _ops.reject_unknown_external_values(
        resolved_relations,
        {
            relation.id
            for relation in revision.relations
            if not relation.target_periods or snapshot.period in relation.target_periods
        },
        "relation",
    )
    _ops.reject_unknown_external_values(
        {relation_id: _ZERO for relation_id in resolved_unresolved_relations},
        {
            relation.id
            for relation in revision.relations
            if not relation.target_periods or snapshot.period in relation.target_periods
        },
        "unresolved_relation",
    )
    _ops.reject_unknown_external_values(
        {binding_id: _ZERO for binding_id in resolved_unresolved_bindings},
        {binding.id for binding in revision.bindings},
        "unresolved_binding",
    )
    values, absent_by_design_casilla_ids = _formula_inputs.initial_values(
        revision,
        resolved_inputs,
        binding_values=supplied_bindings,
        target_period=snapshot.period,
    )
    formulas = {formula.target_casilla_id: formula for formula in revision.formulas}
    parameters = {parameter.id: parameter for parameter in revision.parameters}
    casillas_by_id = _casillas_by_id(revision)
    _validate_text_input_targets(resolved_text_inputs, casillas_by_id=casillas_by_id)
    # Per-casilla provenance accumulator. Formula-computed casillas overwrite
    # the input/bound placeholder with the full operand lineage; non-computed
    # casillas keep the registry-sourced legal_refs/source_refs.
    computed_provenance: dict[CasillaId, CasillaObservation] = {}
    unresolved_outcomes: list[RegistryCalculationUnresolvedOutcome] = []
    unresolved_casilla_ids: set[CasillaId] = set()

    with localcontext() as ctx:
        ctx.prec = 28
        for target in formula_evaluation_order(revision):
            formula = formulas[target]
            operand_refs: list[str] = []
            operand_casilla_refs: list[CasillaId] = []
            operand_values: list[Decimal] = []
            try:
                value = _evaluate_expression(
                    formula.expression,
                    values=values,
                    binding_values=resolved_bindings,
                    parameters=parameters,
                    date_context=resolved_date_context,
                    relation_values=resolved_relations,
                    unresolved_relation_ids=resolved_unresolved_relations,
                    unresolved_binding_ids=resolved_unresolved_bindings,
                    unresolved_casilla_ids=unresolved_casilla_ids,
                    operand_refs=operand_refs,
                    operand_casilla_refs=operand_casilla_refs,
                    operand_values=operand_values,
                    enum_binding_values=resolved_enum_bindings,
                    date_binding_values=resolved_date_bindings,
                    filing_year=snapshot.filing_year,
                    text_values=resolved_text_inputs,
                    convenio=snapshot.convenio,
                )
            except _UnresolvedFormulaOutcomeError as exc:
                unresolved_casilla_ids.add(target)
                unresolved_outcomes.append(
                    RegistryCalculationUnresolvedOutcome(
                        casilla_id=target,
                        reason=exc.reason,
                        formula_id=formula.id,
                        op=formula.expression.op or "value",
                        operand_refs=tuple(operand_refs),
                        operand_casilla_refs=tuple(operand_casilla_refs),
                        operand_values=tuple(operand_values),
                        legal_refs=tuple(formula.legal_refs),
                        source_refs=tuple(formula.source_refs),
                        context=exc.context,
                    ),
                )
                continue
            except _UnresolvedFormulaDependencyError:
                unresolved_casilla_ids.add(target)
                continue
            value = _ops.apply_rounding(value, formula.rounding)
            target_casilla_def = casillas_by_id.get(target)
            if target_casilla_def is not None and target_casilla_def.constraints is not None:
                violation = target_casilla_def.constraints.violates(value)
                if violation is not None:
                    raise CasillaConstraintViolationError(
                        f"casilla {target_casilla_def.number!r} ({target_casilla_def.label}) "
                        f"violates declared constraint: {violation}",
                        translated_message="errors.calc.casilla_constraint_violation",
                        context={
                            "casilla_id": target,
                            "display_number": target_casilla_def.number,
                            "value": str(value),
                            "violation": str(violation),
                            "formula_id": formula.id,
                            "legal_refs": ",".join(target_casilla_def.constraints.legal_refs),
                            "source_refs": ",".join(target_casilla_def.constraints.source_refs),
                        },
                    )
            values[target] = value
            computed_provenance[target] = CasillaObservation(
                casilla_id=target,
                value=value,
                formula_id=formula.id,
                op=formula.expression.op or "value",
                operand_refs=tuple(operand_refs),
                operand_casilla_refs=tuple(operand_casilla_refs),
                operand_values=tuple(operand_values),
                legal_refs=tuple(formula.legal_refs),
                source_refs=tuple(formula.source_refs),
            )

    observations = _formula_inputs.materialise_observations(
        values=values,
        computed_provenance=computed_provenance,
        casillas_by_id=casillas_by_id,
        absent_by_design_casilla_ids=absent_by_design_casilla_ids,
    )
    _validate_operand_casilla_refs(observations, known_casilla_ids=frozenset(casillas_by_id))

    return RegistryCalculationResult(
        modelo=snapshot.modelo.id,
        revision=revision.id,
        observations=observations,
        unresolved_outcomes=tuple(unresolved_outcomes),
    )


def _validate_operand_casilla_refs(
    observations: tuple[CasillaObservation, ...],
    *,
    known_casilla_ids: frozenset[CasillaId],
) -> None:
    for observation in observations:
        unknown = sorted(set(observation.operand_casilla_refs).difference(known_casilla_ids))
        if unknown:
            raise RegistryValidationError(
                f"formula provenance for casilla {observation.casilla_id!r} references unknown "
                f"operand casilla ids: {unknown!r}",
                context={
                    "casilla_id": observation.casilla_id,
                    "operand_casilla_refs": ",".join(unknown),
                },
            )
        expected: list[CasillaId] = []
        for ref in observation.operand_refs:
            if ref in known_casilla_ids:
                expected.append(validated_casilla_id(ref, surface="formula operand_ref casilla projection"))
        expected_tuple = tuple(expected)
        if observation.operand_casilla_refs != expected_tuple:
            raise RegistryValidationError(
                f"formula provenance for casilla {observation.casilla_id!r} has ambiguous operand refs: "
                f"operand_refs projects to casillas {expected_tuple!r} but operand_casilla_refs is "
                f"{observation.operand_casilla_refs!r}",
                context={
                    "casilla_id": observation.casilla_id,
                    "expected_operand_casilla_refs": ",".join(expected_tuple),
                    "actual_operand_casilla_refs": ",".join(observation.operand_casilla_refs),
                },
            )


def _evaluate_expression(
    expression: FormulaExpression,
    *,
    values: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal],
    parameters: Mapping[str, ParameterDefinition],
    date_context: Mapping[str, date],
    relation_values: Mapping[RelationId, Decimal],
    unresolved_relation_ids: frozenset[RelationId],
    unresolved_casilla_ids: set[CasillaId],
    operand_refs: list[str],
    operand_casilla_refs: list[CasillaId],
    operand_values: list[Decimal],
    unresolved_binding_ids: frozenset[BindingId] = frozenset(),
    enum_binding_values: Mapping[BindingId, str] | None = None,
    date_binding_values: Mapping[BindingId, date] | None = None,
    filing_year: int = 0,
    text_values: Mapping[CasillaId, str] | None = None,
    convenio: ConvenioAuthority | None = None,
) -> Decimal:
    resolved_enum_bindings: Mapping[BindingId, str] = enum_binding_values or {}
    resolved_date_bindings: Mapping[BindingId, date] = date_binding_values or {}
    resolved_text_values: Mapping[CasillaId, str] = text_values or {}
    resolved_convenio: ConvenioAuthority = convenio if convenio is not None else ConvenioAuthority.empty()
    if expression.op is None:
        return _evaluate_leaf(
            expression,
            values=values,
            binding_values=binding_values,
            parameters=parameters,
            date_context=date_context,
            relation_values=relation_values,
            unresolved_relation_ids=unresolved_relation_ids,
            unresolved_binding_ids=unresolved_binding_ids,
            unresolved_casilla_ids=unresolved_casilla_ids,
            operand_refs=operand_refs,
            operand_casilla_refs=operand_casilla_refs,
            operand_values=operand_values,
            date_binding_values=resolved_date_bindings,
            filing_year=filing_year,
        )
    ctx = _EvalContext(
        values=values,
        binding_values=binding_values,
        parameters=parameters,
        date_context=date_context,
        relation_values=relation_values,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        unresolved_casilla_ids=unresolved_casilla_ids,
        operand_refs=operand_refs,
        operand_casilla_refs=operand_casilla_refs,
        operand_values=operand_values,
        enum_binding_values=resolved_enum_bindings,
        date_binding_values=resolved_date_bindings,
        filing_year=filing_year,
        text_values=resolved_text_values,
        convenio=resolved_convenio,
    )
    op = expression.op
    if op == "lookup_bracket":
        return _evaluate_lookup_bracket(expression, ctx)
    if op == "lookup_bracket_by_ccaa":
        return _evaluate_lookup_bracket_by_ccaa(expression, ctx)
    if op == "m100_resolve_renta_inmobiliaria_imputada":
        return _evaluate_m100_resolve_renta_inmobiliaria_imputada(expression, ctx)
    if op == "irnr_resolve_tipo_gravamen":
        return _evaluate_irnr_resolve_tipo_gravamen(expression, ctx)
    if op == "m210_resolve_base_imponible":
        return _evaluate_m210_resolve_base_imponible(expression, ctx)
    if op == "lookup_parameter_by_entity_type":
        return _evaluate_lookup_parameter_by_entity_type(expression, ctx)
    if op == "lookup_bracket_by_entity_type":
        return _evaluate_lookup_bracket_by_entity_type(expression, ctx)
    if op == "if_then_else":
        return _evaluate_if_then_else(expression, ctx)
    if op == "age_at_year_end":
        return _evaluate_age_at_year_end(expression, ctx)
    if op == "m131_resolve_modulos_previo":
        return _evaluate_m131_resolve_modulos_previo(expression, ctx)
    args = [_evaluate_with_ctx(arg, ctx) for arg in expression.args]
    return _ops.evaluate_args_op(op, args)


@dataclass(frozen=True)
class _EvalContext:
    """Bundles the runtime sinks + maps threaded through every recursive call.

    Kept frozen and slot-equivalent so the dispatcher can hand the same
    context to every per-op evaluator without copying. The three list
    sinks (operand_refs, operand_casilla_refs, operand_values) ARE mutated in place — they
    accumulate evaluation provenance for the explainability surface.
    """

    values: Mapping[CasillaId, Decimal]
    binding_values: Mapping[BindingId, Decimal]
    parameters: Mapping[str, ParameterDefinition]
    date_context: Mapping[str, date]
    relation_values: Mapping[RelationId, Decimal]
    unresolved_relation_ids: frozenset[RelationId]
    unresolved_casilla_ids: set[CasillaId]
    operand_refs: list[str]
    operand_casilla_refs: list[CasillaId]
    operand_values: list[Decimal]
    enum_binding_values: Mapping[BindingId, str]
    date_binding_values: Mapping[BindingId, date]
    filing_year: int
    unresolved_binding_ids: frozenset[BindingId] = frozenset()
    text_values: Mapping[CasillaId, str] = field(default_factory=dict)
    convenio: ConvenioAuthority = field(default_factory=ConvenioAuthority.empty)


def _evaluate_with_ctx(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Convenience: re-enter the dispatcher carrying every context field forward."""
    return _evaluate_expression(
        expression,
        values=ctx.values,
        binding_values=ctx.binding_values,
        parameters=ctx.parameters,
        date_context=ctx.date_context,
        relation_values=ctx.relation_values,
        unresolved_relation_ids=ctx.unresolved_relation_ids,
        unresolved_binding_ids=ctx.unresolved_binding_ids,
        unresolved_casilla_ids=ctx.unresolved_casilla_ids,
        operand_refs=ctx.operand_refs,
        operand_casilla_refs=ctx.operand_casilla_refs,
        operand_values=ctx.operand_values,
        enum_binding_values=ctx.enum_binding_values,
        date_binding_values=ctx.date_binding_values,
        filing_year=ctx.filing_year,
        text_values=ctx.text_values,
        convenio=ctx.convenio,
    )


def _evaluate_lookup_bracket(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    if len(expression.args) != 2:
        raise RegistryValidationError("formula op 'lookup_bracket' expects 2 args")
    bracket_arg = expression.args[1]
    if bracket_arg.parameter is None:
        raise RegistryValidationError("formula op 'lookup_bracket' requires args[1] to be a parameter leaf")
    bracket_param = ctx.parameters.get(bracket_arg.parameter)
    if bracket_param is None:
        raise RegistryValidationError(f"parameter {bracket_arg.parameter!r} not registered")
    if bracket_param.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {bracket_arg.parameter!r} must declare data_type='bracket_table' to be used by lookup_bracket",
        )
    base = _evaluate_with_ctx(expression.args[0], ctx)
    ctx.operand_refs.append(bracket_arg.parameter)
    result = _ops.resolve_bracket(bracket_param, base, ctx.date_context)
    ctx.operand_values.append(result)
    return result


def _evaluate_lookup_bracket_by_ccaa(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    if len(expression.args) != 3:
        raise RegistryValidationError("formula op 'lookup_bracket_by_ccaa' expects 3 args")
    binding_arg = expression.args[1]
    dispatch_arg = expression.args[2]
    if binding_arg.binding is None:
        raise RegistryValidationError("formula op 'lookup_bracket_by_ccaa' requires args[1] to be a binding leaf")
    if dispatch_arg.dispatch_table is None:
        raise RegistryValidationError(
            "formula op 'lookup_bracket_by_ccaa' requires args[2] to be a dispatch_table leaf",
        )
    if binding_arg.binding not in ctx.enum_binding_values:
        raise RegistryValidationError(
            f"enum binding {binding_arg.binding!r} has no supplied value; required by lookup_bracket_by_ccaa",
        )
    dispatch_key = ctx.enum_binding_values[binding_arg.binding]
    dispatch_table = dispatch_arg.dispatch_table
    if dispatch_key not in dispatch_table:
        raise RegistryValidationError(
            f"lookup_bracket_by_ccaa dispatch_table is missing CCAA {dispatch_key!r} "
            f"(declared keys: {sorted(dispatch_table)})",
        )
    bracket_param_id = dispatch_table[dispatch_key]
    bracket_param = ctx.parameters.get(bracket_param_id)
    if bracket_param is None:
        raise RegistryValidationError(f"parameter {bracket_param_id!r} not registered")
    if bracket_param.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {bracket_param_id!r} must declare data_type='bracket_table' "
            f"to be used by lookup_bracket_by_ccaa",
        )
    base = _evaluate_with_ctx(expression.args[0], ctx)
    ctx.operand_refs.append(binding_arg.binding)
    ctx.operand_refs.append(bracket_param_id)
    result = _ops.resolve_bracket(bracket_param, base, ctx.date_context)
    ctx.operand_values.append(result)
    return result


def _evaluate_m100_resolve_renta_inmobiliaria_imputada(
    expression: FormulaExpression,
    ctx: _EvalContext,
) -> Decimal:
    """Resolve M100 Art. 85 imputed real-estate income for cadastral-value rows.

    M100's 0083-0089 property row has the cadastral-value branch inputs:
    value, revised-value checkbox, days at disposal, and the mixed-use
    percentage/days override. The same row does not carry the no-cadastral
    substitute base (max of acquisition and administration-checked values), so
    that branch fails closed instead of inventing a base or silently returning
    zero for a positive imputation period.
    """
    op = "m100_resolve_renta_inmobiliaria_imputada"
    args = _m100_resolve_imputed_rent_args(expression)

    catastral_value = _m100_numeric_casilla_value(args.catastral_value_casilla_id, ctx)
    disposal_days = _m100_numeric_casilla_value(args.disposal_days_casilla_id, ctx)
    mixed_use = _m100_boolean_casilla_value(args.mixed_use_flag_casilla_id, ctx, op=op)
    disposal_percentage = _m100_numeric_casilla_value(args.disposal_percentage_casilla_id, ctx)
    mixed_use_days = _m100_numeric_casilla_value(args.mixed_use_days_casilla_id, ctx)
    is_revised = _m100_revised_cadastral_value_flag(args.revised_flag_casilla_id, ctx)

    if catastral_value < _ZERO:
        raise RegistryValidationError(
            "M100 Art.85 valor catastral must be non-negative",
            translated_message="errors.calc.m100_art85_catastral_value_negative",
            context={"casilla_id": args.catastral_value_casilla_id, "value": str(catastral_value)},
        )
    for casilla_id, value in (
        (args.disposal_days_casilla_id, disposal_days),
        (args.disposal_percentage_casilla_id, disposal_percentage),
        (args.mixed_use_days_casilla_id, mixed_use_days),
    ):
        if value < _ZERO:
            raise RegistryValidationError(
                "M100 Art.85 numeric inputs must be non-negative",
                translated_message="errors.calc.m100_art85_input_negative",
                context={"casilla_id": casilla_id, "value": str(value)},
            )
    if catastral_value == _ZERO:
        if disposal_days > _ZERO or mixed_use_days > _ZERO or mixed_use or disposal_percentage > _ZERO:
            raise RegistryValidationError(
                "M100 Art.85 no-catastral imputation requires substitute-base casillas that are not "
                "present in the 0083-0089 registry row",
                translated_message="errors.calc.m100_art85_no_catastral_base_missing",
                context={
                    "catastral_value_casilla_id": args.catastral_value_casilla_id,
                    "disposal_days_casilla_id": args.disposal_days_casilla_id,
                    "mixed_use_days_casilla_id": args.mixed_use_days_casilla_id,
                },
            )
        return _ZERO

    effective_days = mixed_use_days if mixed_use else disposal_days
    _m100_validate_imputation_days(
        effective_days,
        casilla_id=args.mixed_use_days_casilla_id if mixed_use else args.disposal_days_casilla_id,
    )
    if not mixed_use and (mixed_use_days != _ZERO or disposal_percentage != _ZERO):
        raise RegistryValidationError(
            "M100 Art.85 mixed-use days or percentage require casilla 0086 to be checked",
            translated_message="errors.calc.m100_art85_mixed_use_inputs_without_flag",
            context={
                "mixed_use_flag_casilla_id": args.mixed_use_flag_casilla_id,
                "mixed_use_days_casilla_id": args.mixed_use_days_casilla_id,
                "disposal_percentage_casilla_id": args.disposal_percentage_casilla_id,
            },
        )
    share = _ONE
    if mixed_use:
        if disposal_percentage <= _ZERO or disposal_percentage > Decimal("100"):
            raise RegistryValidationError(
                "M100 Art.85 mixed-use percentage must be in (0, 100]",
                translated_message="errors.calc.m100_art85_disposal_percentage_invalid",
                context={
                    "casilla_id": args.disposal_percentage_casilla_id,
                    "value": str(disposal_percentage),
                },
            )
        share = disposal_percentage / Decimal("100")

    recent_rate = _m100_scalar_parameter_value(args.recent_rate_parameter, ctx, op=op)
    old_rate = _m100_scalar_parameter_value(args.old_rate_parameter, ctx, op=op)
    rate = recent_rate if is_revised else old_rate
    return catastral_value * rate * (effective_days / _M100_IMPUTATION_YEAR_DAYS) * share


def _m100_resolve_imputed_rent_args(expression: FormulaExpression) -> _M100ResolveImputedRentArgs:
    op = "m100_resolve_renta_inmobiliaria_imputada"
    if len(expression.args) != 8:
        raise RegistryValidationError(f"formula op {op!r} expects 8 args, got {len(expression.args)}")
    (
        catastral_value_arg,
        revised_flag_arg,
        disposal_days_arg,
        mixed_use_flag_arg,
        disposal_percentage_arg,
        mixed_use_days_arg,
        recent_rate_arg,
        old_rate_arg,
    ) = expression.args
    if catastral_value_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[0] to be a casilla leaf")
    if revised_flag_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[1] to be a casilla leaf")
    if disposal_days_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[2] to be a casilla leaf")
    if mixed_use_flag_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[3] to be a casilla leaf")
    if disposal_percentage_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[4] to be a casilla leaf")
    if mixed_use_days_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[5] to be a casilla leaf")
    if recent_rate_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[6] to be a parameter leaf")
    if old_rate_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[7] to be a parameter leaf")
    return _M100ResolveImputedRentArgs(
        catastral_value_casilla_id=catastral_value_arg.casilla_id,
        revised_flag_casilla_id=revised_flag_arg.casilla_id,
        disposal_days_casilla_id=disposal_days_arg.casilla_id,
        mixed_use_flag_casilla_id=mixed_use_flag_arg.casilla_id,
        disposal_percentage_casilla_id=disposal_percentage_arg.casilla_id,
        mixed_use_days_casilla_id=mixed_use_days_arg.casilla_id,
        recent_rate_parameter=recent_rate_arg.parameter,
        old_rate_parameter=old_rate_arg.parameter,
    )


def _m100_revised_cadastral_value_flag(casilla_id: CasillaId, ctx: _EvalContext) -> bool:
    raw_value = ctx.text_values.get(casilla_id, "")
    ctx.operand_refs.append(casilla_id)
    ctx.operand_casilla_refs.append(casilla_id)
    if raw_value == "":
        return False
    normalised = raw_value.strip().upper()
    if normalised == "X":
        return True
    raise RegistryValidationError(
        "M100 Art.85 revised cadastral value flag must be the official X checkbox value",
        translated_message="errors.calc.m100_art85_revision_flag_invalid",
        context={"casilla_id": casilla_id, "value": raw_value},
    )


def _m100_numeric_casilla_value(casilla_id: CasillaId, ctx: _EvalContext) -> Decimal:
    if casilla_id not in ctx.values:
        if casilla_id in ctx.unresolved_casilla_ids:
            raise _UnresolvedFormulaDependencyError((casilla_id,))
        raise RegistryValidationError(
            f"casilla {casilla_id!r} referenced before evaluation",
            translated_message="errors.calc.casilla_referenced_before_evaluation",
            context={"casilla_id": casilla_id},
        )
    value = ctx.values[casilla_id]
    ctx.operand_refs.append(casilla_id)
    ctx.operand_casilla_refs.append(casilla_id)
    ctx.operand_values.append(value)
    return value


def _m100_boolean_casilla_value(casilla_id: CasillaId, ctx: _EvalContext, *, op: str) -> bool:
    value = _m100_numeric_casilla_value(casilla_id, ctx)
    if value not in {_ZERO, _ONE}:
        raise RegistryValidationError(
            "M100 Art.85 boolean casilla must be 0 or 1",
            translated_message="errors.calc.m100_art85_boolean_invalid",
            context={"casilla_id": casilla_id, "value": str(value), "op": op},
        )
    return value == _ONE


def _m100_validate_imputation_days(days: Decimal, *, casilla_id: CasillaId) -> None:
    if days != days.to_integral_value() or days <= _ZERO or days > _M100_IMPUTATION_YEAR_DAYS:
        raise RegistryValidationError(
            "M100 Art.85 imputation days must be an integer in [1, 365]",
            translated_message="errors.calc.m100_art85_imputation_days_invalid",
            context={"casilla_id": casilla_id, "value": str(days), "max_days": str(_M100_IMPUTATION_YEAR_DAYS)},
        )


def _m100_scalar_parameter_value(parameter_id: ParameterId, ctx: _EvalContext, *, op: str) -> Decimal:
    parameter = ctx.parameters.get(parameter_id)
    if parameter is None:
        raise RegistryValidationError(
            f"parameter {parameter_id!r} not registered",
            translated_message="errors.calc.parameter_unknown",
            context={"parameter_id": parameter_id},
        )
    if parameter.data_type not in {"decimal", "money", "integer", "ratio"}:
        raise RegistryValidationError(
            f"parameter {parameter_id!r} must be scalar to be used by {op}",
            translated_message="errors.calc.dispatch_parameter_kind",
            context={"parameter_id": parameter_id, "op": op},
        )
    value = _ops.resolve_parameter(parameter, ctx.date_context)
    ctx.operand_refs.append(parameter_id)
    ctx.operand_values.append(value)
    return value


def _evaluate_irnr_resolve_tipo_gravamen(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Resolve the IRNR tipo de gravamen rate, applying any treaty override.

    The single tipo-de-gravamen resolution path for every IRNR consumer
    (Modelo 210 today, the retenciones-a-no-residentes modelos when they
    land). It resolves the TRLIRNR domestic baseline and, when the profile
    declares a fiscal-residence country, consults the cross-cutting
    :class:`~._convenio.ConvenioAuthority` projected onto the snapshot. On a
    matched override it branches on the typed
    :class:`~aeat.core.ConvenioOverrideKind`:

    * ``flat`` replaces the domestic rate outright,
    * ``ceiling`` applies ``min(domestic, treaty)`` so "más favorable" is
      computed rather than assumed,
    * ``allocation_domestic_tariff`` delegates the amount to the domestic
      tariff (the Art. 25.1.b progressive pension tariff for ``pension``, the
      baseline rate otherwise),
    * ``exempt`` drives the source-state rate to zero.

    A declared treaty country with no override row yields a typed unresolved
    outcome (``no-silent-under-declaration``); the application verification
    layer converts it into a finding post-engine.
    """
    args = _irnr_resolve_tipo_gravamen_args(expression)
    tipo_renta = ctx.text_values.get(args.tipo_casilla_id, "")
    ctx.operand_refs.append(args.tipo_casilla_id)
    ctx.operand_casilla_refs.append(args.tipo_casilla_id)
    if not tipo_renta:
        _raise_m210_unresolved_outcome(
            RegistryUnresolvedOutcomeReason.M210_BASELINE_TIPO_DEFERRED,
            ctx=ctx,
            args=args,
            tipo_renta=tipo_renta,
            country="",
        )

    baseline_param = ctx.parameters.get(args.baseline_parameter)
    ctx.operand_refs.extend((args.baseline_parameter, args.country_binding))
    baseline_rate = _m210_baseline_rate(baseline_param, tipo_renta=tipo_renta, year=ctx.filing_year)
    country = ctx.enum_binding_values.get(args.country_binding) or ""
    override = _resolve_convenio_override(ctx, country=country, tipo_renta=tipo_renta)

    if tipo_renta == TipoRentaIrnr.PENSION.value:
        rate = _irnr_pension_effective_rate(args, ctx, override=override, country=country)
        if rate is None:
            _raise_m210_unresolved_outcome(
                RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING,
                ctx=ctx,
                args=args,
                tipo_renta=tipo_renta,
                country=country,
            )
        ctx.operand_values.append(rate)
        return rate

    if not country:
        if baseline_rate is None:
            _raise_m210_unresolved_outcome(
                RegistryUnresolvedOutcomeReason.M210_BASELINE_TIPO_DEFERRED,
                ctx=ctx,
                args=args,
                tipo_renta=tipo_renta,
                country=country,
            )
        ctx.operand_values.append(baseline_rate)
        return baseline_rate

    if override is None:
        _raise_m210_unresolved_outcome(
            RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING,
            ctx=ctx,
            args=args,
            tipo_renta=tipo_renta,
            country=country,
        )
    rate = _apply_convenio_override(override, baseline_rate=baseline_rate)
    if rate is None:
        _raise_m210_unresolved_outcome(
            RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING,
            ctx=ctx,
            args=args,
            tipo_renta=tipo_renta,
            country=country,
        )
    ctx.operand_values.append(rate)
    return rate


def _raise_m210_unresolved_outcome(
    reason: RegistryUnresolvedOutcomeReason,
    *,
    ctx: _EvalContext,
    args: _IrnrResolveTipoGravamenArgs,
    tipo_renta: str,
    country: str,
) -> None:
    raise _UnresolvedFormulaOutcomeError(
        reason,
        context={
            "tipo_renta": tipo_renta,
            "country": country,
            "filing_year": str(ctx.filing_year),
            "baseline_parameter": args.baseline_parameter,
            "country_binding": args.country_binding,
        },
    )


def _irnr_resolve_tipo_gravamen_args(expression: FormulaExpression) -> _IrnrResolveTipoGravamenArgs:
    op = "irnr_resolve_tipo_gravamen"
    if len(expression.args) != 5:
        raise RegistryValidationError(f"formula op {op!r} expects 5 args, got {len(expression.args)}")
    tipo_arg, base_arg, baseline_arg, pension_tariff_arg, country_arg = expression.args
    if tipo_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[0] to be a casilla leaf")
    if base_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[1] to be a casilla leaf")
    if baseline_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[2] to be a parameter leaf")
    if pension_tariff_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[3] to be a parameter leaf")
    if country_arg.binding is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[4] to be a binding leaf")
    return _IrnrResolveTipoGravamenArgs(
        tipo_casilla_id=tipo_arg.casilla_id,
        baseline_parameter=baseline_arg.parameter,
        country_binding=country_arg.binding,
        base_casilla_id=base_arg.casilla_id,
        pension_tariff_parameter=pension_tariff_arg.parameter,
    )


def _m210_baseline_rate(
    parameter: ParameterDefinition | None,
    *,
    tipo_renta: str,
    year: int,
) -> Decimal | None:
    if parameter is None:
        return None
    for entry in parameter.keyed_brackets:
        if (
            entry.key == tipo_renta
            and entry.valid_from.year <= year
            and (entry.valid_to is None or entry.valid_to.year >= year)
        ):
            try:
                return Decimal(entry.value)
            except (ArithmeticError, ValueError):
                return None
    return None


def _resolve_convenio_override(
    ctx: _EvalContext,
    *,
    country: str,
    tipo_renta: str,
) -> ConvenioOverride | None:
    """Resolve the treaty override for the declared country + income type, or None.

    Hydrates the free-text ``tipo_renta`` casilla value to the closed
    :class:`~aeat.core.TipoRentaIrnr` enum at this boundary; an unrecognised
    value carries no treaty override (the domestic baseline stands).
    """
    if not country:
        return None
    try:
        tipo_enum = TipoRentaIrnr(tipo_renta)
    except ValueError:
        return None
    return ctx.convenio.resolve(country.upper(), tipo_enum, ctx.filing_year)


def _apply_convenio_override(override: ConvenioOverride, *, baseline_rate: Decimal | None) -> Decimal | None:
    """Apply a non-pension treaty override to the domestic baseline rate."""
    kind = override.kind
    if kind is ConvenioOverrideKind.EXEMPT:
        return _ZERO
    if kind is ConvenioOverrideKind.ALLOCATION_DOMESTIC_TARIFF:
        return baseline_rate
    if override.rate is None:
        return None
    if kind is ConvenioOverrideKind.FLAT:
        return override.rate
    # CEILING: min(domestic, treaty) — "más favorable" computed, not assumed.
    if baseline_rate is None:
        return None
    return min(baseline_rate, override.rate)


def _irnr_pension_effective_rate(
    args: _IrnrResolveTipoGravamenArgs,
    ctx: _EvalContext,
    *,
    override: ConvenioOverride | None,
    country: str,
) -> Decimal | None:
    if country:
        if override is None:
            return None
        if override.kind is ConvenioOverrideKind.EXEMPT:
            return _ZERO
        if override.kind is ConvenioOverrideKind.FLAT and override.rate is not None:
            return override.rate
        if override.kind is ConvenioOverrideKind.CEILING and override.rate is not None:
            effective = _m210_effective_rate_from_tariff(args.base_casilla_id, args.pension_tariff_parameter, ctx)
            return min(effective, override.rate)
        # ALLOCATION_DOMESTIC_TARIFF delegates the amount to the domestic tariff.
    return _m210_effective_rate_from_tariff(args.base_casilla_id, args.pension_tariff_parameter, ctx)


def _m210_effective_rate_from_tariff(
    base_casilla_id: CasillaId,
    tariff_parameter_id: ParameterId,
    ctx: _EvalContext,
) -> Decimal:
    base = _m210_numeric_casilla_value(base_casilla_id, ctx)
    tariff_parameter = ctx.parameters.get(tariff_parameter_id)
    if tariff_parameter is None:
        raise RegistryValidationError(
            f"parameter {tariff_parameter_id!r} not registered",
            translated_message="errors.calc.parameter_unknown",
            context={"parameter_id": tariff_parameter_id},
        )
    if tariff_parameter.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {tariff_parameter_id!r} must declare data_type='bracket_table' "
            "to be used by M210 pension tariff resolution",
            translated_message="errors.calc.dispatch_parameter_kind",
            context={"parameter_id": tariff_parameter_id, "op": "irnr_resolve_tipo_gravamen"},
        )
    ctx.operand_refs.append(tariff_parameter_id)
    cuota = _ops.resolve_bracket(tariff_parameter, base, ctx.date_context)
    ctx.operand_values.append(cuota)
    if base == _ZERO:
        return _ZERO
    return cuota / base


def _evaluate_m210_resolve_base_imponible(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Resolve M210 base imponible, including Art. 24.6 and Art. 13.1.h branches.

    Non-imputed Art. 24.1 tipos start from ``rendimientos_integros``. Art.
    24.6 permits deducting linked expenses when the filer is in the EU/EEA
    path, represented by ``tipo_renta='ue_residente'`` or an EU/EEA
    ``country_of_fiscal_residence`` binding. For ``inmobiliaria``, the
    operator applies the LIRPF Art. 85 imputation mechanics reached through
    TRLIRNR Arts. 13.1.h and 24.5; own-use imputation admits no expenses.
    """
    args = _m210_resolve_base_args(expression)
    tipo_renta = ctx.text_values.get(args.tipo_casilla_id, "")
    ctx.operand_refs.append(args.tipo_casilla_id)
    ctx.operand_casilla_refs.append(args.tipo_casilla_id)
    country = (ctx.enum_binding_values.get(args.country_binding) or "").upper()
    ctx.operand_refs.append(args.country_binding)
    deductible_expenses = _m210_numeric_casilla_value(args.deductible_expenses_casilla_id, ctx)
    if deductible_expenses < _ZERO:
        raise RegistryValidationError(
            "M210 gastos_deducibles must be non-negative",
            translated_message="errors.calc.m210_gastos_deducibles_negative",
            context={"casilla_id": args.deductible_expenses_casilla_id, "value": str(deductible_expenses)},
        )
    if tipo_renta != "inmobiliaria":
        gross = _m210_numeric_casilla_value(args.gross_casilla_id, ctx)
        if deductible_expenses == _ZERO:
            return gross
        if not _m210_allows_art_24_6_expenses(tipo_renta=tipo_renta, country_code=country):
            raise RegistryValidationError(
                "M210 gastos_deducibles require the EU/EEA Art. 24.6 path",
                translated_message="errors.calc.m210_gastos_deducibles_not_allowed",
                context={
                    "casilla_id": args.deductible_expenses_casilla_id,
                    "tipo_renta": tipo_renta,
                    "country_of_fiscal_residence": country,
                },
            )
        return gross - deductible_expenses
    if deductible_expenses != _ZERO:
        raise RegistryValidationError(
            "M210 imputed real-estate own-use base cannot deduct gastos_deducibles",
            translated_message="errors.calc.m210_gastos_deducibles_not_allowed",
            context={
                "casilla_id": args.deductible_expenses_casilla_id,
                "tipo_renta": tipo_renta,
                "country_of_fiscal_residence": country,
            },
        )

    days = _m210_imputation_days(args.imputation_days_casilla_id, ctx)
    days_fraction = days / Decimal(_m210_days_in_filing_year(ctx.filing_year))
    catastral_value = _m210_numeric_casilla_value(args.catastral_value_casilla_id, ctx)
    if catastral_value > _ZERO:
        recent_rate = _m210_scalar_parameter_value(args.recent_rate_parameter, ctx)
        old_rate = _m210_scalar_parameter_value(args.old_rate_parameter, ctx)
        coefficient = _m210_numeric_casilla_value(args.imputation_coefficient_casilla_id, ctx)
        if coefficient not in {recent_rate, old_rate}:
            raise RegistryValidationError(
                "M210 inmobiliaria coefficient must be one of the registry-authored "
                f"LIRPF art.85 rates ({recent_rate} or {old_rate}); got {coefficient}",
                translated_message="errors.calc.m210_imputation_coefficient_invalid",
                context={
                    "casilla_id": args.imputation_coefficient_casilla_id,
                    "value": str(coefficient),
                    "allowed_values": f"{recent_rate},{old_rate}",
                },
            )
        return catastral_value * coefficient * days_fraction

    acquisition_value = _m210_numeric_casilla_value(args.acquisition_value_casilla_id, ctx)
    administrative_value = _m210_numeric_casilla_value(args.administrative_value_casilla_id, ctx)
    substitute_value = max(acquisition_value, administrative_value)
    if substitute_value <= _ZERO:
        raise RegistryValidationError(
            "M210 inmobiliaria without cadastral value requires a positive acquisition or administrative checked value",
            translated_message="errors.calc.m210_imputation_no_catastral_value_missing",
            context={
                "acquisition_casilla_id": args.acquisition_value_casilla_id,
                "administrative_casilla_id": args.administrative_value_casilla_id,
            },
        )
    no_catastral_fraction = _m210_scalar_parameter_value(args.no_catastral_fraction_parameter, ctx)
    recent_rate = _m210_scalar_parameter_value(args.recent_rate_parameter, ctx)
    return substitute_value * no_catastral_fraction * recent_rate * days_fraction


def _m210_resolve_base_args(expression: FormulaExpression) -> _M210ResolveBaseArgs:
    op = "m210_resolve_base_imponible"
    if len(expression.args) != 12:
        raise RegistryValidationError(f"formula op {op!r} expects 12 args, got {len(expression.args)}")
    (
        tipo_arg,
        gross_arg,
        deductible_expenses_arg,
        country_arg,
        catastral_value_arg,
        imputation_coefficient_arg,
        imputation_days_arg,
        acquisition_value_arg,
        administrative_value_arg,
        recent_rate_arg,
        old_rate_arg,
        no_catastral_fraction_arg,
    ) = expression.args
    if tipo_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[0] to be a casilla leaf")
    if gross_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[1] to be a casilla leaf")
    if deductible_expenses_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[2] to be a casilla leaf")
    if country_arg.binding is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[3] to be a binding leaf")
    if catastral_value_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[4] to be a casilla leaf")
    if imputation_coefficient_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[5] to be a casilla leaf")
    if imputation_days_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[6] to be a casilla leaf")
    if acquisition_value_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[7] to be a casilla leaf")
    if administrative_value_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[8] to be a casilla leaf")
    if recent_rate_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[9] to be a parameter leaf")
    if old_rate_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[10] to be a parameter leaf")
    if no_catastral_fraction_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[11] to be a parameter leaf")
    return _M210ResolveBaseArgs(
        tipo_casilla_id=tipo_arg.casilla_id,
        gross_casilla_id=gross_arg.casilla_id,
        deductible_expenses_casilla_id=deductible_expenses_arg.casilla_id,
        country_binding=country_arg.binding,
        catastral_value_casilla_id=catastral_value_arg.casilla_id,
        imputation_coefficient_casilla_id=imputation_coefficient_arg.casilla_id,
        imputation_days_casilla_id=imputation_days_arg.casilla_id,
        acquisition_value_casilla_id=acquisition_value_arg.casilla_id,
        administrative_value_casilla_id=administrative_value_arg.casilla_id,
        recent_rate_parameter=recent_rate_arg.parameter,
        old_rate_parameter=old_rate_arg.parameter,
        no_catastral_fraction_parameter=no_catastral_fraction_arg.parameter,
    )


def _m210_allows_art_24_6_expenses(*, tipo_renta: str, country_code: str) -> bool:
    return tipo_renta == "ue_residente" or country_code in UE_EEA_COUNTRY_CODES


def _m210_numeric_casilla_value(casilla_id: CasillaId, ctx: _EvalContext) -> Decimal:
    if casilla_id not in ctx.values:
        if casilla_id in ctx.unresolved_casilla_ids:
            raise _UnresolvedFormulaDependencyError((casilla_id,))
        raise RegistryValidationError(
            f"casilla {casilla_id!r} referenced before evaluation",
            translated_message="errors.calc.casilla_referenced_before_evaluation",
            context={"casilla_id": casilla_id},
        )
    value = ctx.values[casilla_id]
    ctx.operand_refs.append(casilla_id)
    ctx.operand_casilla_refs.append(casilla_id)
    ctx.operand_values.append(value)
    return value


def _m210_scalar_parameter_value(parameter_id: ParameterId, ctx: _EvalContext) -> Decimal:
    parameter = ctx.parameters.get(parameter_id)
    if parameter is None:
        raise RegistryValidationError(
            f"parameter {parameter_id!r} not registered",
            translated_message="errors.calc.parameter_unknown",
            context={"parameter_id": parameter_id},
        )
    if parameter.data_type not in {"decimal", "money", "integer", "ratio"}:
        raise RegistryValidationError(
            f"parameter {parameter_id!r} must be scalar to be used by m210_resolve_base_imponible",
            translated_message="errors.calc.dispatch_parameter_kind",
            context={"parameter_id": parameter_id, "op": "m210_resolve_base_imponible"},
        )
    value = _ops.resolve_parameter(parameter, ctx.date_context)
    ctx.operand_refs.append(parameter_id)
    ctx.operand_values.append(value)
    return value


def _m210_imputation_days(casilla_id: CasillaId, ctx: _EvalContext) -> Decimal:
    days = _m210_numeric_casilla_value(casilla_id, ctx)
    year_days = Decimal(_m210_days_in_filing_year(ctx.filing_year))
    if days != days.to_integral_value() or days <= _ZERO or days > year_days:
        raise RegistryValidationError(
            f"M210 inmobiliaria imputation days must be an integer in [1, {year_days}]",
            translated_message="errors.calc.m210_imputation_days_invalid",
            context={"casilla_id": casilla_id, "value": str(days), "max_days": str(year_days)},
        )
    return days


def _m210_days_in_filing_year(year: int) -> int:
    if year <= 0:
        raise RegistryValidationError(
            "m210_resolve_base_imponible requires a non-zero filing_year in evaluation context",
            translated_message="errors.calc.m210_imputation_no_filing_year",
        )
    return (date(year, 12, 31) - date(year, 1, 1)).days + 1


@dataclass(frozen=True, slots=True)
class _M131ResolveModulosPrevioArgs:
    """Resolved registry ids for the M131 estimación-objetiva módulos Fase 1ª dispatcher."""

    epigrafe_casilla_id: CasillaId
    modulo_unit_casilla_ids: tuple[CasillaId, CasillaId, CasillaId, CasillaId]
    coefficient_parameter: ParameterId


#: Módulo slot count the M131 first-slice coefficient tables carry (the
#: highest-cardinality tabled activity, 972.1 peluquería, uses all four; the
#: 3-módulo activities pass a literal ``0`` for the unused 4th slot).
_M131_MODULOS_SLOT_COUNT = 4


def _m131_resolve_modulos_previo_args(expression: FormulaExpression) -> _M131ResolveModulosPrevioArgs:
    op = "m131_resolve_modulos_previo"
    expected_arg_count = 2 + _M131_MODULOS_SLOT_COUNT
    if len(expression.args) != expected_arg_count:
        raise RegistryValidationError(
            f"formula op {op!r} expects {expected_arg_count} args, got {len(expression.args)}",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": str(expected_arg_count)},
        )
    epigrafe_arg = expression.args[0]
    modulo_args = expression.args[1 : 1 + _M131_MODULOS_SLOT_COUNT]
    coefficient_arg = expression.args[1 + _M131_MODULOS_SLOT_COUNT]
    if epigrafe_arg.casilla_id is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[0] to be a casilla leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[0]", "expected_kind": "casilla"},
        )
    resolved_modulo_ids: list[CasillaId] = []
    for index, modulo_arg in enumerate(modulo_args, start=1):
        if modulo_arg.casilla_id is None:
            raise RegistryValidationError(
                f"formula op {op!r} requires args[{index}] to be a casilla leaf",
                translated_message="errors.calc.lookup_dispatch_arg_kind",
                context={"op": op, "position": f"args[{index}]", "expected_kind": "casilla"},
            )
        resolved_modulo_ids.append(modulo_arg.casilla_id)
    if coefficient_arg.parameter is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[{1 + _M131_MODULOS_SLOT_COUNT}] to be a parameter leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={
                "op": op,
                "position": f"args[{1 + _M131_MODULOS_SLOT_COUNT}]",
                "expected_kind": "parameter",
            },
        )
    modulo_ids = (resolved_modulo_ids[0], resolved_modulo_ids[1], resolved_modulo_ids[2], resolved_modulo_ids[3])
    return _M131ResolveModulosPrevioArgs(
        epigrafe_casilla_id=epigrafe_arg.casilla_id,
        modulo_unit_casilla_ids=modulo_ids,
        coefficient_parameter=coefficient_arg.parameter,
    )


def _m131_modulos_coefficient(
    parameter: ParameterDefinition | None,
    *,
    epigrafe: str,
    modulo_index: int,
    year: int,
) -> Decimal | None:
    """Look up the (epígrafe, módulo) coefficient in the M131 keyed-bracket table.

    Returns ``None`` when the composite key has no row for the filing year —
    the epígrafe is not (yet) part of the first-slice tabled activities, or
    the module slot does not apply to that activity. A ``None`` result is the
    engine's "not table-driven" signal; the caller returns ``Decimal('0')``
    rather than raising, because :func:`_evaluate_m131_resolve_modulos_previo`
    feeds an internal-only advisory-support casilla, not a filed casilla — the
    official casilla 01 stays reachable as a manual operator input and the
    registry-declared advisory predicate surfaces the gap
    (no-silent-under-declaration), never a silent computed zero standing in
    for the filed figure.
    """
    if parameter is None:
        return None
    key = f"{epigrafe}:{modulo_index}"
    for entry in parameter.keyed_brackets:
        in_window = entry.valid_from.year <= year and (entry.valid_to is None or entry.valid_to.year >= year)
        if entry.key == key and in_window:
            try:
                return Decimal(entry.value)
            except (ArithmeticError, ValueError):
                return None
    return None


def _evaluate_m131_resolve_modulos_previo(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Resolve the M131/M100 estimación-objetiva Fase 1ª rendimiento neto previo.

    LIRPF art. 31 + the annual Orden de módulos (Anexo II) fix the mechanism:
    rendimiento neto previo = Σ(unidades_módulo × rendimiento anual por unidad
    antes de amortización), per IAE epígrafe. This op reads the operator-
    declared IAE epígrafe (a text casilla) and up to four módulo unit-count
    casillas, looks up each módulo's coefficient in the registry-declared
    :class:`~aeat.domain.calculations.registry.ParameterDefinition`
    (``data_type='keyed_bracket_table'``, key ``"<epígrafe>:<módulo>"``), and
    sums the per-módulo products.

    An untabled epígrafe (bounded first-slice per the
    ``2026-07-01-modelo-131-eo-modulos-engine-adr``) or a blank epígrafe
    resolves to ``Decimal('0')`` — this op feeds an internal-only
    advisory-support casilla, never the filed casilla 01 directly, so a zero
    here means "the table-driven engine has no coverage for this activity",
    not "the rendimiento is zero". The
    ``advisory_when_computed_diverges`` verification predicate surfaces the
    gap or the discrepancy to the operator; it never silently substitutes.
    """
    args = _m131_resolve_modulos_previo_args(expression)
    epigrafe = ctx.text_values.get(args.epigrafe_casilla_id, "").strip()
    ctx.operand_refs.append(args.epigrafe_casilla_id)
    ctx.operand_casilla_refs.append(args.epigrafe_casilla_id)
    parameter = ctx.parameters.get(args.coefficient_parameter)
    ctx.operand_refs.append(args.coefficient_parameter)
    if not epigrafe or parameter is None:
        return _ZERO
    total = _ZERO
    for modulo_index, modulo_casilla_id in enumerate(args.modulo_unit_casilla_ids, start=1):
        units = _m210_numeric_casilla_value(modulo_casilla_id, ctx)
        if units == _ZERO:
            continue
        coefficient = _m131_modulos_coefficient(
            parameter,
            epigrafe=epigrafe,
            modulo_index=modulo_index,
            year=ctx.filing_year,
        )
        if coefficient is None:
            # This módulo slot has no row for the declared epígrafe (either the
            # epígrafe is entirely untabled, or this slot does not apply to it).
            # A non-zero unit count against an untabled epígrafe means the
            # WHOLE Fase 1ª product is untabled — the engine cannot mix tabled
            # and untabled módulos for one activity — so the running total is
            # abandoned and the internal casilla resolves to zero.
            return _ZERO
        ctx.operand_values.append(coefficient)
        total += units * coefficient
    return total


def _evaluate_lookup_parameter_by_entity_type(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Dispatch a scalar parameter lookup by an enum binding (e.g. entity_type → tipo gravamen for IS modelo 200).

    Three args: args[0] is unused (placeholder for symmetry with the
    bracket variant); args[1] is the binding leaf carrying the enum
    value; args[2] is the dispatch_table mapping enum keys to
    parameter ids.
    """
    op = "lookup_parameter_by_entity_type"
    if len(expression.args) != 3:
        raise RegistryValidationError(
            "formula op 'lookup_parameter_by_entity_type' expects 3 args",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": "3"},
        )
    binding_arg = expression.args[1]
    dispatch_arg = expression.args[2]
    if binding_arg.binding is None:
        raise RegistryValidationError(
            "formula op 'lookup_parameter_by_entity_type' requires args[1] to be a binding leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[1]", "expected_kind": "binding"},
        )
    if dispatch_arg.dispatch_table is None:
        raise RegistryValidationError(
            "formula op 'lookup_parameter_by_entity_type' requires args[2] to be a dispatch_table leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[2]", "expected_kind": "dispatch_table"},
        )
    if binding_arg.binding not in ctx.enum_binding_values:
        raise RegistryValidationError(
            f"enum binding {binding_arg.binding!r} has no supplied value; required by lookup_parameter_by_entity_type",
            translated_message="errors.calc.enum_binding_value_missing",
            context={"binding_id": binding_arg.binding, "op": op},
        )
    dispatch_key = ctx.enum_binding_values[binding_arg.binding]
    dispatch_table = dispatch_arg.dispatch_table
    if dispatch_key not in dispatch_table:
        raise RegistryValidationError(
            f"lookup_parameter_by_entity_type dispatch_table is missing key {dispatch_key!r} "
            f"(declared keys: {sorted(dispatch_table)})",
            translated_message="errors.calc.dispatch_key_unknown",
            context={
                "op": op,
                "binding_id": binding_arg.binding,
                "dispatch_key": dispatch_key,
                "available_keys": ",".join(sorted(dispatch_table)),
            },
        )
    scalar_param_id = dispatch_table[dispatch_key]
    scalar_param = ctx.parameters.get(scalar_param_id)
    if scalar_param is None:
        raise RegistryValidationError(
            f"parameter {scalar_param_id!r} not registered",
            translated_message="errors.calc.parameter_unknown",
            context={"parameter_id": scalar_param_id},
        )
    if scalar_param.data_type == "bracket_table":
        raise RegistryValidationError(
            f"parameter {scalar_param_id!r} declares data_type='bracket_table'; "
            f"lookup_parameter_by_entity_type requires a scalar parameter (decimal / money / integer / ratio)",
            translated_message="errors.calc.dispatch_parameter_kind",
            context={"parameter_id": scalar_param_id, "op": op},
        )
    result = _ops.resolve_parameter(scalar_param, ctx.date_context)
    ctx.operand_refs.append(binding_arg.binding)
    ctx.operand_refs.append(scalar_param_id)
    ctx.operand_values.append(result)
    return result


def _evaluate_lookup_bracket_by_entity_type(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Dispatch a bracket-table lookup by an entity-type enum binding.

    Mirrors :func:`_evaluate_lookup_parameter_by_entity_type` but routes
    against a ``bracket_table`` parameter (e.g. the LIS Art. 29.1
    micro-empresa two-tranche scale on Modelo 200): args[0] is the base
    value resolved against the bracket; args[1] is the binding leaf
    carrying the enum value (typically ``legal_entity_form``); args[2]
    is the dispatch_table mapping enum keys to bracket-table parameter
    ids. A scalar parameter resolved by the dispatch is rejected — the
    op exists precisely because the per-sub-form rate is a tranche
    scale, not a flat scalar.
    """
    op = "lookup_bracket_by_entity_type"
    if len(expression.args) != 3:
        raise RegistryValidationError(
            "formula op 'lookup_bracket_by_entity_type' expects 3 args",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": "3"},
        )
    binding_arg = expression.args[1]
    dispatch_arg = expression.args[2]
    if binding_arg.binding is None:
        raise RegistryValidationError(
            "formula op 'lookup_bracket_by_entity_type' requires args[1] to be a binding leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[1]", "expected_kind": "binding"},
        )
    if dispatch_arg.dispatch_table is None:
        raise RegistryValidationError(
            "formula op 'lookup_bracket_by_entity_type' requires args[2] to be a dispatch_table leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[2]", "expected_kind": "dispatch_table"},
        )
    if binding_arg.binding not in ctx.enum_binding_values:
        raise RegistryValidationError(
            f"enum binding {binding_arg.binding!r} has no supplied value; required by lookup_bracket_by_entity_type",
            translated_message="errors.calc.enum_binding_value_missing",
            context={"binding_id": binding_arg.binding, "op": op},
        )
    dispatch_key = ctx.enum_binding_values[binding_arg.binding]
    dispatch_table = dispatch_arg.dispatch_table
    if dispatch_key not in dispatch_table:
        raise RegistryValidationError(
            f"lookup_bracket_by_entity_type dispatch_table is missing key {dispatch_key!r} "
            f"(declared keys: {sorted(dispatch_table)})",
            translated_message="errors.calc.dispatch_key_unknown",
            context={
                "op": op,
                "binding_id": binding_arg.binding,
                "dispatch_key": dispatch_key,
                "available_keys": ",".join(sorted(dispatch_table)),
            },
        )
    bracket_param_id = dispatch_table[dispatch_key]
    bracket_param = ctx.parameters.get(bracket_param_id)
    if bracket_param is None:
        raise RegistryValidationError(
            f"parameter {bracket_param_id!r} not registered",
            translated_message="errors.calc.parameter_unknown",
            context={"parameter_id": bracket_param_id},
        )
    if bracket_param.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {bracket_param_id!r} must declare data_type='bracket_table' "
            f"to be used by lookup_bracket_by_entity_type",
            translated_message="errors.calc.dispatch_parameter_kind",
            context={"parameter_id": bracket_param_id, "op": op},
        )
    base = _evaluate_with_ctx(expression.args[0], ctx)
    ctx.operand_refs.append(binding_arg.binding)
    ctx.operand_refs.append(bracket_param_id)
    result = _ops.resolve_bracket(bracket_param, base, ctx.date_context)
    ctx.operand_values.append(result)
    return result


def _evaluate_if_then_else(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Short-circuit: evaluate the predicate first, then only the selected branch.

    Eager evaluation of both branches would surface false-branch
    errors (e.g. divide-by-zero) even when the predicate routes around
    them — defeating the conditional.
    """
    if len(expression.args) != 3:
        raise RegistryValidationError("formula op 'if_then_else' expects 3 args")
    predicate_value = _evaluate_with_ctx(expression.args[0], ctx)
    selected_branch = expression.args[1] if predicate_value != _ZERO else expression.args[2]
    return _evaluate_with_ctx(selected_branch, ctx)


def _evaluate_age_at_year_end(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Compute age at the fiscal year-end from a date-channel binding.

    Expects exactly one arg which must be a ``date_binding`` leaf — the
    id of a date-valued profile fact (e.g. taxpayer birth_date).
    Returns ``Decimal(filing_year - birth_date.year)``.

    Art. 57.1.b LIRPF ages the taxpayer at 31 December of the tax year
    (fin del período impositivo).  Because birth month/day cannot be
    after 31 December of any year, the simplistic
    ``filing_year - birth_year`` formula is correct for all cases.
    """
    if len(expression.args) != 1:
        raise RegistryValidationError("formula op 'age_at_year_end' expects exactly 1 arg")
    arg = expression.args[0]
    if arg.date_binding is None:
        raise RegistryValidationError("formula op 'age_at_year_end' requires args[0] to be a date_binding leaf")
    binding_id = str(arg.date_binding)
    if binding_id not in ctx.date_binding_values:
        raise RegistryValidationError(
            f"date_binding {binding_id!r} has no supplied value; required by age_at_year_end",
            translated_message="errors.calc.date_binding_value_missing",
            context={"binding_id": binding_id},
        )
    birth_date = ctx.date_binding_values[binding_id]
    if ctx.filing_year == 0:
        raise RegistryValidationError(
            "age_at_year_end requires a non-zero filing_year in evaluation context",
            translated_message="errors.calc.age_at_year_end_no_filing_year",
        )
    age = Decimal(ctx.filing_year - birth_date.year)
    ctx.operand_refs.append(binding_id)
    ctx.operand_values.append(age)
    return age


def _evaluate_leaf(
    expression: FormulaExpression,
    *,
    values: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal],
    parameters: Mapping[str, ParameterDefinition],
    date_context: Mapping[str, date],
    relation_values: Mapping[RelationId, Decimal],
    unresolved_relation_ids: frozenset[RelationId],
    unresolved_casilla_ids: set[CasillaId],
    operand_refs: list[str],
    operand_casilla_refs: list[CasillaId],
    operand_values: list[Decimal],
    unresolved_binding_ids: frozenset[BindingId] = frozenset(),
    date_binding_values: Mapping[BindingId, date] | None = None,
    filing_year: int = 0,
) -> Decimal:
    if expression.literal is not None:
        return expression.literal
    if expression.casilla_id is not None:
        if expression.casilla_id not in values:
            if expression.casilla_id in unresolved_casilla_ids:
                raise _UnresolvedFormulaDependencyError((expression.casilla_id,))
            raise RegistryValidationError(
                f"casilla {expression.casilla_id!r} referenced before evaluation",
                translated_message="errors.calc.casilla_referenced_before_evaluation",
                context={"casilla_id": expression.casilla_id},
            )
        value = values[expression.casilla_id]
        operand_refs.append(expression.casilla_id)
        operand_casilla_refs.append(expression.casilla_id)
        operand_values.append(value)
        return value
    if expression.binding is not None:
        if expression.binding not in binding_values:
            if expression.binding in unresolved_binding_ids:
                raise _UnresolvedFormulaDependencyError((expression.binding,))
            raise RegistryValidationError(
                f"binding {expression.binding!r} has no supplied value",
                translated_message="errors.calc.binding_value_missing",
                context={"binding_id": expression.binding},
            )
        value = binding_values[expression.binding]
        operand_refs.append(expression.binding)
        operand_values.append(value)
        return value
    if expression.date_binding is not None:
        # A date_binding leaf is consumed exclusively by the age_at_year_end op.
        # As a bare leaf (outside age_at_year_end) it has no Decimal projection;
        # callers should never reach here for a standalone date_binding leaf
        # without wrapping it in age_at_year_end.  Raise descriptively.
        raise RegistryValidationError(
            f"date_binding {expression.date_binding!r} leaf must be consumed inside an "
            "'age_at_year_end' op, not used as a standalone Decimal leaf",
            translated_message="errors.calc.date_binding_used_as_decimal_leaf",
            context={"binding_id": str(expression.date_binding)},
        )
    if expression.parameter is not None:
        parameter = parameters[expression.parameter]
        value = _ops.resolve_parameter(parameter, date_context)
        operand_refs.append(expression.parameter)
        operand_values.append(value)
        return value
    if expression.relation is not None:
        if expression.relation not in relation_values:
            if expression.relation in unresolved_relation_ids:
                raise _UnresolvedFormulaDependencyError((expression.relation,))
            raise RegistryValidationError(
                f"relation {expression.relation!r} has no supplied value",
                translated_message="errors.calc.relation_value_missing",
                context={"relation_id": expression.relation},
            )
        value = relation_values[expression.relation]
        operand_refs.append(expression.relation)
        operand_values.append(value)
        return value
    raise RegistryValidationError(
        "empty formula expression",
        translated_message="errors.calc.empty_expression",
    )
