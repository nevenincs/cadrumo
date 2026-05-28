"""Registry-backed formula runtime using typed operation graphs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ._bindings import CasillaObservation, _PreviousModeloSelector
from ._errors import CasillaConstraintViolationError, RegistrySnapshotError, RegistryValidationError
from ._runtime_graph import formula_evaluation_order
from ._schema import (
    CasillaDefinition,
    DataBindingDefinition,
    DatedValue,
    FormulaExpression,
    InputKind,
    ModeloRevision,
    ParameterDefinition,
    RegistrySnapshot,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")

# M210 IRNR Phase 1 sentinel rate values. Emitted by
# ``m210_resolve_rate`` when a deterministic rate cannot be resolved
# from the registry parameters at evaluation time. The verification
# layer rewrites these sentinels into BLOCKING findings post-engine
# (see ``_rewrite_m210_sentinels`` in the application layer); they
# never leak past the verification boundary into a draft / export.
# Negative magnitudes guarantee no collision with a real registry-
# authored rate, which is always in ``[0, 1]`` per TRLIRNR Art 25.
_M210_DEFERRED_TIPO_SENTINEL = Decimal("-1")
_M210_CONVENIO_MISSING_SENTINEL = Decimal("-2")
_M210_NOT_YET_AUTHORED_SENTINEL = Decimal("-3")
_M210_RATE_SENTINELS = frozenset(
    {
        _M210_DEFERRED_TIPO_SENTINEL,
        _M210_CONVENIO_MISSING_SENTINEL,
        _M210_NOT_YET_AUTHORED_SENTINEL,
    }
)

# Public-aliased re-exports for the application-layer verification
# sweep. The private module-internal names stay primary so the engine
# implementation can be reorganised without forcing every caller to
# track the rename.
M210_DEFERRED_TIPO_SENTINEL = _M210_DEFERRED_TIPO_SENTINEL
M210_CONVENIO_MISSING_SENTINEL = _M210_CONVENIO_MISSING_SENTINEL
M210_NOT_YET_AUTHORED_SENTINEL = _M210_NOT_YET_AUTHORED_SENTINEL
M210_RATE_SENTINELS = _M210_RATE_SENTINELS


class RegistryCalculationEntry(BaseModel):
    """One trace row emitted by the registry formula runtime.

    Carries the per-formula provenance (``formula_id``, ``op``,
    ``operand_refs``, ``operand_values``, ``legal_refs``,
    ``source_refs``) for a single formula-computed casilla. Entries
    cover ONLY the casillas that were computed by a registry formula
    — input casillas and bound casillas are absent from the entries
    tuple. Callers that need provenance for non-computed casillas
    must look them up against
    :attr:`RegistrySnapshot.revision.casillas` directly.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    formula_id: str
    target: str
    op: str
    operand_refs: tuple[str, ...]
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

    The legacy :attr:`values` and :attr:`entries` views are derived
    properties for backward compatibility with downstream readers that
    iterate the flat ``{casilla_id: Decimal}`` map or the
    formula-only entry tuple. The typed envelope is the contract; the
    flat views never grow new fields.

    Coverage asymmetry preserved by the derivation:

    * :attr:`values` covers every observation (inputs, bound, computed)
      — keyed by ``casilla_id`` → ``value``.
    * :attr:`entries` covers ONLY observations where ``formula_id`` is
      set. ``len(entries) <= len(observations)`` always; equality holds
      only when every casilla is formula-computed (rare in practice).

    Consumers that need provenance for non-computed casillas must iterate
    :attr:`observations` directly — the entries view drops them by design.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str
    revision: str
    observations: tuple[CasillaObservation, ...] = Field(default_factory=tuple)

    @property
    def values(self) -> Mapping[str, Decimal]:
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

        Preserves the historical entry shape (with ``target`` and
        ``op`` fields) for the application-layer indexers that build
        ``{target: entry}`` dictionaries. Insertion order from
        ``observations`` is preserved — the engine emits in formula
        evaluation order, which matches the original ``entries`` shape.
        """
        return tuple(
            RegistryCalculationEntry(
                formula_id=obs.formula_id,
                target=obs.casilla_id,
                op=obs.op or "value",
                operand_refs=obs.operand_refs,
                operand_values=obs.operand_values,
                value=obs.value,
                legal_refs=obs.legal_refs,
                source_refs=obs.source_refs,
            )
            for obs in self.observations
            if obs.formula_id is not None
        )


def calculate_registry_snapshot(
    snapshot: RegistrySnapshot,
    *,
    inputs: Mapping[str, Decimal],
    date_context: Mapping[str, date],
    binding_values: Mapping[str, Decimal] | None = None,
    enum_binding_values: Mapping[str, str] | None = None,
    relation_values: Mapping[str, Decimal] | None = None,
    date_binding_values: Mapping[str, date] | None = None,
    text_inputs: Mapping[str, str] | None = None,
) -> RegistryCalculationResult:
    """Evaluate all computed formulas in a validated registry snapshot.

    ``enum_binding_values`` carries string-valued bindings (typically
    profile-sourced enums like ``CCAA``) that the
    :func:`lookup_bracket_by_ccaa` op routes against. They are kept in
    a separate mapping from ``binding_values`` so the Decimal-only
    contract on numeric bindings stays intact.

    ``date_binding_values`` carries date-valued profile facts (e.g.
    birth_date) consumed by the ``age_at_year_end`` op.  Date facts
    cannot flow through the Decimal ``binding_values`` channel; keeping
    them in a dedicated channel preserves the Decimal-only invariant.
    """

    _reject_non_decimal(inputs, "input")
    resolved_date_context = dict(date_context)
    resolved_date_context.setdefault("filing_period", date(snapshot.filing_year, 12, 31))
    resolved_bindings = binding_values or {}
    _reject_non_decimal(resolved_bindings, "binding")
    resolved_enum_bindings = enum_binding_values or {}
    _reject_non_string(resolved_enum_bindings, "enum_binding")
    resolved_relations = relation_values or {}
    _reject_non_decimal(resolved_relations, "relation")
    resolved_date_bindings: Mapping[str, date] = date_binding_values or {}
    resolved_text_inputs: Mapping[str, str] = text_inputs or {}
    _reject_non_string(resolved_text_inputs, "text_input")

    revision = snapshot.revision
    _reject_unknown_external_values(resolved_bindings, {binding.id for binding in revision.bindings}, "binding")
    _reject_unknown_external_values(
        resolved_relations,
        {
            relation.id
            for relation in revision.relations
            if not relation.target_periods or snapshot.period in relation.target_periods
        },
        "relation",
    )
    values, absent_by_design_casillas = _initial_values(
        revision,
        inputs,
        binding_values=resolved_bindings,
        target_period=snapshot.period,
    )
    formulas = {formula.target: formula for formula in revision.formulas}
    parameters = {parameter.id: parameter for parameter in revision.parameters}
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    # Text-input casillas (e.g. an IRNR ``tipo_renta`` enum string) flow
    # through a dedicated string-keyed channel into the eval context;
    # the Decimal ``values`` map carries a Decimal(0) placeholder for
    # the same casilla via ``_initial_values`` so existing
    # value-coverage invariants stay intact. Reject unknown casilla ids
    # and ids that point at non-text casillas so a caller's typo cannot
    # silently strand the input.
    text_casilla_ids = {
        casilla_id for casilla_id, casilla in casillas_by_id.items() if casilla.data_type == "text"
    }
    unknown_text_inputs = sorted(set(resolved_text_inputs).difference(casillas_by_id))
    if unknown_text_inputs:
        raise RegistryValidationError(
            f"unknown text_input casilla ids: {unknown_text_inputs!r}",
            translated_message="errors.calc.unknown_text_input_casillas",
            context={"casilla_ids": ",".join(unknown_text_inputs)},
        )
    mistyped_text_inputs = sorted(set(resolved_text_inputs).difference(text_casilla_ids))
    if mistyped_text_inputs:
        raise RegistryValidationError(
            f"text_input supplied for non-text casilla ids: {mistyped_text_inputs!r}",
            translated_message="errors.calc.text_input_non_text_casillas",
            context={"casilla_ids": ",".join(mistyped_text_inputs)},
        )
    # Per-casilla provenance accumulator. Formula-computed casillas overwrite
    # the input/bound placeholder with the full operand lineage; non-computed
    # casillas keep the registry-sourced legal_refs/source_refs.
    computed_provenance: dict[str, CasillaObservation] = {}

    with localcontext() as ctx:
        ctx.prec = 28
        for target in formula_evaluation_order(revision):
            formula = formulas[target]
            operand_refs: list[str] = []
            operand_values: list[Decimal] = []
            value = _evaluate_expression(
                formula.expression,
                values=values,
                binding_values=resolved_bindings,
                parameters=parameters,
                date_context=resolved_date_context,
                relation_values=resolved_relations,
                operand_refs=operand_refs,
                operand_values=operand_values,
                enum_binding_values=resolved_enum_bindings,
                date_binding_values=resolved_date_bindings,
                filing_year=snapshot.filing_year,
                text_values=resolved_text_inputs,
            )
            value = _apply_rounding(value, formula.rounding)
            target_casilla = casillas_by_id.get(target)
            if target_casilla is not None and target_casilla.constraints is not None:
                violation = target_casilla.constraints.violates(value)
                if violation is not None:
                    raise CasillaConstraintViolationError(
                        f"casilla {target_casilla.number!r} ({target_casilla.label}) "
                        f"violates declared constraint: {violation}",
                        translated_message="errors.calc.casilla_constraint_violation",
                        context={
                            "casilla_id": target,
                            "casilla_number": target_casilla.number,
                            "value": str(value),
                            "formula_id": formula.id,
                            "legal_refs": ",".join(target_casilla.constraints.legal_refs),
                            "source_refs": ",".join(target_casilla.constraints.source_refs),
                        },
                    )
            values[target] = value
            computed_provenance[target] = CasillaObservation(
                casilla_id=target,
                value=value,
                formula_id=formula.id,
                op=formula.expression.op or "value",
                operand_refs=tuple(operand_refs),
                operand_values=tuple(operand_values),
                legal_refs=tuple(formula.legal_refs),
                source_refs=tuple(formula.source_refs),
            )

    observations = _materialise_observations(
        values=values,
        computed_provenance=computed_provenance,
        casillas_by_id=casillas_by_id,
        absent_by_design_casillas=absent_by_design_casillas,
    )

    return RegistryCalculationResult(
        modelo=snapshot.modelo.id,
        revision=revision.id,
        observations=observations,
    )


def _materialise_observations(
    *,
    values: Mapping[str, Decimal],
    computed_provenance: Mapping[str, CasillaObservation],
    casillas_by_id: Mapping[str, CasillaDefinition],
    absent_by_design_casillas: frozenset[str] = frozenset(),
) -> tuple[CasillaObservation, ...]:
    """Project the engine's per-casilla state into the canonical observation tuple.

    Every casilla in ``values`` lands as a :class:`CasillaObservation`:
    computed casillas pull formula lineage from ``computed_provenance``;
    input / bound casillas pull legal_refs and source_refs from the
    registry casilla definition so provenance survives the boundary
    even when no formula ran. Stable ordering by ``casilla_id`` makes
    downstream snapshots and audit diffs deterministic.
    """
    materialised: list[CasillaObservation] = []
    for casilla_id in sorted(values):
        computed = computed_provenance.get(casilla_id)
        if computed is not None:
            materialised.append(computed)
            continue
        registry_casilla = casillas_by_id.get(casilla_id)
        legal_refs = tuple(registry_casilla.legal_refs) if registry_casilla is not None else ()
        source_refs = tuple(registry_casilla.source_refs) if registry_casilla is not None else ()
        materialised.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=values[casilla_id],
                legal_refs=legal_refs,
                source_refs=source_refs,
                absent_by_design=casilla_id in absent_by_design_casillas,
            )
        )
    return tuple(materialised)


def _initial_values(
    revision: ModeloRevision,
    inputs: Mapping[str, Decimal],
    *,
    binding_values: Mapping[str, Decimal],
    target_period: str,
) -> tuple[dict[str, Decimal], frozenset[str]]:
    # The public runtime entry point validates Decimal-only inputs via
    # `_reject_non_decimal` before this private helper runs. Keep that
    # boundary centralised so unknown/computed-casilla diagnostics below
    # stay focused on registry identity rather than value typing.
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    unknown = sorted(set(inputs).difference(casillas))
    if unknown:
        raise RegistryValidationError(
            f"unknown registry input casilla ids: {unknown!r}",
            translated_message="errors.calc.unknown_input_casillas",
            context={"casilla_ids": ",".join(unknown)},
        )
    formula_targets = {formula.target for formula in revision.formulas}
    computed = sorted(
        casilla_id
        for casilla_id in inputs
        if casillas[casilla_id].input_kind == InputKind.COMPUTED or casilla_id in formula_targets
    )
    if computed:
        raise RegistryValidationError(
            f"computed registry casillas cannot be supplied as inputs: {computed!r}",
            translated_message="errors.calc.computed_supplied_as_input",
            context={"casilla_ids": ",".join(computed)},
        )
    # The campaign motivating this rewrite (Modelo 130 carry-forward
    # silent-zero hazard) closes through the binding pipeline below:
    # previous-filing bound casillas resolve through `binding_values`
    # or surface as absent-by-design / raise. The established
    # `resolve_bound_casilla_inputs` helper legitimately projects
    # binding values into the `inputs` mapping as a convenience for
    # callers; that projection is recognised and not a masking
    # pattern (the source of truth is the binding map).
    #
    # P07.S36 hardening: re-impose ADR Decision Z2's lost design
    # intent on previous-filing bound casillas specifically. The
    # ONLY legitimate way to land a previous-filing bound casilla
    # value in `inputs` is the projection pattern where the same
    # value is ALSO present in `binding_values` under the casilla's
    # binding id. A previous-filing bound casilla supplied via
    # `inputs` WITHOUT the matching `binding_values[binding_id]`
    # entry is a test-fixture lie — the silent-zero hazard in
    # disguise. Raise loudly so the lie is caught at fixture
    # authoring time, not absorbed as a silent default.
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    smuggled_previous_filing_bound = sorted(
        casilla_id
        for casilla_id in inputs
        if casillas[casilla_id].input_kind == InputKind.BOUND
        and casillas[casilla_id].binding is not None
        and (binding_def := bindings_by_id.get(casillas[casilla_id].binding or "")) is not None
        and binding_def.source == "previous_filing"
        and binding_def.id not in binding_values
    )
    if smuggled_previous_filing_bound:
        raise RegistryValidationError(
            "previous-filing bound registry casillas cannot be supplied via inputs "
            "without the matching binding_values entry; the projection from "
            "resolve_bound_casilla_inputs must include the binding value as the "
            f"source of truth: {smuggled_previous_filing_bound!r}",
            translated_message="errors.calc.bound_input_smuggled_without_binding_value",
            context={"casilla_ids": ",".join(smuggled_previous_filing_bound)},
        )
    # P08.S50 hardening: when BOTH inputs[bound_casilla_id] AND
    # binding_values[binding_id] are populated, the two values MUST
    # match. A divergence means the fixture (or production caller's
    # projection helper) declared two contradictory values for the
    # same casilla; the runtime would silently pick binding_values
    # as source of truth and the inconsistency would never surface.
    # Reject the inconsistency loudly so the caller fixes the
    # projection at its origin.
    inconsistent_previous_filing_projections: list[str] = []
    for casilla_id, input_value in inputs.items():
        casilla = casillas[casilla_id]
        if casilla.input_kind != InputKind.BOUND or casilla.binding is None:
            continue
        binding = bindings_by_id.get(casilla.binding)
        if binding is None or binding.source != "previous_filing":
            continue
        binding_value = binding_values.get(binding.id)
        if binding_value is None:
            continue
        if input_value != binding_value:
            inconsistent_previous_filing_projections.append(
                f"casilla {casilla_id!r}: inputs={input_value!r} vs binding_values[{binding.id!r}]={binding_value!r}"
            )
    if inconsistent_previous_filing_projections:
        raise RegistryValidationError(
            "previous-filing bound casilla projection is inconsistent between "
            "inputs and binding_values; the binding_values entry is the source "
            "of truth and the inputs projection must match it: "
            + "; ".join(inconsistent_previous_filing_projections),
            translated_message="errors.calc.bound_projection_inconsistent",
            context={
                "casilla_ids": ",".join(
                    c.split(":")[0].split("'")[1] for c in inconsistent_previous_filing_projections
                )
            },
        )
    values: dict[str, Decimal] = {}
    absent_by_design: set[str] = set()
    for casilla in revision.casillas:
        if casilla.input_kind == InputKind.COMPUTED:
            continue
        # Previous-filing bound casillas MUST resolve through the binding
        # pipeline because the silent zero fallback masked dead-binding
        # regressions (Modelo 130 carry-forward). Non-numeric data types
        # under this rule still receive a Decimal("0") placeholder via the
        # absent-by-design path; the string value is consumed through a
        # parallel provenance channel.
        if casilla.input_kind == InputKind.BOUND:
            binding_id = casilla.binding
            binding = bindings_by_id.get(binding_id or "")
            if binding is not None and binding.source == "previous_filing":
                if binding_id in binding_values:
                    values[casilla.id] = binding_values[binding_id]
                    continue
                if _binding_is_absent_by_design(binding, target_period=target_period):
                    values[casilla.id] = _ZERO
                    absent_by_design.add(casilla.id)
                    continue
                raise RegistryValidationError(
                    f"bound casilla {casilla.id!r} requires resolved binding {binding_id!r} value",
                    translated_message="errors.calc.bound_casilla_binding_value_missing",
                    context={"casilla_id": casilla.id, "binding_id": binding_id or ""},
                )
        # Manual casillas and non-previous_filing bound casillas:
        # operator-supplied through inputs (or the wizard at runtime).
        # Default to Decimal("0") when not provided — manual blank is
        # legitimate, and non-previous_filing bindings are resolved by
        # the application layer before reaching the calculator.
        values[casilla.id] = inputs.get(casilla.id, _ZERO)
    return values, frozenset(absent_by_design)


def _binding_is_absent_by_design(binding: DataBindingDefinition, *, target_period: str) -> bool:
    """Return True when a previous-filing binding declares no anchors for the target period.

    The empty-anchor return from the selector is the structural signal
    that the binding's contract intentionally suppresses a value for
    this target period (e.g. Modelo 130 casilla 15 at 1T under
    `source_period_offset_from_target = -1, max_year_delta = 0` — no
    prior quarter exists within the same ejercicio).

    Bindings with sources other than `previous_filing` (profile,
    invoice, ledger, etc.) do not carry the period-anchor concept and
    are never absent-by-design from this helper's perspective; a
    missing binding value for those sources is a caller-supply
    failure, not an authored suppression.
    """

    if binding.source != "previous_filing":
        return False
    try:
        selector = _PreviousModeloSelector.model_validate(_binding_selector_as_dict(binding))
    except ValueError:
        return False
    if not _previous_filing_selector_has_period_anchor(selector):
        return False
    return selector.required_period_anchors_for_target(target_period) == ()


def _previous_filing_selector_has_period_anchor(selector: _PreviousModeloSelector) -> bool:
    return (
        selector.period is not None
        or bool(selector.source_periods)
        or selector.source_period_offset_from_target is not None
    )


def _binding_selector_as_dict(binding: DataBindingDefinition) -> dict[str, object]:
    """Return the binding selector as a plain dict, stripping the injected ``source`` key."""
    selector = binding.selector
    if isinstance(selector, BaseModel):
        return selector.model_dump(exclude={"source"}, exclude_none=True)
    return {k: v for k, v in selector.items() if k != "source"}


def _evaluate_expression(
    expression: FormulaExpression,
    *,
    values: Mapping[str, Decimal],
    binding_values: Mapping[str, Decimal],
    parameters: Mapping[str, ParameterDefinition],
    date_context: Mapping[str, date],
    relation_values: Mapping[str, Decimal],
    operand_refs: list[str],
    operand_values: list[Decimal],
    enum_binding_values: Mapping[str, str] | None = None,
    date_binding_values: Mapping[str, date] | None = None,
    filing_year: int = 0,
    text_values: Mapping[str, str] | None = None,
) -> Decimal:
    resolved_enum_bindings: Mapping[str, str] = enum_binding_values or {}
    resolved_date_bindings: Mapping[str, date] = date_binding_values or {}
    resolved_text_values: Mapping[str, str] = text_values or {}
    if expression.op is None:
        return _evaluate_leaf(
            expression,
            values=values,
            binding_values=binding_values,
            parameters=parameters,
            date_context=date_context,
            relation_values=relation_values,
            operand_refs=operand_refs,
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
        operand_refs=operand_refs,
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
    if op == "lookup_parameter_by_entity_type":
        return _evaluate_lookup_parameter_by_entity_type(expression, ctx)
    if op == "lookup_bracket_by_entity_type":
        return _evaluate_lookup_bracket_by_entity_type(expression, ctx)
    if op == "if_then_else":
        return _evaluate_if_then_else(expression, ctx)
    if op == "age_at_year_end":
        return _evaluate_age_at_year_end(expression, ctx)
    args = [_evaluate_with_ctx(arg, ctx) for arg in expression.args]
    return _evaluate_args_op(op, args)


@dataclass(frozen=True)
class _EvalContext:
    """Bundles the runtime sinks + maps threaded through every recursive call.

    Kept frozen and slot-equivalent so the dispatcher can hand the same
    context to every per-op evaluator without copying. The two list
    sinks (operand_refs, operand_values) ARE mutated in place — they
    accumulate evaluation provenance for the explainability surface.
    """

    values: Mapping[str, Decimal]
    binding_values: Mapping[str, Decimal]
    parameters: Mapping[str, ParameterDefinition]
    date_context: Mapping[str, date]
    relation_values: Mapping[str, Decimal]
    operand_refs: list[str]
    operand_values: list[Decimal]
    enum_binding_values: Mapping[str, str]
    date_binding_values: Mapping[str, date]
    filing_year: int
    text_values: Mapping[str, str] = field(default_factory=dict)


def _evaluate_with_ctx(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Convenience: re-enter the dispatcher carrying every context field forward."""
    return _evaluate_expression(
        expression,
        values=ctx.values,
        binding_values=ctx.binding_values,
        parameters=ctx.parameters,
        date_context=ctx.date_context,
        relation_values=ctx.relation_values,
        operand_refs=ctx.operand_refs,
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
            f"parameter {bracket_arg.parameter!r} must declare data_type='bracket_table' "
            f"to be used by lookup_bracket"
        )
    base = _evaluate_with_ctx(expression.args[0], ctx)
    ctx.operand_refs.append(bracket_arg.parameter)
    result = _resolve_bracket(bracket_param, base, ctx.date_context)
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
            "formula op 'lookup_bracket_by_ccaa' requires args[2] to be a dispatch_table leaf"
        )
    if binding_arg.binding not in ctx.enum_binding_values:
        raise RegistryValidationError(
            f"enum binding {binding_arg.binding!r} has no supplied value; required by lookup_bracket_by_ccaa"
        )
    dispatch_key = ctx.enum_binding_values[binding_arg.binding]
    dispatch_table = dispatch_arg.dispatch_table
    if dispatch_key not in dispatch_table:
        raise RegistryValidationError(
            f"lookup_bracket_by_ccaa dispatch_table is missing CCAA {dispatch_key!r} "
            f"(declared keys: {sorted(dispatch_table)})"
        )
    bracket_param_id = dispatch_table[dispatch_key]
    bracket_param = ctx.parameters.get(bracket_param_id)
    if bracket_param is None:
        raise RegistryValidationError(f"parameter {bracket_param_id!r} not registered")
    if bracket_param.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {bracket_param_id!r} must declare data_type='bracket_table' "
            f"to be used by lookup_bracket_by_ccaa"
        )
    base = _evaluate_with_ctx(expression.args[0], ctx)
    ctx.operand_refs.append(binding_arg.binding)
    ctx.operand_refs.append(bracket_param_id)
    result = _resolve_bracket(bracket_param, base, ctx.date_context)
    ctx.operand_values.append(result)
    return result


def _evaluate_m210_resolve_rate(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Resolve the M210 IRNR tipo de gravamen rate from registry parameters.

    Four leaf args: ``(tipo_renta_casilla, baseline_param,
    convenio_param, country_binding)``. The handler reads the text
    casilla via ``ctx.text_values``, the baseline / convenio
    parameters via ``ctx.parameters``, and the country binding via
    ``ctx.enum_binding_values``. Returns the resolved Decimal rate, or
    one of the M210 rate-sentinel constants when a deterministic rate
    cannot be produced (deferred baseline, missing Convenio row,
    NOT_YET_AUTHORED placeholder). The verification layer rewrites
    the sentinels into BLOCKING findings post-engine.
    """
    op = "m210_resolve_rate"
    if len(expression.args) != 4:
        raise RegistryValidationError(
            f"formula op {op!r} expects 4 args, got {len(expression.args)}"
        )
    tipo_arg, baseline_arg, convenio_arg, country_arg = expression.args
    if tipo_arg.casilla is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[0] to be a casilla leaf"
        )
    if baseline_arg.parameter is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[1] to be a parameter leaf"
        )
    if convenio_arg.parameter is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[2] to be a parameter leaf"
        )
    if country_arg.binding is None:
        raise RegistryValidationError(
            f"formula op {op!r} requires args[3] to be a binding leaf"
        )

    tipo_renta = ctx.text_values.get(tipo_arg.casilla, "")
    ctx.operand_refs.append(tipo_arg.casilla)
    if not tipo_renta:
        ctx.operand_values.append(_M210_DEFERRED_TIPO_SENTINEL)
        return _M210_DEFERRED_TIPO_SENTINEL

    baseline_param = ctx.parameters.get(baseline_arg.parameter)
    convenio_param = ctx.parameters.get(convenio_arg.parameter)
    ctx.operand_refs.append(baseline_arg.parameter)
    ctx.operand_refs.append(convenio_arg.parameter)
    ctx.operand_refs.append(country_arg.binding)

    year = ctx.filing_year

    baseline_rate: Decimal | None = None
    if baseline_param is not None:
        for entry in baseline_param.keyed_brackets:
            if (
                entry.key == tipo_renta
                and entry.valid_from.year <= year
                and (entry.valid_to is None or entry.valid_to.year >= year)
            ):
                try:
                    baseline_rate = Decimal(entry.value)
                except (ArithmeticError, ValueError):
                    baseline_rate = None
                break

    country = ctx.enum_binding_values.get(country_arg.binding) or ""

    if not country:
        if baseline_rate is None:
            ctx.operand_values.append(_M210_DEFERRED_TIPO_SENTINEL)
            return _M210_DEFERRED_TIPO_SENTINEL
        ctx.operand_values.append(baseline_rate)
        return baseline_rate

    cc = country.upper()
    matched_row = None
    if convenio_param is not None:
        for row in convenio_param.convenio_rates:
            if (
                row.country_code == cc
                and row.tipo_renta == tipo_renta
                and row.valid_from.year <= year
                and (row.valid_to is None or row.valid_to.year >= year)
            ):
                matched_row = row
                break

    if matched_row is None:
        ctx.operand_values.append(_M210_CONVENIO_MISSING_SENTINEL)
        return _M210_CONVENIO_MISSING_SENTINEL
    if matched_row.rate == "NOT_YET_AUTHORED":
        ctx.operand_values.append(_M210_NOT_YET_AUTHORED_SENTINEL)
        return _M210_NOT_YET_AUTHORED_SENTINEL
    try:
        rate = Decimal(matched_row.rate)
    except (ArithmeticError, ValueError):
        ctx.operand_values.append(_M210_CONVENIO_MISSING_SENTINEL)
        return _M210_CONVENIO_MISSING_SENTINEL
    ctx.operand_values.append(rate)
    return rate


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
            f"enum binding {binding_arg.binding!r} has no supplied value;"
            " required by lookup_parameter_by_entity_type",
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
    result = _resolve_parameter(scalar_param, ctx.date_context)
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
            f"enum binding {binding_arg.binding!r} has no supplied value;"
            " required by lookup_bracket_by_entity_type",
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
    result = _resolve_bracket(bracket_param, base, ctx.date_context)
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
        raise RegistryValidationError(
            "formula op 'age_at_year_end' requires args[0] to be a date_binding leaf"
        )
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


_COMPARISON_OPS = frozenset({"less_than", "less_equal", "greater_than", "greater_equal", "equal"})
_UNARY_PASSTHROUGH_OPS = frozenset({"copy", "lookup_parameter", "previous_period_value", "cross_model_sum"})


def _evaluate_args_op(op: str, args: list[Decimal]) -> Decimal:
    """Dispatch an N-arg arithmetic / comparison op once every arg has been evaluated."""
    if op in {"add", "sum", "previous_period_sum"}:
        if op == "previous_period_sum":
            _require_non_empty(op, args)
        return sum(args, _ZERO)
    if op in _COMPARISON_OPS:
        _require_arg_count(op, args, 2)
        return _ONE if _compare(op, args[0], args[1]) else _ZERO
    if op in _UNARY_PASSTHROUGH_OPS:
        _require_arg_count(op, args, 1)
        return args[0]
    return _dispatch_named_arithmetic_op(op, args)


def _dispatch_named_arithmetic_op(op: str, args: list[Decimal]) -> Decimal:
    """Dispatch the per-name arithmetic ops (subtract / multiply / divide / percent / min / max / clamp / negate)."""
    match op:
        case "subtract":
            _require_arg_count(op, args, 2)
            return args[0] - args[1]
        case "multiply":
            result = _ONE
            for arg in args:
                result *= arg
            return result
        case "divide":
            _require_arg_count(op, args, 2)
            if args[1] == _ZERO:
                raise RegistryValidationError(
                    "formula expression divides by zero",
                    translated_message="errors.calc.divide_by_zero",
                )
            return args[0] / args[1]
        case "percent":
            _require_arg_count(op, args, 2)
            return args[0] * args[1] / Decimal("100")
        case "min":
            _require_non_empty(op, args)
            return min(args)
        case "max":
            _require_non_empty(op, args)
            return max(args)
        case "clamp":
            _require_arg_count(op, args, 3)
            return max(args[1], min(args[0], args[2]))
        case "negate":
            _require_arg_count(op, args, 1)
            return -args[0]
        case _:
            raise RegistryValidationError(f"formula expression uses unsupported op {op!r}")


def _evaluate_leaf(
    expression: FormulaExpression,
    *,
    values: Mapping[str, Decimal],
    binding_values: Mapping[str, Decimal],
    parameters: Mapping[str, ParameterDefinition],
    date_context: Mapping[str, date],
    relation_values: Mapping[str, Decimal],
    operand_refs: list[str],
    operand_values: list[Decimal],
    date_binding_values: Mapping[str, date] | None = None,
    filing_year: int = 0,
) -> Decimal:
    if expression.literal is not None:
        return expression.literal
    if expression.casilla is not None:
        if expression.casilla not in values:
            raise RegistryValidationError(
                f"casilla {expression.casilla!r} referenced before evaluation",
                translated_message="errors.calc.casilla_referenced_before_evaluation",
                context={"casilla_id": expression.casilla},
            )
        value = values[expression.casilla]
        operand_refs.append(expression.casilla)
        operand_values.append(value)
        return value
    if expression.binding is not None:
        if expression.binding not in binding_values:
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
        value = _resolve_parameter(parameter, date_context)
        operand_refs.append(expression.parameter)
        operand_values.append(value)
        return value
    if expression.relation is not None:
        if expression.relation not in relation_values:
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


def _compare(op: str, left: Decimal, right: Decimal) -> bool:
    if op == "less_than":
        return left < right
    if op == "less_equal":
        return left <= right
    if op == "greater_than":
        return left > right
    if op == "greater_equal":
        return left >= right
    if op == "equal":
        return left == right
    raise RegistryValidationError(f"formula expression uses unsupported comparison op {op!r}")


def _resolve_bracket(
    parameter: ParameterDefinition,
    base: Decimal,
    date_context: Mapping[str, date],
) -> Decimal:
    """Compute the cuota for ``base`` using parameter's piecewise-linear bracket schedule."""
    if parameter.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {parameter.id!r} must declare data_type='bracket_table' to use lookup_bracket"
        )
    if parameter.bracket_axis is None:
        raise RegistryValidationError(f"parameter {parameter.id!r} bracket_table requires bracket_axis")
    if parameter.bracket_axis not in date_context:
        raise RegistryValidationError(f"parameter {parameter.id!r} requires date axis {parameter.bracket_axis!r}")
    selected = date_context[parameter.bracket_axis]
    candidates = [
        b for b in parameter.brackets if b.valid_from <= selected and (b.valid_to is None or selected <= b.valid_to)
    ]
    if not candidates:
        raise RegistryValidationError(
            f"parameter {parameter.id!r} has no bracket valid for {selected.isoformat()}",
            translated_message="errors.calc.bracket_no_window",
            context={"parameter_id": parameter.id, "as_of": selected.isoformat()},
        )
    base = Decimal(base)
    if base < Decimal("0"):
        raise RegistryValidationError(
            f"parameter {parameter.id!r} lookup_bracket received negative base {base}",
            translated_message="errors.calc.bracket_negative_base",
            context={"parameter_id": parameter.id, "base": str(base)},
        )
    sorted_brackets = sorted(candidates, key=lambda b: b.lower_bound)
    selected_entry = None
    for entry in sorted_brackets:
        if entry.lower_bound <= base and (entry.upper_bound is None or base <= entry.upper_bound):
            selected_entry = entry
            break
    if selected_entry is None:
        raise RegistryValidationError(
            f"parameter {parameter.id!r} has no bracket covering base {base}",
            translated_message="errors.calc.bracket_no_coverage",
            context={"parameter_id": parameter.id, "base": str(base)},
        )
    return selected_entry.fixed_addition + selected_entry.marginal_rate * (base - selected_entry.lower_bound)


def _resolve_parameter(parameter: ParameterDefinition, date_context: Mapping[str, date]) -> Decimal:
    if not parameter.values:
        raise RegistryValidationError(f"parameter {parameter.id!r} has no dated values")
    matches: list[DatedValue] = []
    for value in parameter.values:
        if value.date_axis not in date_context:
            raise RegistryValidationError(f"parameter {parameter.id!r} requires date axis {value.date_axis!r}")
        selected = date_context[value.date_axis]
        if value.valid_from <= selected and (value.valid_to is None or selected <= value.valid_to):
            matches.append(value)
    if len(matches) != 1:
        raise RegistryValidationError(
            f"parameter {parameter.id!r} expected exactly one dated value, found {len(matches)}"
        )
    return matches[0].value


def _apply_rounding(value: Decimal, rounding: str | None) -> Decimal:
    if rounding is None:
        return value
    if rounding == "money-2":
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounding == "integer":
        return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    raise RegistryValidationError(f"unsupported rounding rule {rounding!r}")


def _reject_non_decimal(values: Mapping[str, Decimal], label: str) -> None:
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError(f"{label} {key!r} must be a Decimal")


def _reject_non_string(values: Mapping[str, str], label: str) -> None:
    for key, value in values.items():
        if not isinstance(value, str) or not value:
            raise RegistryValidationError(f"{label} {key!r} must be a non-empty string")


def _reject_unknown_external_values(values: Mapping[str, Decimal], known_ids: set[str], label: str) -> None:
    unknown = sorted(set(values).difference(known_ids))
    if unknown:
        raise RegistryValidationError(f"unknown registry {label} ids: {unknown!r}")


def _require_arg_count(op: str, args: list[Decimal], count: int) -> None:
    if len(args) != count:
        raise RegistryValidationError(f"formula op {op!r} expects {count} args, got {len(args)}")


def _require_non_empty(op: str, args: list[Decimal]) -> None:
    if not args:
        raise RegistryValidationError(f"formula op {op!r} expects at least one arg")


def read_parameter(
    modelo_id: str,
    revision_id: str,
    parameter_id: str,
    *,
    date_context: Mapping[str, date],
    registry_root: Path | None = None,
) -> Decimal:
    """Resolve a registered registry parameter value for the given date context.

    Public delegate over the same ``_resolve_parameter`` logic the formula runtime
    uses. Non-formula consumers (the rental tier resolver, IVA category resolver,
    etc.) call this surface to read parameter values without going through a
    formula expression. Registry access goes through ``ValidatedRegistryAuthority``
    whether ``registry_root`` is provided or the bundled registry is used.

    Raises :class:`RegistryValidationError` if the modelo / revision / parameter
    is not registered, or if the date context selects 0 or >1 dated values.
    """
    from aeat.core.resources import bundled_path

    from ._authority import ValidatedRegistryAuthority

    root = registry_root if registry_root is not None else bundled_path("registry", "aeat")
    authority = ValidatedRegistryAuthority.load(root, source_root=bundled_path())
    try:
        modelo_match = authority.modelo(modelo_id)
    except RegistrySnapshotError as exc:
        raise RegistryValidationError(f"modelo {modelo_id!r} not registered in {root}") from exc
    revision = modelo_match.revisions.get(revision_id)
    if revision is None:
        raise RegistryValidationError(f"modelo {modelo_id!r} has no revision {revision_id!r}")
    parameter = next((p for p in revision.parameters if p.id == parameter_id), None)
    if parameter is None:
        raise RegistryValidationError(
            f"parameter {parameter_id!r} not registered under modelo {modelo_id!r} revision {revision_id!r}"
        )
    return _resolve_parameter(parameter, date_context)
