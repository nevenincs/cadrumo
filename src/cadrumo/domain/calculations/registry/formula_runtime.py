"""Registry-backed formula runtime using typed operation graphs.

Evaluates
:class:`~domain.calculations.registry.FormulaExpression` trees declared on
a :class:`~domain.calculations.registry.ModeloRevision` against casilla
inputs and binding values drawn from a
:class:`~domain.calculations.registry.RegistrySnapshot`.
The calculation entry point :func:`calculate_registry_snapshot` is the
primary surface used by
:class:`~domain.calculations.registry.ValidatedRegistryAuthority`-backed
callers to produce
:class:`~domain.calculations.registry.CasillaObservation` rows with full
provenance.

See Also:
    :mod:`domain.calculations.registry._runtime_graph`
        Produces formula evaluation order and dependency projections.
    :mod:`domain.calculations.registry._formula_runtime_ops`
        Arithmetic, rounding, and parameter lookup helpers called by this
        evaluator.
    :mod:`domain.calculations.registry._formula_initial_values`
        Builds the initial casilla value map and materialised observation
        envelope for this runtime.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, localcontext

from pydantic import BaseModel, Field, model_validator

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.decimal.constants import ZERO
from ....core.models import STRICT_FROZEN_CONFIG
from ....domain.period import calculation_filing_date
from . import _formula_runtime_irnr as _irnr
from . import _formula_runtime_m131 as _m131
from . import formula_runtime_m100 as _m100
from ._formula_operator_contracts import require_formula_operator_arity
from .bindings import CasillaObservation
from .casilla_membership import casillas_by_id as _casillas_by_id
from .casilla_membership import duplicate_casilla_ids
from .convenio import ConvenioAuthority
from .errors import CasillaConstraintViolationError, RegistryValidationError
from .formula_initial_values import (
    binding_values_with_absent_by_design_defaults as _binding_values_with_absent_by_design_defaults,
)
from .formula_initial_values import (
    initial_values as _initial_values,
)
from .formula_initial_values import (
    materialise_observations as _materialise_observations,
)
from .formula_runtime_ops import (
    RegistryUnresolvedOutcomeReason,
)
from .formula_runtime_ops import (
    UnresolvedFormulaDependencyError as _UnresolvedFormulaDependencyError,
)
from .formula_runtime_ops import (
    UnresolvedFormulaOutcomeError as _UnresolvedFormulaOutcomeError,
)
from .formula_runtime_ops import (
    apply_rounding as _apply_rounding,
)
from .formula_runtime_ops import (
    evaluate_args_op as _evaluate_args_op,
)
from .formula_runtime_ops import (
    read_parameter as _read_parameter,
)
from .formula_runtime_ops import (
    reject_non_decimal as _reject_non_decimal,
)
from .formula_runtime_ops import (
    reject_non_string as _reject_non_string,
)
from .formula_runtime_ops import (
    reject_unknown_external_values as _reject_unknown_external_values,
)
from .formula_runtime_ops import (
    resolve_bracket as _resolve_bracket,
)
from .formula_runtime_ops import (
    resolve_scalar_parameter as _resolve_scalar_parameter,
)
from .formula_runtime_ops import (
    validated_decimal_input_casilla_ids as _validated_decimal_input_casilla_ids,
)
from .formula_text_inputs import validate_text_input_targets as _validate_text_input_targets
from .formula_text_inputs import validated_text_input_casilla_ids as _validated_text_input_casilla_ids
from .ids import (
    BindingId,
    FormulaId,
    LegalRefId,
    RelationId,
    SourceRefId,
)
from .runtime_graph import formula_evaluation_order
from .schema import RegistrySnapshot
from .schema_formula import FormulaExpression, ParameterDefinition

read_parameter = _read_parameter


class RegistryCalculationEntry(BaseModel):
    """One trace row emitted by the registry formula runtime.

    Carries the per-formula provenance for a single formula-computed
    :class:`~core.CasillaId`. Entries cover only
    casillas computed by a registry formula; input and bound casillas remain in
    :class:`~domain.calculations.registry.CasillaObservation` storage and
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
    :class:`~domain.calculations.registry.CasillaObservation` covering
    every casilla on the
    :class:`~domain.calculations.registry.RegistrySnapshot` revision
    (inputs, bound, and formula-computed). Each observation carries
    its final scalar ``value`` plus the legal / source provenance for
    that casilla pulled from the registry. Formula-computed
    observations additionally carry ``formula_id``, ``op``,
    ``operand_refs``, and ``operand_values`` so the full evaluation
    lineage survives the engine boundary.

    The :attr:`values` and :attr:`entries` views are derived convenience
    properties for readers that need the flat ``{casilla_id: Decimal}``
    map or the formula-only :class:`RegistryCalculationEntry` tuple. The typed
    envelope is the contract; the flat views never grow new fields.

    Coverage asymmetry preserved by the derivation:

    * :attr:`values` covers every Decimal observation (inputs, bound,
      computed), keyed by ``casilla_id`` to ``value``. Text observations stay
      exclusively on the canonical typed envelope.
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
    def _reject_duplicate_casilla_rows(self) -> RegistryCalculationResult:
        for channel, casilla_ids in (
            ("observations", tuple(item.casilla_id for item in self.observations)),
            ("unresolved_outcomes", tuple(item.casilla_id for item in self.unresolved_outcomes)),
        ):
            duplicates = duplicate_casilla_ids(casilla_ids)
            if duplicates:
                raise RegistryValidationError(
                    f"registry calculation result for modelo {self.modelo!r} revision {self.revision!r} "
                    f"carries more than one {channel} row for casilla(s) {duplicates!r}; "
                    "the derived values mapping cannot represent conflicting rows",
                    context={
                        "modelo": self.modelo,
                        "revision": self.revision,
                        "channel": channel,
                        "casilla_ids": ",".join(duplicates),
                    },
                )
        return self

    @model_validator(mode="after")
    def _reject_resolved_and_unresolved_for_one_casilla(self) -> RegistryCalculationResult:
        """Keep the value and unresolved channels disjoint per casilla.

        A casilla is either resolved to a Decimal or blocked by a typed
        unresolved reason; it is never both. Carrying both makes ``values``
        report a concrete figure while verification separately emits the
        blocking finding for the same casilla, so two downstream surfaces
        disagree about the same filing without either being able to detect it.
        """
        contradictory = tuple(
            sorted(
                {item.casilla_id for item in self.observations}
                & {item.casilla_id for item in self.unresolved_outcomes},
            ),
        )
        if contradictory:
            raise RegistryValidationError(
                f"registry calculation result for modelo {self.modelo!r} revision {self.revision!r} "
                f"carries both a resolved value and an unresolved outcome for casilla(s) "
                f"{contradictory!r}; a casilla resolves to exactly one outcome",
                context={
                    "modelo": self.modelo,
                    "revision": self.revision,
                    "casilla_ids": ",".join(contradictory),
                },
            )
        return self

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
        return {obs.casilla_id: obs.value for obs in self.observations if isinstance(obs.value, Decimal)}

    @property
    def entries(self) -> tuple[RegistryCalculationEntry, ...]:
        """Read-only view of formula-computed :class:`RegistryCalculationEntry` rows.

        Preserves the formula-only entry view with ``target_casilla_id`` and
        ``op`` fields for the application-layer indexers that build
        ``{target_casilla_id: entry}`` dictionaries. Insertion order from
        ``observations`` is preserved; the engine emits in formula
        evaluation order, which matches the original ``entries`` shape.
        """
        entries: list[RegistryCalculationEntry] = []
        for observation in self.observations:
            if observation.formula_id is None:
                continue
            if not isinstance(observation.value, Decimal):
                raise RegistryValidationError(
                    f"formula observation for casilla {observation.casilla_id!r} must carry a Decimal value"
                )
            entries.append(
                RegistryCalculationEntry(
                    formula_id=observation.formula_id,
                    target_casilla_id=observation.casilla_id,
                    op=observation.op or "value",
                    operand_refs=observation.operand_refs,
                    operand_casilla_refs=observation.operand_casilla_refs,
                    operand_values=observation.operand_values,
                    value=observation.value,
                    legal_refs=observation.legal_refs,
                    source_refs=observation.source_refs,
                )
            )
        return tuple(entries)


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
    :class:`~domain.calculations.registry.CasillaObservation` rows for all
    materialised casillas. Input validation is delegated to
    :mod:`domain.calculations.registry._formula_runtime_ops` and
    :mod:`domain.calculations.registry._formula_text_inputs`; initial
    casilla values and absent-by-design markers are delegated to
    :mod:`domain.calculations.registry._formula_initial_values`.

    Args:
        snapshot: The
            :class:`~domain.calculations.registry.RegistrySnapshot` that
            supplies the revision, casilla definitions, and formula graph to
            evaluate.
        inputs: Operator-supplied input casilla values; rejected if any value
            is not a :class:`decimal.Decimal`.
        date_context: Date-axis context (e.g. ``filing_period``) consumed by
            date-aware ops; ``filing_period`` defaults to the snapshot's typed
            calculation filing date when present, otherwise its year-end.
        binding_values: Optional resolved numeric binding values keyed by
            :class:`~domain.calculations.registry.DataBindingDefinition`
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
    resolved_inputs = _validated_decimal_input_casilla_ids(
        inputs,
        revision=revision,
    )
    resolved_date_context = dict(date_context)
    default_filing_date = (
        calculation_filing_date(snapshot.filing_period)
        if snapshot.filing_period is not None
        else date(snapshot.filing_year, 12, 31)
    )
    resolved_date_context.setdefault("filing_period", default_filing_date)
    supplied_bindings = binding_values or {}
    _reject_non_decimal(supplied_bindings, "binding")
    resolved_bindings = _binding_values_with_absent_by_design_defaults(
        revision,
        supplied_bindings,
        target_period=snapshot.period,
    )
    _reject_non_decimal(resolved_bindings, "binding")
    resolved_enum_bindings = enum_binding_values or {}
    _reject_non_string(resolved_enum_bindings, "enum_binding")
    resolved_relations = relation_values or {}
    _reject_non_decimal(resolved_relations, "relation")
    resolved_unresolved_relations = frozenset(unresolved_relation_ids).difference(resolved_relations)
    resolved_unresolved_bindings = frozenset(unresolved_binding_ids).difference(resolved_bindings)
    resolved_date_bindings: Mapping[BindingId, date] = date_binding_values or dict[BindingId, date]()
    resolved_text_inputs = _validated_text_input_casilla_ids(text_inputs or {})

    _validate_external_value_ids(
        snapshot,
        resolved_bindings=resolved_bindings,
        resolved_relations=resolved_relations,
        resolved_unresolved_relations=resolved_unresolved_relations,
        resolved_unresolved_bindings=resolved_unresolved_bindings,
    )
    values, absent_by_design_casilla_ids = _initial_values(
        revision,
        resolved_inputs,
        binding_values=supplied_bindings,
        target_period=snapshot.period,
    )
    formulas = {formula.target_casilla_id: formula for formula in revision.formulas}
    parameters = {parameter.id: parameter for parameter in revision.parameters}
    casillas_by_id = _casillas_by_id(revision)
    resolved_text_inputs = _validate_text_input_targets(resolved_text_inputs, casillas_by_id=casillas_by_id)
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
                        # UnresolvedFormulaOutcomeError.context is always a str-keyed,
                        # str-valued mapping (its constructor only accepts
                        # Mapping[str, str]); the inherited CadrumoError.context attribute
                        # is declared dict[str, object] | None for the general error
                        # hierarchy, so re-stringify here rather than narrowing the
                        # shared base attribute for every CadrumoError subclass.
                        context={str(key): str(value) for key, value in (exc.context or {}).items()},
                    ),
                )
                continue
            except _UnresolvedFormulaDependencyError:
                unresolved_casilla_ids.add(target)
                continue
            value = _apply_rounding(value, formula.rounding)
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
                legal_refs=formula.legal_refs,
                source_refs=formula.source_refs,
            )

    observations = _materialise_observations(
        values=values,
        text_values=resolved_text_inputs,
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


def _validate_external_value_ids(
    snapshot: RegistrySnapshot,
    *,
    resolved_bindings: Mapping[BindingId, Decimal],
    resolved_relations: Mapping[RelationId, Decimal],
    resolved_unresolved_relations: frozenset[RelationId],
    resolved_unresolved_bindings: frozenset[BindingId],
) -> None:
    revision = snapshot.revision
    binding_ids = {binding.id for binding in revision.bindings}
    relation_ids = {
        relation.id
        for relation in revision.relations
        if not relation.target_periods or snapshot.period in relation.target_periods
    }
    _reject_unknown_external_values(resolved_bindings, binding_ids, "binding")
    _reject_unknown_external_values(resolved_relations, relation_ids, "relation")
    _reject_unknown_external_values(
        {relation_id: ZERO for relation_id in resolved_unresolved_relations},
        relation_ids,
        "unresolved_relation",
    )
    _reject_unknown_external_values(
        {binding_id: ZERO for binding_id in resolved_unresolved_bindings},
        binding_ids,
        "unresolved_binding",
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
    """Build the shared :class:`_EvalContext` for one formula tree and evaluate it.

    The entry point from loose arguments: it normalises the optional channels
    and constructs the context once. Recursive re-entry goes through
    :func:`_evaluate_with_ctx`, which carries that same context object forward
    instead of rebuilding it.

    Returns:
        The evaluated :class:`~decimal.Decimal` value of ``expression``.
    """
    resolved_enum_bindings: Mapping[BindingId, str] = enum_binding_values or dict[BindingId, str]()
    resolved_date_bindings: Mapping[BindingId, date] = date_binding_values or dict[BindingId, date]()
    resolved_text_values: Mapping[CasillaId, str] = text_values or dict[CasillaId, str]()
    resolved_convenio: ConvenioAuthority = convenio if convenio is not None else ConvenioAuthority.empty()
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
    return _evaluate_with_ctx(expression, ctx)


@dataclass(frozen=True, slots=True)
class _EvalContext:
    """Bundles the runtime sinks + maps threaded through every recursive call.

    Frozen and slotted. Exactly one instance is built per formula tree, by
    :func:`_evaluate_expression`, and handed by reference to every per-op
    evaluator and every recursive re-entry through
    :func:`_evaluate_with_ctx`; the tree is walked without rebuilding it.
    The three list sinks (operand_refs, operand_casilla_refs, operand_values)
    ARE mutated in place — they accumulate evaluation provenance for the
    explainability surface, and passing the one context object by reference is
    what keeps every node of the tree appending to those same three lists.
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
    text_values: Mapping[CasillaId, str] = field(default_factory=lambda: dict[CasillaId, str]())
    convenio: ConvenioAuthority = field(default_factory=ConvenioAuthority.empty)


def _evaluate_with_ctx(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Evaluate one expression node against ``ctx``, recursing into its args.

    The dispatcher proper: leaf, specialised per-op evaluator, or generic
    arg-folding op. ``ctx`` is passed through by reference rather than
    destructured and rebuilt, so the whole tree shares one context object and
    one set of provenance sinks.
    """
    if expression.op is None:
        return _evaluate_leaf(expression, ctx)
    op = expression.op
    require_formula_operator_arity(op, len(expression.args))
    evaluator = _SPECIALIZED_EXPRESSION_EVALUATORS.get(op)
    if evaluator is not None:
        return evaluator(expression, ctx)
    args = [_evaluate_with_ctx(arg, ctx) for arg in expression.args]
    return _evaluate_args_op(op, args)


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
    result = _resolve_bracket(bracket_param, base, ctx.date_context)
    ctx.operand_values.append(result)
    return result


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
    ctx.operand_refs.append(binding_arg.binding)
    return _resolve_scalar_parameter(scalar_param_id, ctx, op=op)


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
    selected_branch = expression.args[1] if predicate_value != ZERO else expression.args[2]
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


def _evaluate_leaf(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    if expression.literal is not None:
        return expression.literal
    if expression.casilla_id is not None:
        if expression.casilla_id not in ctx.values:
            if expression.casilla_id in ctx.unresolved_casilla_ids:
                raise _UnresolvedFormulaDependencyError((expression.casilla_id,))
            raise RegistryValidationError(
                f"casilla {expression.casilla_id!r} referenced before evaluation",
                translated_message="errors.calc.casilla_referenced_before_evaluation",
                context={"casilla_id": expression.casilla_id},
            )
        value = ctx.values[expression.casilla_id]
        ctx.operand_refs.append(expression.casilla_id)
        ctx.operand_casilla_refs.append(expression.casilla_id)
        ctx.operand_values.append(value)
        return value
    if expression.binding is not None:
        if expression.binding not in ctx.binding_values:
            if expression.binding in ctx.unresolved_binding_ids:
                raise _UnresolvedFormulaDependencyError((expression.binding,))
            raise RegistryValidationError(
                f"binding {expression.binding!r} has no supplied value",
                translated_message="errors.calc.binding_value_missing",
                context={"binding_id": expression.binding},
            )
        value = ctx.binding_values[expression.binding]
        ctx.operand_refs.append(expression.binding)
        ctx.operand_values.append(value)
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
        return _resolve_scalar_parameter(expression.parameter, ctx, op="formula_parameter")
    if expression.relation is not None:
        if expression.relation not in ctx.relation_values:
            if expression.relation in ctx.unresolved_relation_ids:
                raise _UnresolvedFormulaDependencyError((expression.relation,))
            raise RegistryValidationError(
                f"relation {expression.relation!r} has no supplied value",
                translated_message="errors.calc.relation_value_missing",
                context={"relation_id": expression.relation},
            )
        value = ctx.relation_values[expression.relation]
        ctx.operand_refs.append(expression.relation)
        ctx.operand_values.append(value)
        return value
    raise RegistryValidationError(
        "empty formula expression",
        translated_message="errors.calc.empty_expression",
    )


_FormulaExpressionEvaluator = Callable[[FormulaExpression, _EvalContext], Decimal]
_SPECIALIZED_EXPRESSION_EVALUATORS: dict[str, _FormulaExpressionEvaluator] = {
    "lookup_bracket": _evaluate_lookup_bracket,
    "lookup_bracket_by_ccaa": _evaluate_lookup_bracket_by_ccaa,
    "m100_resolve_renta_inmobiliaria_imputada": _m100.evaluate_m100_resolve_renta_inmobiliaria_imputada,
    "irnr_resolve_tipo_gravamen": _irnr.evaluate_irnr_resolve_tipo_gravamen,
    "m210_resolve_base_imponible": _irnr.evaluate_m210_resolve_base_imponible,
    "lookup_parameter_by_entity_type": _evaluate_lookup_parameter_by_entity_type,
    "lookup_bracket_by_entity_type": _evaluate_lookup_bracket_by_entity_type,
    "if_then_else": _evaluate_if_then_else,
    "age_at_year_end": _evaluate_age_at_year_end,
    "m131_resolve_modulos_previo": _m131.evaluate_m131_resolve_modulos_previo,
    "m131_resolve_modulos_minoracion_empleo": _m131.evaluate_m131_resolve_modulos_minoracion_empleo,
    "m131_resolve_modulos_indice_exceso": _m131.evaluate_m131_resolve_modulos_indice_exceso,
    "m131_resolve_modulos_indices_generales": _m131.evaluate_m131_resolve_modulos_indices_generales,
    "m131_resolve_modulos_pequena_dimension_ignorado_flag": (
        _m131.evaluate_m131_resolve_modulos_pequena_dimension_ignorado_flag
    ),
    "m131_resolve_modulos_temporada_inicio_conflicto_flag": (
        _m131.evaluate_m131_resolve_modulos_temporada_inicio_conflicto_flag
    ),
    "m100_resolve_eo_agraria_indices_correctores": _m100.evaluate_m100_resolve_eo_agraria_indices_correctores,
}


EvalContext = _EvalContext
