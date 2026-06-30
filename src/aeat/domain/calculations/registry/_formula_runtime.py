"""Registry-backed formula runtime using typed operation graphs.

Evaluates formula expressions declared on a :class:`ModeloRevision` against
casilla inputs and binding values drawn from a :class:`RegistrySnapshot`.
The calculation entry point :func:`calculate_registry_snapshot` is the
primary surface used by :class:`ValidatedRegistryAuthority`-backed callers
to produce :class:`~._bindings.CasillaObservation` rows with full provenance.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, localcontext

from pydantic import BaseModel, Field, model_validator

from ....core import STRICT_FROZEN_CONFIG
from ...contribuyente import UE_EEA_COUNTRY_CODES
from . import _formula_initial_values as _formula_inputs
from . import _formula_runtime_ops as _ops
from ._bindings import CasillaObservation
from ._casilla_membership import casillas_by_id as _casillas_by_id
from ._errors import CasillaConstraintViolationError, RegistrySnapshotError, RegistryValidationError
from ._formula_text_inputs import validate_text_input_targets as _validate_text_input_targets
from ._formula_text_inputs import validated_text_input_casilla_ids as _validated_text_input_casilla_ids
from ._ids import BindingId, CasillaId, FormulaId, ParameterId, RelationId, validated_casilla_id
from ._runtime_graph import formula_evaluation_order
from ._schema import FormulaExpression, ParameterDefinition, RegistrySnapshot

_ZERO = Decimal("0")
read_parameter, _resolve_bracket = _ops.read_parameter, _ops.resolve_bracket

# M210 IRNR sentinel rate values. Emitted by
# ``m210_resolve_rate`` when a deterministic rate cannot be resolved
# from the registry parameters at evaluation time. The verification
# layer rewrites these sentinels into BLOCKING findings post-engine
# (see ``_rewrite_m210_sentinels`` in the application layer); they
# never leak past the verification boundary into a draft / export.
# Negative magnitudes guarantee no collision with a real registry-
# authored rate, which is always in ``[0, 1]`` per TRLIRNR Art 25.
_M210_DEFERRED_TIPO_SENTINEL = Decimal("-1")
_M210_CONVENIO_MISSING_SENTINEL = Decimal("-2")
_M210_DOMESTIC_TARIFF_RATE = "DOMESTIC_TARIFF"
_M210_RATE_SENTINELS = frozenset({_M210_DEFERRED_TIPO_SENTINEL, _M210_CONVENIO_MISSING_SENTINEL})

# Public-aliased re-exports for the application-layer verification
# sweep. The private module-internal names stay primary so the engine
# implementation can be reorganised without forcing every caller to
# track the rename.
M210_DEFERRED_TIPO_SENTINEL = _M210_DEFERRED_TIPO_SENTINEL
M210_CONVENIO_MISSING_SENTINEL = _M210_CONVENIO_MISSING_SENTINEL
M210_RATE_SENTINELS = _M210_RATE_SENTINELS


class _UnresolvedFormulaDependencyError(RegistrySnapshotError):
    """Raised internally when a non-blocking source gap makes a formula unresolved."""

    def __init__(self, dependency_ids: tuple[str, ...]) -> None:
        super().__init__(", ".join(dependency_ids))
        self.dependency_ids = dependency_ids


@dataclass(frozen=True, slots=True)
class _M210ResolveRateArgs:
    tipo_casilla_id: CasillaId
    baseline_parameter: ParameterId
    convenio_parameter: ParameterId
    country_binding: BindingId
    base_casilla_id: CasillaId | None = None
    pension_tariff_parameter: ParameterId | None = None


@dataclass(frozen=True, slots=True)
class _M210ResolveBaseArgs:
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


class RegistryCalculationEntry(BaseModel):
    """One trace row emitted by the registry formula runtime.

    Carries the per-formula provenance (``formula_id``, ``op``,
    ``operand_refs``, ``operand_values``, ``legal_refs``,
    ``source_refs``) for a single formula-computed casilla. Entries
    cover ONLY the casillas that were computed by a registry formula
    — input casillas and bound casillas are absent from the entries
    tuple. Callers that need provenance for non-computed casillas
    must look them up against
    ``RegistrySnapshot.revision.casillas`` directly.
    """

    model_config = STRICT_FROZEN_CONFIG

    formula_id: FormulaId
    target_casilla_id: CasillaId
    op: str
    operand_refs: tuple[str, ...]
    operand_casilla_refs: tuple[CasillaId, ...]
    operand_values: tuple[Decimal, ...]
    value: Decimal
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


class RegistryCalculationResult(BaseModel):
    """Calculated outputs for one registry snapshot.

    Canonical storage is :attr:`observations` — a typed tuple of
    :class:`CasillaObservation` covering EVERY casilla on the revision
    (inputs, bound, and formula-computed). Each observation carries
    its final Decimal ``value`` plus the legal / source provenance for
    that casilla pulled from the registry. Formula-computed
    observations additionally carry ``formula_id``, ``op``,
    ``operand_refs``, and ``operand_values`` so the full evaluation
    lineage survives the engine boundary.

    The :attr:`values` and :attr:`entries` views are derived convenience
    properties for readers that need the flat ``{casilla_id: Decimal}``
    map or the formula-only entry tuple. The typed envelope is the
    contract; the flat views never grow new fields.

    Coverage asymmetry preserved by the derivation:

    * :attr:`values` covers every observation (inputs, bound, computed)
      — keyed by ``casilla_id`` → ``value``.
    * :attr:`entries` covers ONLY observations where ``formula_id`` is
      set. ``len(entries) <= len(observations)`` always; equality holds
      only when every casilla is formula-computed (rare in practice).

    Consumers that need provenance for non-computed casillas must iterate
    :attr:`observations` directly — the entries view drops them by design.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    revision: str
    observations: tuple[CasillaObservation, ...] = Field(default_factory=tuple)

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
        return self

    @property
    def values(self) -> Mapping[CasillaId, Decimal]:
        """Read-only view: casilla_id → final Decimal value.

        Deliberately a plain ``@property``, not a pydantic
        ``computed_field``: the typed ``observations`` envelope is
        canonical storage; exposing this in JSON would round-trip
        self-incompatibly under ``extra='forbid'`` because the loader
        would refuse the duplicate field on the way back in.
        """
        return {obs.casilla_id: obs.value for obs in self.observations}

    @property
    def entries(self) -> tuple[RegistryCalculationEntry, ...]:
        """Read-only view: formula-computed observations as :class:`RegistryCalculationEntry` rows.

        Preserves the formula-only entry view with ``target_casilla_id`` and
        ``op`` fields for the application-layer indexers that build
        ``{target_casilla_id: entry}`` dictionaries. Insertion order from
        ``observations`` is preserved — the engine emits in formula
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
    """Evaluate all computed formulas and return a :class:`RegistryCalculationResult`.

    ``enum_binding_values`` carries string-valued bindings (typically
    profile-sourced enums like ``CCAA``) that the
    ``lookup_bracket_by_ccaa`` op routes against. They are kept in
    a separate mapping from ``binding_values`` so the Decimal-only
    contract on numeric bindings stays intact.

    ``date_binding_values`` carries date-valued profile facts (e.g.
    birth_date) consumed by the ``age_at_year_end`` op.  Date facts
    cannot flow through the Decimal ``binding_values`` channel; keeping
    them in a dedicated channel preserves the Decimal-only invariant.

    Args:
        snapshot: The :class:`RegistrySnapshot` that supplies the revision,
            casilla definitions, and formula graph to evaluate.
        inputs: Operator-supplied input casilla values; rejected if any value
            is not a :class:`Decimal`.
        date_context: Date-axis context (e.g. ``filing_period``) consumed by
            date-aware ops; ``filing_period`` defaults to the snapshot's
            year-end when absent.
        binding_values: Optional resolved numeric binding values keyed by
            ``DataBindingDefinition.id``; Decimal-only.
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
                )
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
) -> Decimal:
    resolved_enum_bindings: Mapping[BindingId, str] = enum_binding_values or {}
    resolved_date_bindings: Mapping[BindingId, date] = date_binding_values or {}
    resolved_text_values: Mapping[CasillaId, str] = text_values or {}
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
    )
    op = expression.op
    if op == "lookup_bracket":
        return _evaluate_lookup_bracket(expression, ctx)
    if op == "lookup_bracket_by_ccaa":
        return _evaluate_lookup_bracket_by_ccaa(expression, ctx)
    if op == "m210_resolve_rate":
        return _evaluate_m210_resolve_rate(expression, ctx)
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


def _evaluate_m210_resolve_rate(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Resolve the M210 IRNR tipo de gravamen rate from registry parameters.

    Four leaf args keep the original flat-rate contract:
    ``(tipo_renta_casilla, baseline_param, convenio_param,
    country_binding)``. Six leaf args add ``base_imponible`` and the
    Art. 25.1.b pension bracket table so the pension branch can expose
    an effective rate whose downstream ``base * tipo`` equals the
    statutory progressive quota.
    """
    args = _m210_resolve_rate_args(expression)
    tipo_renta = ctx.text_values.get(args.tipo_casilla_id, "")
    ctx.operand_refs.append(args.tipo_casilla_id)
    ctx.operand_casilla_refs.append(args.tipo_casilla_id)
    if not tipo_renta:
        ctx.operand_values.append(_M210_DEFERRED_TIPO_SENTINEL)
        return _M210_DEFERRED_TIPO_SENTINEL

    baseline_param = ctx.parameters.get(args.baseline_parameter)
    convenio_param = ctx.parameters.get(args.convenio_parameter)
    ctx.operand_refs.extend((args.baseline_parameter, args.convenio_parameter, args.country_binding))
    baseline_rate = _m210_baseline_rate(baseline_param, tipo_renta=tipo_renta, year=ctx.filing_year)
    country = ctx.enum_binding_values.get(args.country_binding) or ""

    if tipo_renta == "pension" and args.base_casilla_id is not None and args.pension_tariff_parameter is not None:
        rate = _m210_pension_effective_rate(
            args,
            ctx,
            convenio_param=convenio_param,
            country=country,
        )
        ctx.operand_values.append(rate)
        return rate

    if not country:
        if baseline_rate is None:
            ctx.operand_values.append(_M210_DEFERRED_TIPO_SENTINEL)
            return _M210_DEFERRED_TIPO_SENTINEL
        ctx.operand_values.append(baseline_rate)
        return baseline_rate

    matched_row = _m210_convenio_rate_row(
        convenio_param,
        country_code=country.upper(),
        tipo_renta=tipo_renta,
        year=ctx.filing_year,
    )
    if matched_row is None:
        ctx.operand_values.append(_M210_CONVENIO_MISSING_SENTINEL)
        return _M210_CONVENIO_MISSING_SENTINEL
    rate = _m210_rate_from_convenio_row(matched_row.rate)
    ctx.operand_values.append(rate)
    return rate


def _m210_resolve_rate_args(expression: FormulaExpression) -> _M210ResolveRateArgs:
    op = "m210_resolve_rate"
    if len(expression.args) == 4:
        tipo_arg, baseline_arg, convenio_arg, country_arg = expression.args
        base_arg = None
        pension_tariff_arg = None
    elif len(expression.args) == 6:
        tipo_arg, base_arg, baseline_arg, convenio_arg, pension_tariff_arg, country_arg = expression.args
    else:
        raise RegistryValidationError(f"formula op {op!r} expects 4 or 6 args, got {len(expression.args)}")
    if tipo_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[0] to be a casilla leaf")
    if base_arg is not None and base_arg.casilla_id is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[1] to be a casilla leaf when present")
    if baseline_arg.parameter is None:
        position = "args[2]" if base_arg is not None else "args[1]"
        raise RegistryValidationError(f"formula op {op!r} requires {position} to be a parameter leaf")
    if convenio_arg.parameter is None:
        position = "args[3]" if base_arg is not None else "args[2]"
        raise RegistryValidationError(f"formula op {op!r} requires {position} to be a parameter leaf")
    if pension_tariff_arg is not None and pension_tariff_arg.parameter is None:
        raise RegistryValidationError(f"formula op {op!r} requires args[4] to be a parameter leaf when present")
    if country_arg.binding is None:
        position = "args[5]" if base_arg is not None else "args[3]"
        raise RegistryValidationError(f"formula op {op!r} requires {position} to be a binding leaf")
    return _M210ResolveRateArgs(
        tipo_casilla_id=tipo_arg.casilla_id,
        baseline_parameter=baseline_arg.parameter,
        convenio_parameter=convenio_arg.parameter,
        country_binding=country_arg.binding,
        base_casilla_id=base_arg.casilla_id if base_arg is not None else None,
        pension_tariff_parameter=(pension_tariff_arg.parameter if pension_tariff_arg is not None else None),
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


def _m210_convenio_rate_row(
    parameter: ParameterDefinition | None,
    *,
    country_code: str,
    tipo_renta: str,
    year: int,
):
    if parameter is None:
        return None
    for row in parameter.convenio_rates:
        if (
            row.country_code == country_code
            and row.tipo_renta == tipo_renta
            and row.valid_from.year <= year
            and (row.valid_to is None or row.valid_to.year >= year)
        ):
            return row
    return None


def _m210_rate_from_convenio_row(rate: str) -> Decimal | str:
    if rate == _M210_DOMESTIC_TARIFF_RATE:
        return _M210_DOMESTIC_TARIFF_RATE
    try:
        return Decimal(rate)
    except (ArithmeticError, ValueError):
        return _M210_CONVENIO_MISSING_SENTINEL


def _m210_pension_effective_rate(
    args: _M210ResolveRateArgs,
    ctx: _EvalContext,
    *,
    convenio_param: ParameterDefinition | None,
    country: str,
) -> Decimal:
    assert args.base_casilla_id is not None
    assert args.pension_tariff_parameter is not None
    if country:
        matched_row = _m210_convenio_rate_row(
            convenio_param,
            country_code=country.upper(),
            tipo_renta="pension",
            year=ctx.filing_year,
        )
        if matched_row is None:
            return _M210_CONVENIO_MISSING_SENTINEL
        convenio_rate = _m210_rate_from_convenio_row(matched_row.rate)
        if convenio_rate != _M210_DOMESTIC_TARIFF_RATE:
            return convenio_rate if isinstance(convenio_rate, Decimal) else _M210_CONVENIO_MISSING_SENTINEL
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
            context={"parameter_id": tariff_parameter_id, "op": "m210_resolve_rate"},
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
